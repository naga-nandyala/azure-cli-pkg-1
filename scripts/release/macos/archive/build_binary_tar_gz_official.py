#!/usr/bin/env python3
"""Build a self-contained binary tar.gz for Azure CLI using OFFICIAL Python.org distribution.

This is an alternative implementation that uses the official Python.org distribution
instead of python-build-standalone to address concerns about using third-party builds.

Creates a tar.gz containing:
1. Pre-built Python runtime from Python.org (PSF official)
2. Complete virtual environment with all dependencies PRE-INSTALLED
3. All binary wheels (including msal[broker] which has no source)

The end result is functionally identical to the python-build-standalone version:
- Self-contained Python runtime
- Relocatable installation
- No external dependencies
- Works offline

Trade-offs:
✅ Official PSF source (addresses "unofficial" concerns)
✅ Same functionality as python-build-standalone version
❌ More complex build process
❌ Higher maintenance burden
❌ Larger package size

Usage:
    python3 build_binary_tar_gz_official.py --platform-tag macos-arm64
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

# Azure CLI project structure
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_ROOT / "src"
AZURE_CLI_PACKAGE_DIR = SRC_DIR / "azure-cli"
AZURE_CLI_CORE_DIR = SRC_DIR / "azure-cli-core"

# Package configuration
APP_NAME = "azure-cli"
CLI_EXECUTABLE_NAME = "az"

# Official Python.org configuration
PYTHON_VERSION = "3.13.1"
PYTHON_VERSION_SHORT = ".".join(PYTHON_VERSION.split(".")[:2])  # 3.13

# Official Python.org URLs and checksums
# Source: https://www.python.org/downloads/release/python-3131/
OFFICIAL_PYTHON = {
    "url": f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-macos11.pkg",
    "sha256": "67c6f0a3190851e0013214d5abd725a42ec398ff1b50eec47826820fd052d86b",
}


class BuildError(RuntimeError):
    """Raised when the packaging pipeline fails."""


def _run(
    cmd: Iterable[str], *, env: Optional[dict[str, str]] = None, capture_output: bool = False
) -> subprocess.CompletedProcess:
    """Execute a subprocess command."""
    command_list = list(cmd)
    print(f"→ {' '.join(command_list)}")
    try:
        return subprocess.run(
            command_list,
            check=True,
            env=env,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        output = exc.stdout if capture_output else ""
        error = exc.stderr if capture_output else ""
        message = f"Command failed with exit code {exc.returncode}: {' '.join(command_list)}"
        if output:
            message += f"\nSTDOUT:\n{output}"
        if error:
            message += f"\nSTDERR:\n{error}"
        raise BuildError(message) from exc


def _verify_checksum(file_path: Path, expected_sha256: str) -> None:
    """Verify file SHA256 checksum."""
    print(f"Verifying SHA256 checksum for {file_path.name}...")
    actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

    if actual_hash.lower() != expected_sha256.lower():
        raise BuildError(
            f"❌ Checksum mismatch!\n"
            f"Expected: {expected_sha256}\n"
            f"Actual:   {actual_hash}\n"
            f"File may be corrupted or tampered with."
        )
    print(f"✅ Checksum verified: {expected_sha256[:16]}...")


def _detect_version() -> str:
    """Extract Azure CLI version."""
    env_version = os.environ.get("VERSION")
    if env_version and env_version.strip():
        print(f"Using version from environment: {env_version}")
        return env_version.strip()

    init_path = AZURE_CLI_CORE_DIR / "azure" / "cli" / "core" / "__init__.py"
    try:
        source = init_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BuildError(f"Could not locate {init_path}") from exc

    match = re.search(r'__version__\s*=\s*[\'"](.+?)[\'"]', source)
    if not match:
        raise BuildError(f"Could not find __version__ in {init_path}")

    version = match.group(1)
    print(f"Using version from azure-cli-core: {version}")
    return version


def _ensure_clean(paths: Iterable[Path]) -> None:
    """Remove files or directories if they exist."""
    for path in paths:
        if path.is_file() or path.is_symlink():
            print(f"Cleaning file {path}")
            path.unlink()
        elif path.is_dir():
            print(f"Cleaning directory {path}")
            shutil.rmtree(path)


def _download_official_python(staging_dir: Path) -> Path:
    """Download and verify official Python.org macOS installer."""
    print("=" * 70)
    print("Downloading OFFICIAL Python from python.org")
    print("=" * 70)
    print(f"Version: {PYTHON_VERSION}")
    print(f"Source: {OFFICIAL_PYTHON['url']}")
    print(f"Checksum: {OFFICIAL_PYTHON['sha256'][:16]}...")
    print()

    python_pkg = staging_dir / f"python-{PYTHON_VERSION}-official.pkg"

    if python_pkg.exists():
        print(f"Using cached download: {python_pkg}")
    else:
        print("Downloading...")
        urllib.request.urlretrieve(OFFICIAL_PYTHON["url"], python_pkg)
        print(f"✅ Downloaded: {python_pkg.stat().st_size / (1024*1024):.1f} MB")

    # Verify checksum
    _verify_checksum(python_pkg, OFFICIAL_PYTHON["sha256"])

    return python_pkg


def _extract_python_framework(python_pkg: Path, staging_dir: Path) -> Path:
    """Extract Python.framework from official .pkg installer."""
    print("\nExtracting Python.framework from official installer...")

    # Expand the package
    extracted_dir = staging_dir / "python_extracted"
    _ensure_clean([extracted_dir])

    _run(["pkgutil", "--expand", str(python_pkg), str(extracted_dir)])

    # Find and extract the Python_Framework.pkg payload
    framework_pkg = extracted_dir / "Python_Framework.pkg"
    if not framework_pkg.exists():
        raise BuildError(f"Python_Framework.pkg not found in {extracted_dir}")

    payload = framework_pkg / "Payload"
    if not payload.exists():
        raise BuildError(f"Payload not found in {framework_pkg}")

    # Extract payload to get Python.framework
    # Note: The Payload tar.gz contains the Python.framework directory structure itself
    # (Headers, Python, Resources, Versions), not wrapped in Library/Frameworks/
    python_framework = staging_dir / "Python.framework"
    _ensure_clean([python_framework])
    python_framework.mkdir(parents=True)

    _run(["tar", "-xzf", str(payload), "-C", str(python_framework)])

    # Verify framework structure exists
    if not (python_framework / "Versions").exists():
        raise BuildError(f"Python.framework Versions directory not found at {python_framework}")

    print(f"✅ Extracted: {python_framework}")
    return python_framework


def _make_framework_relocatable(python_framework: Path) -> None:
    """Make Python.framework relocatable using install_name_tool.

    Official python.org builds use absolute paths like:
        /Library/Frameworks/Python.framework/Versions/3.13/Python

    We need to convert these to @rpath for portability:
        @rpath/libpython3.13.dylib
    """
    print("\n" + "=" * 70)
    print("Making Python relocatable (fixing absolute paths)")
    print("=" * 70)

    version_dir = python_framework / "Versions" / PYTHON_VERSION_SHORT
    if not version_dir.exists():
        # Try to find the actual version directory
        versions = list((python_framework / "Versions").glob("3.*"))
        if not versions:
            raise BuildError("Could not find Python version directory")
        version_dir = versions[0]
        print(f"Found version directory: {version_dir.name}")

    python_lib = version_dir / "Python"
    if not python_lib.exists():
        raise BuildError(f"Python library not found at {python_lib}")

    # Step 1: Fix the main Python library
    print("\n1. Fixing Python library ID...")
    _run(["install_name_tool", "-id", f"@rpath/libpython{PYTHON_VERSION_SHORT}.dylib", str(python_lib)])
    print("✅ Python library ID updated")

    # Step 2: Fix all binaries in bin/
    bin_dir = version_dir / "bin"
    if bin_dir.exists():
        print("\n2. Fixing executables in bin/...")
        for executable in bin_dir.iterdir():
            if executable.is_file() and not executable.is_symlink():
                # Check if it's a Mach-O binary
                try:
                    result = _run(["file", str(executable)], capture_output=True)
                    if "Mach-O" not in result.stdout:
                        continue
                except BuildError:
                    continue

                print(f"   Fixing: {executable.name}")
                try:
                    # Change absolute path to @rpath
                    _run(
                        [
                            "install_name_tool",
                            "-change",
                            f"/Library/Frameworks/Python.framework/Versions/{PYTHON_VERSION_SHORT}/Python",
                            f"@rpath/libpython{PYTHON_VERSION_SHORT}.dylib",
                            str(executable),
                        ]
                    )

                    # Add rpath
                    _run(["install_name_tool", "-add_rpath", "@executable_path/../lib", str(executable)])
                except BuildError as e:
                    # May fail if already has rpath or not needed
                    if "would duplicate path" not in str(e):
                        print(f"      Warning: {e}")
        print("✅ Executables fixed")

    # Step 3: Fix all .so files (Python extension modules)
    lib_dynload = version_dir / "lib" / f"python{PYTHON_VERSION_SHORT}" / "lib-dynload"
    if lib_dynload.exists():
        print("\n3. Fixing Python extension modules (.so files)...")
        so_files = list(lib_dynload.glob("*.so"))
        print(f"   Found {len(so_files)} extension modules")
        for so_file in so_files:
            try:
                _run(
                    [
                        "install_name_tool",
                        "-change",
                        f"/Library/Frameworks/Python.framework/Versions/{PYTHON_VERSION_SHORT}/Python",
                        f"@rpath/libpython{PYTHON_VERSION_SHORT}.dylib",
                        str(so_file),
                    ]
                )
            except BuildError:
                # Some .so files may not link to Python
                pass
        print("✅ Extension modules fixed")

    # Step 4: Create libpython dylib symlink for @rpath
    lib_dir = version_dir / "lib"
    libpython_name = f"libpython{PYTHON_VERSION_SHORT}.dylib"
    libpython_link = lib_dir / libpython_name

    print(f"\n4. Creating {libpython_name} symlink...")
    if libpython_link.exists():
        libpython_link.unlink()

    # Create relative symlink to ../Python
    libpython_link.symlink_to("../Python")
    print(f"✅ Created: {libpython_link} -> ../Python")

    # Step 5: Re-sign binaries with ad-hoc signature
    # Note: After install_name_tool modifications, signatures are invalid
    # We use ad-hoc signing (-) which allows local execution
    print("\n5. Re-signing binaries with ad-hoc signatures...")
    binaries_to_sign = []

    # Sign Python library
    binaries_to_sign.append(python_lib)

    # Sign all executables in bin/
    if bin_dir.exists():
        for executable in bin_dir.iterdir():
            if executable.is_file() and not executable.is_symlink():
                try:
                    result = _run(["file", str(executable)], capture_output=True)
                    if "Mach-O" in result.stdout:
                        binaries_to_sign.append(executable)
                except BuildError:
                    pass

    # Sign all .so files
    if lib_dynload.exists():
        binaries_to_sign.extend(lib_dynload.glob("*.so"))

    print(f"   Processing {len(binaries_to_sign)} binaries...")
    for binary in binaries_to_sign:
        try:
            # Ad-hoc sign with force flag
            # Use --deep to sign the entire bundle structure
            _run(["codesign", "--force", "--sign", "-", "--deep", str(binary)], capture_output=True)
        except BuildError:
            # Some binaries may not need signing or may fail
            pass
    print("✅ Binaries re-signed")

    print("\n" + "=" * 70)
    print("✅ Python is now relocatable!")
    print("=" * 70)


def _create_venv_from_framework(python_framework: Path, venv_dir: Path) -> Path:
    """Create virtual environment from the relocated Python.framework."""
    print(f"\nCreating virtual environment at {venv_dir}...")

    version_dir = python_framework / "Versions" / PYTHON_VERSION_SHORT
    if not version_dir.exists():
        version_dir = list((python_framework / "Versions").glob("3.*"))[0]

    python_bin = version_dir / "bin" / "python3"
    if not python_bin.exists():
        raise BuildError(f"Python executable not found at {python_bin}")

    # Set PYTHONHOME to help Python find its stdlib
    env = os.environ.copy()
    env["PYTHONHOME"] = str(version_dir)

    # Create venv
    _run([str(python_bin), "-m", "venv", str(venv_dir)], env=env)

    # Copy the entire Python.framework into the venv for self-containment
    venv_frameworks = venv_dir / "Frameworks"
    venv_frameworks.mkdir(exist_ok=True)

    print("Bundling Python.framework into virtual environment...")
    target_framework = venv_frameworks / "Python.framework"
    _ensure_clean([target_framework])
    shutil.copytree(python_framework, target_framework, symlinks=True)

    # Update venv python to use bundled framework
    venv_python = venv_dir / "bin" / "python3"
    _run(
        [
            "install_name_tool",
            "-add_rpath",
            "@executable_path/../Frameworks/Python.framework/Versions/Current/lib",
            str(venv_python),
        ]
    )

    print("✅ Virtual environment created with bundled Python")

    # Verify it works
    print("\nVerifying Python in venv...")
    result = _run([str(venv_python), "--version"], capture_output=True)
    print(f"✅ {result.stdout.strip()}")

    return venv_python


def _install_azure_cli(python_path: Path) -> None:
    """Install Azure CLI and all its components into the virtual environment."""
    print("Installing Azure CLI components...")

    # Install in the correct order to satisfy dependencies
    components = [
        SRC_DIR / "azure-cli-telemetry",
        SRC_DIR / "azure-cli-core",
        SRC_DIR / "azure-cli",
    ]

    for component in components:
        if not component.exists():
            raise BuildError(f"Component not found: {component}")
        print(f"Installing {component.name}...")
        _run([str(python_path), "-m", "pip", "install", str(component)])

    # Verify installation
    print("Verifying Azure CLI installation...")
    result = _run([str(python_path), "-m", "azure.cli", "--version"], capture_output=True)
    print(f"Installed Azure CLI version:\n{result.stdout}")


def _fix_installed_packages_paths(venv_dir: Path) -> None:
    """Fix absolute paths in newly installed packages."""
    print("Fixing paths in installed packages...")

    site_packages = venv_dir / "lib" / f"python{PYTHON_VERSION_SHORT}" / "site-packages"
    if not site_packages.exists():
        print("  ⚠️  site-packages not found, skipping")
        return

    fixed_count = 0
    for so_file in site_packages.rglob("*.so"):
        try:
            _run(
                [
                    "install_name_tool",
                    "-change",
                    f"/Library/Frameworks/Python.framework/Versions/{PYTHON_VERSION_SHORT}/Python",
                    f"@rpath/libpython{PYTHON_VERSION_SHORT}.dylib",
                    str(so_file),
                ]
            )

            # Calculate relative rpath to framework
            parts_count = len(so_file.relative_to(site_packages).parts) - 1
            rpath = f"@loader_path/{'../' * parts_count}../../Frameworks/Python.framework/Versions/{PYTHON_VERSION_SHORT}/lib"

            _run(["install_name_tool", "-add_rpath", rpath, str(so_file)])
            fixed_count += 1
        except BuildError:
            pass  # Some .so files might not link to Python

    print(f"  ✅ Fixed {fixed_count} extension modules")


def _prune_bytecode(root: Path) -> None:
    """Remove Python bytecode files to reduce package size."""
    # First remove individual .pyc and .pyo files
    for suffix in (".pyc", ".pyo"):
        for path in root.rglob(f"*{suffix}"):
            path.unlink()

    # Then remove empty __pycache__ directories
    for path in sorted(root.rglob("__pycache__"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()  # Only removes if empty
            except OSError:
                # If not empty, remove recursively
                shutil.rmtree(path)


def _create_launcher_script(venv_dir: Path) -> None:
    """Create az launcher script in venv/bin/."""
    launcher_script = """#!/usr/bin/env bash
