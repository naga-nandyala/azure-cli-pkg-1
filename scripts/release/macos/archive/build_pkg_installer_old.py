#!/usr/bin/env python3
"""Build a macOS .pkg installer for the Azure CLI.

This script creates a native macOS installer package (.pkg) that installs the
Azure CLI directly to system locations (/usr/local). This eliminates
the complexity of symlink management that comes with .tar.gz Homebrew Casks.

The installer includes:
1. Complete Python virtual environment with all dependencies
2. Direct installation to /usr/local/bin and /usr/local/microsoft
3. Native macOS installer experience
4. Proper integration with Homebrew Cask using 'pkg' directive
5. Productbuild support for enhanced installers

Example artifact layout:

```
artifacts/
  azure-cli-2.76.0-macos-arm64.pkg
  azure-cli-2.76.0-macos-arm64.pkg.sha256
  azure-cli-2.76.0-macos-x86_64.pkg
  azure-cli-2.76.0-macos-x86_64.pkg.sha256
```

Installation layout on target system:
```
/usr/local/
├── bin/
│   └── az                       # Direct executable (no symlinks)
└── microsoft/
    └── azure-cli/               # Complete Python environment
        ├── bin/python3
        └── lib/python3.12/site-packages/
            ├── azure/
            ├── knack/
            └── ...
```

Notes:
- Requires macOS with pkgbuild and productbuild (Xcode Command Line Tools)
- Creates distribution package suitable for Homebrew Cask distribution
- Admin privileges required during installation (standard for system installs)
- Simpler launcher scripts (no symlink resolution needed)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
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
INSTALL_PREFIX = "microsoft"  # /usr/local/microsoft/
INSTALL_DIR = f"{INSTALL_PREFIX}/{APP_NAME}"  # Results in: microsoft/azure-cli
PKG_IDENTIFIER = "com.microsoft.azure-cli"


class BuildError(RuntimeError):
    """Raised when the packaging pipeline fails."""


def _run(
    cmd: Iterable[str], *, env: Optional[dict[str, str]] = None, capture_output: bool = False
) -> subprocess.CompletedProcess:
    """Execute a subprocess command, optionally capturing stdout/stderr."""

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


def _detect_version() -> str:
    """Extract the Azure CLI version from azure-cli-core/__init__.py or environment."""

    # Check if VERSION environment variable is set (from GitHub workflow)
    env_version = os.environ.get("VERSION")
    if env_version and env_version.strip():
        print(f"Using version from environment: {env_version}")
        return env_version.strip()

    # Fall back to reading from azure-cli-core/__init__.py
    init_path = AZURE_CLI_CORE_DIR / "azure" / "cli" / "core" / "__init__.py"
    try:
        source = init_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BuildError(f"Could not locate {init_path} to determine version") from exc

    # Parse __version__ = "x.y.z"
    match = re.search(r'__version__\s*=\s*[\'"](.+?)[\'"]', source)
    if not match:
        raise BuildError(f"Could not find __version__ in {init_path}")

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
        if path.is_file() or path.is_symlink():
            print(f"Cleaning file {path}")
            path.unlink()
        elif path.is_dir():
            print(f"Cleaning directory {path}")
            shutil.rmtree(path)


def _create_virtualenv(venv_dir: Path) -> Path:
    """Create a virtual environment specifically for building the package."""

    _ensure_clean([venv_dir])
    print(f"Creating build virtual environment at {venv_dir}")
    cmd = [sys.executable, "-m", "venv", "--copies", str(venv_dir)]
    _run(cmd)
    python_path = _virtualenv_python(venv_dir)
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
            raise BuildError(f"Component directory not found: {component}")

        print(f"  Installing {component.name}...")
        _run([str(python_path), "-m", "pip", "install", str(component)])

    # Verify installation
    print("Verifying Azure CLI installation...")
    result = _run([str(python_path), "-m", "azure.cli", "--version"], capture_output=True)
    print(f"Installed Azure CLI version:\n{result.stdout}")


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
    """Write content to a file, creating parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _create_system_launcher(bin_dir: Path) -> None:
    """Create simplified launcher script for direct system installation."""

    launcher_script = f"""#!/usr/bin/env bash
set -euo pipefail

# Simple direct path - no symlink resolution needed
VENV_DIR="/usr/local/{INSTALL_DIR}"
PYTHON="${{VENV_DIR}}/bin/python3"

# Verify installation integrity
if [[ ! -x "${{PYTHON}}" ]]; then
    echo "Error: Azure CLI installation appears corrupted" >&2
    echo "Python executable not found at: ${{PYTHON}}" >&2
    echo "Try reinstalling with: brew reinstall --cask azure-cli" >&2
    exit 1
fi

# Set Azure CLI installer identifier
export AZ_INSTALLER=PKG

# Execute the Azure CLI
exec "${{PYTHON}}" -m azure.cli "$@"
"""

    _write_file(bin_dir / CLI_EXECUTABLE_NAME, launcher_script, executable=True)
    print(f"Created launcher script: {bin_dir / CLI_EXECUTABLE_NAME}")


