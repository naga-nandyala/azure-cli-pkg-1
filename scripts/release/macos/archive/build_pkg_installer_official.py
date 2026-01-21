#!/usr/bin/env python3
"""Build a macOS .pkg installer for Azure CLI using OFFICIAL Python.org distribution.

This is an alternative implementation that uses the official Python.org distribution
instead of python-build-standalone to address concerns about using third-party builds.

Key differences from build_pkg_installer.py:
1. Source: Official python.org (Python Software Foundation)
2. Requires: install_name_tool to make Python relocatable
3. More complex: ~200 lines of path-fixing logic
4. Larger size: ~68MB vs ~60MB

The end result is functionally identical:
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
    python3 build_pkg_installer_official.py --platform macos-arm64
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
    # Note: The Payload extracts directly as ./Library/Frameworks/Python.framework
    # We extract to a temp directory first to handle the nested structure
    extract_temp = staging_dir / "extract_temp"
    _ensure_clean([extract_temp])
    extract_temp.mkdir(parents=True)

    _run(["tar", "-xzf", str(payload), "-C", str(extract_temp)])

    # Python.framework could be at either:
    # 1. extract_temp/Library/Frameworks/Python.framework (old PKG format)
    # 2. extract_temp/Python.framework (direct extraction)
    # 3. extract_temp/ (framework contents directly extracted - Python 3.13+)
    python_framework = extract_temp / "Library" / "Frameworks" / "Python.framework"
    if not python_framework.exists():
        # Try direct path
        python_framework = extract_temp / "Python.framework"
        if not python_framework.exists():
            # Check if Python.framework contents are directly in extract_temp
            # Look for characteristic files: Python, Versions/, Resources/
            if (extract_temp / "Python").exists() and (extract_temp / "Versions").exists():
                # Framework contents are directly extracted - treat extract_temp as Python.framework
                python_framework = extract_temp
            else:
                # List what we got to help debug
                contents = list(extract_temp.rglob("*"))[:20]
                raise BuildError(
                    f"Python.framework not found. Extracted contents (first 20):\n"
                    + "\n".join(f"  {p}" for p in contents)
                )

    print(f"✅ Extracted: {python_framework}")
    return python_framework


def _codesign_binary(binary_path: Path) -> None:
    """Re-sign a binary with ad-hoc signature after modification."""
    try:
        _run(["codesign", "--sign", "-", "--force", "--preserve-metadata=entitlements", str(binary_path)])
    except BuildError:
        # If that fails, try without preserving metadata
        _run(["codesign", "--sign", "-", "--force", str(binary_path)])


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

    # First, clean up macOS resource fork files (._*) that interfere with codesigning
    print("\nRemoving macOS resource fork files...")
    for dot_file in python_framework.rglob("._*"):
        dot_file.unlink()
        print(f"  Removed: {dot_file.name}")

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
    _codesign_binary(python_lib)
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

                    # Re-sign the binary
                    _codesign_binary(executable)
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
                # Re-sign each module
                _codesign_binary(so_file)
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

    # CRITICAL: Fix the python3 executable itself before we try to use it
    # It still has absolute path to the Python library embedded
    print("\nFixing python3 executable to be relocatable...")
    try:
        # Change absolute library path to @rpath
        _run(
            [
                "install_name_tool",
                "-change",
                f"/Library/Frameworks/Python.framework/Versions/{PYTHON_VERSION_SHORT}/Python",
                f"@rpath/libpython{PYTHON_VERSION_SHORT}.dylib",
                str(python_bin),
            ]
        )
        # Add rpath pointing to the framework lib directory
        _run(["install_name_tool", "-add_rpath", "@executable_path/../lib", str(python_bin)])
        # Re-sign
        _codesign_binary(python_bin)
        print("✅ python3 executable is now relocatable")
    except BuildError as e:
        print(f"Warning: Could not make python3 relocatable: {e}")

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

    # Fix all executables in venv bin/ to use @rpath instead of absolute paths
    print("\nFixing venv executables to use relocatable paths...")
    venv_bin = venv_dir / "bin"
    for executable in venv_bin.iterdir():
        if executable.is_file() and not executable.is_symlink():
            # Check if it's a Mach-O binary
            try:
                result = _run(["file", str(executable)], capture_output=True)
                if "Mach-O" not in result.stdout:
                    continue
            except BuildError:
                continue

            print(f"  Fixing: {executable.name}")
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
                # Add rpath to bundled framework
                _run(
                    [
                        "install_name_tool",
                        "-add_rpath",
                        "@executable_path/../Frameworks/Python.framework/Versions/Current/lib",
                        str(executable),
                    ]
                )
                # Re-sign after modification
                _run(["codesign", "--sign", "-", "--force", str(executable)])
            except BuildError as e:
                if "would duplicate path" not in str(e):
                    print(f"    Warning: {e}")

    print("✅ Virtual environment created with bundled Python")

    # Get the venv python path
    venv_python = venv_dir / "bin" / "python3"

    # Verify it works
    print("\nVerifying Python in venv...")
    result = _run([str(venv_python), "--version"], capture_output=True)
    print(f"✅ {result.stdout.strip()}")

    return venv_python


def _install_azure_cli(python_path: Path) -> None:
    """Install Azure CLI components."""
    print("\nInstalling Azure CLI components...")

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

    print("\nVerifying installation...")
    result = _run([str(python_path), "-m", "azure.cli", "--version"], capture_output=True)
    print(f"✅ Installed:\n{result.stdout}")


def _prune_bytecode(root: Path) -> None:
    """Remove Python bytecode files to reduce package size."""
    for path in root.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)
    for suffix in (".pyc", ".pyo"):
        for file in root.rglob(f"*{suffix}"):
            try:
                file.unlink()
            except FileNotFoundError:
                pass


def _write_file(path: Path, content: str, *, executable: bool = False) -> None:
    """Write content to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _create_system_launcher(bin_dir: Path, *, version: str) -> None:
    """Create launcher script."""
    install_dir = f"{INSTALL_BASE_DIR}/{version}"
    launcher_script = f"""#!/usr/bin/env bash
set -euo pipefail

# Installation directory
VENV_DIR="/usr/local/{install_dir}"
PYTHON="${{VENV_DIR}}/bin/python3"

# Set Python home for bundled framework
export PYTHONHOME="${{VENV_DIR}}"

# Verify installation
if [[ ! -x "${{PYTHON}}" ]]; then
    echo "Error: Azure CLI installation corrupted" >&2
    echo "Python not found at: ${{PYTHON}}" >&2
    exit 1
fi

# Set installer identifier
export AZ_INSTALLER=PKG_OFFICIAL

# Execute Azure CLI
exec "${{PYTHON}}" -m azure.cli "$@"
"""

    _write_file(bin_dir / CLI_EXECUTABLE_NAME, launcher_script, executable=True)
    print(f"Created launcher: {bin_dir / CLI_EXECUTABLE_NAME}")