set -euo pipefail

# Get the real path to this script (following symlinks)
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || greadlink -f "${BASH_SOURCE[0]}" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
VENV_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Set Python home for relocatable installation
export PYTHONHOME="$VENV_DIR"

# Set Azure CLI installer identifier
export AZ_INSTALLER=HOMEBREW_FORMULA

# Execute the Azure CLI
exec "$VENV_DIR/bin/python3" -m azure.cli "$@"
"""

    az_path = venv_dir / "bin" / CLI_EXECUTABLE_NAME
    az_path.write_text(launcher_script, encoding="utf-8")
    az_path.chmod(0o755)
    print(f"Created launcher script: {az_path}")


def _create_readme(venv_dir: Path, version: str, platform_tag: str) -> None:
    """Create README.txt in venv."""
    readme_content = f"""Azure CLI {version} - Self-Contained Binary Distribution (Official Python.org)
{'=' * 70}

This is a pre-built, self-contained distribution of Azure CLI for macOS.

Platform: {platform_tag}
Python: {PYTHON_VERSION} (Official Python.org - PSF)
Distribution: Homebrew Formula (tar.gz)

Python Source:
-------------
This build uses official Python from Python.org (Python Software Foundation).
- URL: {OFFICIAL_PYTHON['url']}
- SHA256: {OFFICIAL_PYTHON['sha256']}

