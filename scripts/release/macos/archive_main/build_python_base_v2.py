#!/usr/bin/env python3
"""Build a relocatable Python base tarball for Azure CLI packaging.

This script creates a pre-built Python tarball that can be:
1. Stored in Azure Blob Storage / Pipeline Artifacts / GitHub Releases
2. Downloaded during Azure CLI packaging to skip the Python build step

Benefits:
- Python build (with PGO/LTO) takes 15-20 minutes
- Pre-building saves time for every Azure CLI release
- Only rebuild when Python version changes

Output:
```
dist/python_base/
  python-{VERSION}-macos-{ARCH}-base.tar.gz
  python-{VERSION}-macos-{ARCH}-base.tar.gz.sha256
```

The base tarball contains:
- Python built from official python.org source
- PGO + LTO optimizations
- Relocatable paths (@executable_path)
- pip pre-installed
- NO Azure CLI (that's added during packaging)

Usage:
    # Build Python 3.13.1 base for ARM64
    python build_python_base.py --platform-tag macos-arm64

    # Build specific Python version
    python build_python_base.py --platform-tag macos-arm64 --python-version 3.14.0

    # Build for Intel
    python build_python_base.py --platform-tag macos-x86_64

Pipeline Usage:
    1. Run this script occasionally (when Python version changes)
    2. Upload resulting tarball to storage
    3. Use --python-base-url in build_binary_tar_gz_python_source.py

Storage Locations (examples):
    - Azure Blob: https://azureclipython.blob.core.windows.net/base/python-3.13.1-macos-arm64-base.tar.gz
    - GitHub Release: https://github.com/Azure/azure-cli/releases/download/python-base/python-3.13.1-macos-arm64-base.tar.gz
    - Pipeline Artifact: $(Pipeline.Workspace)/python-base/python-3.13.1-macos-arm64-base.tar.gz
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Iterable, Optional

# =============================================================================
# Python Version Configuration
# =============================================================================
DEFAULT_PYTHON_VERSION = "3.13.1"

# macOS deployment target - minimum supported macOS version
# macOS 11.0 (Big Sur) is the minimum for ARM64 support
MACOS_DEPLOYMENT_TARGET = "11.0"


class BuildError(RuntimeError):
    """Raised when the build fails."""


def get_python_source_url(version: str) -> str:
    """Get the Python source download URL for a given version."""
    return f"https://www.python.org/ftp/python/{version}/Python-{version}.tgz"


def get_python_major_minor(version: str) -> str:
    """Extract major.minor from full version string."""
    return ".".join(version.split(".")[:2])


def validate_python_version(version: str) -> None:
    """Validate Python version format and availability."""
    if not re.match(r"^3\.[0-9]+\.[0-9]+$", version):
        raise BuildError(f"Invalid Python version format: {version}. Expected: 3.X.Y")

    url = get_python_source_url(version)
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                raise BuildError(f"Python {version} source not found at {url}")
    except urllib.error.URLError as e:
        raise BuildError(f"Cannot verify Python {version} availability: {e}")


def _run(
    cmd: Iterable[str],
    *,
    env: Optional[dict[str, str]] = None,
    capture_output: bool = False,
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """Execute a subprocess command."""
    command_list = list(cmd)
    cmd_str = " ".join(command_list[:8])
    if len(command_list) > 8:
        cmd_str += "..."
    print(f"→ {cmd_str}")
    try:
        result = subprocess.run(
            command_list,
            check=True,
            capture_output=capture_output,
            text=True,
            env=env,
            cwd=cwd,
        )
        if capture_output and result.stdout:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as exc:
        raise BuildError(f"Command failed: {' '.join(command_list)}") from exc


def _run_output(cmd: list[str]) -> str:
    """Run a command and return output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


def _verify_host_architecture(platform_tag: str) -> None:
    """Verify host can build for target architecture."""
    host_arch = subprocess.check_output(["uname", "-m"], text=True).strip().lower()
    target_is_arm = "arm64" in platform_tag

    if host_arch == "x86_64" and target_is_arm:
        raise BuildError(
            "Cannot build ARM64 on Intel (x86_64) host.\n" f"Current host: {host_arch}, Target: {platform_tag}"
        )


