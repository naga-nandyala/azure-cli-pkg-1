#!/usr/bin/env python3
"""Build Azure CLI tar.gz that uses Homebrew Python (no bundled Python).

This v3 approach creates a LIGHTWEIGHT tar.gz containing:
1. Azure CLI packages and dependencies (site-packages)
2. Pre-built native extensions (.so files) - already signed
3. Entry script that uses Homebrew Python

This approach:
- Does NOT bundle Python runtime (~60 MB savings)
- Relies on Homebrew python@3.13 as a dependency
- Pre-built native extensions are already signed and work with any Python 3.13
- Significantly smaller tarball and fewer binaries to sign

Output Structure:
```
dist/binary_tar_gz_v3/
  azure-cli-{VERSION}-macos-arm64-nopython.tar.gz
  azure-cli-{VERSION}-macos-arm64-nopython.tar.gz.sha256
```

Archive Contents:
```
├── bin/
│   └── az → ../libexec/bin/az
└── libexec/
    ├── bin/
    │   └── az (entry script - finds Homebrew Python)
    ├── lib/
    │   └── python3.13/
    │       └── site-packages/
    │           ├── azure/
    │           ├── msal/
    │           └── ... (all CLI packages)
    └── README.txt
```

Usage:
    python build_binary_tar_gz_v3.py --platform-tag macos-arm64

Requirements:
    - Homebrew python@3.13 installed (brew install python@3.13)
    - pip packages will be installed into a venv
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

# Azure CLI project structure
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_ROOT / "src"
AZURE_CLI_CORE_DIR = SRC_DIR / "azure-cli-core"

# Package configuration
APP_NAME = "azure-cli"
CLI_EXECUTABLE_NAME = "az"

# Python version we're building for (must match Homebrew python@3.13)
PYTHON_MAJOR_MINOR = "3.13"


class BuildError(RuntimeError):
    """Raised when the packaging pipeline fails."""


def get_cli_version() -> str:
    """Get Azure CLI version from source."""
    version_file = AZURE_CLI_CORE_DIR / "azure" / "cli" / "core" / "__init__.py"
    if not version_file.exists():
        raise BuildError(f"Version file not found: {version_file}")

    content = version_file.read_text(encoding="utf-8")
    for line in content.splitlines():
        if line.startswith("__version__"):
            # Extract version from: __version__ = "2.77.0"
            version = line.split("=")[1].strip().strip("'\"")
            return version

    raise BuildError(f"Could not find __version__ in {version_file}")


def find_homebrew_python() -> Path:
    """Find Homebrew Python 3.13 installation."""
    # Try common locations
    candidates = [
        Path("/opt/homebrew/opt/python@3.13/libexec/bin/python3"),  # ARM64
        Path("/usr/local/opt/python@3.13/libexec/bin/python3"),  # Intel
        Path("/opt/homebrew/bin/python3.13"),
        Path("/usr/local/bin/python3.13"),
    ]

    for python_path in candidates:
        if python_path.exists():
            # Verify it's the right version
            try:
                result = subprocess.run([str(python_path), "--version"], capture_output=True, text=True, check=True)
                if f"Python 3.13" in result.stdout:
                    print(f"Found Homebrew Python: {python_path}")
                    return python_path
            except subprocess.CalledProcessError:
                continue

    # Try brew --prefix
    try:
        result = subprocess.run(["brew", "--prefix", "python@3.13"], capture_output=True, text=True, check=True)
        prefix = Path(result.stdout.strip())
        python_path = prefix / "libexec" / "bin" / "python3"
        if python_path.exists():
            print(f"Found Homebrew Python via brew --prefix: {python_path}")
            return python_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    raise BuildError("Homebrew Python 3.13 not found. Install it with: brew install python@3.13")


def create_venv(python_path: Path, venv_dir: Path) -> Path:
    """Create a virtual environment using Homebrew Python."""
    print(f"\n=== Creating virtual environment ===")
    print(f"Python: {python_path}")
    print(f"Venv: {venv_dir}")

    subprocess.run([str(python_path), "-m", "venv", str(venv_dir)], check=True)

    venv_python = venv_dir / "bin" / "python3"

    # Upgrade pip
    subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)

    return venv_python


def install_azure_cli(venv_python: Path) -> None:
    """Install Azure CLI from local source into the venv."""
    print("\n=== Installing Azure CLI from source ===")

    # Install from local source directories (same as v2)
    # This installs azure-cli and all its dependencies including native extensions:
    # - cryptography (Rust-based)
    # - bcrypt, pynacl, cffi, pyyaml, psutil, wrapt
    # - pymsalruntime (via msal[broker])

    components = [
        SRC_DIR / "azure-cli-telemetry",
        SRC_DIR / "azure-cli-core",
        SRC_DIR / "azure-cli",
    ]

    for component in components:
        if not component.exists():
            raise BuildError(f"Component not found: {component}")
        print(f"  Installing {component.name}...")
        subprocess.run([str(venv_python), "-m", "pip", "install", "--prefer-binary", str(component)], check=True)

    # Install msal[broker] for macOS authentication (pymsalruntime)
    print("  Installing msal[broker]...")
    subprocess.run([str(venv_python), "-m", "pip", "install", "--prefer-binary", "msal[broker]"], check=True)

    # Verify installation
    print("\nVerifying Azure CLI installation...")
    result = subprocess.run([str(venv_python), "-m", "azure.cli", "--version"], capture_output=True, text=True)
    print(f"Installed Azure CLI version:\n{result.stdout[:500]}")


def create_install_structure(venv_dir: Path, install_dir: Path, version: str, platform_tag: str) -> None:
    """Create the final installation directory structure."""
    print(f"\n=== Creating installation structure ===")

    # Create directory structure
    libexec_dir = install_dir / "libexec"
    bin_dir = install_dir / "bin"
    libexec_bin = libexec_dir / "bin"
    libexec_lib = libexec_dir / "lib" / f"python{PYTHON_MAJOR_MINOR}"
    site_packages = libexec_lib / "site-packages"

    for d in [bin_dir, libexec_bin, site_packages]:
        d.mkdir(parents=True, exist_ok=True)

    # Copy site-packages from venv
    venv_site_packages = venv_dir / "lib" / f"python{PYTHON_MAJOR_MINOR}" / "site-packages"
    print(f"Copying site-packages from: {venv_site_packages}")
    print(f"                       to: {site_packages}")

    shutil.copytree(venv_site_packages, site_packages, dirs_exist_ok=True)

    # Create az entry script
    _create_launcher_script(libexec_bin, PYTHON_MAJOR_MINOR)

    # Create symlink: bin/az -> ../libexec/bin/az
    az_symlink = bin_dir / CLI_EXECUTABLE_NAME
    az_target = Path("..") / "libexec" / "bin" / CLI_EXECUTABLE_NAME
    az_symlink.symlink_to(az_target)
    print(f"Created symlink: {az_symlink} -> {az_target}")

    # Create README
    _create_readme(libexec_dir, version, platform_tag)

    # Clean up bytecode cache
    _cleanup_bytecode(site_packages)

    # Report sizes
    _report_sizes(install_dir)


def _create_launcher_script(bin_dir: Path, python_version: str) -> None:
    """Create az launcher script that uses Homebrew Python."""

    # This script finds Homebrew Python and sets PYTHONPATH to our site-packages
    launcher_script = f"""#!/usr/bin/env bash
