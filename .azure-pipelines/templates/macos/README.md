# macOS Azure DevOps Pipeline Templates

This directory contains reusable Azure DevOps YAML job templates for building, signing, testing, and publishing Azure CLI macOS tarballs.

## Overview

The templates implement a modular pipeline design where each template covers a distinct phase of the macOS release process. They are consumed by the main pipeline files in `.azure-pipelines/`.

```
.azure-pipelines/
├── macos-standalone-release.yml          ← end-to-end pipeline (uses all 4 templates)
├── macos-tarball-build-v3.yml            ← standalone build pipeline
├── macos-tarball-sign-notarize-v3.yml    ← standalone sign/notarize pipeline
└── templates/
    └── macos/
        ├── macos-build-jobs.yml               ← Phase 1: Build
        ├── macos-sign-notarize-jobs.yml        ← Phase 2: Sign & Notarize
        ├── macos-cask-generation-and-tests.yml ← Phase 3a: Test
        └── macos-publish-jobs.yml              ← Phase 3b: Publish
```

## Pipeline Flow

```
[macos-build-jobs.yml]
  BuildMacOSCli  (ARM64 + Intel matrix)
  VerifyMacOSCli (ARM64 + Intel matrix)
         │
         ▼ artifacts: macos-cli-build-unsigned-arm64 / x86_64
[macos-sign-notarize-jobs.yml]
  DownloadAnalyze      (ARM64 + Intel matrix)
  SignBinaries         (ARM64 + Intel matrix, Windows agent for ESRP)
  CreateNotarizeBundle (ARM64 + Intel matrix)
  Notarize             (ARM64 + Intel matrix, Windows agent for ESRP)
  CreateFinalTarball   (ARM64 + Intel matrix)
         │
         ▼ artifacts: macos-cli-signed-notarized-arm64 / x86_64
[macos-cask-generation-and-tests.yml]          [macos-publish-jobs.yml]
  TestTempTapCask  (ARM64 + Intel matrix)        CreateGitHubRelease
  TestOfflineInstall (ARM64 + Intel matrix)      UpdateHomebrewCask
                                                 TestPublishedCask (optional)
                                                 PrintSummary
```

## Templates

### `macos-build-jobs.yml` — Build

Builds Azure CLI tar.gz artifacts for ARM64 and Intel using a matrix strategy. Uses Homebrew Python (no bundled Python).

**Jobs produced:**
| Job | Description |
|-----|-------------|
| `BuildMacOSCli` | Builds and stages unsigned `.tar.gz` (ARM64 + Intel) |
| `VerifyMacOSCli` | Downloads artifact and verifies CLI runs on each architecture |

**Artifacts published:**
- `macos-cli-build-unsigned-arm64`
- `macos-cli-build-unsigned-x86_64`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `PythonVersion` | string | `3.13` | Homebrew Python version used during build |
| `MacosArm64Image` | string | `macos-15-arm64` | Azure Pipelines VM image for ARM64 |
| `MacosIntelImage` | string | `macos-15` | Azure Pipelines VM image for Intel |
| `condition` | string | `succeeded()` | Job execution condition |
| `dependsOn` | object | `[]` | Jobs this template depends on |

---

### `macos-sign-notarize-jobs.yml` — Sign & Notarize

Downloads unsigned builds, signs all Mach-O binaries via ESRP (Developer ID Application certificate), notarizes the result with Apple via ESRP, and produces final signed+notarized tarballs.

**Jobs produced:**
| Job | Description |
|-----|-------------|
| `DownloadAnalyze` | Downloads unsigned artifacts and produces a list of Mach-O binaries to sign |
| `SignBinaries` | Runs ESRP signing on each binary (Windows agent, `CP-401337-Apple`) |
| `CreateNotarizeBundle` | Merges signed binaries back into the tarball and creates a notarization ZIP |
| `Notarize` | Submits the ZIP to Apple for notarization via ESRP (`MacAppNotarize`) |
| `CreateFinalTarball` | Merges signed binaries, re-packages as final `.tar.gz`, verifies signatures |

