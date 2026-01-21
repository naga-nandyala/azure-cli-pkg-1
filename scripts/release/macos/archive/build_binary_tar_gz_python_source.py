#!/usr/bin/env python3
"""Build self-contained binary tar.gz using Python built from python.org SOURCE.

This script creates a BINARY tar.gz (not source) containing:
1. Python runtime built from official python.org source code
2. Complete virtual environment with all dependencies PRE-INSTALLED
3. All binary wheels (including msal[broker] which has no source)

This approach:
- Uses 100% official Python.org source (no third-party binaries)
- Builds a truly relocatable Python using install_name_tool
- Is fully auditable and reproducible
- Works in air-gapped/offline environments after packaging

Build time: ~10-15 minutes (due to Python compilation with PGO/LTO)

Output Structure:
```
dist/binary_tar_gz_source/
  azure-cli-{VERSION}-macos-arm64.tar.gz
  azure-cli-{VERSION}-macos-arm64.tar.gz.sha256
```

Archive Contents:
```
├── bin/
│   └── az → ../libexec/bin/az
└── libexec/
    ├── bin/
    │   ├── python3
    │   ├── pip3
    │   └── az
    ├── lib/
    │   ├── libpython3.13.dylib
    │   └── python3.13/
    │       └── site-packages/
    │           ├── azure/
    │           ├── msal/
    │           └── ...
    └── README.txt
```

Usage:
    python build_binary_tar_gz_python_source.py --platform-tag macos-arm64
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
AZURE_CLI_CORE_DIR = SRC_DIR / "azure-cli-core"

# Package configuration
APP_NAME = "azure-cli"
CLI_EXECUTABLE_NAME = "az"

# =============================================================================
# Python Version Configuration
# =============================================================================
# To update Python version for future Azure CLI releases:
#   1. Update DEFAULT_PYTHON_VERSION below (e.g., "3.14.0")
#   2. Or pass --python-version 3.14.0 at build time
#
# Python version requirements:
#   - Must be available at https://www.python.org/ftp/python/{VERSION}/
#   - Must support macOS deployment target (11.0+)
#   - Azure CLI currently requires Python 3.9+ (as of 2024)
# =============================================================================
DEFAULT_PYTHON_VERSION = "3.13.1"

# These globals are set from command-line or default at runtime
# Do NOT modify directly - use --python-version argument
PYTHON_VERSION = DEFAULT_PYTHON_VERSION
PYTHON_MAJOR_MINOR = ".".join(PYTHON_VERSION.split(".")[:2])
PYTHON_SOURCE_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/Python-{PYTHON_VERSION}.tgz"

# macOS deployment target - minimum supported macOS version
# macOS 11.0 (Big Sur) is the minimum for ARM64 support
MACOS_DEPLOYMENT_TARGET = "11.0"


class BuildError(RuntimeError):
    """Raised when the packaging pipeline fails."""


def get_python_source_url(version: str) -> str:
    """Get the Python source download URL for a given version."""
    return f"https://www.python.org/ftp/python/{version}/Python-{version}.tgz"


def get_python_major_minor(version: str) -> str:
    """Extract major.minor from full version string (e.g., '3.13' from '3.13.1')."""
    return ".".join(version.split(".")[:2])


def validate_python_version(version: str) -> None:
    """Validate Python version format and availability.

    Raises:
        BuildError: If version format is invalid or source not available
    """
    import re

    # Validate format (e.g., 3.13.1, 3.14.0)
    if not re.match(r"^3\.[0-9]+\.[0-9]+$", version):
        raise BuildError(f"Invalid Python version format: {version}. " "Expected format: 3.X.Y (e.g., 3.13.1, 3.14.0)")

    # Check if source is available (HEAD request)
    url = get_python_source_url(version)
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                raise BuildError(f"Python {version} source not found at {url}")
    except urllib.error.URLError as e:
        raise BuildError(f"Cannot verify Python {version} availability at {url}: {e}")


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


def _detect_version() -> str:
    """Extract the Azure CLI version from azure-cli-core/__init__.py or environment."""
    env_version = os.environ.get("VERSION")
    if env_version and env_version.strip():
        print(f"Using version from environment: {env_version}")
        return env_version.strip()

    init_path = AZURE_CLI_CORE_DIR / "azure" / "cli" / "core" / "__init__.py"
    try:
        source = init_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BuildError(f"Could not find version file: {init_path}") from exc

    match = re.search(r'__version__\s*=\s*[\'"](.+?)[\'"]', source)
    if not match:
        raise BuildError(f"Could not parse version from {init_path}")

    version = match.group(1)
    print(f"Using version from azure-cli-core: {version}")
    return version


def _ensure_clean(paths: Iterable[Path]) -> None:
    """Remove files or directories if they exist."""
    for path in paths:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
                print(f"Removed directory: {path}")
            else:
                path.unlink()
                print(f"Removed file: {path}")


def _verify_host_architecture(platform_tag: str) -> None:
    """Verify host can build for target architecture."""
    host_arch = subprocess.check_output(["uname", "-m"], text=True).strip().lower()
    target_is_arm = "arm64" in platform_tag

    if host_arch == "x86_64" and target_is_arm:
        raise BuildError(
            "Cannot build ARM64 on Intel (x86_64) host.\n"
            "ARM64 builds require an Apple Silicon (ARM64) machine.\n"
            f"Current host: {host_arch}, Target: {platform_tag}"
        )


def _find_openssl() -> Optional[Path]:
    """Find OpenSSL installation (Homebrew or system)."""
    # Try Homebrew first
    try:
        result = subprocess.run(
            ["brew", "--prefix", "openssl@3"],
            capture_output=True,
            text=True,
            check=True,
        )
        openssl_path = Path(result.stdout.strip())
        if openssl_path.exists():
            print(f"Found OpenSSL at: {openssl_path}")
            return openssl_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Try openssl@1.1 as fallback
    try:
        result = subprocess.run(
            ["brew", "--prefix", "openssl@1.1"],
            capture_output=True,
            text=True,
            check=True,
        )
        openssl_path = Path(result.stdout.strip())
        if openssl_path.exists():
            print(f"Found OpenSSL at: {openssl_path}")
            return openssl_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Check common system locations
    for path in ["/usr/local/opt/openssl@3", "/opt/homebrew/opt/openssl@3"]:
        if Path(path).exists():
            print(f"Found OpenSSL at: {path}")
            return Path(path)

    return None


def _download_python_source(staging_dir: Path) -> Path:
    """Download official Python source from python.org."""
    tarball = staging_dir / f"Python-{PYTHON_VERSION}.tgz"

    print(f"Downloading Python {PYTHON_VERSION} source from python.org...")
    print(f"  URL: {PYTHON_SOURCE_URL}")

    if tarball.exists():
        print(f"  Using cached: {tarball}")
        return tarball

    urllib.request.urlretrieve(PYTHON_SOURCE_URL, tarball)
    size_mb = tarball.stat().st_size / (1024 * 1024)
    print(f"  Downloaded: {size_mb:.1f} MB")

    return tarball


def _extract_python_source(tarball: Path, staging_dir: Path) -> Path:
    """Extract Python source tarball."""
    print("Extracting Python source...")

    _run(["tar", "xzf", str(tarball), "-C", str(staging_dir)])

    source_dir = staging_dir / f"Python-{PYTHON_VERSION}"
    if not source_dir.exists():
        raise BuildError(f"Expected source directory not found: {source_dir}")

    print(f"  Extracted to: {source_dir}")
    return source_dir


def _configure_python(source_dir: Path, install_dir: Path, arch: str, openssl_prefix: Optional[Path]) -> None:
    """Configure Python build with relocatable flags."""
    print(f"Configuring Python for {arch} architecture...")

    env = os.environ.copy()

    # Architecture-specific flags
    arch_flag = f"-arch {arch}"

    env["MACOSX_DEPLOYMENT_TARGET"] = MACOS_DEPLOYMENT_TARGET
    env["CFLAGS"] = f"{arch_flag} -mmacosx-version-min={MACOS_DEPLOYMENT_TARGET}"
    env["CXXFLAGS"] = env["CFLAGS"]
    env["LDFLAGS"] = f"{arch_flag} -mmacosx-version-min={MACOS_DEPLOYMENT_TARGET} -Wl,-rpath,@executable_path/../lib"

    configure_args = [
        "./configure",
        f"--prefix={install_dir}",
        "--enable-optimizations",  # PGO optimization
        "--with-lto",  # Link-time optimization
        "--enable-shared",  # Build shared library (libpython)
        "--without-ensurepip",  # We'll install pip separately
    ]

    # Add OpenSSL if found
    if openssl_prefix:
        configure_args.append(f"--with-openssl={openssl_prefix}")
        configure_args.append("--with-openssl-rpath=auto")

    print(f"  Install prefix: {install_dir}")
    print(f"  Architecture: {arch}")
    print(f"  Deployment target: macOS {MACOS_DEPLOYMENT_TARGET}")
    if openssl_prefix:
        print(f"  OpenSSL: {openssl_prefix}")

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


def _make_python_relocatable(install_dir: Path) -> None:
    """Fix dylib paths to make Python relocatable.

    On macOS, shared libraries have embedded paths. We need to change these
    from absolute paths to relative paths using @executable_path, @loader_path,
    or @rpath so the installation can be moved anywhere.
    """
    print("Making Python relocatable...")

    lib_dir = install_dir / "lib"
    bin_dir = install_dir / "bin"

    # Find the main libpython dylib (not symlinks)
    libpython_name = f"libpython{PYTHON_MAJOR_MINOR}.dylib"
    libpython = lib_dir / libpython_name

    if not libpython.exists():
        # Try alternate naming
        for dylib in lib_dir.glob("libpython*.dylib"):
            if not dylib.is_symlink():
                libpython = dylib
                libpython_name = dylib.name
                break

    if not libpython.exists():
        raise BuildError(f"libpython not found in {lib_dir}")

    print(f"  Found: {libpython}")

    # 1. Get current install name
    current_id = _run_output(["otool", "-D", str(libpython)]).split("\n")[-1].strip()
    print(f"  Current install name: {current_id}")

    # 2. Change libpython's install name to use @rpath
    new_id = f"@rpath/{libpython_name}"
    _run(["install_name_tool", "-id", new_id, str(libpython)])
    print(f"  New install name: {new_id}")

    # 3. Fix python executable to find libpython relative to itself
    python_exe = bin_dir / f"python{PYTHON_MAJOR_MINOR}"
    if not python_exe.exists():
        python_exe = bin_dir / "python3"

    if python_exe.is_symlink():
        python_exe = python_exe.resolve()

    print(f"  Fixing python executable: {python_exe.name}")

    _run(["install_name_tool", "-change", current_id, f"@executable_path/../lib/{libpython_name}", str(python_exe)])

    # 4. Add rpath for alternative lookup
    try:
        _run(["install_name_tool", "-add_rpath", "@executable_path/../lib", str(python_exe)])
    except BuildError:
        pass  # rpath might already exist

    # 5. Fix all extension modules in lib-dynload
    lib_dynload = lib_dir / f"python{PYTHON_MAJOR_MINOR}" / "lib-dynload"
    if lib_dynload.exists():
        so_files = list(lib_dynload.glob("*.so"))
        print(f"  Fixing {len(so_files)} extension modules...")
        for so_file in so_files:
            try:
                _run(["install_name_tool", "-change", current_id, f"@loader_path/../../{libpython_name}", str(so_file)])
            except BuildError:
                pass  # Some modules might not reference libpython

    # 6. Verify changes
    print("  Verifying relocatability...")
    new_refs = _run_output(["otool", "-L", str(python_exe)])
    if "@executable_path" in new_refs:
        print("  ✅ Relocatability fixes applied")
    else:
        print("  ⚠️  Warning: @executable_path not found in references")


def _install_pip(python_path: Path) -> None:
    """Install pip using get-pip.py."""
    print("Installing pip...")

    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    get_pip_path = python_path.parent / "get-pip.py"

    urllib.request.urlretrieve(get_pip_url, get_pip_path)
    _run([str(python_path), str(get_pip_path)])
    get_pip_path.unlink()

    print("  ✅ pip installed")


def _install_azure_cli(python_path: Path) -> None:
    """Install Azure CLI and all its components."""
    print("Installing Azure CLI components...")

    components = [
        SRC_DIR / "azure-cli-telemetry",
        SRC_DIR / "azure-cli-core",
        SRC_DIR / "azure-cli",
    ]

    for component in components:
        if not component.exists():
            raise BuildError(f"Component not found: {component}")
        print(f"  Installing {component.name}...")
        _run([str(python_path), "-m", "pip", "install", str(component)])

    print("Verifying Azure CLI installation...")
    result = _run([str(python_path), "-m", "azure.cli", "--version"], capture_output=True)
    print(f"Installed Azure CLI version:\n{result.stdout}")


def _prune_bytecode(root: Path) -> None:
    """Remove Python bytecode files to reduce package size."""
    for suffix in (".pyc", ".pyo"):
        for path in root.rglob(f"*{suffix}"):
            path.unlink()

    for path in sorted(root.rglob("__pycache__"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                shutil.rmtree(path)


def _create_launcher_script(install_dir: Path) -> None:
    """Create az launcher script."""
    launcher_script = f"""#!/usr/bin/env bash
