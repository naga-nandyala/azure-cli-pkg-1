#!/usr/bin/env python3
"""Build self-contained binary tar.gz for Azure CLI - Homebrew Formula distribution.

This script creates a BINARY tar.gz (not source) containing:
1. Pre-built Python runtime (python-build-standalone)
2. Complete virtual environment with all dependencies PRE-INSTALLED
3. All binary wheels (including msal[broker] which has no source)

This is similar to how azd/bicep distribute pre-built binaries via Homebrew Formula.

The Formula simply extracts and creates symlinks - NO building required.

Output Structure:
```
dist/binary_tar_gz/
  azure-cli-{VERSION}-macos-arm64.tar.gz
  azure-cli-{VERSION}-macos-arm64.tar.gz.sha256
  azure-cli-{VERSION}-macos-x86_64.tar.gz
  azure-cli-{VERSION}-macos-x86_64.tar.gz.sha256
```

Archive Contents (pre-built virtualenv):
```
azure-cli-{VERSION}/
  ├── bin/
  │   ├── python3
  │   ├── pip
  │   └── az           # Launcher script
  ├── lib/
  │   └── python3.13/
  │       └── site-packages/
  │           ├── azure/
  │           ├── msal/
  │           └── ...
  └── README.txt
```

Homebrew Formula will just:
```ruby
def install
  libexec.install Dir["*"]
  bin.install_symlink libexec/"bin/az"
end
```

Usage:
    python build_binary_tar_gz.py --platform-tag macos-arm64
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
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

# Python build configuration - use python-build-standalone (relocatable Python)
PYTHON_VERSION = "3.13.11"


def _get_python_standalone_url(platform_tag: str) -> str:
    """Get the appropriate Python standalone URL for the target platform."""
    # Extract architecture from platform tag (e.g., "macos-arm64" -> "arm64")
    if "arm64" in platform_tag:
        arch_tag = "aarch64"
    elif "x86_64" in platform_tag:
        arch_tag = "x86_64"
    else:
        raise BuildError(f"Unsupported platform tag: {platform_tag}")

    return (
        f"https://github.com/astral-sh/python-build-standalone/releases/download/20251217/"
        f"cpython-{PYTHON_VERSION}%2B20251217-{arch_tag}-apple-darwin-install_only.tar.gz"
    )


class BuildError(RuntimeError):
    """Raised when the packaging pipeline fails."""


def _run(
    cmd: Iterable[str], *, env: Optional[dict[str, str]] = None, capture_output: bool = False
) -> subprocess.CompletedProcess:
    """Execute a subprocess command, optionally capturing stdout/stderr."""
    command_list = list(cmd)
    print(f"→ {' '.join(command_list)}")
    try:
        result = subprocess.run(
            command_list,
            check=True,
            capture_output=capture_output,
            text=True,
            env=env,
        )
        if capture_output and result.stdout:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as exc:
        raise BuildError(f"Command failed: {' '.join(command_list)}") from exc


def _detect_version() -> str:
    """Extract the Azure CLI version from azure-cli-core/__init__.py or environment."""
    # Check if VERSION environment variable is set
    env_version = os.environ.get("VERSION")
    if env_version and env_version.strip():
        print(f"Using version from environment: {env_version}")
        return env_version.strip()

    # Fall back to reading from azure-cli-core/__init__.py
    init_path = AZURE_CLI_CORE_DIR / "azure" / "cli" / "core" / "__init__.py"
    try:
        source = init_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BuildError(f"Could not find version file: {init_path}") from exc

    # Parse __version__ = "x.y.z"
    match = re.search(r'__version__\s*=\s*[\'"](.+?)[\'"]', source)
    if not match:
        raise BuildError(f"Could not parse version from {init_path}")

    version = match.group(1)
    print(f"Using version from azure-cli-core: {version}")
    return version


def _virtualenv_python(venv_dir: Path) -> Path:
    """Get the Python executable path in a virtual environment."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python3"


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