def _find_openssl() -> Optional[Path]:
    """Find OpenSSL installation."""
    for prefix_cmd in [["brew", "--prefix", "openssl@3"], ["brew", "--prefix", "openssl@1.1"]]:
        try:
            result = subprocess.run(prefix_cmd, capture_output=True, text=True, check=True)
            openssl_path = Path(result.stdout.strip())
            if openssl_path.exists():
                print(f"Found OpenSSL at: {openssl_path}")
                return openssl_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    for path in ["/usr/local/opt/openssl@3", "/opt/homebrew/opt/openssl@3"]:
        if Path(path).exists():
            return Path(path)

    return None


def _download_python_source(staging_dir: Path, version: str) -> Path:
    """Download official Python source from python.org."""
    url = get_python_source_url(version)
    tarball = staging_dir / f"Python-{version}.tgz"

    print(f"Downloading Python {version} source...")
    print(f"  URL: {url}")

    if tarball.exists():
        print(f"  Using cached: {tarball}")
        return tarball

    urllib.request.urlretrieve(url, tarball)
    size_mb = tarball.stat().st_size / (1024 * 1024)
    print(f"  Downloaded: {size_mb:.1f} MB")

    return tarball


def _extract_python_source(tarball: Path, staging_dir: Path, version: str) -> Path:
    """Extract Python source tarball."""
    print("Extracting Python source...")
    _run(["tar", "xzf", str(tarball), "-C", str(staging_dir)])

    source_dir = staging_dir / f"Python-{version}"
    if not source_dir.exists():
        raise BuildError(f"Expected source directory not found: {source_dir}")

    print(f"  Extracted to: {source_dir}")
    return source_dir


def _configure_python(
    source_dir: Path,
    install_dir: Path,
    arch: str,
    openssl_prefix: Optional[Path],
) -> None:
    """Configure Python build with relocatable flags."""
    print(f"Configuring Python for {arch} architecture...")

    env = os.environ.copy()
    arch_flag = f"-arch {arch}"

    env["MACOSX_DEPLOYMENT_TARGET"] = MACOS_DEPLOYMENT_TARGET
    env["CFLAGS"] = f"{arch_flag} -mmacosx-version-min={MACOS_DEPLOYMENT_TARGET}"
    env["CXXFLAGS"] = env["CFLAGS"]
    env["LDFLAGS"] = f"{arch_flag} -mmacosx-version-min={MACOS_DEPLOYMENT_TARGET} -Wl,-rpath,@executable_path/../lib"

    configure_args = [
        "./configure",
        f"--prefix={install_dir}",
        "--enable-optimizations",  # PGO
        "--with-lto",  # LTO
        "--enable-shared",
        "--without-ensurepip",
    ]

    if openssl_prefix:
        configure_args.append(f"--with-openssl={openssl_prefix}")
        configure_args.append("--with-openssl-rpath=auto")

    print(f"  Install prefix: {install_dir}")
    print(f"  Architecture: {arch}")
    print(f"  Deployment target: macOS {MACOS_DEPLOYMENT_TARGET}")

    _run(configure_args, cwd=source_dir, env=env)
    print("  ✅ Configuration complete")


def _build_python(source_dir: Path) -> None:
    """Build Python from source."""
    print("Building Python (this may take 10-15 minutes with PGO/LTO)...")
    cpu_count = os.cpu_count() or 4
    print(f"  Using {cpu_count} parallel jobs")
    _run(["make", f"-j{cpu_count}"], cwd=source_dir)
    print("  ✅ Build complete")


def _install_python(source_dir: Path) -> None:
    """Install Python to prefix directory."""
    print("Installing Python...")
    _run(["make", "install"], cwd=source_dir)
    print("  ✅ Installation complete")