set -euo pipefail

# Azure CLI Launcher (v3 - Homebrew Python)
# This script uses Homebrew Python instead of bundled Python

# Get the real path to this script (following symlinks)
SCRIPT_PATH="$(readlink -f "${{BASH_SOURCE[0]}}" 2>/dev/null || greadlink -f "${{BASH_SOURCE[0]}}" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "${{BASH_SOURCE[0]}}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
INSTALL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Our bundled site-packages
AZURE_CLI_SITE_PACKAGES="$INSTALL_DIR/libexec/lib/python{python_version}/site-packages"

# Find Homebrew Python {python_version}
find_homebrew_python() {{
    local python_path
    
    # Try brew --prefix first (most reliable)
    if command -v brew &>/dev/null; then
        local prefix
        prefix="$(brew --prefix python@{python_version} 2>/dev/null)" || true
        if [[ -n "$prefix" && -x "$prefix/libexec/bin/python3" ]]; then
            echo "$prefix/libexec/bin/python3"
            return 0
        fi
    fi
    
    # Fallback to common paths
    for python_path in \\
        "/opt/homebrew/opt/python@{python_version}/libexec/bin/python3" \\
        "/usr/local/opt/python@{python_version}/libexec/bin/python3" \\
        "/opt/homebrew/bin/python{python_version}" \\
        "/usr/local/bin/python{python_version}"; do
        if [[ -x "$python_path" ]]; then
            echo "$python_path"
            return 0
        fi
    done
    
    return 1
}}