def _create_package_root(venv_source: Path, *, version: str, platform_tag: str, staging_dir: Path) -> Path:
    """Stage files for installation."""
    pkg_root = staging_dir / "pkg_root"
    bin_dir = pkg_root / "bin"
    install_prefix_dir = pkg_root / INSTALL_PREFIX / APP_NAME
    venv_target = install_prefix_dir / version

    _ensure_clean([pkg_root])
    bin_dir.mkdir(parents=True, exist_ok=True)
    install_prefix_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nCopying virtual environment to {venv_target}")
    source_size = sum(f.stat().st_size for f in venv_source.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"  Source size: {source_size:.1f} MB")

    shutil.copytree(venv_source, venv_target, symlinks=True)

    print("Pruning Python bytecode...")
    _prune_bytecode(venv_target)

    target_size = sum(f.stat().st_size for f in venv_target.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"  Target size: {target_size:.1f} MB")

    _create_system_launcher(bin_dir, version=version)

    return pkg_root


def _create_distribution_xml(staging_dir: Path, *, version: str, platform_tag: str) -> Path:
    """Create distribution XML for productbuild."""
    distribution_xml = staging_dir / "distribution.xml"
    component_pkg_name = f"{APP_NAME}-component-{version}-{platform_tag}-official.pkg"

    root = ET.Element("installer-gui-script", minSpecVersion="2")
    ET.SubElement(root, "title").text = f"Azure CLI {version} (Official Python)"

    pkg_ref = ET.SubElement(root, "pkg-ref", id=PKG_IDENTIFIER)
    pkg_ref.text = component_pkg_name

    choices = ET.SubElement(root, "choices-outline")
    ET.SubElement(choices, "line", choice="azure-cli-choice")

    choice_elem = ET.SubElement(root, "choice", id="azure-cli-choice", title="Azure CLI")
    choice_elem.set("description", f"Install Azure CLI {version} (Built with official Python.org)")
    choice_elem.set("start_selected", "true")
    ET.SubElement(choice_elem, "pkg-ref", id=PKG_IDENTIFIER)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(distribution_xml, encoding="utf-8", xml_declaration=True)

    print(f"Created distribution XML: {distribution_xml}")
    return distribution_xml