def _make_python_relocatable(install_dir: Path, python_major_minor: str) -> None:
    """Fix dylib paths to make Python relocatable."""
    print("Making Python relocatable...")

    lib_dir = install_dir / "lib"
    bin_dir = install_dir / "bin"

    libpython_name = f"libpython{python_major_minor}.dylib"
    libpython = lib_dir / libpython_name

    if not libpython.exists():
        for dylib in lib_dir.glob("libpython*.dylib"):
            if not dylib.is_symlink():
                libpython = dylib
                libpython_name = dylib.name
                break

    if not libpython.exists():
        raise BuildError(f"libpython not found in {lib_dir}")

    print(f"  Found: {libpython}")

    # Get current install name
    current_id = _run_output(["otool", "-D", str(libpython)]).split("\n")[-1].strip()
    print(f"  Current install name: {current_id}")

    # Change libpython's install name to use @rpath
    new_id = f"@rpath/{libpython_name}"
    _run(["install_name_tool", "-id", new_id, str(libpython)])
    print(f"  New install name: {new_id}")

    # Fix python executable
    python_exe = bin_dir / f"python{python_major_minor}"
    if not python_exe.exists():
        python_exe = bin_dir / "python3"

    if python_exe.is_symlink():
        python_exe = python_exe.resolve()

    print(f"  Fixing python executable: {python_exe.name}")
    _run(["install_name_tool", "-change", current_id, f"@executable_path/../lib/{libpython_name}", str(python_exe)])

    try:
        _run(["install_name_tool", "-add_rpath", "@executable_path/../lib", str(python_exe)])
    except BuildError:
        pass

    # Fix extension modules
    lib_dynload = lib_dir / f"python{python_major_minor}" / "lib-dynload"
    if lib_dynload.exists():
        so_files = list(lib_dynload.glob("*.so"))
        print(f"  Fixing {len(so_files)} extension modules...")
        for so_file in so_files:
            try:
                _run(["install_name_tool", "-change", current_id, f"@loader_path/../../{libpython_name}", str(so_file)])
            except BuildError:
                pass

    # Verify
    print("  Verifying relocatability...")
    new_refs = _run_output(["otool", "-L", str(python_exe)])
    if "@executable_path" in new_refs:
        print("  ✅ Relocatability fixes applied")


def _get_library_dependencies(binary_path: Path) -> list[str]:
    """Get list of library dependencies for a binary using otool."""
    try:
        output = _run_output(["otool", "-L", str(binary_path)])
        deps = []
        for line in output.split("\n")[1:]:  # Skip first line (the binary itself)
            line = line.strip()
            if line and not line.startswith("@"):
                # Extract path (before the compatibility version info)
                path = line.split(" (")[0].strip()
                if path:
                    deps.append(path)
        return deps
    except Exception:
        return []


def _is_system_library(lib_path: str) -> bool:
    """Check if a library is a system library that doesn't need bundling.

    System libraries are signed by Apple and always available on macOS.
    """
    system_prefixes = [
        "/usr/lib/",
        "/System/Library/",
        "/Library/Apple/",
    ]
    return any(lib_path.startswith(prefix) for prefix in system_prefixes)


def _find_external_libraries(install_dir: Path) -> dict[str, set[Path]]:
    """Scan all binaries and find external (non-system) library dependencies.

    Returns:
        Dict mapping external library paths to set of binaries that use them
    """
    print("  Scanning for external library dependencies...")

    external_libs: dict[str, set[Path]] = {}

    # Find all Mach-O binaries
    binaries = []
    for pattern in ["*.so", "*.dylib"]:
        binaries.extend(install_dir.rglob(pattern))

    # Also check executables in bin/
    bin_dir = install_dir / "bin"
    if bin_dir.exists():
        for exe in bin_dir.iterdir():
            if exe.is_file() and not exe.is_symlink():
                # Check if it's a Mach-O binary
                try:
                    file_type = _run_output(["file", str(exe)])
                    if "Mach-O" in file_type:
                        binaries.append(exe)
                except Exception:
                    pass

    for binary in binaries:
        if binary.is_symlink():
            continue

        deps = _get_library_dependencies(binary)
        for dep in deps:
            if not _is_system_library(dep) and not dep.startswith("@"):
                if dep not in external_libs:
                    external_libs[dep] = set()
                external_libs[dep].add(binary)

    return external_libs