def _create_package_root(venv_source: Path, *, platform_tag: str, staging_dir: Path) -> Path:
    """Stage files in the layout they should appear on the target system."""

    # Create the installation structure that mirrors /usr/local
    pkg_root = staging_dir / "pkg_root"
    bin_dir = pkg_root / "bin"
    install_prefix_dir = pkg_root / INSTALL_PREFIX
    venv_target = install_prefix_dir / APP_NAME

    _ensure_clean([pkg_root])
    bin_dir.mkdir(parents=True, exist_ok=True)
    install_prefix_dir.mkdir(parents=True, exist_ok=True)

    # Copy the virtual environment
    print(f"Copying virtual environment to {venv_target}")
    print(f"  Source size: {sum(f.stat().st_size for f in venv_source.rglob('*') if f.is_file()) / (1024*1024):.1f} MB")
    shutil.copytree(venv_source, venv_target, symlinks=False)

    # Prune bytecode to reduce size
    print("Pruning Python bytecode files...")
    _prune_bytecode(venv_target)
    print(f"  Target size: {sum(f.stat().st_size for f in venv_target.rglob('*') if f.is_file()) / (1024*1024):.1f} MB")

    # Create the launcher script
    print("Creating system launcher script")
    _create_system_launcher(bin_dir)

    return pkg_root


def _create_distribution_xml(staging_dir: Path, *, version: str, platform_tag: str) -> Path:
    """Create distribution XML for productbuild with proper package references."""

    distribution_xml = staging_dir / "distribution.xml"
    component_pkg_name = f"{APP_NAME}-component-{version}-{platform_tag}.pkg"

    # Create distribution XML
    root = ET.Element("installer-gui-script", minSpecVersion="2")

    # Title
    ET.SubElement(root, "title").text = f"Azure CLI {version}"

    # Package reference - this MUST come before choices
    pkg_ref = ET.SubElement(root, "pkg-ref", id=PKG_IDENTIFIER)
    pkg_ref.text = component_pkg_name

    # Choices outline
    choices = ET.SubElement(root, "choices-outline")
    ET.SubElement(choices, "line", choice="azure-cli-choice")

    # Choice definition
    choice_elem = ET.SubElement(root, "choice", id="azure-cli-choice", title="Azure CLI")
    choice_elem.set("description", f"Install Azure CLI {version} command-line tool")
    choice_elem.set("start_selected", "true")
    ET.SubElement(choice_elem, "pkg-ref", id=PKG_IDENTIFIER)

    # Write XML with proper formatting
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(distribution_xml, encoding="utf-8", xml_declaration=True)

    print(f"Created distribution XML: {distribution_xml}")

    # Debug: Show XML content and verify component package reference
    print("Distribution XML content:")
    with open(distribution_xml, "r") as f:
        print(f.read())

    # Verify component package exists in staging directory
    expected_component = staging_dir / component_pkg_name
    if expected_component.exists():
        print(
            f"✅ Component package found: {expected_component} ({expected_component.stat().st_size / (1024*1024):.1f} MB)"
        )
    else:
        print(f"❌ Component package missing: {expected_component}")
        print(f"Available files in staging: {list(staging_dir.glob('*.pkg'))}")

    return distribution_xml