**Artifacts published:**
- `macos-cli-signed-notarized-arm64`
- `macos-cli-signed-notarized-x86_64`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `TarballBuildId` | string | `''` | Build ID to download unsigned artifacts from (standalone mode) |
| `UseCurrentPipelineArtifacts` | boolean | `false` | If `true`, downloads from the current pipeline run (integrated mode) |
| `BundleId` | string | `com.microsoft.azure.cli` | Apple bundle ID used for notarization |
| `PythonVersion` | string | `3.13` | Homebrew Python version for post-sign verification |
| `MacosArm64Image` | string | `macos-15-arm64` | Azure Pipelines VM image for ARM64 |
| `MacosIntelImage` | string | `macos-15` | Azure Pipelines VM image for Intel |
| `condition` | string | `succeeded()` | Job execution condition |
| `dependsOn` | object | `[]` | Jobs this template depends on |

> **Note:** `SignBinaries` and `Notarize` jobs run on `windows-latest` because the ESRP signing tasks require a Windows agent.

---

### `macos-cask-generation-and-tests.yml` — Cask Generation & Tests

Generates a Homebrew cask definition from the signed tarballs and runs two independent test suites:

1. **Temp-tap test** — Creates a temporary local Homebrew tap with `file://` URLs pointing to the pipeline artifacts and installs the cask, verifying end-to-end Homebrew installation.
2. **Offline install test** — Extracts the tarball directly and runs `az version` to confirm the CLI works without Homebrew.

**Jobs produced:**
| Job | Description |
|-----|-------------|
| `TestTempTapCask` | Generates cask, installs via a temporary tap (`file://` URLs), verifies `az version` |
| `TestOfflineInstall` | Extracts tarball directly, runs `az version` without Homebrew |

**Artifacts published:**
- `macos-cask-definition` — contains `azure-cli.rb` with production GitHub release URLs (published from ARM64 job only)

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `MacosArm64Image` | string | `macos-15-arm64` | Azure Pipelines VM image for ARM64 |
| `MacosIntelImage` | string | `macos-15` | Azure Pipelines VM image for Intel |
| `PythonVersion` | string | `3.13` | Homebrew Python version for testing |
| `GitHubRepo` | string | `placeholder/repo` | GitHub repository (`owner/repo`) used in generated cask URLs |
| `Debug` | boolean | `false` | Enable additional diagnostic output |
| `condition` | string | `succeeded()` | Job execution condition |
| `dependsOn` | object | `['CreateFinalTarball']` | Jobs this template depends on |

---

### `macos-publish-jobs.yml` — Publish

Publishes the signed+notarized artifacts to a GitHub release and updates the Homebrew tap cask. Optionally runs a post-publish installation test.

**Jobs produced:**
| Job | Condition | Description |
|-----|-----------|-------------|
| `CreateGitHubRelease` | `PublishToGitHub: true` | Creates (or replaces) a GitHub release with both architecture tarballs |
| `UpdateHomebrewCask` | `UpdateHomebrew: true` | Pushes the generated `azure-cli.rb` cask to the Homebrew tap repository |
| `TestPublishedCask` | `TestAfterPublish: true` and `UpdateHomebrew: true` | Installs the published cask from the tap and verifies it |
| `PrintSummary` | always | Prints a summary banner |

**Artifacts consumed:**
- `macos-cli-signed-notarized-arm64`
- `macos-cli-signed-notarized-x86_64`
- `macos-cask-definition`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `PublishToGitHub` | boolean | `true` | Create a GitHub release |
| `UpdateHomebrew` | boolean | `true` | Push updated cask to Homebrew tap |
| `TestAfterPublish` | boolean | `true` | Run cask installation test after publishing |
| `GitHubRepo` | string | `''` | GitHub repository for the release (`owner/repo`) |
| `HomebrewTapRepo` | string | `''` | Homebrew tap repository name |
| `MacosArm64Image` | string | `macos-15-arm64` | Azure Pipelines VM image for ARM64 |
| `MacosIntelImage` | string | `macos-15` | Azure Pipelines VM image for Intel |
| `PythonVersion` | string | `3.13` | Homebrew Python version for post-publish testing |
| `Debug` | boolean | `false` | Enable additional diagnostic output |
| `condition` | string | `succeeded()` | Job execution condition |
| `dependsOn` | object | `['TestTempTapCask', 'TestOfflineInstall']` | Jobs this template depends on |

---

## Prerequisites

Before running any pipeline that uses these templates:

