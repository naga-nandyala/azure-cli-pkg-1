# Azure CLI macOS Cask Pipeline - Code Components & Flow

Complete reference for the macOS Homebrew Cask packaging pipeline: every file, its purpose, and how they connect.

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Pipeline Files](#2-pipeline-files)
3. [Build Scripts](#3-build-scripts)
4. [Templates](#4-templates)
5. [Phase 1: Build](#5-phase-1-build)
6. [Phase 2: Sign & Notarize](#6-phase-2-sign--notarize)
7. [Phase 3: Cask Generation & Tests](#7-phase-3-cask-generation--tests)
8. [Phase 4: Publish](#8-phase-4-publish)
9. [Artifact Flow Diagram](#9-artifact-flow-diagram)
10. [Classic Release Pipeline Integration](#10-classic-release-pipeline-integration)
11. [Legacy Homebrew Formula (Existing)](#11-legacy-homebrew-formula-existing)
12. [File Inventory](#12-file-inventory)

---

## 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        azure-pipelines.yml (main)                          │
│                                                                              │
│  ┌───────────────┐    ┌──────────────────┐    ┌──────────────────────────┐  │
│  │  Phase 1:     │───>│  Phase 2:        │───>│  Phase 3:                │  │
│  │  Build        │    │  Sign+Notarize   │    │  Cask Gen + Tests        │  │
│  │  (macOS)      │    │  (macOS+Windows) │    │  (macOS)                 │  │
│  └───────────────┘    └──────────────────┘    └──────────────────────────┘  │
│         │                     │                        │                     │
│   Unsigned tarballs    Signed+notarized          Cask definition            │
│   ARM64 + x86_64       final tarballs            + test results             │
│                        ARM64 + x86_64                                        │
└──────────────────────────────────────────────────────────────────────────────┘
                                                         │
                                                         ▼
                                              ┌──────────────────┐
                                              │  Phase 4:        │
                                              │  Publish         │
                                              │  (standalone)    │
                                              └──────────────────┘
                                              GitHub Release +
                                              Homebrew Tap Update
```

**Key design decisions:**
- **No bundled Python** — tarball contains only site-packages and native extensions; depends on Homebrew Python 3.13 at runtime.
- **Dual architecture** — ARM64 (Apple Silicon) and x86_64 (Intel) built, signed, and tested in parallel via matrix strategies.
- **ESRP signing on Windows** — Microsoft's ESRP service requires a Windows agent for the signing API calls, while macOS agents handle binary analysis and tarball creation.
- **Two install modes** — Homebrew Cask (auto-discovers Python) and offline/tarball (requires `AZ_PYTHON` env var).

---

## 2. Pipeline Files

### Main Pipeline Entry Point

| File | Lines | Purpose |
|------|-------|---------|
| `azure-pipelines.yml` | ~1241 | Main CI/CD pipeline; macOS cask templates at lines 720-748 |

The macOS cask section in `azure-pipelines.yml` consists of 3 template references:

```yaml
# Phase 1: Build unsigned tarballs (ARM64 + Intel)
- template: .azure-pipelines/templates/macos/macos-build-jobs.yml
  parameters:
    PythonVersion: $(macos_cask_python_version)
    condition: and(succeeded(), in(variables['Build.Reason'], 'IndividualCI', 'BatchedCI', 'Manual', 'Schedule'))
    dependsOn: ['ExtractMetadata']

# Phase 2: Sign and notarize via ESRP
- template: .azure-pipelines/templates/macos/macos-sign-notarize-jobs.yml
  parameters:
    BundleId: 'com.microsoft.azure.cli'
    UseCurrentPipelineArtifacts: true
    dependsOn: ['VerifyMacOSCli']

# Phase 3: Generate cask and test via temp tap
- template: .azure-pipelines/templates/macos/macos-cask-generation-and-tests.yml
  parameters:
    GitHubRepo: $(Build.Repository.Name)
    dependsOn: ['CreateFinalTarball']
```

**Trigger condition:** Same as `BuildHomebrewFormula` — runs on CI pushes, manual, and scheduled triggers (not on PR builds).

### Variables

| Variable | Value | Defined In |
|----------|-------|------------|
| `macos_cask_python_version` | `'3.13'` | `azure-pipelines.yml` (root) |
| `macos_pool` | `macos-15` | `.azure-pipelines/templates/variables.yml` |
| `macos_intel_pool` | `macos-15` | `.azure-pipelines/templates/variables.yml` |
| `macos_arm64_pool` | `macos-15-arm64` | `.azure-pipelines/templates/variables.yml` |

---

## 3. Build Scripts

### `scripts/release/macos/build_binary_tar_gz.py` (467 lines)

**The core build script.** Creates a lightweight tar.gz containing Azure CLI site-packages with pre-built native extensions.

**Build flow:**

```
┌─────────────────────┐
│ 1. get_cli_version() │  Reads __version__ from azure/cli/core/__init__.py
└─────────┬───────────┘
          ▼
┌──────────────────────────┐
│ 2. find_homebrew_python() │  Finds Homebrew Python 3.13 via well-known paths
└─────────┬────────────────┘  /opt/homebrew/opt/python@3.13 (ARM64)
          │                   /usr/local/opt/python@3.13 (Intel)
          ▼
┌──────────────────┐
│ 3. create_venv() │  Creates a venv with Homebrew Python
└─────────┬────────┘
          ▼
┌──────────────────────────┐
│ 4. install_azure_cli()   │  pip install --no-deps azure-cli, azure-cli-core,
└─────────┬────────────────┘  azure-cli-telemetry, then pinned deps from
          │                   requirements.py3.Darwin.txt
          ▼
┌────────────────────────────────┐
│ 5. create_install_structure()  │  Copies site-packages, creates launcher
└─────────┬──────────────────────┘  script, creates symlink, cleans .pyc
          ▼
┌────────────────────┐
│ 6. create_tarball() │  Creates .tar.gz + .sha256 checksum
└─────────────────────┘
```

**CLI usage:**
```bash
python build_binary_tar_gz.py --platform-tag macos-arm64 --output-dir dist/binary_tar_gz
```

**Output:** `azure-cli-{VERSION}-macos-{arch}-nopython.tar.gz`

**Tarball contents:**
```
├── bin/
│   └── az → ../libexec/bin/az          (symlink)
└── libexec/
    ├── bin/
    │   └── az                           (launcher script from az_launcher.sh.in)
    ├── lib/
    │   └── python3.13/
    │       └── site-packages/
    │           ├── azure/cli/           (azure-cli, azure-cli-core)
    │           ├── msal/                (MSAL for auth)
    │           ├── cryptography/        (native .so files)
    │           ├── cffi/                (native .so files)
    │           └── ... (all pinned dependencies)
    └── README.txt                       (from README.txt.in template)
```

### `scripts/release/macos/cask_generate.py` (92 lines)

**Generates the Homebrew cask `.rb` file** from a Jinja2-like template with simple `{{ placeholder }}` substitution.

**Inputs:** `--version`, `--arm64-sha`, `--x86-64-sha`, `--github-repo`, `--template`, `--output`

**Can also read from environment variables:** `VERSION`, `ARM64_SHA`, `X86_64_SHA`, `GITHUB_REPO`, `TEMPLATE`, `OUTPUT`

---

## 4. Templates

### `scripts/release/macos/templates/`

| File | Purpose | Placeholders |
|------|---------|--------------|
| `az_launcher.sh.in` | Entry script placed at `libexec/bin/az` | `{PYTHON_MAJOR_MINOR}`, `{PYTHON_BIN}` |
| `azure-cli.rb.in` | Homebrew cask definition template | `{{ version }}`, `{{ arm64_sha }}`, `{{ x86_64_sha }}`, `{{ github_repo }}` |
| `README.txt.in` | README placed in tarball | `{AZURE_CLI_VERSION}`, `{PLATFORM_TAG}`, `{PYTHON_MAJOR_MINOR}` |

### Launcher Script (`az_launcher.sh.in`) — Runtime Behavior

The launcher auto-detects install mode based on its own path:

```
┌──────────────────────────────────────────────┐
│           Is path under Caskroom?            │
│ /opt/homebrew/Caskroom/* or                  │
│ /usr/local/Caskroom/*                        │
├──────────┬───────────────────────────────────┤
│    YES   │              NO                   │
│          │                                   │
│ HOMEBREW │         TARBALL mode              │
│  mode    │                                   │
│          │  Requires AZ_PYTHON env var       │
│ Auto-find│  pointing to Python 3.13          │
│ Homebrew │                                   │
│ Python   │                                   │
└──────────┴───────────────────────────────────┘
                      │
                      ▼
        Sets PYTHONPATH to bundled site-packages
        Sets AZ_INSTALLER to "HOMEBREW" or "TARBALL"
        exec python -sm azure.cli "$@"
```

**Homebrew Python search order (ARM64 Mac):**
1. `/opt/homebrew/opt/python@3.13/libexec/bin/python3`
2. `/usr/local/opt/python@3.13/libexec/bin/python3`
3. `/opt/homebrew/bin/python3.13`
4. `/usr/local/bin/python3.13`

### Cask Template (`azure-cli.rb.in`)

```ruby
cask "azure-cli" do
  arch arm: "arm64", intel: "x86_64"
  os macos: "macos"

  version "{{ version }}"
  sha256 arm:   "{{ arm64_sha }}",
         intel: "{{ x86_64_sha }}"

  url "https://github.com/{{ github_repo }}/releases/download/azure-cli-#{version}/azure-cli-#{version}-#{os}-#{arch}.tar.gz"
  name "Azure CLI"
  desc "Microsoft Azure CLI 2.0"
  homepage "https://docs.microsoft.com/cli/azure/overview"

  livecheck do
    url :url
    strategy :github_latest
  end

  depends_on formula: "python@3.13"
  binary "bin/az"
  zap trash: "~/.azure"
end
```

**Key behaviors:**
- `arch arm: "arm64", intel: "x86_64"` — Homebrew auto-selects the right download URL
- `depends_on formula: "python@3.13"` — Homebrew auto-installs Python if missing
- `binary "bin/az"` — Homebrew symlinks `bin/az` to the Homebrew bin directory
- `livecheck` — enables `brew livecheck` to detect new versions via GitHub releases

---

## 5. Phase 1: Build

**Template:** `.azure-pipelines/templates/macos/macos-build-jobs.yml` (185 lines)

**Jobs:**

### Job: `BuildMacOSCli`

| Property | Value |
|----------|-------|
| Display Name | `macOS \| Build CLI` |
| Strategy | Matrix: ARM64 (`macos-15-arm64`) + Intel (`macos-15`) |
| Depends On | `ExtractMetadata` |
| Timeout | 60 minutes |

**Steps:**
1. **Install Homebrew Python** — `brew install python@3.13`
2. **Build Azure CLI Tarball** — Runs `build_binary_tar_gz.py --platform-tag macos-{arch}`
3. **Generate SBOM** — `ManifestGeneratorTask` for supply chain security
4. **Publish Artifact** — `macos-cli-build-unsigned-{arch}`

### Job: `VerifyMacOSCli`

| Property | Value |
|----------|-------|
| Display Name | `macOS \| Verify CLI` |
| Strategy | Matrix: ARM64 + Intel |
| Depends On | `BuildMacOSCli` |

**Steps:**
1. **Analyze Tarball** — Extract, count `.so` files, report sizes
2. **Verify CLI Works** — Extract, set `AZ_PYTHON` to Homebrew Python, run `az version`

---

## 6. Phase 2: Sign & Notarize

**Template:** `.azure-pipelines/templates/macos/macos-sign-notarize-jobs.yml` (750 lines)

This is the most complex phase. It runs 5 jobs in sequence, alternating between macOS agents (for Mach-O binary analysis/tarball creation) and Windows agents (for ESRP API calls).

```
macOS Agent          Windows Agent         macOS Agent          Windows Agent         macOS Agent
┌──────────┐        ┌──────────────┐      ┌─────────────────┐  ┌──────────┐         ┌────────────────┐
│ Download  │──────>│  Sign        │────>│  Create          │─>│ Notarize │───────>│ Create Final   │
│ Analyze   │       │  Binaries    │     │  Notarize Bundle │  │          │        │ Tarball        │
│           │       │  (ESRP)      │     │                  │  │  (ESRP)  │        │                │
└──────────┘        └──────────────┘      └─────────────────┘  └──────────┘         └────────────────┘
```

### Job 1: `DownloadAnalyze` (macOS)

**Purpose:** Extract unsigned tarball, identify all Mach-O binaries that need signing.

**Steps:**
1. Download unsigned build artifact
2. Extract tarball, run `file` on every file to find Mach-O binaries
3. Generate `binaries-to-sign.txt` — list of relative paths to all `.so`, `.dylib`, and Mach-O executables
4. Keep extracted contents for the signing job

**Publishes:**
- `macos-unsigned-tarball-{arch}` — original tarball (preserved for final recomposition)
- `macos-binaries-list-{arch}` — text file listing all binaries to sign
- `macos-unsigned-contents-{arch}` — extracted tarball contents

### Job 2: `SignBinaries` (Windows — ESRP)

**Purpose:** Sign each Mach-O binary with Apple Developer ID via ESRP.

**Steps:**
1. Download unsigned contents + binaries list
2. For each binary in the list:
   - Create an individual ZIP file (ESRP requires ZIP input)
   - Flatten path separators (`/` → `__`) for unique ZIP names
3. Submit all ZIPs to ESRP for signing
4. Extract signed binaries from returned ZIPs, restore original directory structure

**ESRP Configuration:**
```json
[
  {
    "KeyCode": "CP-401337-Apple",
    "OperationCode": "MacAppDeveloperSign",
    "ToolName": "sign",
    "ToolVersion": "1.0",
    "Parameters": {
      "Hardening": "--options=runtime"
    }
  }
]
```

**Publishes:** `macos-signed-binaries-{arch}` — flat directory of signed binaries

### Job 3: `CreateNotarizeBundle` (macOS)

**Purpose:** Merge signed binaries back into the tarball contents, create a ZIP for Apple notarization.

**Steps:**
1. Download unsigned tarball + signed binaries
2. Extract unsigned tarball
3. Overlay signed binaries on top (replacing unsigned originals)
4. Restore execute permissions on `.so` and `.dylib` files
5. Create a ZIP of the entire merged content (Apple requires ZIP for notarization)

**Publishes:** `macos-notarization-bundle-{arch}` — ZIP ready for Apple notarization

### Job 4: `Notarize` (Windows — ESRP)

**Purpose:** Submit ZIP to Apple's notarization service via ESRP.

**Steps:**
1. Download notarization bundle ZIP
2. Submit to ESRP with `MacAppNotarize` operation
3. ESRP handles Apple notarization workflow (upload → Apple review → ticket registration)

**ESRP Configuration:**
```json
[
  {
    "KeyCode": "CP-401337-Apple",
    "OperationCode": "MacAppNotarize",
    "ToolName": "sign",
    "ToolVersion": "1.0",
    "Parameters": {
      "BundleId": "com.microsoft.azure.cli"
    }
  }
]
```

**Publishes:** `macos-notarized-bundle-{arch}` — ZIP with Apple notarization ticket

### Job 5: `CreateFinalTarball` (macOS)

**Purpose:** Create the final production tar.gz with signed binaries and comprehensive verification.

**Steps:**
1. Download unsigned tarball + signed binaries
2. Extract unsigned tarball, overlay signed binaries
3. Verify/recreate `bin/az → ../libexec/bin/az` symlink
4. Restore execute permissions
5. Create final tarball: `azure-cli-{VERSION}-macos-{arch}.tar.gz`
6. Generate SHA256: `azure-cli-{VERSION}-macos-{arch}.tar.gz.sha256`
7. **Comprehensive verification** on every binary:
   - Basic signature check: `codesign -v`
   - Strict verification: `codesign --verify --deep --strict`
   - Developer ID check: `codesign -dvv | grep "Developer ID"`
8. **Functional test**: Extract, set `AZ_PYTHON`, run `az version`
9. Generate SBOM

**Note:** The final tarball uses a simplified name (no `-nopython` suffix):
- Unsigned: `azure-cli-{VERSION}-macos-{arch}-nopython.tar.gz`
- Final: `azure-cli-{VERSION}-macos-{arch}.tar.gz`

**Publishes:** `macos-cli-signed-notarized-{arch}` — production-ready tarball + SHA256

---

## 7. Phase 3: Cask Generation & Tests

**Template:** `.azure-pipelines/templates/macos/macos-cask-generation-and-tests.yml` (318 lines)

### Job: `TestTempTapCask` (Matrix: ARM64 + Intel)

**Purpose:** Generate the cask definition and test it via a temporary Homebrew tap using local `file://` URLs.

**Steps:**
1. Download both signed tarballs (ARM64 + Intel — cask references both)
2. Extract SHA256 checksums from `.sha256` files
3. Run `cask_generate.py` to create `azure-cli.rb` with GitHub URLs
4. Modify a copy to use `file://` URLs for local testing
5. Create a temporary Homebrew tap: `brew tap-new test/azure-cli`
6. Copy the `file://` cask into the tap's `Casks/` directory
7. `git commit` in the tap (required by Homebrew)
8. `brew install --cask test/azure-cli/azure-cli`
9. Verify: `which az`, `az --version`
10. Cleanup: uninstall cask, remove tap

**Publishes:** `macos-cask-definition` (from ARM64 job only — cask is identical for both architectures)

### Job: `TestOfflineInstall` (Matrix: ARM64 + Intel)

**Purpose:** Test that the tarball works correctly when extracted to an arbitrary directory without Homebrew Cask.

**Steps:**
1. Remove any pre-installed Azure CLI
2. Download signed tarball for current architecture
3. Extract to `~/azure-cli-test/`
4. Set `AZ_PYTHON` to Homebrew Python 3.13 path
5. Run `./bin/az version` — verifies the tarball launcher works in TARBALL mode
6. Cleanup

---

## 8. Phase 4: Publish

**Template:** `.azure-pipelines/templates/macos/macos-publish-jobs.yml` (304 lines)

This template is **not referenced from the main `azure-pipelines.yml`** — it's designed for standalone use (e.g., in a separate release pipeline or manual trigger).

### Job: `CreateGitHubRelease`

**Purpose:** Upload both architecture tarballs as GitHub release assets.

**Steps:**
1. Download both `macos-cli-signed-notarized-{arch}` artifacts
2. Copy `.tar.gz` and `.sha256` files to staging
3. Extract version number from tarball filename
4. Delete existing GitHub release if present (idempotent)
5. Create GitHub release with tag `azure-cli-{VERSION}`
6. Upload all files from staging as release assets

### Job: `UpdateHomebrewCask`

**Purpose:** Push the generated `azure-cli.rb` cask to the Homebrew tap repository.

**Steps:**
1. Checkout the `homebrewtap` repository resource (with `persistCredentials: true`)
2. Download `macos-cask-definition` artifact
3. Copy `azure-cli.rb` to `Casks/` in the tap repo
4. `git commit -m "Update azure-cli to {VERSION}"` and push

### Job: `TestPublishedCask` (optional)

**Purpose:** End-to-end verification after publishing.

**Steps:**
1. `brew tap {tap-repo}`
2. `brew install --cask azure-cli`
3. `az version`
4. `brew uninstall --cask azure-cli`

### Job: `PrintSummary`

Prints a summary banner with all artifact names and configuration.

---

## 9. Artifact Flow Diagram

```
ExtractMetadata
      │
      ▼
BuildMacOSCli (ARM64)                    BuildMacOSCli (Intel)
  → macos-cli-build-unsigned-arm64         → macos-cli-build-unsigned-x86_64
      │                                        │
      ▼                                        ▼
VerifyMacOSCli (ARM64)                   VerifyMacOSCli (Intel)
      │                                        │
      ▼                                        ▼
DownloadAnalyze (ARM64)                  DownloadAnalyze (Intel)
  → macos-unsigned-tarball-arm64           → macos-unsigned-tarball-x86_64
  → macos-binaries-list-arm64              → macos-binaries-list-x86_64
  → macos-unsigned-contents-arm64          → macos-unsigned-contents-x86_64
      │                                        │
      ▼                                        ▼
SignBinaries (ARM64) [Windows]           SignBinaries (Intel) [Windows]
  → macos-signed-binaries-arm64            → macos-signed-binaries-x86_64
      │                                        │
      ▼                                        ▼
CreateNotarizeBundle (ARM64)             CreateNotarizeBundle (Intel)
  → macos-notarization-bundle-arm64        → macos-notarization-bundle-x86_64
      │                                        │
      ▼                                        ▼
Notarize (ARM64) [Windows]              Notarize (Intel) [Windows]
  → macos-notarized-bundle-arm64           → macos-notarized-bundle-x86_64
      │                                        │
      ▼                                        ▼
CreateFinalTarball (ARM64)               CreateFinalTarball (Intel)
  → macos-cli-signed-notarized-arm64       → macos-cli-signed-notarized-x86_64
      │                                        │
      ├────────────────────────────────────────┤
      ▼                                        ▼
TestTempTapCask (ARM64)                  TestTempTapCask (Intel)
  → macos-cask-definition                   (no artifact, test only)
      │                                        │
TestOfflineInstall (ARM64)               TestOfflineInstall (Intel)
      │                                        │
      ├────────────────────────────────────────┤
      ▼
CreateGitHubRelease (publish template, standalone)
UpdateHomebrewCask  (publish template, standalone)
TestPublishedCask   (publish template, standalone)
```

### Artifact Summary

| Artifact Name | Contents | Size (approx.) |
|---------------|----------|----------------|
| `macos-cli-build-unsigned-{arch}` | Unsigned tarball + SHA256 + SBOM | ~50 MB |
| `macos-unsigned-tarball-{arch}` | Copy of unsigned tarball | ~50 MB |
| `macos-binaries-list-{arch}` | `binaries-to-sign.txt` | ~5 KB |
| `macos-unsigned-contents-{arch}` | Extracted tarball contents | ~150 MB |
| `macos-signed-binaries-{arch}` | Signed `.so`/`.dylib` files | ~20 MB |
| `macos-notarization-bundle-{arch}` | ZIP for Apple notarization | ~150 MB |
| `macos-notarized-bundle-{arch}` | ZIP with notarization ticket | ~150 MB |
| `macos-cli-signed-notarized-{arch}` | **Final production tarball** + SHA256 + SBOM | ~50 MB |
| `macos-cask-definition` | `azure-cli.rb` cask file | ~1 KB |

---

## 10. Classic Release Pipeline Integration

The existing classic release pipeline ("Azure CLI Release-Corp") handles MSI, DEB, RPM, ZIP uploads and GitHub release creation. For the macOS tarballs:

### Current State

The main build pipeline uploads artifacts via the "Upload All Artifact" stage (rank 7) to Azure Blob Storage (`azurecliprod`). The "Create Release Tag" stage (rank 17) downloads from blob storage and uploads to GitHub releases.

### What Needs to Change

The "Create Release Tag" stage needs to also download and upload the macOS tarballs:

**Blob paths:** `archive/{BuildNumber}/macos-cli-signed-notarized-arm64/azure-cli-{VERSION}-macos-arm64.tar.gz`
**and:** `archive/{BuildNumber}/macos-cli-signed-notarized-x86_64/azure-cli-{VERSION}-macos-x86_64.tar.gz`

These tarballs will be added to the GitHub release alongside the existing MSI and ZIP assets.

---

## 11. Legacy Homebrew Formula (Existing)

The legacy Homebrew formula pipeline (lines 587-718 in `azure-pipelines.yml`) uses a completely different approach:

| Aspect | Legacy Formula | New Cask |
|--------|---------------|----------|
| Install method | `brew install azure-cli` | `brew install --cask azure-cli` |
| Build approach | `brew install --build-from-source` | Pre-built tarball download |
| Python runtime | Homebrew Python (built at install time) | Homebrew Python (dependency) |
| Native extensions | Compiled on user's machine | Pre-built, signed, notarized |
| Build environment | Docker (`python:3.12-bookworm`) | macOS agents (ARM64 + Intel) |
| Install time | 15-30 minutes (compilation) | ~30 seconds (download + extract) |
| Code signing | None | Apple Developer ID + notarization |

### Legacy Pipeline Scripts

| File | Purpose |
|------|---------|
| `scripts/release/homebrew/upload.sh` | Downloads source tarball from GitHub, uploads to Azure Blob Storage |
| `scripts/release/homebrew/pipeline.sh` | Runs Docker container to generate formula from template |
| `scripts/release/homebrew/docker/run.sh` | Inside Docker: installs CLI, generates formula with pinned deps |
| `scripts/release/homebrew/docker/formula_generate.py` | Generates `azure-cli.rb` formula from template + installed deps |
| `scripts/release/homebrew/docker/formula_template.txt` | Ruby formula template with dependency placeholders |
| `scripts/release/homebrew/test_homebrew_package.sh` | Tests formula install on macOS agent |
| `scripts/release/homebrew/test_homebrew_package.py` | Python test suite for Homebrew package |

### Legacy Pipeline Flow

```
BuildPythonWheel
      │
      ▼
BuildHomebrewFormula (Docker)
  1. upload.sh → downloads source tar from GitHub, uploads to blob storage
  2. pipeline.sh → runs Docker container with run.sh
  3. Docker: pip install all CLI packages → formula_generate.py → azure-cli.rb
  → Artifact: homebrew/azure-cli.rb
      │
      ▼
TestHomebrewFormula (Docker)
  → brew install --build-from-source azure-cli.rb inside Docker
      │
      ▼
TestHomebrewPackage (macOS agent — currently disabled)
  → test_homebrew_package.sh on real macOS hardware
```

---

## 12. File Inventory

### Pipeline Templates (`.azure-pipelines/templates/macos/`)

| File | Lines | Jobs Inside |
|------|-------|-------------|
| `macos-build-jobs.yml` | 185 | `BuildMacOSCli`, `VerifyMacOSCli` |
| `macos-sign-notarize-jobs.yml` | 750 | `DownloadAnalyze`, `SignBinaries`, `CreateNotarizeBundle`, `Notarize`, `CreateFinalTarball` |
| `macos-cask-generation-and-tests.yml` | 318 | `TestTempTapCask`, `TestOfflineInstall` |
| `macos-publish-jobs.yml` | 304 | `CreateGitHubRelease`, `UpdateHomebrewCask`, `TestPublishedCask`, `PrintSummary` |

### Build Scripts (`scripts/release/macos/`)

| File | Lines | Purpose |
|------|-------|---------|
| `build_binary_tar_gz.py` | 467 | Core build: creates tar.gz with site-packages |
| `cask_generate.py` | 92 | Generates cask `.rb` from template |

### Templates (`scripts/release/macos/templates/`)

| File | Purpose |
|------|---------|
| `az_launcher.sh.in` | Launcher script (Homebrew + offline modes) |
| `azure-cli.rb.in` | Homebrew cask definition template |
| `README.txt.in` | README included in tarball |

### Legacy Homebrew Scripts (`scripts/release/homebrew/`)

| File | Purpose |
|------|---------|
| `upload.sh` | Upload source tarball to Azure Blob Storage |
| `pipeline.sh` | Run formula generation in Docker |
| `test_homebrew_package.sh` | Test formula on macOS agent |
| `test_homebrew_package.py` | Python test suite |
| `docker/run.sh` | Docker entrypoint for formula generation |
| `docker/formula_generate.py` | Generate formula `.rb` with pinned deps |
| `docker/formula_template.txt` | Ruby formula template |
| `docker/requirements.txt` | Python requirements for formula generation |

### ESRP Signing Configuration

| Parameter | Value |
|-----------|-------|
| KeyCode | `CP-401337-Apple` |
| Sign Operation | `MacAppDeveloperSign` |
| Notarize Operation | `MacAppNotarize` |
| Hardening | `--options=runtime` |
| Bundle ID | `com.microsoft.azure.cli` |
| Service Connection | `ame_esrp_connection` |
| Signing Agent | Windows (`windows-latest`) |
| What Gets Signed | All `.so`, `.dylib`, and Mach-O executables |