set -euo pipefail

# Get the real path to this script (following symlinks)
SCRIPT_PATH="$(readlink -f "${{BASH_SOURCE[0]}}" 2>/dev/null || greadlink -f "${{BASH_SOURCE[0]}}" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "${{BASH_SOURCE[0]}}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
INSTALL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Set Python home for relocatable installation
export PYTHONHOME="$INSTALL_DIR"

# Set Azure CLI installer identifier
export AZ_INSTALLER=HOMEBREW_FORMULA

# Execute the Azure CLI
exec "$INSTALL_DIR/bin/python3" -m azure.cli "$@"
"""

    az_path = install_dir / "bin" / CLI_EXECUTABLE_NAME
    az_path.write_text(launcher_script, encoding="utf-8")
    az_path.chmod(0o755)
    print(f"Created launcher script: {az_path}")


def _create_readme(install_dir: Path, version: str, platform_tag: str) -> None:
    """Create README.txt."""
    readme_content = f"""Azure CLI {version} - Self-Contained Binary Distribution
{'=' * 70}

This is a pre-built, self-contained distribution of Azure CLI for macOS.

Platform: {platform_tag}
Python: {PYTHON_VERSION} (built from python.org source)
Distribution: Homebrew Formula (tar.gz)

Build Method:
-------------
Python was built from official python.org source code with:
- Profile-guided optimization (PGO)
- Link-time optimization (LTO)
- Relocatable library paths (@executable_path)