PYTHON="$(find_homebrew_python)" || {{
    echo "Error: Homebrew Python {python_version} not found." >&2
    echo "Install it with: brew install python@{python_version}" >&2
    exit 1
}}

# Set PYTHONPATH to use our bundled packages
export PYTHONPATH="$AZURE_CLI_SITE_PACKAGES${{PYTHONPATH:+:$PYTHONPATH}}"

# Set Azure CLI installer identifier
export AZ_INSTALLER=HOMEBREW_CASK

# Execute the Azure CLI
exec "$PYTHON" -m azure.cli "$@"
"""

    az_path = bin_dir / CLI_EXECUTABLE_NAME
    az_path.write_text(launcher_script, encoding="utf-8")
    az_path.chmod(0o755)
    print(f"Created launcher script: {az_path}")


def _create_readme(install_dir: Path, version: str, platform_tag: str) -> None:
    """Create README.txt."""
    readme_content = f"""Azure CLI {version} - Homebrew Python Distribution (v3)
{'=' * 70}

This is a lightweight distribution of Azure CLI for macOS.
It uses Homebrew Python instead of bundling a Python runtime.

Platform: {platform_tag}
Python Required: {PYTHON_MAJOR_MINOR} (from Homebrew)
Distribution: Homebrew Cask (tar.gz)

Requirements:
-------------
This package requires Homebrew Python {PYTHON_MAJOR_MINOR}:

    brew install python@{PYTHON_MAJOR_MINOR}

Contents:
---------
- Azure CLI and all dependencies (pre-installed in site-packages)
- Native extensions (.so files) pre-built and signed
- msal[broker] for macOS authentication