def _create_virtualenv(venv_dir: Path, staging_dir: Path, platform_tag: str) -> Path:
    """Create a virtual environment using python-build-standalone (relocatable Python)."""
    _ensure_clean([venv_dir])

    # Download python-build-standalone for target architecture
    python_root = staging_dir / "python"
    python_root.mkdir(parents=True, exist_ok=True)

    python_url = _get_python_standalone_url(platform_tag)

    # Extract target architecture from platform tag
    target_arch = "ARM64" if "arm64" in platform_tag else "Intel (x86_64)"
    host_arch = platform.machine().lower()

    print(f"Downloading relocatable Python {PYTHON_VERSION} for {target_arch}...")
    print(f"Host architecture: {host_arch}")
    print(f"Target platform: {platform_tag}")

    tarball = staging_dir / "python.tar.gz"
    urllib.request.urlretrieve(python_url, tarball)

    print(f"Extracting Python to {python_root}")
    _run(["tar", "xzf", str(tarball), "-C", str(python_root), "--strip-components=1"])

    python_bin = python_root / "bin" / "python3"

    print(f"Creating virtual environment at {venv_dir}")
    _run([str(python_bin), "-m", "venv", str(venv_dir)])

    python_path = _virtualenv_python(venv_dir)

    # Manually copy Python stdlib (python-build-standalone venv doesn't copy by default)
    python_major_minor = ".".join(PYTHON_VERSION.split(".")[:2])
    stdlib_src = python_root / "lib" / f"python{python_major_minor}"
    stdlib_dest = venv_dir / "lib" / f"python{python_major_minor}"

    if stdlib_src.exists():
        print(f"Copying Python stdlib from {stdlib_src} to {stdlib_dest}")
        shutil.copytree(stdlib_src, stdlib_dest, dirs_exist_ok=True)

    # Copy libpython dylib to venv (python-build-standalone doesn't copy it automatically)
    lib_src = python_root / "lib" / f"libpython{python_major_minor}.dylib"
    lib_dest = venv_dir / "lib"
    lib_dest.mkdir(exist_ok=True)

    if lib_src.exists():
        print(f"Copying libpython from {lib_src} to {lib_dest}")
        shutil.copy2(lib_src, lib_dest)
    else:
        print(f"Warning: libpython not found at {lib_src}")

    # Fix symlinks to be relative instead of absolute (for relocatability)
    print("Fixing symlinks to be relative...")
    bin_dir = venv_dir / "bin"

    # Fix python3 symlink to point to the copied python executable
    python3_link = bin_dir / "python3"
    if python3_link.is_symlink():
        python3_link.unlink()

    # Copy the actual Python executable instead of symlinking
    shutil.copy2(python_bin, python3_link)
    python3_link.chmod(0o755)
    print(f"  Copied Python executable to {python3_link}")

    # Install pip/setuptools/wheel
    _run([str(python_path), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])

    return python_path


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