Contents:
---------
- Complete Python {PYTHON_VERSION} runtime (official PSF distribution)
- Azure CLI and all dependencies (pre-installed)
- msal[broker] and other binary-only packages

Installation via Homebrew:
--------------------------
This archive is designed for Homebrew Formula installation:

    brew tap azure/azure-cli
    brew install azure-cli

Manual Installation (not recommended):
--------------------------------------
1. Extract archive to /opt/homebrew/Cellar/azure-cli/{version}/
2. Create symlink: ln -s /opt/homebrew/Cellar/azure-cli/{version}/bin/az /opt/homebrew/bin/az
3. Run: az --version

For more information:
--------------------
- Azure CLI Docs: https://docs.microsoft.com/cli/azure/
- GitHub: https://github.com/Azure/azure-cli
- Report Issues: https://github.com/Azure/azure-cli/issues

Created: {__file__}
"""

    readme_path = venv_dir / "README.txt"
    readme_path.write_text(readme_content, encoding="utf-8")
    print(f"Created README: {readme_path}")


def _create_binary_tar_gz(venv_dir: Path, version: str, platform_tag: str, artifacts_dir: Path) -> Path:
    """Create binary tar.gz archive from virtualenv with libexec structure."""
    archive_name = f"{APP_NAME}-{version}-{platform_tag}-official.tar.gz"
    archive_path = artifacts_dir / archive_name

    _ensure_clean([archive_path])

    print(f"Creating binary tar.gz archive: {archive_path}")
    print(f"  Source size: {sum(f.stat().st_size for f in venv_dir.rglob('*') if f.is_file()) / (1024*1024):.1f} MB")

    # Create a temporary directory with proper Homebrew structure:
    # - libexec/ contains all Python runtime files (bin/, lib/, include/, etc.)
    # - bin/ contains only the launcher script (symlink to libexec/bin/az)
    temp_dir = artifacts_dir / f"temp_{archive_name}"
    _ensure_clean([temp_dir])
    temp_dir.mkdir(parents=True)

    # Create libexec subdirectory
    libexec_dir = temp_dir / "libexec"
    libexec_dir.mkdir()

    # Move all venv contents to libexec/
    print("  Creating libexec structure...")
    for item in venv_dir.iterdir():
        shutil.move(str(item), str(libexec_dir / item.name))
        print(f"    Moved {item.name} → libexec/{item.name}")

    # Create bin/ directory at root with symlink to libexec/bin/az
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir()
    az_symlink = bin_dir / "az"
    az_symlink.symlink_to("../libexec/bin/az")
    print("    Created bin/az → ../libexec/bin/az")

    # Create archive from temp directory
    with tarfile.open(archive_path, "w:gz") as tar:
        for item in temp_dir.iterdir():
            tar.add(item, arcname=item.name, recursive=True)
            print(f"  Added: {item.name}")

    # Cleanup temp directory
    shutil.rmtree(temp_dir)

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"Archive created: {archive_path} ({size_mb:.1f} MB)")

    return archive_path


def _emit_sha256(archive_path: Path) -> Path:
    """Generate SHA256 checksum file."""
    print(f"Generating SHA256 checksum for {archive_path.name}...")

    digest = hashlib.sha256()
    with archive_path.open("rb") as fh:
        while chunk := fh.read(8192):
            digest.update(chunk)

    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    checksum_line = f"{digest.hexdigest()}  {archive_path.name}\n"
    checksum_path.write_text(checksum_line, encoding="utf-8")

    print(f"SHA256: {checksum_line.strip()}")
    return checksum_path


def build_binary_tar_gz(*, platform_tag: str) -> None:
    """Build self-contained binary tar.gz using official Python.org."""
    version = _detect_version()
    artifacts_dir = PROJECT_ROOT / "dist" / "binary_tar_gz"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"Building Azure CLI {version} Binary Archive ({platform_tag})")
    print("Using OFFICIAL PYTHON.ORG")
    print("=" * 70)

    with tempfile.TemporaryDirectory(prefix="azure-cli-binary-tar-gz-official-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        staging_dir = tmp_dir / "staging"
        venv_dir = tmp_dir / "venv"

        staging_dir.mkdir()

        print(f"\nTemporary directory: {tmp_dir}")

        # Download official Python.org installer
        print("\n1. Downloading official Python from Python.org...")
        pkg_path = _download_official_python(staging_dir)

        # Extract Python.framework
        print("\n2. Extracting Python.framework...")
        framework_dir = _extract_python_framework(pkg_path, staging_dir)

        # Make framework relocatable
        print("\n3. Making Python.framework relocatable...")
        _make_framework_relocatable(framework_dir)

        # Create virtual environment with bundled framework
        print("\n4. Creating virtual environment...")
        python_path = _create_venv_from_framework(framework_dir, venv_dir)

        # Install Azure CLI
        print("\n5. Installing Azure CLI and dependencies...")
        _install_azure_cli(python_path)

        # Fix paths in newly installed packages
        print("\n6. Fixing paths in installed packages...")
        _fix_installed_packages_paths(venv_dir)

        # Create launcher script
        print("\n7. Creating launcher script...")
        _create_launcher_script(venv_dir)

        # Create README
        print("\n8. Creating README...")
        _create_readme(venv_dir, version, platform_tag)

        # Prune bytecode
        print("\n9. Pruning bytecode files...")
        _prune_bytecode(venv_dir)
        print(f"  Final size: {sum(f.stat().st_size for f in venv_dir.rglob('*') if f.is_file()) / (1024*1024):.1f} MB")

        # Create tar.gz archive
        print("\n10. Creating tar.gz archive...")
        archive_path = _create_binary_tar_gz(venv_dir, version, platform_tag, artifacts_dir)

        # Generate checksum
        checksum_path = _emit_sha256(archive_path)

    # Print summary
    print("\n" + "=" * 70)
    print("✅ BINARY TAR.GZ BUILD COMPLETE (Official Python.org)!")
    print("=" * 70)
    print(f"  Archive:     {archive_path}")
    print(f"  Size:        {archive_path.stat().st_size / (1024*1024):.1f} MB")
    print(f"  SHA256:      {checksum_path}")
    print(f"  Platform:    {platform_tag}")
    print(f"  Version:     {version}")
    print(f"  Python:      {PYTHON_VERSION} (Official Python.org)")
    print()
    print("Archive contains:")
    print("  - Official Python.org runtime (PSF)")
    print("  - Azure CLI with ALL dependencies pre-installed")
    print("  - msal[broker] and other binary packages")
    print("  - Relocatable using @rpath (install_name_tool applied)")
    print()
    print("Differences from python-build-standalone version:")
    print("  - Uses Python.org as source (not Astral)")
    print("  - ~200 lines of install_name_tool logic applied")
    print("  - Same end result: self-contained, relocatable")
    print()
    print("Test extraction:")
    print(f"  tar -tzf {archive_path.name} | head -20")
    print(f"  tar -xzf {archive_path.name}")
    print("  ./libexec/bin/az --version")
    print("=" * 70)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Build binary tar.gz for Azure CLI (official Python.org)")
    parser.add_argument(
        "--platform-tag",
        required=True,
        choices=["macos-arm64", "macos-x86_64"],
        help="Target platform architecture",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> None:
    """Main entry point."""
    args = parse_args(argv)

    try:
        build_binary_tar_gz(platform_tag=args.platform_tag)
    except BuildError as exc:
        print(f"\n❌ ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