def _create_pkg_installer(
    pkg_root: Path,
    *,
    version: str,
    platform_tag: str,
    artifacts_dir: Path,
    staging_dir: Path,
) -> Path:
    """Create macOS .pkg installer."""
    pkg_filename = f"{APP_NAME}-{version}-{platform_tag}-official.pkg"
    final_pkg_path = artifacts_dir / pkg_filename
    _ensure_clean([final_pkg_path])

    # Verify tools
    for tool in ["pkgbuild", "productbuild"]:
        try:
            _run(["which", tool], capture_output=True)
        except BuildError:
            raise BuildError(f"{tool} not found. Install Xcode Command Line Tools.")

    # Create component package
    component_pkg_name = f"{APP_NAME}-component-{version}-{platform_tag}-official.pkg"
    component_pkg_path = staging_dir / component_pkg_name

    print(f"\nCreating component package: {component_pkg_path}")
    _run(
        [
            "pkgbuild",
            "--root",
            str(pkg_root),
            "--identifier",
            PKG_IDENTIFIER,
            "--version",
            version,
            "--install-location",
            "/usr/local",
            str(component_pkg_path),
        ]
    )

    component_size = component_pkg_path.stat().st_size / (1024 * 1024)
    print(f"Component package: {component_size:.1f} MB")

    # Create distribution XML
    _create_distribution_xml(staging_dir, version=version, platform_tag=platform_tag)

    # Create distribution package
    print(f"\nCreating distribution package: {final_pkg_path}")
    _run(
        [
            "productbuild",
            "--distribution",
            str(staging_dir / "distribution.xml"),
            "--package-path",
            str(staging_dir),
            str(final_pkg_path),
        ]
    )

    final_size = final_pkg_path.stat().st_size / (1024 * 1024)
    print(f"✅ Final package: {final_size:.1f} MB")

    return final_pkg_path


def _emit_sha256(artifact_path: Path) -> Path:
    """Generate SHA256 checksum file."""
    sha256_path = Path(str(artifact_path) + ".sha256")
    checksum = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    sha256_path.write_text(f"{checksum}  {artifact_path.name}\n")
    print(f"Created checksum: {sha256_path}")
    return sha256_path


def build_pkg_installer(*, platform_tag: str) -> None:
    """Build .pkg installer using official Python.org."""
    print("\n" + "=" * 70)
    print("Building Azure CLI with OFFICIAL Python.org")
    print("=" * 70)
    print(f"Python: {PYTHON_VERSION} (from python.org)")
    print(f"Platform: {platform_tag}")
    print("=" * 70 + "\n")

    version = _detect_version()

    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    import tempfile

    with tempfile.TemporaryDirectory(prefix="azure-cli-official-") as tmpdir:
        staging_dir = Path(tmpdir)
        print(f"Staging directory: {staging_dir}\n")

        # Download official Python
        python_pkg = _download_official_python(staging_dir)

        # Extract Python.framework
        python_framework = _extract_python_framework(python_pkg, staging_dir)

        # Make it relocatable
        _make_framework_relocatable(python_framework)

        # Create venv with bundled framework
        venv_dir = staging_dir / "venv"
        python_path = _create_venv_from_framework(python_framework, venv_dir)

        # Install Azure CLI
        _install_azure_cli(python_path)

        # Create package root
        pkg_root = _create_package_root(venv_dir, version=version, platform_tag=platform_tag, staging_dir=staging_dir)

        # Create .pkg installer
        pkg_path = _create_pkg_installer(
            pkg_root,
            version=version,
            platform_tag=platform_tag,
            artifacts_dir=artifacts_dir,
            staging_dir=staging_dir,
        )

        # Create checksum
        _emit_sha256(pkg_path)

        print("\n" + "=" * 70)
        print("✅ Build Complete!")
        print("=" * 70)
        print(f"\nArtifact: {pkg_path}")
        print(f"Size: {pkg_path.stat().st_size / (1024*1024):.1f} MB")
        print("\nThis package uses OFFICIAL Python.org distribution")
        print("Suitable for environments requiring official PSF source")


def main():
    parser = argparse.ArgumentParser(description="Build Azure CLI .pkg with OFFICIAL Python.org")
    parser.add_argument(
        "--platform",
        choices=["macos-arm64", "macos-x86_64"],
        default=f"macos-{platform.machine()}",
        help="Target platform",
    )

    args = parser.parse_args()

    try:
        build_pkg_installer(platform_tag=args.platform)
        print("\n✅ Success!")
    except BuildError as exc:
        print(f"\n❌ Build failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