def _fix_hardcoded_paths(venv_dir: Path) -> None:
    """Fix hardcoded build paths in pyvenv.cfg and Python configuration.

    python-build-standalone leaves hardcoded /install paths in:
    1. pyvenv.cfg (home = /install)
    2. Python's sys.path (includes /install/lib/python3.13/lib-dynload)
    3. sysconfig paths (platinclude = /install/include/python3.13)

    We need to make these paths relative to the venv for true relocatability.
    """
    print("Fixing hardcoded build paths for relocatability...")

    # Fix pyvenv.cfg
    pyvenv_cfg = venv_dir / "pyvenv.cfg"
    if pyvenv_cfg.exists():
        content = pyvenv_cfg.read_text(encoding="utf-8")
        original_content = content

        # Replace absolute paths with relative paths
        # The 'home' key should point to the bin directory (use ".")
        content = re.sub(r"^home = .+$", "home = .", content, flags=re.MULTILINE)

        # Remove absolute executable path
        content = re.sub(r"^executable = .+$", "", content, flags=re.MULTILINE)

        # Remove absolute command path
        content = re.sub(r"^command = .+$", "", content, flags=re.MULTILINE)

        # Clean up empty lines
        content = re.sub(r"\n\n+", "\n", content)

        if content != original_content:
            pyvenv_cfg.write_text(content, encoding="utf-8")
            print("  ✅ Fixed pyvenv.cfg - removed absolute paths")

    # Create _pth file to ensure Python looks in the right places
    # This helps Python find stdlib and lib-dynload relative to itself
    python_major_minor = ".".join(PYTHON_VERSION.split(".")[:2])

    # Verify lib-dynload exists and is populated
    lib_dynload_src = venv_dir / "lib" / f"python{python_major_minor}" / "lib-dynload"
    if not lib_dynload_src.exists() or not list(lib_dynload_src.iterdir()):
        print(f"  ℹ️  lib-dynload not found or empty, Python may have issues with platform-dependent modules")
    else:
        print(f"  ✅ lib-dynload exists with {len(list(lib_dynload_src.iterdir()))} modules")


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
    readme_content = f"""Azure CLI {version} - Self-Contained Binary Distribution
{'=' * 70}

This is a pre-built, self-contained distribution of Azure CLI for macOS.

Platform: {platform_tag}
Python: {PYTHON_VERSION}
Distribution: Homebrew Formula (tar.gz)

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


def _reorganize_bin_directory(venv_dir: Path) -> None:
    """Reorganize bin/ directory for Homebrew compatibility.

    Homebrew expects only clean launchers in bin/ (az, python3).
    Move extra scripts (.bat, .ps1, .sh, activate scripts) to bin-extra/.
    """
    bin_dir = venv_dir / "bin"
    bin_extra_dir = venv_dir / "bin-extra"

    if not bin_dir.exists():
        print("  ⚠️  bin/ directory not found, skipping reorganization")
        return

    bin_extra_dir.mkdir(exist_ok=True)

    # Files to keep in bin/ (Homebrew-compatible launchers only)
    keep_in_bin = {"az", "python3", "pip", "pip3"}

    # Move everything else to bin-extra/
    moved_count = 0
    for item in bin_dir.iterdir():
        if item.name not in keep_in_bin:
            target = bin_extra_dir / item.name
            shutil.move(str(item), str(target))
            moved_count += 1
            print(f"  Moved: {item.name} → bin-extra/")

    print(f"  Kept {len(keep_in_bin)} files in bin/, moved {moved_count} to bin-extra/")


def _create_binary_tar_gz(venv_dir: Path, version: str, platform_tag: str, artifacts_dir: Path) -> Path:
    """Create binary tar.gz archive from virtualenv with libexec structure."""
    archive_name = f"{APP_NAME}-{version}-{platform_tag}.tar.gz"
    archive_path = artifacts_dir / archive_name

    _ensure_clean([archive_path])

    print(f"Creating binary tar.gz archive: {archive_path}")
    print(f"  Source size: {sum(f.stat().st_size for f in venv_dir.rglob('*') if f.is_file()) / (1024*1024):.1f} MB")

    # Create a temporary directory with proper Homebrew structure:
    # - libexec/ contains all Python runtime files (bin/, lib/, include/, etc.)
    # - bin/ contains only the launcher script (symlink to libexec/bin/az)
    # This isolates the Python runtime from system Python packages
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
    """Build self-contained binary tar.gz for Homebrew Formula."""
    version = _detect_version()
    artifacts_dir = PROJECT_ROOT / "dist" / "binary_tar_gz"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"Building Azure CLI {version} Binary Archive ({platform_tag})")
    print("=" * 70)

    with tempfile.TemporaryDirectory(prefix="azure-cli-binary-tar-gz-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        staging_dir = tmp_dir / "staging"
        venv_dir = tmp_dir / "venv"

        staging_dir.mkdir()

        print(f"\nTemporary directory: {tmp_dir}")

        # Create virtual environment with python-build-standalone for target platform
        print("\n1. Creating virtual environment...")
        python_path = _create_virtualenv(venv_dir, staging_dir, platform_tag)

        # Install Azure CLI
        print("\n2. Installing Azure CLI and dependencies...")
        _install_azure_cli(python_path)

        # Fix hardcoded paths for relocatability
        print("\n3. Fixing hardcoded paths for relocatability...")
        _fix_hardcoded_paths(venv_dir)

        # Create launcher script
        print("\n4. Creating launcher script...")
        _create_launcher_script(venv_dir)

        # Create README
        print("\n5. Creating README...")
        _create_readme(venv_dir, version, platform_tag)

        # Reorganize bin directory for Homebrew
        # print("\n6. Reorganizing bin/ directory for Homebrew compatibility...")
        # _reorganize_bin_directory(venv_dir)

        # Prune bytecode
        print("\n6. Pruning bytecode files...")
        _prune_bytecode(venv_dir)
        print(f"  Final size: {sum(f.stat().st_size for f in venv_dir.rglob('*') if f.is_file()) / (1024*1024):.1f} MB")

        # Create tar.gz archive
        print("\n7. Creating tar.gz archive...")
        archive_path = _create_binary_tar_gz(venv_dir, version, platform_tag, artifacts_dir)

        # Generate checksum
        checksum_path = _emit_sha256(archive_path)

    # Print summary
    print("\n" + "=" * 70)
    print("✅ BINARY TAR.GZ BUILD COMPLETE!")
    print("=" * 70)
    print(f"  Archive:     {archive_path}")
    print(f"  Size:        {archive_path.stat().st_size / (1024*1024):.1f} MB")
    print(f"  SHA256:      {checksum_path}")
    print(f"  Platform:    {platform_tag}")
    print(f"  Version:     {version}")
    print()
    print("Archive contains:")
    print("  - Self-contained Python runtime")
    print("  - Azure CLI with ALL dependencies pre-installed")
    print("  - msal[broker] and other binary packages")
    print()
    print("Next Steps:")
    print("  1. Upload to GitHub Releases")
    print("  2. Create Homebrew Formula:")
    print()
    print("     class AzureCli < Formula")
    print('       desc "Microsoft Azure CLI 2.0"')
    print(f'       url "https://github.com/.../azure-cli-{version}-{platform_tag}.tar.gz"')
    print('       sha256 "<paste from .sha256 file>"')
    print()
    print("       def install")
    print('         libexec.install Dir["*"]')
    print('         bin.install_symlink libexec/"bin/az"')
    print("       end")
    print("     end")
    print()
    print("  3. Test extraction:")
    print(f"     tar -tzf {archive_path} | head -20")
    print(f"     tar -xzf {archive_path} && ./{APP_NAME}-{version}/bin/az --version")
    print("=" * 70)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Build binary tar.gz for Azure CLI")
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