def _copy_library_symlinks(source_dir: Path, dest_dir: Path, lib_name: str) -> None:
    """Copy symlinks that point to the given library.

    Homebrew often has symlink chains like:
        libcrypto.dylib -> libcrypto.3.dylib -> libcrypto.3.6.0.dylib

    We need to preserve these so binaries referencing any name will work.
    """
    # Find all symlinks in the source directory that ultimately resolve to a file
    # with the same base name pattern
    base_name = lib_name.split('.')[0]  # e.g., "libcrypto" from "libcrypto.3.dylib"

    for item in source_dir.iterdir():
        if item.is_symlink() and item.name.startswith(base_name):
            target = os.readlink(item)
            dest_link = dest_dir / item.name

            # Only create if it doesn't exist and target is a relative name
            if not dest_link.exists() and not target.startswith('/'):
                # Check if target exists in dest_dir (we may have copied it)
                if (dest_dir / target).exists() or (dest_dir / Path(target).name).exists():
                    try:
                        dest_link.symlink_to(target)
                        print(f"    Created symlink: {item.name} -> {target}")
                    except OSError:
                        pass  # Symlink already exists or can't be created


def _bundle_external_libraries(install_dir: Path, python_major_minor: str) -> None:
    """Dynamically detect and bundle all external (non-system) library dependencies.

    This function:
    1. Scans all .so and .dylib files for external dependencies
    2. Copies external libraries (e.g., from Homebrew) into the package
    3. Preserves symlink chains for library compatibility
    4. Rewrites library paths to use @loader_path/@rpath for relocatability
    5. Ad-hoc signs the bundled libraries

    This ensures the package works with hardened runtime (required for notarization)
    where library validation enforces Team ID matching.
    """
    print("Bundling external libraries...")

    lib_dir = install_dir / "lib"

    # Find all external dependencies
    external_libs = _find_external_libraries(install_dir)

    if not external_libs:
        print("  No external libraries to bundle")
        return

    print(f"  Found {len(external_libs)} external libraries to bundle:")
    for lib_path in sorted(external_libs.keys()):
        lib_name = Path(lib_path).name
        users = len(external_libs[lib_path])
        print(f"    - {lib_name} (used by {users} binaries)")

    # Copy libraries and track new locations
    bundled_libs: dict[str, Path] = {}  # original_path -> new_path

    for original_path in external_libs:
        original = Path(original_path)
        if not original.exists():
            raise BuildError(f"External library not found: {original_path}. Cannot create relocatable build.")

        # Resolve the library to get the real file (follow symlinks)
        real_lib = original.resolve()
        lib_name = original.name
        new_path = lib_dir / lib_name

        # Copy the library (the real file)
        print(f"  Copying: {lib_name}")
        shutil.copy2(real_lib, new_path)

        # Also create any symlinks that exist in the source directory
        # This handles Homebrew's symlink chains (e.g., libcrypto.dylib -> libcrypto.3.dylib)
        _copy_library_symlinks(original.parent, lib_dir, lib_name)

        # Make writable for install_name_tool
        new_path.chmod(0o755)

        # Note: We don't remove the existing signature here. install_name_tool will
        # invalidate the signature when it modifies the binary, and we'll ad-hoc sign
        # at the end. ESRP will then re-sign with the proper Microsoft certificate.

        bundled_libs[original_path] = new_path

        # Change the library's own install name
        new_id = f"@rpath/{lib_name}"
        try:
            _run(["install_name_tool", "-id", new_id, str(new_path)])
        except BuildError as e:
            raise BuildError(f"Failed to set install name for {lib_name}: {e}")

    # Now fix references in bundled libraries (they may depend on each other)
    # Use @loader_path for inter-library references since they're in the same directory
    # IMPORTANT: We need to scan the bundled libs for their actual internal references,
    # which may differ from the paths found when scanning Python binaries
    # (e.g., symlink path vs actual Cellar path in Homebrew)
    print("  Fixing inter-library references...")

    # Build a mapping of library names to their new @loader_path references
    lib_name_to_loader_path: dict[str, str] = {}
    for new_path in bundled_libs.values():
        lib_name_to_loader_path[new_path.name] = f"@loader_path/{new_path.name}"

    for lib_path in bundled_libs.values():
        # Get actual dependencies from the bundled library itself
        deps = _get_library_dependencies(lib_path)
        for dep in deps:
            dep_name = Path(dep).name
            # If this dependency matches one of our bundled libraries, rewrite it
            if dep_name in lib_name_to_loader_path:
                try:
                    _run(["install_name_tool", "-change", dep, lib_name_to_loader_path[dep_name], str(lib_path)])
                except BuildError:
                    pass

    # Fix references in all binaries that use these libraries
    print("  Fixing binary references...")
    for original_path, users in external_libs.items():
        if original_path not in bundled_libs:
            continue

        lib_name = bundled_libs[original_path].name

        for binary in users:
            # Calculate relative path from binary to lib/
            try:
                # For .so files in lib-dynload, path is ../../libname
                if "lib-dynload" in str(binary):
                    new_ref = f"@loader_path/../../{lib_name}"
                # For executables in bin/, path is ../lib/libname
                elif "/bin/" in str(binary):
                    new_ref = f"@executable_path/../lib/{lib_name}"
                else:
                    # Default: use @rpath
                    new_ref = f"@rpath/{lib_name}"

                _run(["install_name_tool", "-change", original_path, new_ref, str(binary)])
            except BuildError:
                pass

    # Add rpath to bundled libraries pointing to their own directory
    print("  Adding rpath to bundled libraries...")
    for lib_path in bundled_libs.values():
        try:
            _run(["install_name_tool", "-add_rpath", "@loader_path", str(lib_path)])
        except BuildError:
            pass

    # Ad-hoc sign the bundled libraries
    # This is a temporary signature; ESRP will re-sign with proper identity and hardened runtime
    print("  Ad-hoc signing bundled libraries...")
    for lib_path in bundled_libs.values():
        try:
            _run(["codesign", "--force", "--sign", "-", str(lib_path)])
        except BuildError as e:
            print(f"  ⚠️  Could not sign {lib_path.name}: {e}")

    print(f"  ✅ Bundled {len(bundled_libs)} external libraries")