This ensures:
- 100% official, auditable source
- Optimal performance
- True relocatability (can be moved anywhere)
- Works in air-gapped/offline environments

Contents:
---------
- Complete Python {PYTHON_VERSION} runtime
- Azure CLI and all dependencies (pre-installed)
- msal[broker] and other binary-only packages

Installation via Homebrew:
--------------------------
This archive is designed for Homebrew Formula installation:

    brew tap azure/azure-cli
    brew install azure-cli

Manual Installation:
--------------------
1. Extract: tar xzf azure-cli-{version}-{platform_tag}.tar.gz
2. Run: ./libexec/bin/az --version

For more information:
--------------------
- Azure CLI Docs: https://docs.microsoft.com/cli/azure/
- GitHub: https://github.com/Azure/azure-cli
"""

    readme_path = install_dir / "README.txt"
    readme_path.write_text(readme_content, encoding="utf-8")
    print(f"Created README: {readme_path}")


def _create_binary_tar_gz(install_dir: Path, version: str, platform_tag: str, artifacts_dir: Path) -> Path:
    """Create binary tar.gz archive with libexec structure."""
    archive_name = f"{APP_NAME}-{version}-{platform_tag}.tar.gz"
    archive_path = artifacts_dir / archive_name

    _ensure_clean([archive_path])

    print(f"Creating binary tar.gz archive: {archive_path}")

    # Calculate source size
    source_size = sum(f.stat().st_size for f in install_dir.rglob("*") if f.is_file())
    print(f"  Source size: {source_size / (1024*1024):.1f} MB")

    # Create temporary directory with Homebrew structure
    temp_dir = artifacts_dir / f"temp_{archive_name}"
    _ensure_clean([temp_dir])
    temp_dir.mkdir(parents=True)

    # Create libexec subdirectory with all content
    libexec_dir = temp_dir / "libexec"
    libexec_dir.mkdir()

    for item in install_dir.iterdir():
        shutil.move(str(item), str(libexec_dir / item.name))
        print(f"  Moved {item.name} → libexec/{item.name}")

    # Create bin/ directory with symlink to libexec/bin/az
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir()
    az_symlink = bin_dir / "az"
    az_symlink.symlink_to("../libexec/bin/az")
    print("  Created bin/az → ../libexec/bin/az")

    # Create archive
    with tarfile.open(archive_path, "w:gz") as tar:
        for item in temp_dir.iterdir():
            tar.add(item, arcname=item.name, recursive=True)
            print(f"  Added: {item.name}")

    # Cleanup
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


def _download_python_base(url: str, staging_dir: Path) -> Path:
    """Download pre-built Python base tarball."""
    print(f"Downloading pre-built Python base...")
    print(f"  URL: {url}")

    tarball = staging_dir / "python-base.tar.gz"

    if url.startswith("file://"):
        # Local file
        local_path = Path(url[7:])
        if not local_path.exists():
            raise BuildError(f"Local Python base file not found: {local_path}")
        shutil.copy(local_path, tarball)
        print(f"  Copied from: {local_path}")
    else:
        # Remote URL
        urllib.request.urlretrieve(url, tarball)
        size_mb = tarball.stat().st_size / (1024 * 1024)
        print(f"  Downloaded: {size_mb:.1f} MB")

    return tarball


def _extract_python_base(tarball: Path, install_dir: Path) -> dict:
    """Extract pre-built Python base and return metadata."""
    print("Extracting Python base...")

    _run(["tar", "xzf", str(tarball), "-C", str(install_dir)])

    # Read metadata if present
    metadata_path = install_dir / "PYTHON_BASE_METADATA"
    metadata = {}
    if metadata_path.exists():
        for line in metadata_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                metadata[key.strip()] = value.strip()
        print(f"  Python version: {metadata.get('PYTHON_VERSION', 'unknown')}")
        print(f"  Architecture: {metadata.get('ARCHITECTURE', 'unknown')}")

    return metadata


def build_binary_tar_gz(*, platform_tag: str, python_base_url: Optional[str] = None) -> None:
    """Build self-contained binary tar.gz from python.org source or pre-built base."""
    version = _detect_version()
    artifacts_dir = PROJECT_ROOT / "dist" / "binary_tar_gz_source"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Determine architecture
    if "arm64" in platform_tag:
        arch = "arm64"
    elif "x86_64" in platform_tag:
        arch = "x86_64"
    else:
        raise BuildError(f"Unsupported platform: {platform_tag}")

    use_prebuilt = python_base_url is not None

    print("=" * 70)
    print(f"Building Azure CLI {version} Binary Archive ({platform_tag})")
    if use_prebuilt:
        print("Source: Pre-built Python base (FAST mode)")
    else:
        print("Source: https://www.python.org (official)")
    print("=" * 70)

    # Verify we can build for target architecture (only needed for source build)
    if not use_prebuilt:
        _verify_host_architecture(platform_tag)

        # Find OpenSSL (only needed for source build)
        openssl_prefix = _find_openssl()
        if not openssl_prefix:
            print("⚠️  OpenSSL not found. SSL support may be limited.")
            print("   Install with: brew install openssl@3")

    with tempfile.TemporaryDirectory(prefix="azure-cli-python-source-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        staging_dir = tmp_dir / "staging"
        install_dir = tmp_dir / "python"

        staging_dir.mkdir()
        install_dir.mkdir()

        print(f"\nTemporary directory: {tmp_dir}")

        if use_prebuilt:
            # FAST PATH: Use pre-built Python base
            print("\n1. Downloading pre-built Python base...")
            base_tarball = _download_python_base(python_base_url, staging_dir)

            print("\n2. Extracting Python base...")
            metadata = _extract_python_base(base_tarball, install_dir)
            if metadata.get("PYTHON_VERSION"):
                print(f"  Using Python {metadata['PYTHON_VERSION']} from pre-built base")

            # Skip steps 3-7 (already done in base)
            step_num = 3
        else:
            # FULL PATH: Build Python from source
            # Step 1: Download Python source
            print("\n1. Downloading Python source...")
            tarball = _download_python_source(staging_dir)

            # Step 2: Extract source
            print("\n2. Extracting source...")
            source_dir = _extract_python_source(tarball, staging_dir)

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
            _make_python_relocatable(install_dir)

            # Step 7: Install pip
            print("\n7. Installing pip...")
            python_path = install_dir / "bin" / "python3"
            _install_pip(python_path)

            step_num = 8

        # Common path: Install Azure CLI and create package
        python_path = install_dir / "bin" / "python3"

        print(f"\n{step_num}. Installing Azure CLI...")
        _install_azure_cli(python_path)
        step_num += 1

        print(f"\n{step_num}. Creating launcher script...")
        _create_launcher_script(install_dir)
        step_num += 1

        print(f"\n{step_num}. Creating README...")
        _create_readme(install_dir, version, platform_tag)
        step_num += 1

        print(f"\n{step_num}. Pruning bytecode...")
        _prune_bytecode(install_dir)
        step_num += 1

        # Calculate final size
        final_size = sum(f.stat().st_size for f in install_dir.rglob("*") if f.is_file())
        print(f"  Final size: {final_size / (1024*1024):.1f} MB")

        print(f"\n{step_num}. Creating tar.gz archive...")
        archive_path = _create_binary_tar_gz(install_dir, version, platform_tag, artifacts_dir)

        # Generate checksum
        checksum_path = _emit_sha256(archive_path)

    # Print summary
    print("\n" + "=" * 70)
    if use_prebuilt:
        print("✅ BINARY TAR.GZ BUILD COMPLETE (Pre-built Python Base - FAST)!")
    else:
        print("✅ BINARY TAR.GZ BUILD COMPLETE (Python.org Source)!")
    print("=" * 70)
    print(f"  Archive:     {archive_path}")
    print(f"  Size:        {archive_path.stat().st_size / (1024*1024):.1f} MB")
    print(f"  SHA256:      {checksum_path}")
    print(f"  Platform:    {platform_tag}")
    print(f"  Version:     {version}")
    print(f"  Python:      {PYTHON_VERSION} (built from source)")
    print()
    print("Archive contains:")
    print("  - Python built from official python.org source")
    print("  - Profile-guided optimization (PGO)")
    print("  - Link-time optimization (LTO)")
    print("  - Azure CLI with ALL dependencies pre-installed")
    print("  - Fully relocatable (works from any location)")
    print()
    print("Homebrew Formula:")
    print()
    print("  class AzureCli < Formula")
    print('    desc "Microsoft Azure CLI 2.0"')
    print(f'    url "https://github.com/.../azure-cli-{version}-{platform_tag}.tar.gz"')
    print('    sha256 "<paste from .sha256 file>"')
    print()
    print("    def install")
    print('      libexec.install Dir["libexec/*"]')
    print('      bin.install_symlink libexec/"bin/az"')
    print("    end")
    print("  end")
    print("=" * 70)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build binary tar.gz for Azure CLI using Python built from python.org source",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Build from source (full build, ~15-20 minutes)
    python build_binary_tar_gz_python_source.py --platform-tag macos-arm64

    # Use pre-built Python base (fast, ~3 minutes)
    python build_binary_tar_gz_python_source.py --platform-tag macos-arm64 \\
        --python-base-url https://storage.blob.core.windows.net/python-base/python-3.13.1-macos-arm64-base.tar.gz

    # Use local Python base file
    python build_binary_tar_gz_python_source.py --platform-tag macos-arm64 \\
        --python-base-url file:///path/to/python-3.13.1-macos-arm64-base.tar.gz
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
        help=f"Python version to build (default: {DEFAULT_PYTHON_VERSION}). "
        "Must be available at python.org/ftp/python/{{VERSION}}/",
    )
    parser.add_argument(
        "--python-base-url",
        default=None,
        help="URL or file path to pre-built Python base tarball. "
        "When provided, skips Python build (much faster). "
        "Use build_python_base.py to create the base tarball.",
    )
    parser.add_argument(
        "--skip-version-check",
        action="store_true",
        help="Skip Python version availability check (for offline builds)",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> None:
    """Main entry point."""
    global PYTHON_VERSION, PYTHON_MAJOR_MINOR, PYTHON_SOURCE_URL

    args = parse_args(argv)

    # Set global Python version variables
    PYTHON_VERSION = args.python_version
    PYTHON_MAJOR_MINOR = get_python_major_minor(PYTHON_VERSION)
    PYTHON_SOURCE_URL = get_python_source_url(PYTHON_VERSION)

    try:
        # Validate Python version if not skipped and not using pre-built base
        if not args.skip_version_check and not args.python_base_url:
            print(f"Validating Python {args.python_version} availability...")
            validate_python_version(args.python_version)
            print(f"✓ Python {args.python_version} source available")

        build_binary_tar_gz(
            platform_tag=args.platform_tag,
            python_base_url=args.python_base_url,
        )
    except BuildError as exc:
        print(f"\n❌ ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
