#!/usr/bin/env python3
"""Build a macOS .pkg installer for Azure CLI with VERSIONED installation support (PR2).

This is the PR2 variant that implements Homebrew-style versioned installation:
- Each version installs to: /usr/local/microsoft/azure-cli/{version}/
- Symlink 'current' points to active version: /usr/local/microsoft/azure-cli/current
- Launcher script reads 'current' symlink to find active version
- Old versions preserved during upgrades (not removed)
- Includes cleanup utility for manual old version removal

Key differences from original build_pkg_installer.py:
1. VERSIONED_INSTALL mode: Installs to azure-cli/{version}/ instead of azure-cli/
2. Preinstall script: Preserves old versions, removes old 'current' symlink
3. Postinstall script: Creates 'current' symlink pointing to new version
4. Launcher script: Resolves 'current' symlink to find active installation
5. Cleanup utility: cleanup-old-versions.sh for removing old versions

Installation layout on target system:
```
/usr/local/
├── bin/
│   ├── az                                    # Launcher (resolves 'current' symlink)
│   └── cleanup-azure-cli-versions.sh        # Cleanup utility
└── microsoft/
    └── azure-cli/
        ├── 2.80.0/                          # Old version (preserved)
        │   ├── bin/python3
        │   └── lib/python3.12/site-packages/
        ├── 2.81.0/                          # New version
        │   ├── bin/python3
        │   └── lib/python3.12/site-packages/
        └── current -> 2.81.0                # Symlink to active version
```

See docs/PKG_VERSIONING_DESIGN.md for complete design specification.
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
BASE_INSTALL_DIR = f"{INSTALL_PREFIX}/{APP_NAME}"  # microsoft/azure-cli
PKG_IDENTIFIER = "com.microsoft.azure-cli"  # Same identifier for both variants
CLEANUP_SCRIPT_NAME = "cleanup-azure-cli-versions.sh"


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


def _create_versioned_launcher(bin_dir: Path, *, version: str) -> None:
    """Create launcher script that resolves 'current' symlink to find active version."""

    launcher_script = f"""#!/usr/bin/env bash
set -euo pipefail

# Versioned installation paths
BASE_DIR="/usr/local/{BASE_INSTALL_DIR}"
CURRENT_LINK="${{BASE_DIR}}/current"

# Resolve 'current' symlink to find active version
if [[ ! -L "${{CURRENT_LINK}}" ]]; then
    echo "Error: Azure CLI 'current' symlink not found" >&2
    echo "Expected symlink at: ${{CURRENT_LINK}}" >&2
    echo "Your installation may be corrupted. Try reinstalling with:" >&2
    echo "  brew reinstall --cask azure-cli" >&2
    exit 1
fi

# Get the active version directory
VERSION_DIR=$(readlink "${{CURRENT_LINK}}")
if [[ "${{VERSION_DIR}}" =~ ^/ ]]; then
    # Absolute path (unlikely but handle it)
    VENV_DIR="${{VERSION_DIR}}"
else
    # Relative path (expected: just "2.81.0")
    VENV_DIR="${{BASE_DIR}}/${{VERSION_DIR}}"
fi

PYTHON="${{VENV_DIR}}/bin/python3"

# Verify installation integrity
if [[ ! -x "${{PYTHON}}" ]]; then
    echo "Error: Azure CLI installation appears corrupted" >&2
    echo "Current symlink points to: ${{VERSION_DIR}}" >&2
    echo "Python executable not found at: ${{PYTHON}}" >&2
    echo "Available versions:" >&2
    ls -1 "${{BASE_DIR}}" 2>/dev/null | grep -E '^[0-9]+\\.[0-9]+\\.[0-9]+$' || echo "  (none found)" >&2
    echo "" >&2
    echo "Try reinstalling with: brew reinstall --cask azure-cli" >&2
    exit 1
fi

# Set Azure CLI installer identifier
export AZ_INSTALLER=PKG

# Execute the Azure CLI
exec "${{PYTHON}}" -m azure.cli "$@"
"""

    _write_file(bin_dir / CLI_EXECUTABLE_NAME, launcher_script, executable=True)
    print(f"Created versioned launcher script: {bin_dir / CLI_EXECUTABLE_NAME}")


def _create_cleanup_script(bin_dir: Path) -> None:
    """Create cleanup utility for removing old Azure CLI versions."""

    cleanup_script = f"""#!/usr/bin/env bash
# cleanup-azure-cli-versions.sh
# Utility to remove old Azure CLI versions while preserving the current version
#
# Usage:
#   cleanup-azure-cli-versions.sh --keep N    # Keep N most recent versions
#   cleanup-azure-cli-versions.sh --all       # Remove all except current
#   cleanup-azure-cli-versions.sh --dry-run   # Show what would be deleted

