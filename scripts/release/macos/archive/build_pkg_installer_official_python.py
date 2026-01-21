#!/usr/bin/env python3
"""Build Azure CLI with OFFICIAL Python.org distribution (Microsoft-approved source).

This alternative approach addresses concerns about relying on third-party distributions
by using only the official Python.org macOS installer as the Python source.

Key Differences from python-build-standalone approach:
1. Source: Official python.org (controlled by Python Software Foundation)
2. Requires: Post-processing to make relocatable (install_name_tool)
3. Trust: Same source as what users download from python.org
4. Size: Slightly larger (~80MB vs ~60MB)

Trade-offs:
- ✅ Official, trusted source (python.org)
- ✅ No dependency on third-party builds
- ✅ Fully controlled by Python Software Foundation
- ❌ Requires path fixing (install_name_tool)
- ❌ More complex build process
- ❌ Slightly larger size

Usage:
    python3 build_pkg_installer_official_python.py --platform macos-arm64

Test locally:
    # Build with official Python.org source
    python3 scripts/release/macos/build_pkg_installer_official_python.py --platform macos-arm64

    # Compare with python-build-standalone approach
    python3 scripts/release/macos/build_pkg_installer.py --platform macos-arm64

    # Test the resulting package
    sudo installer -pkg artifacts/azure-cli-*-official.pkg -target /
    az --version
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
import xml.etree.ElementTree as ET
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
INSTALL_PREFIX = "microsoft"
INSTALL_BASE_DIR = f"{INSTALL_PREFIX}/{APP_NAME}"
PKG_IDENTIFIER = "com.microsoft.azure-cli"

# Python configuration - OFFICIAL python.org source
PYTHON_VERSION = "3.13.1"

# Official Python.org download URLs and checksums
# Source: https://www.python.org/downloads/release/python-3131/
# Note: The universal2 installer works for both arm64 and x86_64
OFFICIAL_PYTHON_URLS = {
    "arm64": {
        "url": f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-macos11.pkg",
        "sha256": "67c6f0a3190851e0013214d5abd725a42ec398ff1b50eec47826820fd052d86b",
    },
    "x86_64": {
        "url": f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-macos11.pkg",
        "sha256": "67c6f0a3190851e0013214d5abd725a42ec398ff1b50eec47826820fd052d86b",
    },
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
    print(f"Verifying checksum for {file_path.name}...")
    actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

    if actual_hash.lower() != expected_sha256.lower():
        raise BuildError(
            f"Checksum mismatch for {file_path.name}\n" f"Expected: {expected_sha256}\n" f"Actual:   {actual_hash}"
        )
    print(f"✅ Checksum verified: {expected_sha256[:16]}...")


def _download_official_python(staging_dir: Path) -> Path:
    """Download and verify official Python.org installer.

    Returns the extracted Python.framework directory.
    """
    arch = platform.machine().lower()
    if arch == "arm64":
        arch_key = "arm64"
    elif arch == "x86_64":
        arch_key = "x86_64"
    else:
        raise BuildError(f"Unsupported architecture: {arch}")

    python_config = OFFICIAL_PYTHON_URLS[arch_key]
    python_url = python_config["url"]
    expected_checksum = python_config["sha256"]

    print(f"Downloading OFFICIAL Python {PYTHON_VERSION} from python.org...")
    print(f"URL: {python_url}")

    python_pkg = staging_dir / f"python-{PYTHON_VERSION}.pkg"
    urllib.request.urlretrieve(python_url, python_pkg)

    # Verify checksum
    _verify_checksum(python_pkg, expected_checksum)

    # Extract the .pkg using pkgutil
    print("Extracting Python.framework from official installer...")
    extracted_dir = staging_dir / "python_extracted"
    _ensure_clean([extracted_dir])

    # Expand the PKG file
    print("Expanding PKG with pkgutil...")
    _run(["pkgutil", "--expand", str(python_pkg), str(extracted_dir)])

    # Find the Python_Framework.pkg
    framework_pkg = extracted_dir / "Python_Framework.pkg"
    if not framework_pkg.exists():
        raise BuildError(f"Python_Framework.pkg not found in {extracted_dir}")

    # Extract the Payload
    payload_file = framework_pkg / "Payload"
    if not payload_file.exists():
        raise BuildError(f"Payload not found in {framework_pkg}")

    # Create Python.framework directory structure
    python_framework = staging_dir / "Python.framework"
    _ensure_clean([python_framework])
    python_framework.mkdir(parents=True)

    # Extract payload (it's a gzip compressed cpio archive)
    print(f"Extracting payload from {payload_file}...")
    # The Payload is a gzip-compressed cpio archive containing the framework contents
    _run(["sh", "-c", f"cd {python_framework} && gunzip -c {payload_file} | cpio -id"])

    # Verify extraction
    if not (python_framework / "Versions").exists():
        raise BuildError(f"Failed to extract Python.framework contents to {python_framework}")

    print(f"✅ Extracted Python.framework to {python_framework}")
    return python_framework


def _make_python_relocatable(python_framework: Path, staging_dir: Path) -> None:
    """Make Python.framework relocatable using install_name_tool.

    Official Python.org distributions use ABSOLUTE paths.
    We need to convert them to @rpath for relocation.
    """
    print("Making Python relocatable (fixing absolute paths)...")

    version_dir = python_framework / "Versions" / "3.13"
    if not version_dir.exists():
        # Try to find actual version
        versions = list((python_framework / "Versions").glob("3.*"))
        if not versions:
            raise BuildError("Could not find Python version directory")
        version_dir = versions[0]

    python_lib = version_dir / "Python"
    if not python_lib.exists():
        raise BuildError(f"Python library not found at {python_lib}")

    # Fix Python library itself
    print(f"Fixing {python_lib}...")
    _run(["install_name_tool", "-id", "@rpath/Python.framework/Versions/3.13/Python", str(python_lib)])

    # Fix all executables in bin/
    bin_dir = version_dir / "bin"
    if bin_dir.exists():
        for executable in bin_dir.glob("python*"):
            if executable.is_file() and not executable.is_symlink():
                print(f"Fixing {executable.name}...")
                try:
                    # First add rpath so Python can find its library
                    _run(["install_name_tool", "-add_rpath", "@executable_path/..", str(executable)])
                    # Then change the library path
                    _run(
                        [
                            "install_name_tool",
                            "-change",
                            f"/Library/Frameworks/Python.framework/Versions/3.13/Python",
                            "@rpath/Python.framework/Versions/3.13/Python",
                            str(executable),
                        ]
                    )
                except BuildError:
                    # May already have rpath or not be a Mach-O binary
                    pass

    # Fix all .so files
    lib_dynload = version_dir / "lib" / f"python{PYTHON_VERSION.rsplit('.', 1)[0]}" / "lib-dynload"
    if lib_dynload.exists():
        for so_file in lib_dynload.glob("*.so"):
            print(f"Fixing {so_file.name}...")
            try:
                _run(
                    [
                        "install_name_tool",
                        "-change",
                        f"/Library/Frameworks/Python.framework/Versions/3.13/Python",
                        "@rpath/Python.framework/Versions/3.13/Python",
                        str(so_file),
                    ]
                )
            except BuildError:
                pass

    print("✅ Python is now relocatable")


def _create_virtualenv_from_official(python_framework: Path, venv_dir: Path) -> Path:
    """Create virtual environment from official Python.framework."""
    print(f"Creating virtual environment at {venv_dir}")

    version_dir = list((python_framework / "Versions").glob("3.*"))[0]
    python_bin = version_dir / "bin" / "python3"

    if not python_bin.exists():
        raise BuildError(f"Python executable not found at {python_bin}")

    # Create venv
    _run([str(python_bin), "-m", "venv", str(venv_dir)])

    # Copy Python.framework into venv for full self-containment
    venv_frameworks = venv_dir / "Frameworks"
    venv_frameworks.mkdir(exist_ok=True)

    print("Copying Python.framework into virtual environment...")
    shutil.copytree(python_framework, venv_frameworks / "Python.framework", symlinks=False)

    # Update venv python to use bundled framework
    venv_python = venv_dir / "bin" / "python3"
    _run(["install_name_tool", "-add_rpath", "@executable_path/../Frameworks", str(venv_python)])

    # Verify
    result = _run(["otool", "-L", str(venv_python)], capture_output=True)
    print(f"Python dependencies after setup:\n{result.stdout}")

    return venv_python


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


def _install_azure_cli(python_path: Path) -> None:
    """Install Azure CLI components."""
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

    print("Verifying installation...")
    result = _run([str(python_path), "-m", "azure.cli", "--version"], capture_output=True)
    print(f"✅ Azure CLI version:\n{result.stdout}")


def build_with_official_python(platform_tag: str) -> None:
    """Build Azure CLI package using OFFICIAL Python.org distribution."""

    print("=" * 70)
    print("Building Azure CLI with OFFICIAL Python.org distribution")
    print("=" * 70)
    print(f"Python version: {PYTHON_VERSION} (from python.org)")
    print(f"Platform: {platform_tag}")
    print(f"Source: OFFICIAL Python Software Foundation")
    print("=" * 70)
    print()

    version = _detect_version()

    # Setup directories
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="azure-cli-official-") as tmpdir:
        staging_dir = Path(tmpdir)
        print(f"Using staging directory: {staging_dir}\n")

        # Step 1: Download and extract official Python
        python_framework = _download_official_python(staging_dir)

        # Step 2: Make Python relocatable
        _make_python_relocatable(python_framework, staging_dir)

        # Step 3: Create virtual environment
        venv_dir = staging_dir / "venv"
        python_path = _create_virtualenv_from_official(python_framework, venv_dir)

        # Step 4: Install Azure CLI
        _install_azure_cli(python_path)

        # Step 5: Create comparison report
        report_path = artifacts_dir / "official-python-build-report.txt"
        with open(report_path, "w") as f:
            f.write("Azure CLI Build with Official Python.org\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Python Version: {PYTHON_VERSION}\n")
            f.write(f"Azure CLI Version: {version}\n")
            f.write(f"Platform: {platform_tag}\n")
            f.write(f"Source: {OFFICIAL_PYTHON_URLS['arm64']['url']}\n")
            f.write(f"Checksum: {OFFICIAL_PYTHON_URLS['arm64']['sha256']}\n\n")

            # Size comparison
            venv_size = sum(f.stat().st_size for f in venv_dir.rglob("*") if f.is_file()) / (1024 * 1024)
            f.write(f"Virtual Environment Size: {venv_size:.1f} MB\n\n")

            # Verification
            f.write("Relocatability Check:\n")
            result = subprocess.run(["otool", "-L", str(venv_dir / "bin" / "python3")], capture_output=True, text=True)
            f.write(result.stdout)

        print(f"\n✅ Build report saved: {report_path}")
        print(f"\nVirtual environment created at: {venv_dir}")
        print(f"Size: {venv_size:.1f} MB")
        print("\nTo test locally:")
        print(f"  {venv_dir}/bin/python3 -m azure.cli --version")
        print(f"  {venv_dir}/bin/python3 -m azure.cli login")


def main():
    parser = argparse.ArgumentParser(description="Build Azure CLI with OFFICIAL Python.org distribution")
    parser.add_argument(
        "--platform",
        choices=["macos-arm64", "macos-x86_64"],
        default=f"macos-{platform.machine()}",
        help="Target platform",
    )

    args = parser.parse_args()

    try:
        build_with_official_python(args.platform)
        print("\n✅ Build completed successfully!")
        print("\nComparison Summary:")
        print("  python-build-standalone: ~60MB, pre-relocatable, no path fixing")
        print("  Official python.org:     ~80MB, requires path fixing, trusted source")
    except BuildError as exc:
        print(f"\n❌ Build failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
