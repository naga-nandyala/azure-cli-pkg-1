#!/usr/bin/env python3
"""
Build self-contained Azure CLI binary tar.gz with FLAT structure (no libexec).
This version creates a flat tarball to test if Homebrew can handle it without conflicts.
"""

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

# --------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------
APP_NAME = "azure-cli"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_ROOT / "src"
AZURE_CLI_CORE_DIR = SRC_DIR / "azure-cli-core"

# Python version from python-build-standalone
PYTHON_VERSION = "3.13.11"
PYTHON_BUILD_DATE = "20251217"

# Download URLs for python-build-standalone
PYTHON_URLS = {
    "macos-arm64": (
        f"https://github.com/astral-sh/python-build-standalone/releases/download/{PYTHON_BUILD_DATE}/"
        f"cpython-{PYTHON_VERSION}%2B{PYTHON_BUILD_DATE}-aarch64-apple-darwin-install_only.tar.gz"
    ),
    "macos-x86_64": (
        f"https://github.com/astral-sh/python-build-standalone/releases/download/{PYTHON_BUILD_DATE}/"
        f"cpython-{PYTHON_VERSION}%2B{PYTHON_BUILD_DATE}-x86_64-apple-darwin-install_only.tar.gz"
    ),
}


def _detect_version() -> str:
    """Extract the Azure CLI version from azure-cli-core/__init__.py."""
    init_path = AZURE_CLI_CORE_DIR / "azure" / "cli" / "core" / "__init__.py"
    try:
        source = init_path.read_text(encoding="utf-8")
        match = re.search(r'__version__\s*=\s*[\'"](.+?)[\'"]', source)
        if match:
            version = match.group(1)
            print(f"Using version from azure-cli-core: {version}")
            return version
    except (FileNotFoundError, AttributeError):
        pass

    print("Warning: Could not detect version from source.")
    return "0.0.0"


def _ensure_clean(paths):
    """Remove paths if they exist."""
    for p in paths:
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()


def _download_python_standalone(url: str, download_dir: Path) -> Path:
    """Download Python standalone build."""
    tarball_path = download_dir / "python.tar.gz"

    if tarball_path.exists():
        print(f"Using cached Python standalone: {tarball_path}")
        return tarball_path

    print(f"Downloading Python standalone from {url}...")
    urllib.request.urlretrieve(url, tarball_path)
    size_mb = tarball_path.stat().st_size / (1024 * 1024)
    print(f"Downloaded: {tarball_path} ({size_mb:.1f} MB)")

    return tarball_path


def _extract_python(tarball_path: Path, python_dir: Path):
    """Extract Python standalone tarball."""
    print(f"Extracting Python to {python_dir}...")
    python_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tarball_path, "r:gz") as tar:
        tar.extractall(python_dir)

    # Remove top-level 'python' directory if present
    nested_python = python_dir / "python"
    if nested_python.exists() and nested_python.is_dir():
        for item in nested_python.iterdir():
            shutil.move(str(item), str(python_dir / item.name))
        nested_python.rmdir()

    python_bin = python_dir / "bin" / "python3"
    if not python_bin.exists():
        raise FileNotFoundError(f"python3 not found at {python_bin}")

    print(f"✅ Python extracted: {python_bin}")