What's NOT included:
--------------------
- Python runtime (use Homebrew's python@{PYTHON_MAJOR_MINOR})
- Python standard library
- Python headers/development files

Installation via Homebrew:
--------------------------
    brew tap azure/azure-cli
    brew install --cask azure-cli

Manual Installation:
--------------------
1. Install Python: brew install python@{PYTHON_MAJOR_MINOR}
2. Extract: tar xzf azure-cli-{version}-{platform_tag}-nopython.tar.gz
3. Add bin/ to PATH or run: ./libexec/bin/az --version

For more information:
--------------------
- Azure CLI Docs: https://docs.microsoft.com/cli/azure/
- GitHub: https://github.com/Azure/azure-cli
"""

    readme_path = install_dir / "README.txt"
    readme_path.write_text(readme_content, encoding="utf-8")
    print(f"Created README: {readme_path}")


def _cleanup_bytecode(root: Path) -> None:
    """Remove __pycache__ directories and .pyc files."""
    print(f"\n=== Cleaning bytecode cache ===")

    removed_count = 0
    for path in sorted(root.rglob("*.pyc"), reverse=True):
        path.unlink()
        removed_count += 1

    for path in sorted(root.rglob("__pycache__"), reverse=True):
        if path.is_dir():
            try:
                shutil.rmtree(path)
                removed_count += 1
            except OSError:
                pass

    print(f"Removed {removed_count} bytecode files/directories")


def _report_sizes(install_dir: Path) -> None:
    """Report sizes of components."""
    print(f"\n=== Size Report ===")

    def get_size(path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        total = 0
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return total

    def fmt_size(size: int) -> str:
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        elif size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"

    print(f"  Total: {fmt_size(get_size(install_dir))}")

    for subdir in ["bin", "libexec/bin", "libexec/lib"]:
        path = install_dir / subdir
        if path.exists():
            print(f"  {subdir}: {fmt_size(get_size(path))}")

    # Count native extensions
    so_files = list((install_dir / "libexec" / "lib").rglob("*.so"))
    print(f"\n  Native extensions (.so): {len(so_files)} files")
    for so_file in sorted(so_files)[:10]:
        rel_path = so_file.relative_to(install_dir)
        print(f"    - {rel_path.name}: {fmt_size(get_size(so_file))}")
    if len(so_files) > 10:
        print(f"    ... and {len(so_files) - 10} more")


def create_tarball(install_dir: Path, output_dir: Path, version: str, platform_tag: str) -> Path:
    """Create the final tar.gz archive."""
    print(f"\n=== Creating tarball ===")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Tarball name indicates no bundled Python
    tarball_name = f"{APP_NAME}-{version}-{platform_tag}-nopython.tar.gz"
    tarball_path = output_dir / tarball_name

    # Create tarball
    with tarfile.open(tarball_path, "w:gz") as tar:
        # Add with proper archive name prefix
        for item in install_dir.iterdir():
            arcname = item.name
            tar.add(item, arcname=arcname)

    print(f"Created: {tarball_path}")
    print(f"Size: {tarball_path.stat().st_size / (1024 * 1024):.1f} MB")

    # Create SHA256 checksum
    sha256_path = Path(str(tarball_path) + ".sha256")
    sha256_hash = hashlib.sha256()
    with open(tarball_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    checksum = sha256_hash.hexdigest()
    sha256_path.write_text(f"{checksum}  {tarball_name}\n")
    print(f"SHA256: {checksum}")

    return tarball_path


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build Azure CLI tar.gz using Homebrew Python (v3 - no bundled Python)"
    )
    parser.add_argument(
        "--platform-tag", required=True, choices=["macos-arm64", "macos-x86_64"], help="Platform tag for the build"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "dist" / "binary_tar_gz_v3",
        help="Output directory for the tarball",
    )
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary build directory for debugging")

    args = parser.parse_args()

    print("=" * 70)
    print("Azure CLI Tarball Builder (v3 - Homebrew Python)")
    print("=" * 70)
    print(f"Platform: {args.platform_tag}")
    print(f"Output: {args.output_dir}")
    print()

    try:
        # Get CLI version
        version = get_cli_version()
        print(f"Azure CLI version: {version}")

        # Find Homebrew Python
        python_path = find_homebrew_python()

        # Create temp directory
        with tempfile.TemporaryDirectory(prefix="azure-cli-build-") as temp_dir:
            temp_path = Path(temp_dir)
            venv_dir = temp_path / "venv"
            install_dir = temp_path / "install"

            # Create venv and install CLI
            venv_python = create_venv(python_path, venv_dir)
            install_azure_cli(venv_python)

            # Create installation structure
            create_install_structure(venv_dir, install_dir, version, args.platform_tag)

            # Create tarball
            tarball_path = create_tarball(install_dir, args.output_dir, version, args.platform_tag)

            if args.keep_temp:
                print(f"\nTemp directory preserved: {temp_path}")
                # Copy to a permanent location
                preserved_dir = args.output_dir / "build-temp"
                if preserved_dir.exists():
                    shutil.rmtree(preserved_dir)
                shutil.copytree(temp_path, preserved_dir)
                print(f"Copied to: {preserved_dir}")

        print("\n" + "=" * 70)
        print("BUILD SUCCESSFUL")
        print("=" * 70)
        print(f"Tarball: {tarball_path}")
        print(f"\nTo test locally:")
        print(f"  tar xzf {tarball_path}")
        print(f"  ./libexec/bin/az --version")
        print()

        return 0

    except BuildError as e:
        print(f"\n❌ BUILD FAILED: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