def _create_pkg_installer(
    pkg_root: Path,
    *,
    version: str,
    platform_tag: str,
    artifacts_dir: Path,
    staging_dir: Path,
) -> Path:
    """Create macOS .pkg installer using pkgbuild + productbuild for enhanced installer."""

    pkg_filename = f"{APP_NAME}-{version}-{platform_tag}.pkg"
    final_pkg_path = artifacts_dir / pkg_filename
    _ensure_clean([final_pkg_path])

    # Verify build tools
    for tool in ["pkgbuild", "productbuild"]:
        try:
            _run(["which", tool], capture_output=True)
        except BuildError:
            raise BuildError(f"{tool} not found. Install Xcode Command Line Tools: xcode-select --install")

    # Step 1: Create component package
    component_pkg_name = f"{APP_NAME}-component-{version}-{platform_tag}.pkg"
    component_pkg_path = staging_dir / component_pkg_name

    print(f"Creating component package: {component_pkg_path}")
    cmd = [
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
    _run(cmd)

    # Verify component package
    if not component_pkg_path.exists():
        raise BuildError(f"Component package creation failed: {component_pkg_path} does not exist")

    component_size_mb = component_pkg_path.stat().st_size / (1024 * 1024)
    print(f"Component package size: {component_size_mb:.1f} MB")
    if component_size_mb < 1.0:
        print(f"⚠️  WARNING: Component package is unusually small ({component_size_mb:.1f} MB)")

    # Step 2: Create distribution XML
    print("Creating distribution XML...")
    _create_distribution_xml(staging_dir, version=version, platform_tag=platform_tag)

    # Step 3: Create distribution package using productbuild
    print(f"Creating distribution package: {final_pkg_path}")
    distribution_xml_path = staging_dir / "distribution.xml"

    cmd = [
        "productbuild",
        "--distribution",
        str(distribution_xml_path),
        "--package-path",
        str(staging_dir),
        str(final_pkg_path),
    ]
    _run(cmd)

    print(f"Created distribution package: {final_pkg_path} ({final_pkg_path.stat().st_size / (1024*1024):.1f} MB)")

    # Verify final package
    if not final_pkg_path.exists():
        raise BuildError(f"Package creation failed: {final_pkg_path} does not exist")

    return final_pkg_path


def _emit_sha256(artifact_path: Path) -> Path:
    """Generate SHA256 checksum file."""
    print(f"Generating SHA256 checksum for {artifact_path.name}...")
    digest = hashlib.sha256()
    with artifact_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum_path = artifact_path.with_suffix(artifact_path.suffix + ".sha256")
    checksum_line = f"{digest.hexdigest()}  {artifact_path.name}\n"
    checksum_path.write_text(checksum_line, encoding="utf-8")
    print(f"SHA256: {checksum_line.strip()}")
    return checksum_path


def build_pkg_installer(*, platform_tag: str) -> None:
    """Build a .pkg installer for macOS using pkgbuild + productbuild."""

    version = _detect_version()
    artifacts_dir = PROJECT_ROOT / "dist" / "macos_pkg"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"Building Azure CLI {version} for {platform_tag} (.pkg installer)")
    print("=" * 70)

    with tempfile.TemporaryDirectory(prefix="azure-cli-pkg-build-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        # Phase 1: Create virtual environment and install Azure CLI
        print("\n[Phase 1/4] Creating virtual environment and installing Azure CLI")
        venv_dir = tmp_dir / "bundle-venv"
        python_path = _create_virtualenv(venv_dir)
        _install_azure_cli(python_path)

        # Phase 2: Stage package root
        print("\n[Phase 2/4] Staging package root")
        pkg_root = _create_package_root(venv_dir, platform_tag=platform_tag, staging_dir=tmp_dir)

        # Phase 3: Create .pkg installer
        print("\n[Phase 3/4] Creating .pkg installer")
        pkg_path = _create_pkg_installer(
            pkg_root,
            version=version,
            platform_tag=platform_tag,
            artifacts_dir=artifacts_dir,
            staging_dir=tmp_dir,
        )

        # Phase 4: Generate checksum
        print("\n[Phase 4/4] Generating checksum")
        checksum_path = _emit_sha256(pkg_path)

    # Print summary
    print("\n" + "=" * 70)
    print("✅ AZURE CLI PKG INSTALLER BUILD COMPLETE!")
    print("=" * 70)
    print(f"  Package:     {pkg_path}")
    print(f"  Size:        {pkg_path.stat().st_size / (1024*1024):.1f} MB")
    print(f"  SHA256:      {checksum_path}")
    print(f"  Platform:    {platform_tag}")
    print(f"  Version:     {version}")
    print(f"  Identifier:  {PKG_IDENTIFIER}")
    print("  Build Method: productbuild (distribution)")
    print()
    print("Installation Details:")
    print("  Target:      /usr/local/")
    print(f"  Executable:  /usr/local/bin/{CLI_EXECUTABLE_NAME}")
    print(f"  Runtime:     /usr/local/{INSTALL_DIR}/")
    print()
    print("Next steps:")
    print("  1. Test locally: sudo installer -pkg <pkg-file> -target /")
    print("  2. Verify: az --version")
    print("  3. Upload to GitHub releases")
    print("  4. Update Homebrew Cask to use .pkg")
    print("  5. Custom installer UI available via distribution package")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a .pkg installer for Azure CLI")
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
        build_pkg_installer(platform_tag=args.platform_tag)
    except BuildError as exc:
        print(f"\n❌ ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