1. **Azure DevOps service connection** — A GitHub service connection must exist in your Azure DevOps project. The pipeline files reference `github.com_naga-nandyala` by default; update this name to match your own service connection.
2. **ESRP variable group** — A variable group named `AME ESRP Variable Group` must be linked to the pipeline and must contain:
   - `ESRPAppClientId`
   - `ESRPAppTenantId`
   - `ESRPKVName`
   - `ESRPAuthCertName`
   - `ESRPSignCertName`
3. **Homebrew tap repository** — Required when `UpdateHomebrew: true`. The pipeline uses a repository resource named `homebrewtap` pointing to the Homebrew tap.
4. **`ManifestGeneratorTask`** — The Azure Artifacts SBOM manifest generator extension must be installed in your Azure DevOps organization.

See [../../docs/AZURE-DEVOPS-SETUP.md](../../docs/AZURE-DEVOPS-SETUP.md) for step-by-step Azure DevOps setup instructions.

## Usage

### End-to-End Release (recommended)

Use `macos-standalone-release.yml` to run all phases in a single pipeline run:

```yaml
# Run manually from Azure DevOps → Pipelines → Run Pipeline
# File: .azure-pipelines/macos-standalone-release.yml
```

Key parameters:

| Parameter | Description |
|-----------|-------------|
| `PythonVersion` | Homebrew Python version (default: `3.13`) |
| `BundleId` | Apple bundle ID (default: `com.microsoft.azure.cli`) |
| `PublishToGitHub` | Create GitHub release |
| `GitHubRepo` | Target GitHub repository (`owner/repo`) |
| `UpdateHomebrew` | Update Homebrew tap cask |
| `HomebrewTapRepo` | Homebrew tap repository name |

### Standalone Build Only

Use `macos-tarball-build-v3.yml` to produce unsigned tarballs independently. The build ID printed in the summary can be passed to the sign/notarize pipeline.

### Reusing Templates in Your Own Pipeline

```yaml
jobs:
- template: templates/macos/macos-build-jobs.yml
  parameters:
    PythonVersion: '3.13'
    MacosArm64Image: 'macos-15-arm64'
    MacosIntelImage: 'macos-15'

- template: templates/macos/macos-sign-notarize-jobs.yml
  parameters:
    UseCurrentPipelineArtifacts: true
    BundleId: 'com.microsoft.azure.cli'
    dependsOn:
    - VerifyMacOSCli
```

## Artifact Reference

| Artifact name | Produced by | Consumed by |
|---------------|-------------|-------------|
| `macos-cli-build-unsigned-arm64` | `macos-build-jobs.yml` | `macos-sign-notarize-jobs.yml` |
| `macos-cli-build-unsigned-x86_64` | `macos-build-jobs.yml` | `macos-sign-notarize-jobs.yml` |
| `macos-unsigned-tarball-<arch>` | `macos-sign-notarize-jobs.yml` (DownloadAnalyze) | CreateNotarizeBundle, CreateFinalTarball |
| `macos-unsigned-contents-<arch>` | `macos-sign-notarize-jobs.yml` (DownloadAnalyze) | SignBinaries |
| `macos-binaries-list-<arch>` | `macos-sign-notarize-jobs.yml` (DownloadAnalyze) | SignBinaries |
| `macos-signed-binaries-<arch>` | `macos-sign-notarize-jobs.yml` (SignBinaries) | CreateNotarizeBundle, CreateFinalTarball |
| `macos-notarization-bundle-<arch>` | `macos-sign-notarize-jobs.yml` (CreateNotarizeBundle) | Notarize |
| `macos-notarized-bundle-<arch>` | `macos-sign-notarize-jobs.yml` (Notarize) | (informational) |
| `macos-cli-signed-notarized-arm64` | `macos-sign-notarize-jobs.yml` (CreateFinalTarball) | `macos-cask-generation-and-tests.yml`, `macos-publish-jobs.yml` |
| `macos-cli-signed-notarized-x86_64` | `macos-sign-notarize-jobs.yml` (CreateFinalTarball) | `macos-cask-generation-and-tests.yml`, `macos-publish-jobs.yml` |
| `macos-cask-definition` | `macos-cask-generation-and-tests.yml` (TestTempTapCask) | `macos-publish-jobs.yml` |
