#!/usr/bin/env python3
"""Build self-contained binary tar.gz using the official Python.org framework.

This variant mirrors build_binary_tar_gz.py but replaces the python-build-standalone
runtime with a relocatable Python.framework extracted directly from python.org.
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

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_ROOT / "src"
AZURE_CLI_PACKAGE_DIR = SRC_DIR / "azure-cli"
AZURE_CLI_CORE_DIR = SRC_DIR / "azure-cli-core"

APP_NAME = "azure-cli"
CLI_EXECUTABLE_NAME = "az"

PYTHON_VERSION = "3.13.1"
PYTHON_MAJOR_MINOR = ".".join(PYTHON_VERSION.split(".")[:2])
PYTHON_MAC_PKG_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-macos11.pkg"


class BuildError(RuntimeError):
    """Raised when the packaging pipeline fails."""


def _run(
    cmd: Iterable[str], *, env: Optional[dict[str, str]] = None, capture_output: bool = False
) -> subprocess.CompletedProcess:
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
    env_version = os.environ.get("VERSION")
    if env_version and env_version.strip():
        print(f"Using version from environment: {env_version}")
        return env_version.strip()

    init_path = AZURE_CLI_CORE_DIR / "azure" / "cli" / "core" / "__init__.py"
    try:
        source = init_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BuildError(f"Could not find version file: {init_path}") from exc

    match = re.search(r"__version__\s*=\s*[\'\"](.+?)[\'\"]", source)
    if not match:
        raise BuildError(f"Could not parse version from {init_path}")

    version = match.group(1)
    print(f"Using version from azure-cli-core: {version}")
    return version


def _ensure_clean(paths: Iterable[Path]) -> None:
    for path in paths:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
                print(f"Removed directory: {path}")
            else:
                path.unlink()
                print(f"Removed file: {path}")


def _remove_dot_underscore_files(root: Path) -> None:
    for entry in root.rglob("._*"):
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)


def _is_macho(file_path: Path) -> bool:
    try:
        result = subprocess.run(["file", str(file_path)], capture_output=True, text=True, check=False)
        return "Mach-O" in result.stdout
    except Exception:
        return False


def _sign_python_framework(framework_dir: Path) -> None:
    print("Signing Python.framework binaries...")
    for entry in framework_dir.rglob("*"):
        if entry.name.startswith("._"):
            continue
        if entry.is_symlink() or not entry.is_file():
            continue
        if _is_macho(entry):
            _run(["codesign", "--force", "--sign", "-", str(entry)])
    _run(["codesign", "--force", "--sign", "-", str(framework_dir)])


def _prepare_python_framework(staging_dir: Path) -> Path:
    pkg_path = staging_dir / "python.pkg"
    print(f"Downloading official Python {PYTHON_VERSION} package...")
    urllib.request.urlretrieve(PYTHON_MAC_PKG_URL, pkg_path)

    expanded_dir = staging_dir / "python_pkg"
    _ensure_clean([expanded_dir])
    print("Expanding pkg...")
    _run(["pkgutil", "--expand", str(pkg_path), str(expanded_dir)])

    framework_pkg = expanded_dir / "Python_Framework.pkg"
    payload = framework_pkg / "Payload"

    framework_dir = staging_dir / "Python.framework"
    _ensure_clean([framework_dir])
    framework_dir.mkdir(parents=True, exist_ok=True)
    print("Extracting Payload...")
    _run(
        [
            "sh",
            "-c",
            f"cd {framework_dir} && gunzip -c {payload} | cpio -id",
        ]
    )

    print(f"Extracted Python.framework to {framework_dir}")
    _remove_dot_underscore_files(framework_dir)

    python_dylib = framework_dir / f"Versions/{PYTHON_MAJOR_MINOR}/Python"
    _run(
        [
            "install_name_tool",
            "-id",
            f"@rpath/Python.framework/Versions/{PYTHON_MAJOR_MINOR}/Python",
            str(python_dylib),
        ]
    )

    _sign_python_framework(framework_dir)
    return framework_dir


def _verify_host_architecture(platform_tag: str) -> None:
    host_arch = subprocess.check_output(["uname", "-m"], text=True).strip().lower()
    target_is_arm = "arm64" in platform_tag
    if host_arch == "x86_64" and target_is_arm:
        raise BuildError(
            "Cannot build macos-arm64 artifacts on an Intel (x86_64) host.\n"
            "Use an Apple Silicon runner for ARM builds."
        )


def _link_runtime_dirs(runtime_root: Path) -> None:
    rel_base = Path("Python.framework") / "Versions" / PYTHON_MAJOR_MINOR
    for name in ("lib", "include", "Resources", "share"):
        dest = runtime_root / name
        _ensure_clean([dest])
        dest.symlink_to(rel_base / name)


def _prepare_python_runtime(runtime_root: Path, staging_dir: Path, platform_tag: str) -> Path:
    _verify_host_architecture(platform_tag)
    _ensure_clean([runtime_root])
    runtime_root.mkdir(parents=True, exist_ok=True)

    framework_dir = _prepare_python_framework(staging_dir)
    local_framework = runtime_root / "Python.framework"
    print(f"Copying Python.framework to {local_framework}")
    shutil.copytree(framework_dir, local_framework, symlinks=True)

    bin_src = local_framework / f"Versions/{PYTHON_MAJOR_MINOR}/bin"
    bin_dest = runtime_root / "bin"
    _ensure_clean([bin_dest])
    shutil.copytree(bin_src, bin_dest, symlinks=True)

    _link_runtime_dirs(runtime_root)

    python_path = bin_dest / "python3"
    if not python_path.exists():
        raise BuildError(f"python3 executable not found at {python_path}")

    return python_path


def _python_env(runtime_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    framework_root = runtime_root / "Python.framework"
    framework_version_dir = framework_root / "Versions" / PYTHON_MAJOR_MINOR

    env["PYTHONHOME"] = str(framework_version_dir)
    env["PATH"] = f"{runtime_root / 'bin'}:{env.get('PATH', '')}"

    # Ensure the embedded interpreter loads the bundled framework instead of a system-wide install.
    env["DYLD_FRAMEWORK_PATH"] = str(runtime_root)
    lib_dir = framework_version_dir / "lib"
    existing_dyld = env.get("DYLD_LIBRARY_PATH", "")
    env["DYLD_LIBRARY_PATH"] = f"{lib_dir}:{existing_dyld}" if existing_dyld else str(lib_dir)
    return env


def _ensure_pip(python_path: Path, runtime_root: Path) -> None:
    env = _python_env(runtime_root)
    _run([str(python_path), "-m", "ensurepip", "--upgrade"], env=env)
    _run([str(python_path), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], env=env)


def _install_azure_cli(python_path: Path, runtime_root: Path) -> None:
    print("Installing Azure CLI components into Python.framework runtime...")
    env = _python_env(runtime_root)
    components = [
        SRC_DIR / "azure-cli-telemetry",
        SRC_DIR / "azure-cli-core",
        SRC_DIR / "azure-cli",
    ]
    for component in components:
        if not component.exists():
            raise BuildError(f"Component not found: {component}")
        print(f"Installing {component.name}...")
        _run([str(python_path), "-m", "pip", "install", str(component)], env=env)

    print("Verifying Azure CLI installation...")
    result = _run([str(python_path), "-m", "azure.cli", "--version"], env=env, capture_output=True)
    print(f"Installed Azure CLI version:\n{result.stdout}")


def _prune_bytecode(root: Path) -> None:
    for suffix in (".pyc", ".pyo"):
        for path in root.rglob(f"*{suffix}"):
            path.unlink()
    for path in sorted(root.rglob("__pycache__"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                shutil.rmtree(path)


def _create_launcher_script(runtime_root: Path) -> None:
    launcher = f"""#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(readlink -f "${{BASH_SOURCE[0]}}" 2>/dev/null || greadlink -f "${{BASH_SOURCE[0]}}" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "${{BASH_SOURCE[0]}}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