def _install_pip(python_path: Path) -> None:
    """Install pip using get-pip.py."""
    print("Installing pip...")
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    get_pip_path = python_path.parent / "get-pip.py"

    urllib.request.urlretrieve(get_pip_url, get_pip_path)
    _run([str(python_path), str(get_pip_path)])
    get_pip_path.unlink()

    print("  ✅ pip installed")


def _prune_bytecode(root: Path) -> None:
    """Remove Python bytecode files."""
    for suffix in (".pyc", ".pyo"):
        for path in root.rglob(f"*{suffix}"):
            path.unlink()

    for path in sorted(root.rglob("__pycache__"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                shutil.rmtree(path)


def _create_metadata_file(install_dir: Path, version: str, arch: str) -> None:
    """Create metadata file with build info."""
    metadata = f"""# Python Base Build Metadata
# This file is used by build_binary_tar_gz_python_source.py
PYTHON_VERSION={version}
PYTHON_MAJOR_MINOR={get_python_major_minor(version)}
ARCHITECTURE={arch}
MACOS_DEPLOYMENT_TARGET={MACOS_DEPLOYMENT_TARGET}
BUILD_TYPE=base
"""
    metadata_path = install_dir / "PYTHON_BASE_METADATA"
    metadata_path.write_text(metadata, encoding="utf-8")
    print(f"Created metadata: {metadata_path}")


def _validate_relocatability(install_dir: Path) -> None:
    """Validate that all binaries are relocatable (pre-signing integrity gate).

    This function ensures:
    1. No absolute paths to external locations (e.g., /opt/homebrew, /usr/local)
    2. All dependencies use @rpath, @loader_path, @executable_path, or system libs
    3. Build will fail early if issues are found (before signing/notarization)

    Raises:
        BuildError: If any binary has invalid dependencies
    """
    print("  Checking all binaries for external dependencies...")

    errors: list[str] = []
    checked_count = 0

    # Find all Mach-O binaries
    binaries: list[Path] = []
    for pattern in ["*.so", "*.dylib"]:
        binaries.extend(install_dir.rglob(pattern))

    # Also check executables in bin/
    bin_dir = install_dir / "bin"
    if bin_dir.exists():
        for exe in bin_dir.iterdir():
            if exe.is_file() and not exe.is_symlink():
                try:
                    file_type = _run_output(["file", str(exe)])
                    if "Mach-O" in file_type:
                        binaries.append(exe)
                except Exception:
                    pass

    for binary in binaries:
        if binary.is_symlink():
            continue

        checked_count += 1
        deps = _get_library_dependencies(binary)

        for dep in deps:
            # Valid dependencies:
            # - @rpath, @loader_path, @executable_path (relocatable)
            # - /usr/lib/, /System/Library/ (system libraries)
            if dep.startswith("@"):
                continue  # Relocatable reference
            if _is_system_library(dep):
                continue  # System library

            # Invalid: absolute path to external location
            relative_binary = binary.relative_to(install_dir)
            errors.append(f"{relative_binary}: {dep}")

    if errors:
        print(f"  ❌ Found {len(errors)} invalid dependencies:")
        for error in errors[:10]:  # Show first 10
            print(f"      {error}")
        if len(errors) > 10:
            print(f"      ... and {len(errors) - 10} more")
        raise BuildError(
            f"Relocatability validation failed: {len(errors)} binaries have external dependencies. "
            "All dependencies must use @rpath/@loader_path or be system libraries."
        )

    print(f"  ✅ Validated {checked_count} binaries - all dependencies are relocatable")


def _create_base_tarball(
    install_dir: Path,
    version: str,
    arch: str,
    output_dir: Path,
) -> Path:
    """Create the Python base tarball."""
    archive_name = f"python-{version}-macos-{arch}-base.tar.gz"
    archive_path = output_dir / archive_name

    if archive_path.exists():
        archive_path.unlink()
        print(f"Removed existing: {archive_path}")

    print(f"Creating Python base tarball: {archive_path}")

    source_size = sum(f.stat().st_size for f in install_dir.rglob("*") if f.is_file())
    print(f"  Source size: {source_size / (1024*1024):.1f} MB")

    with tarfile.open(archive_path, "w:gz") as tar:
        for item in install_dir.iterdir():
            tar.add(item, arcname=item.name, recursive=True)
            print(f"  Added: {item.name}")

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"Archive created: {archive_path} ({size_mb:.1f} MB)")

    return archive_path


def _emit_sha256(archive_path: Path) -> Path:
    """Generate SHA256 checksum file."""
    print(f"Generating SHA256 checksum...")

    digest = hashlib.sha256()
    with archive_path.open("rb") as fh:
        while chunk := fh.read(8192):
            digest.update(chunk)

    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    checksum_line = f"{digest.hexdigest()}  {archive_path.name}\n"
    checksum_path.write_text(checksum_line, encoding="utf-8")

    print(f"SHA256: {checksum_line.strip()}")
    return checksum_path


def build_python_base(*, platform_tag: str, python_version: str, output_dir: Path) -> Path:
    """Build the Python base tarball."""
    python_major_minor = get_python_major_minor(python_version)

    if "arm64" in platform_tag:
        arch = "arm64"
    elif "x86_64" in platform_tag:
        arch = "x86_64"
    else:
        raise BuildError(f"Unsupported platform: {platform_tag}")

    print("=" * 70)
    print(f"Building Python {python_version} Base Tarball ({platform_tag})")
    print("Source: https://www.python.org (official)")
    print("=" * 70)

    _verify_host_architecture(platform_tag)

    openssl_prefix = _find_openssl()
    if not openssl_prefix:
        print("⚠️  OpenSSL not found. SSL support may be limited.")

    with tempfile.TemporaryDirectory(prefix="python-base-build-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        staging_dir = tmp_dir / "staging"
        install_dir = tmp_dir / "python"

        staging_dir.mkdir()
        install_dir.mkdir()

        print(f"\nTemporary directory: {tmp_dir}")

        # Step 1: Download
        print("\n1. Downloading Python source...")
        tarball = _download_python_source(staging_dir, python_version)

        # Step 2: Extract
        print("\n2. Extracting source...")
        source_dir = _extract_python_source(tarball, staging_dir, python_version)

        # Step 3: Configure
        print("\n3. Configuring Python...")
        _configure_python(source_dir, install_dir, arch, openssl_prefix)

        # Step 4: Build
        print("\n4. Building Python...")
        _build_python(source_dir)

        # Step 5: Install
        print("\n5. Installing Python...")
        _install_python(source_dir)

        # Step 6: Make relocatable
        print("\n6. Making Python relocatable...")
        _make_python_relocatable(install_dir, python_major_minor)

        # Step 7: Bundle external libraries (e.g., OpenSSL, mpdecimal, xz)
        print("\n7. Bundling external libraries...")
        _bundle_external_libraries(install_dir, python_major_minor)

        # Step 8: Install pip
        print("\n8. Installing pip...")
        python_path = install_dir / "bin" / "python3"
        _install_pip(python_path)

        # Step 9: Prune bytecode
        print("\n9. Pruning bytecode...")
        _prune_bytecode(install_dir)

        # Step 10: Create metadata
        print("\n10. Creating metadata...")
        _create_metadata_file(install_dir, python_version, arch)

        # Step 11: Validate relocatability (pre-signing integrity gate)
        print("\n11. Validating relocatability...")
        _validate_relocatability(install_dir)

        # Calculate size
        final_size = sum(f.stat().st_size for f in install_dir.rglob("*") if f.is_file())
        print(f"  Final size: {final_size / (1024*1024):.1f} MB")

        # Step 12: Create tarball
        print("\n12. Creating tarball...")
        archive_path = _create_base_tarball(install_dir, python_version, arch, output_dir)

        # Step 13: Generate checksum
        checksum_path = _emit_sha256(archive_path)

    # Print summary
    print("\n" + "=" * 70)
    print("✅ PYTHON BASE TARBALL BUILD COMPLETE!")
    print("=" * 70)
    print(f"  Archive:     {archive_path}")
    print(f"  Size:        {archive_path.stat().st_size / (1024*1024):.1f} MB")
    print(f"  SHA256:      {checksum_path}")
    print(f"  Platform:    {platform_tag}")
    print(f"  Python:      {python_version}")
    print()
    print("Contents:")
    print("  - Python runtime (PGO + LTO optimized)")
    print("  - Relocatable paths (@executable_path, @loader_path)")
    print("  - Bundled external libraries (OpenSSL, mpdecimal, xz, etc.)")
    print("  - pip pre-installed")
    print("  - NO Azure CLI (add during packaging)")
    print()
    print("Note: All external libraries are bundled and paths rewritten.")
    print("      This ensures compatibility with hardened runtime (notarization).")
    print()
    print("Upload to storage:")
    print(f"  az storage blob upload -f {archive_path} -c python-base -n {archive_path.name}")
    print()
    print("Use in Azure CLI build:")
    print("  python build_binary_tar_gz_python_source.py \\")
    print(f"    --platform-tag {platform_tag} \\")
    print(f"    --python-base-url https://your-storage.blob.core.windows.net/python-base/{archive_path.name}")
    print("=" * 70)

    return archive_path


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    # Get project root for default output
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parents[2]
    default_output = project_root / "dist" / "python_base"

    parser = argparse.ArgumentParser(
        description="Build relocatable Python base tarball for Azure CLI packaging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Build Python 3.13.1 base for ARM64
    python build_python_base.py --platform-tag macos-arm64

    # Build specific Python version
    python build_python_base.py --platform-tag macos-arm64 --python-version 3.14.0

    # Build to custom output directory
    python build_python_base.py --platform-tag macos-arm64 --output-dir /tmp/python-base
""",
    )
    parser.add_argument(
        "--platform-tag",
        required=True,
        choices=["macos-arm64", "macos-x86_64"],
        help="Target platform architecture",
    )
    parser.add_argument(
        "--python-version",
        default=DEFAULT_PYTHON_VERSION,
        help=f"Python version to build (default: {DEFAULT_PYTHON_VERSION})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help=f"Output directory for tarball (default: {default_output})",
    )
    parser.add_argument(
        "--skip-version-check",
        action="store_true",
        help="Skip Python version availability check",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> None:
    """Main entry point."""
    args = parse_args(argv)

    try:
        if not args.skip_version_check:
            print(f"Validating Python {args.python_version} availability...")
            validate_python_version(args.python_version)
            print(f"✓ Python {args.python_version} source available")

        args.output_dir.mkdir(parents=True, exist_ok=True)

        build_python_base(
            platform_tag=args.platform_tag,
            python_version=args.python_version,
            output_dir=args.output_dir,
        )
    except BuildError as exc:
        print(f"\n❌ ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