set -euo pipefail

BASE_DIR="/usr/local/{BASE_INSTALL_DIR}"
CURRENT_LINK="${{BASE_DIR}}/current"

show_usage() {{
    cat << 'EOF'
Usage: cleanup-azure-cli-versions.sh [OPTIONS]

Remove old Azure CLI versions while preserving the currently active version.

Options:
  --keep N      Keep the N most recent versions (including current)
  --all         Remove all versions except the current one
  --dry-run     Show what would be deleted without actually deleting
  --help        Show this help message

Examples:
  cleanup-azure-cli-versions.sh --keep 2      # Keep current + 1 previous
  cleanup-azure-cli-versions.sh --all         # Remove all old versions
  cleanup-azure-cli-versions.sh --dry-run     # Preview deletions

Current version is determined by the 'current' symlink.
EOF
}}

# Parse arguments
KEEP_COUNT=""
DRY_RUN=false
REMOVE_ALL=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep)
            KEEP_COUNT="$2"
            shift 2
            ;;
        --all)
            REMOVE_ALL=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option: $1" >&2
            show_usage
            exit 1
            ;;
    esac
done

# Validate arguments
if [[ -z "${{KEEP_COUNT}}" && "${{REMOVE_ALL}}" != true ]]; then
    echo "Error: Must specify --keep N or --all" >&2
    show_usage
    exit 1
fi

# Verify base directory exists
if [[ ! -d "${{BASE_DIR}}" ]]; then
    echo "Error: Azure CLI installation directory not found: ${{BASE_DIR}}" >&2
    exit 1
fi

# Get current version
if [[ ! -L "${{CURRENT_LINK}}" ]]; then
    echo "Error: 'current' symlink not found at: ${{CURRENT_LINK}}" >&2
    exit 1
fi

CURRENT_VERSION=$(basename "$(readlink "${{CURRENT_LINK}}")")
echo "Current version: ${{CURRENT_VERSION}}"
echo ""

# Find all version directories (match X.Y.Z pattern)
mapfile -t ALL_VERSIONS < <(
    cd "${{BASE_DIR}}" && \\
    find . -maxdepth 1 -type d -name '[0-9]*.[0-9]*.[0-9]*' | \\
    sed 's|^\\./||' | \\
    sort -V
)