RUNTIME_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONHOME="$RUNTIME_DIR/Python.framework/Versions/{PYTHON_MAJOR_MINOR}"
export DYLD_FRAMEWORK_PATH="$RUNTIME_DIR"
export DYLD_LIBRARY_PATH="$RUNTIME_DIR/Python.framework/Versions/{PYTHON_MAJOR_MINOR}/lib:${{DYLD_LIBRARY_PATH:-}}"
export AZ_INSTALLER=HOMEBREW_FORMULA
exec "$RUNTIME_DIR/bin/python3" -m azure.cli "$@"
"""
    az_path = runtime_root / "bin" / CLI_EXECUTABLE_NAME
    az_path.write_text(launcher, encoding="utf-8")
    az_path.chmod(0o755)
    print(f"Created launcher script: {az_path}")


def _create_readme(runtime_root: Path, version: str, platform_tag: str) -> None:
    content = f"""Azure CLI {version} - Official Python.org Runtime
{'=' * 70}

This package bundles the signed Python {PYTHON_VERSION} framework from python.org
alongside Azure CLI and all dependencies. It is intended for Homebrew-style binary
distribution where the CLI is executed from a relocatable libexec directory.

Platform: {platform_tag}
Python: {PYTHON_VERSION} (Python.org macOS installer)
"""
    readme_path = runtime_root / "README.txt"
    readme_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Created README: {readme_path}")


def _create_binary_tar_gz(runtime_root: Path, version: str, platform_tag: str, artifacts_dir: Path) -> Path:
    archive_name = f"{APP_NAME}-{version}-{platform_tag}.tar.gz"
    archive_path = artifacts_dir / archive_name
    _ensure_clean([archive_path])

    temp_dir = artifacts_dir / f"temp_{archive_name}"
    _ensure_clean([temp_dir])
    temp_dir.mkdir(parents=True)

    libexec_dir = temp_dir / "libexec"
    libexec_dir.mkdir()
    for item in runtime_root.iterdir():
        shutil.move(str(item), str(libexec_dir / item.name))
        print(f"Moved {item.name} → libexec/{item.name}")

    bin_dir = temp_dir / "bin"
    bin_dir.mkdir()
    az_symlink = bin_dir / "az"
    az_symlink.symlink_to("../libexec/bin/az")
    print("Created bin/az symlink → ../libexec/bin/az")

    with tarfile.open(archive_path, "w:gz") as tar:
        for item in temp_dir.iterdir():
            tar.add(item, arcname=item.name, recursive=True)
            print(f"Added to archive: {item.name}")

    shutil.rmtree(temp_dir)

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"Archive created: {archive_path} ({size_mb:.1f} MB)")
    return archive_path


def _emit_sha256(archive_path: Path) -> Path:
    digest = hashlib.sha256()
    with archive_path.open("rb") as fh:
        while chunk := fh.read(8192):
            digest.update(chunk)
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    checksum_line = f"{digest.hexdigest()}  {archive_path.name}\n"
    checksum_path.write_text(checksum_line, encoding="utf-8")
    print(f"SHA256: {checksum_line.strip()}")
    return checksum_path


def build_binary_tar_gz_python_org(*, platform_tag: str) -> None:
    version = _detect_version()
    artifacts_dir = PROJECT_ROOT / "dist" / "binary_tar_gz_python_org"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"Building Azure CLI {version} (Python.org runtime) - {platform_tag}")
    print("=" * 70)

    with tempfile.TemporaryDirectory(prefix="azure-cli-pythonorg-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        staging_dir = tmp_dir / "staging"
        staging_dir.mkdir()
        runtime_root = tmp_dir / "runtime"
        runtime_root.mkdir()

        print("\n1. Preparing Python runtime...")
        python_path = _prepare_python_runtime(runtime_root, staging_dir, platform_tag)
        _ensure_pip(python_path, runtime_root)

        print("\n2. Installing Azure CLI components...")
        _install_azure_cli(python_path, runtime_root)

        print("\n3. Creating launcher and documentation...")
        _create_launcher_script(runtime_root)
        _create_readme(runtime_root, version, platform_tag)

        print("\n4. Pruning bytecode...")
        _prune_bytecode(runtime_root)

        print("\n5. Creating tar.gz archive...")
        archive_path = _create_binary_tar_gz(runtime_root, version, platform_tag, artifacts_dir)
        checksum_path = _emit_sha256(archive_path)

    print("\n" + "=" * 70)
    print("✅ PYTHON.ORG BINARY TAR.GZ BUILD COMPLETE!")
    print("=" * 70)
    print(f"  Archive:  {archive_path}")
    print(f"  SHA256:   {checksum_path}")
    print(f"  Platform: {platform_tag}")
    print(f"  Version:  {version}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build binary tar.gz using Python.org runtime")
    parser.add_argument(
        "--platform-tag",
        required=True,
        choices=["macos-arm64", "macos-x86_64"],
        help="Target platform architecture",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    try:
        build_binary_tar_gz_python_org(platform_tag=args.platform_tag)
    except BuildError as exc:
        print(f"\n❌ ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