def _create_venv(python_bin: Path, venv_dir: Path):
    """Create virtual environment using standalone Python."""
    print(f"Creating virtual environment at {venv_dir}...")

    subprocess.run(
        [str(python_bin), "-m", "venv", str(venv_dir)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    venv_python = venv_dir / "bin" / "python3"
    if not venv_python.exists():
        raise FileNotFoundError(f"Virtual environment python3 not found at {venv_python}")

    print(f"✅ Virtual environment created: {venv_python}")
    return venv_python


def _install_azure_cli(venv_python: Path):
    """Install azure-cli package into virtualenv from local source."""
    print("Installing azure-cli package from local source...")

    # Upgrade pip/setuptools/wheel
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Install in the correct order to satisfy dependencies
    components = [
        SRC_DIR / "azure-cli-telemetry",
        SRC_DIR / "azure-cli-core",
        SRC_DIR / "azure-cli",
    ]

    for component in components:
        if not component.exists():
            raise FileNotFoundError(f"Component not found: {component}")
        print(f"  Installing {component.name}...")
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", str(component)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    print("✅ azure-cli installed successfully from local source")


def _verify_az_command(venv_dir: Path):
    """Verify az command works in the venv."""
    az_path = venv_dir / "bin" / "az"
    if not az_path.exists():
        raise FileNotFoundError(f"az command not found at {az_path}")

    result = subprocess.run(
        [str(az_path), "--version"],
        check=True,
        capture_output=True,
        text=True,
    )

    print("✅ az command verification:")
    print(result.stdout[:200])


def _reorganize_bin_directory(venv_dir: Path):
    """Move extra binaries to bin-extra/ to keep bin/ clean for Homebrew."""
    bin_dir = venv_dir / "bin"
    bin_extra_dir = venv_dir / "bin-extra"
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


def _create_binary_tar_gz_flat(venv_dir: Path, version: str, platform_tag: str, artifacts_dir: Path) -> Path:
    """Create binary tar.gz archive from virtualenv with FLAT structure (no libexec)."""
    archive_name = f"{APP_NAME}-{version}-{platform_tag}-flat.tar.gz"
    archive_path = artifacts_dir / archive_name

    _ensure_clean([archive_path])

    print(f"Creating FLAT binary tar.gz archive: {archive_path}")
    print(f"  Source size: {sum(f.stat().st_size for f in venv_dir.rglob('*') if f.is_file()) / (1024*1024):.1f} MB")

    # Create archive directly from venv directory (flat structure)
    with tarfile.open(archive_path, "w:gz") as tar:
        for item in venv_dir.iterdir():
            tar.add(item, arcname=item.name, recursive=True)
            print(f"  Added: {item.name}")

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


def build_binary_tar_gz_flat(*, platform_tag: str) -> None:
    """Build self-contained binary tar.gz with FLAT structure for testing."""
    version = _detect_version()
    artifacts_dir = PROJECT_ROOT / "dist" / "binary_tar_gz"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"Building Azure CLI {version} Binary Archive - FLAT ({platform_tag})")
    print("=" * 70)

    with tempfile.TemporaryDirectory(prefix="azure-cli-binary-tar-gz-flat-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        staging_dir = tmp_dir / "staging"
        venv_dir = tmp_dir / "venv"

        staging_dir.mkdir()

        # 1. Download Python standalone build
        if platform_tag not in PYTHON_URLS:
            raise ValueError(f"Unsupported platform: {platform_tag}")

        python_url = PYTHON_URLS[platform_tag]
        python_tarball = _download_python_standalone(python_url, staging_dir)

        # 2. Extract Python
        python_dir = staging_dir / "python"
        _extract_python(python_tarball, python_dir)

        python_bin = python_dir / "bin" / "python3"

        # 3. Create venv
        venv_python = _create_venv(python_bin, venv_dir)

        # 4. Install Azure CLI
        _install_azure_cli(venv_python)

        # 5. Verify az command
        _verify_az_command(venv_dir)

        # 6. Create binary tar.gz (FLAT structure - no bin reorganization)
        archive_path = _create_binary_tar_gz_flat(venv_dir, version, platform_tag, artifacts_dir)

        # 8. Generate SHA256
        checksum_path = _emit_sha256(archive_path)

    print("\n" + "=" * 70)
    print("✅ BUILD COMPLETE (FLAT)")
    print("=" * 70)
    print(f"Archive:  {archive_path}")
    print(f"Checksum: {checksum_path}")
    print(f"Size:     {archive_path.stat().st_size / (1024*1024):.1f} MB")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python build_binary_tar_gz_flat.py [macos-arm64|macos-x86_64]")
        sys.exit(1)

    platform_tag = sys.argv[1]
    if platform_tag not in PYTHON_URLS:
        print(f"Error: Unsupported platform '{platform_tag}'")
        print(f"Supported: {', '.join(PYTHON_URLS.keys())}")
        sys.exit(1)

    build_binary_tar_gz_flat(platform_tag=platform_tag)


if __name__ == "__main__":
    main()