if [[ ${{#ALL_VERSIONS[@]}} -eq 0 ]]; then
    echo "No versioned installations found."
    exit 0
fi

echo "Installed versions:"
for ver in "${{ALL_VERSIONS[@]}}"; do
    if [[ "$ver" == "${{CURRENT_VERSION}}" ]]; then
        echo "  $ver (current)"
    else
        echo "  $ver"
    fi
done
echo ""

# Determine versions to remove
VERSIONS_TO_REMOVE=()

if [[ "${{REMOVE_ALL}}" == true ]]; then
    # Remove all except current
    for ver in "${{ALL_VERSIONS[@]}}"; do
        if [[ "$ver" != "${{CURRENT_VERSION}}" ]]; then
            VERSIONS_TO_REMOVE+=("$ver")
        fi
    done
else
    # Keep N most recent (including current)
    TOTAL_VERSIONS=${{#ALL_VERSIONS[@]}}
    REMOVE_COUNT=$((TOTAL_VERSIONS - KEEP_COUNT))
    
    if [[ $REMOVE_COUNT -le 0 ]]; then
        echo "Nothing to remove. Installed versions (${{TOTAL_VERSIONS}}) <= keep count (${{KEEP_COUNT}})."
        exit 0
    fi
    
    # Remove oldest versions
    for ((i=0; i<REMOVE_COUNT; i++)); do
        ver="${{ALL_VERSIONS[i]}}"
        if [[ "$ver" != "${{CURRENT_VERSION}}" ]]; then
            VERSIONS_TO_REMOVE+=("$ver")
        fi
    done
fi

# Show what will be removed
if [[ ${{#VERSIONS_TO_REMOVE[@]}} -eq 0 ]]; then
    echo "Nothing to remove."
    exit 0
fi

echo "Versions to remove:"
TOTAL_SIZE=0
for ver in "${{VERSIONS_TO_REMOVE[@]}}"; do
    SIZE=$(du -sh "${{BASE_DIR}}/${{ver}}" 2>/dev/null | cut -f1 || echo "unknown")
    echo "  $ver (${{SIZE}})"
    # Calculate total size in MB (rough estimate)
    if [[ "$SIZE" =~ ^([0-9]+)M ]]; then
        TOTAL_SIZE=$((TOTAL_SIZE + ${{BASH_REMATCH[1]}}))
    elif [[ "$SIZE" =~ ^([0-9.]+)G ]]; then
        TOTAL_SIZE=$((TOTAL_SIZE + ${{BASH_REMATCH[1]}} * 1024))
    fi
done
echo ""
echo "Total space to reclaim: ~${{TOTAL_SIZE}}M"
echo ""

# Execute or dry-run
if [[ "${{DRY_RUN}}" == true ]]; then
    echo "[DRY RUN] Would remove the above versions. Run without --dry-run to delete."
    exit 0
fi

# Confirm deletion
read -p "Remove these versions? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Remove versions
echo "Removing old versions..."
for ver in "${{VERSIONS_TO_REMOVE[@]}}"; do
    echo "  Removing $ver..."
    rm -rf "${{BASE_DIR}}/${{ver}}"
done

echo ""
echo "✅ Cleanup complete!"
echo "Remaining versions:"
cd "${{BASE_DIR}}" && ls -1 | grep -E '^[0-9]+\\.[0-9]+\\.[0-9]+$' || echo "(none)"
"""

    _write_file(bin_dir / CLEANUP_SCRIPT_NAME, cleanup_script, executable=True)
    print(f"Created cleanup utility script: {bin_dir / CLEANUP_SCRIPT_NAME}")


def _create_preinstall_script(scripts_dir: Path, *, version: str) -> Path:
    """Create preinstall script to prepare for versioned installation."""

    preinstall_script = f"""#!/usr/bin/env bash
# Preinstall script for Azure CLI {version} (versioned installation)
# Runs BEFORE PKG payload is extracted
#
# Responsibilities:
# 1. Preserve existing version directories (don't remove old versions)
# 2. Remove old 'current' symlink (will be recreated by postinstall)
# 3. Verify installation directory structure

set -euo pipefail

BASE_DIR="/usr/local/{BASE_INSTALL_DIR}"
CURRENT_LINK="${{BASE_DIR}}/current"
NEW_VERSION="{version}"

echo "Azure CLI {version} - Preinstall"
echo "================================"

# Create base directory if it doesn't exist
if [[ ! -d "${{BASE_DIR}}" ]]; then
    echo "Creating installation directory: ${{BASE_DIR}}"
    mkdir -p "${{BASE_DIR}}"
fi

# List existing versions
if [[ -d "${{BASE_DIR}}" ]]; then
    EXISTING_VERSIONS=$(cd "${{BASE_DIR}}" && find . -maxdepth 1 -type d -name '[0-9]*.[0-9]*.[0-9]*' | sed 's|^\\./||' | sort -V || echo "")
    if [[ -n "${{EXISTING_VERSIONS}}" ]]; then
        echo "Existing versions (will be preserved):"
        echo "${{EXISTING_VERSIONS}}" | sed 's/^/  /'
    else
        echo "No existing versions found."
    fi
fi

# Remove old 'current' symlink (will be recreated by postinstall)
if [[ -L "${{CURRENT_LINK}}" ]]; then
    OLD_CURRENT=$(readlink "${{CURRENT_LINK}}" || echo "unknown")
    echo "Removing old 'current' symlink: ${{CURRENT_LINK}} -> ${{OLD_CURRENT}}"
    rm -f "${{CURRENT_LINK}}"
elif [[ -e "${{CURRENT_LINK}}" ]]; then
    echo "Warning: '${{CURRENT_LINK}}' exists but is not a symlink. Removing it."
    rm -rf "${{CURRENT_LINK}}"
fi

echo "Preinstall complete. Ready to install version {version}."
exit 0
"""

    preinstall_path = scripts_dir / "preinstall"
    _write_file(preinstall_path, preinstall_script, executable=True)
    print(f"Created preinstall script: {preinstall_path}")
    return preinstall_path


def _create_postinstall_script(scripts_dir: Path, *, version: str) -> Path:
    """Create postinstall script to finalize versioned installation."""

    postinstall_script = f"""#!/usr/bin/env bash
# Postinstall script for Azure CLI {version} (versioned installation)
# Runs AFTER PKG payload is extracted
#
# Responsibilities:
# 1. Create 'current' symlink pointing to newly installed version
# 2. Verify installation integrity
# 3. Display installation summary

set -euo pipefail

BASE_DIR="/usr/local/{BASE_INSTALL_DIR}"
CURRENT_LINK="${{BASE_DIR}}/current"
NEW_VERSION="{version}"
VERSION_DIR="${{BASE_DIR}}/${{NEW_VERSION}}"
PYTHON_EXEC="${{VERSION_DIR}}/bin/python3"
LAUNCHER="/usr/local/bin/{CLI_EXECUTABLE_NAME}"

echo "Azure CLI {version} - Postinstall"
echo "================================="

# Ensure base directory exists
if [[ ! -d "${{BASE_DIR}}" ]]; then
    echo "Creating base directory: ${{BASE_DIR}}"
    mkdir -p "${{BASE_DIR}}"
fi

# Verify version directory was installed
if [[ ! -d "${{VERSION_DIR}}" ]]; then
    echo "Error: Version directory not found: ${{VERSION_DIR}}" >&2
    exit 1
fi

# Verify Python executable
if [[ ! -x "${{PYTHON_EXEC}}" ]]; then
    echo "Error: Python executable not found or not executable: ${{PYTHON_EXEC}}" >&2
    exit 1
fi

# Remove old 'current' symlink if it exists
if [[ -L "${{CURRENT_LINK}}" ]] || [[ -e "${{CURRENT_LINK}}" ]]; then
    echo "Removing existing 'current' symlink"
    rm -f "${{CURRENT_LINK}}"
fi

# Create 'current' symlink (relative path)
echo "Creating 'current' symlink: ${{CURRENT_LINK}} -> ${{NEW_VERSION}}"
if cd "${{BASE_DIR}}" && ln -sf "${{NEW_VERSION}}" current; then
    echo "✅ Symlink created successfully"
else
    echo "⚠️  Warning: Failed to create symlink" >&2
fi

# Verify symlink (non-fatal)
if [[ -L "${{CURRENT_LINK}}" ]]; then
    LINK_TARGET=$(readlink "${{CURRENT_LINK}}")
    echo "✅ Current symlink: ${{CURRENT_LINK}} -> ${{LINK_TARGET}}"
else
    echo "⚠️  Warning: Symlink verification failed" >&2
fi

# Verify launcher exists (non-fatal)
if [[ -x "${{LAUNCHER}}" ]]; then
    echo "✅ Launcher installed at: ${{LAUNCHER}}"
else
    echo "⚠️  Warning: Launcher not found at: ${{LAUNCHER}}" >&2
fi

# Show installed versions (non-fatal)
echo ""
echo "Installed versions:"
if cd "${{BASE_DIR}}" 2>/dev/null; then
    ls -1 | grep -E '^[0-9]' | while read ver; do
        if [[ "$ver" == "${{NEW_VERSION}}" ]]; then
            echo "  $ver (current)"
        else
            echo "  $ver"
        fi
    done || echo "  ${{NEW_VERSION}} (current)"
fi

echo ""
echo "Installation complete!"
echo "Run 'az --version' to verify installation."
echo "Run '{CLEANUP_SCRIPT_NAME} --help' to manage old versions."

exit 0
"""

    postinstall_path = scripts_dir / "postinstall"
    _write_file(postinstall_path, postinstall_script, executable=True)
    print(f"Created postinstall script: {postinstall_path}")
    return postinstall_path


def _create_package_root(venv_source: Path, *, version: str, platform_tag: str, staging_dir: Path) -> Path:
    """Stage files in the layout they should appear on the target system (VERSIONED)."""

    # Create the installation structure with VERSION in path
    pkg_root = staging_dir / "pkg_root"
    bin_dir = pkg_root / "bin"
    install_prefix_dir = pkg_root / INSTALL_PREFIX
    versioned_base = install_prefix_dir / APP_NAME
    venv_target = versioned_base / version  # Key change: add version subdirectory

    _ensure_clean([pkg_root])
    bin_dir.mkdir(parents=True, exist_ok=True)
    versioned_base.mkdir(parents=True, exist_ok=True)

    # Copy the virtual environment to versioned directory
    print(f"Copying virtual environment to {venv_target}")
    print(f"  Source size: {sum(f.stat().st_size for f in venv_source.rglob('*') if f.is_file()) / (1024*1024):.1f} MB")
    shutil.copytree(venv_source, venv_target, symlinks=False)

    # Prune bytecode to reduce size
    print("Pruning Python bytecode files...")
    _prune_bytecode(venv_target)
    print(f"  Target size: {sum(f.stat().st_size for f in venv_target.rglob('*') if f.is_file()) / (1024*1024):.1f} MB")

    # Create the versioned launcher script
    print("Creating versioned launcher script")
    _create_versioned_launcher(bin_dir, version=version)

    # Create cleanup utility script
    print("Creating cleanup utility script")
    _create_cleanup_script(bin_dir)

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
    choice_elem.set("description", f"Install Azure CLI {version} command-line tool (versioned installation)")
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
    """Create macOS .pkg installer with preinstall/postinstall scripts for versioning."""

    pkg_filename = f"{APP_NAME}-{version}-{platform_tag}.pkg"
    final_pkg_path = artifacts_dir / pkg_filename
    _ensure_clean([final_pkg_path])

    # Verify build tools
    for tool in ["pkgbuild", "productbuild"]:
        try:
            _run(["which", tool], capture_output=True)
        except BuildError:
            raise BuildError(f"{tool} not found. Install Xcode Command Line Tools: xcode-select --install")

    # Create scripts directory
    scripts_dir = staging_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)

    # Create preinstall and postinstall scripts
    preinstall_path = _create_preinstall_script(scripts_dir, version=version)
    postinstall_path = _create_postinstall_script(scripts_dir, version=version)

    # Step 1: Create component package with scripts
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
        "--scripts",
        str(scripts_dir),
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
    """Build a .pkg installer for macOS with VERSIONED installation support."""

    version = _detect_version()
    artifacts_dir = PROJECT_ROOT / "dist" / "macos_pkg_pr2"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"Building Azure CLI {version} for {platform_tag}")
    print("(.pkg installer with VERSIONED installation - PR2)")
    print("=" * 70)

    with tempfile.TemporaryDirectory(prefix="azure-cli-pkg-pr2-build-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        # Phase 1: Create virtual environment and install Azure CLI
        print("\n[Phase 1/4] Creating virtual environment and installing Azure CLI")
        venv_dir = tmp_dir / "bundle-venv"
        python_path = _create_virtualenv(venv_dir)
        _install_azure_cli(python_path)

        # Phase 2: Stage package root with VERSIONED paths
        print("\n[Phase 2/4] Staging package root (versioned installation)")
        pkg_root = _create_package_root(venv_dir, version=version, platform_tag=platform_tag, staging_dir=tmp_dir)

        # Phase 3: Create .pkg installer with scripts
        print("\n[Phase 3/4] Creating .pkg installer with preinstall/postinstall scripts")
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
    print("✅ AZURE CLI VERSIONED PKG INSTALLER BUILD COMPLETE (PR2)!")
    print("=" * 70)
    print(f"  Package:     {pkg_path}")
    print(f"  Size:        {pkg_path.stat().st_size / (1024*1024):.1f} MB")
    print(f"  SHA256:      {checksum_path}")
    print(f"  Platform:    {platform_tag}")
    print(f"  Version:     {version}")
    print(f"  Identifier:  {PKG_IDENTIFIER}")
    print("  Build Method: productbuild (distribution) with versioned installation")
    print()
    print("Installation Details (VERSIONED):")
    print("  Target:      /usr/local/")
    print(f"  Executable:  /usr/local/bin/{CLI_EXECUTABLE_NAME} (resolves 'current' symlink)")
    print(f"  Cleanup:     /usr/local/bin/{CLEANUP_SCRIPT_NAME}")
    print(f"  Versions:    /usr/local/{BASE_INSTALL_DIR}/{{version}}/")
    print(f"  Current:     /usr/local/{BASE_INSTALL_DIR}/current -> {version}")
    print()
    print("Key Features:")
    print("  ✓ Side-by-side version installation")
    print("  ✓ 'current' symlink points to active version")
    print("  ✓ Old versions preserved during upgrades")
    print("  ✓ Launcher resolves 'current' to find active version")
    print(f"  ✓ Cleanup utility: {CLEANUP_SCRIPT_NAME}")
    print()
    print("Next steps:")
    print("  1. Test locally: sudo installer -pkg <pkg-file> -target /")
    print("  2. Verify: az --version")
    print(f"  3. Check versions: ls -la /usr/local/{BASE_INSTALL_DIR}/")
    print(f"  4. Cleanup old versions: {CLEANUP_SCRIPT_NAME} --help")
    print("  5. Upload to GitHub releases")
    print("  6. Update Homebrew Cask (azure-cli-pr2.rb) with lifecycle hooks")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a VERSIONED .pkg installer for Azure CLI (PR2)")
    parser.add_argument(
        "--platform-tag",
        required=True,
        choices=["macos-arm64", "macos-x86_64"],
        help="Target platform architecture",
    )
    parser.add_argument(
        "--version",
        required=False,
        help="Override version (otherwise detected from azure-cli-core)",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> None:
    """Main entry point."""
    args = parse_args(argv)

    # Set VERSION environment variable if provided
    if args.version:
        os.environ["VERSION"] = args.version

    try:
        build_pkg_installer(platform_tag=args.platform_tag)
    except BuildError as exc:
        print(f"\n❌ ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
