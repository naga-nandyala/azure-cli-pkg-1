# macOS PKG Pipeline Documentation

## Overview
This document describes the complete Azure DevOps pipeline system for building, signing, notarizing, and distributing Azure CLI macOS PKG installers.

---

## Pipeline Architecture

### Complete Production Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MACOS PKG DISTRIBUTION PIPELINE                   │
└─────────────────────────────────────────────────────────────────────┘

1. BUILD
   ├─► macos-pkg-build.yml
   │   └─► Output: Unsigned PKG (ARM64 + x86_64)
   │
2. SIGN ALL BINARIES
   ├─► macos-pkg-sign-all.yml
   │   ├─► Extract all binaries from PKG
   │   ├─► Sign Python executables, libraries, frameworks
   │   ├─► Repack PKG with signed binaries
   │   └─► Sign PKG wrapper itself
   │   └─► Output: Fully signed PKG
   │
3. NOTARIZE WITH APPLE
   ├─► macos-pkg-notarize.yml
   │   ├─► Submit to Apple notarization service
   │   ├─► Wait for Apple approval
   │   ├─► Staple notarization ticket to PKG
   │   └─► Output: Notarized + Stapled PKG
   │
4. PUBLISH TO GITHUB
   ├─► macos-pkg-github-release-publish.yml
   │   ├─► Create GitHub release
   │   ├─► Upload PKG files as assets
   │   └─► Output: Public release on GitHub
   │
5. UPDATE HOMEBREW FORMULA
   ├─► macos-pkg-homebrew-update.yml
   │   ├─► Generate Homebrew formula
   │   ├─► Calculate SHA256 checksums
   │   ├─► Commit directly to homebrew tap
   │   └─► Output: Updated formula in tap repo
   │
6. VALIDATION & TESTING
   └─► macos-pkg-install-test.yml
       ├─► Test Homebrew installation
       ├─► Test offline PKG installation
       ├─► Run formula audit
       └─► Output: Validation report
```

---

## Pipeline Details

### 1. **macos-pkg-build.yml** 📦 BUILD PIPELINE

**Purpose:** Build unsigned PKG installers for macOS (ARM64 and x86_64)

**Input:**
- Azure CLI source code
- Python 3.12 runtime
- Build scripts

**Process:**
1. Set up Python 3.12 environment on macOS-14 (Apple Silicon) and macOS-13 (Intel)
2. Build Azure CLI from source
3. Create PKG installer structure
4. Package into unsigned PKG files (no code signing yet)

**Output:**
- `azure-cli-{version}-macos-arm64.pkg` (unsigned)
- `azure-cli-{version}-macos-x86_64.pkg` (unsigned)
- Published as build artifacts: `pkg-installer-macos-arm64`, `pkg-installer-macos-x86_64`

**Parameters:**
- `Version`: Azure CLI version (e.g., 2.0.0)
- `CreateGitHubRelease`: Optional GitHub release creation (rarely used)
- `Prerelease`: Mark as pre-release flag
- `GitHubRepo`: Target GitHub repository

**Trigger:** Manual only

**Lines:** 735 | **Size:** 27 KB

---

### 2. **macos-pkg-sign-all.yml** ✍️ COMPREHENSIVE SIGNING PIPELINE

**Purpose:** Extract all binaries from PKG, sign everything with ESRP, repack and sign PKG

**Input:**
- Unsigned PKG from `macos-pkg-build.yml` (via SourceBuildId parameter)

**Process:**
1. **Download** unsigned PKG from build artifacts
2. **Extract** PKG contents:
   - Expand PKG using `pkgutil --expand`
   - Extract Payload using `tar -xzf`
3. **Sign ALL binaries** with ESRP:
   - Python executables (`bin/python3`, `bin/az`)
   - Python libraries (`.dylib`, `.so` files)
   - Frameworks and bundles
   - All `.py` files that need signing
4. **Repack PKG**:
   - Compress signed payload back to `Payload.gz`
   - Rebuild PKG structure
   - Flatten back to single PKG file
5. **Sign PKG wrapper** itself with ESRP

**Output:**
- `azure-cli-{version}-macos-arm64-signed.pkg`
- Published as artifact: `signed-macos-pkg`

**Authentication:**
- Uses ESRP Variable Group: `AME ESRP Variable Group`
- ESRP task: `EsrpCodeSigning@5`
- KeyCode: `CP-401337-Apple`
- Operation: `MacAppDeveloperSign`

**Parameters:**
- `SourceBuildId`: Build ID of the unsigned PKG pipeline
- `SourcePipelineName`: Pipeline name (default: `naga_macos_build`)
- `AzureCliVersion`: Version number
- `BundleId`: Bundle ID for signing (default: `com.microsoft.azure.cli`)
- `OfficialBuild`: Enable ESRP signing (true/false)

**Why This is Critical:**
- Apple notarization requires ALL binaries to be signed
- Signing only the PKG wrapper is insufficient
- This pipeline ensures complete code signing compliance

**Trigger:** Manual only

**Lines:** 806 | **Size:** 28 KB

---

### 3. **macos-pkg-notarize.yml** 🍎 APPLE NOTARIZATION PIPELINE

**Purpose:** Submit signed PKG to Apple for notarization and staple the ticket

**Input:**
- Fully signed PKG from `macos-pkg-sign-all.yml` (via SourceBuildId parameter)

**Process:**
1. **Download** signed PKG from previous build
2. **Submit to Apple Notarization Service**:
   - Uses ESRP notarization task
   - Sends PKG to Apple for malware scanning
   - Waits for Apple approval (can take 5-30 minutes)
3. **Retrieve notarization ticket** from Apple
4. **Staple ticket** to PKG:
   - Embeds the notarization proof into PKG
   - Allows offline verification without internet
5. **Verify stapling** worked correctly

**Output:**
- `azure-cli-{version}-macos-arm64-notarized.pkg` (stapled)
- Published as artifact: `stapled-macos-pkg`

**Authentication:**
- Uses ESRP Variable Group: `AME ESRP Variable Group`
- ESRP notarization credentials

**Parameters:**
- `SourceBuildId`: Build ID of the signing pipeline
- `SourcePipelineName`: Pipeline name (default: `macos-pkg-sign-all`)
- `AzureCliVersion`: Version number
- `BundleId`: Bundle ID (default: `com.microsoft.azure.cli`)
- `OfficialBuild`: Enable ESRP notarization

**Why Notarization is Required:**
- macOS Gatekeeper blocks unsigned/non-notarized software
- Users would get "unidentified developer" warnings without this
- Required for distribution outside Mac App Store

**Trigger:** Manual only

**Lines:** 563 | **Size:** 20.8 KB

---

### 4. **macos-pkg-github-release-publish.yml** 🚀 GITHUB RELEASE PIPELINE

**Purpose:** Publish GitHub release with notarized PKG files and release notes

**Input:**
- Notarized + stapled PKG from `macos-pkg-notarize.yml` build artifacts

**Process:**
1. **Download artifacts** from notarization build
2. **Create GitHub release** using `GitHubRelease@1` task
3. **Upload PKG files** as release assets
4. **Add release notes** and changelog
5. **Tag release** with version

**Output:**
- GitHub release at: `https://github.com/{repo}/releases/tag/v{version}`
- PKG files available as downloadable assets

**Authentication:**
- Uses GitHub service connection: `github.com_naga-nandyala`
- OAuth-based authentication (no PAT needed)

**Parameters:**
- `NotarizationBuildId`: Build ID of notarization pipeline
- `NotarizationPipelineName`: Pipeline name (default: `macos-pkg-notarize`)
- `AzureCliVersion`: Version number
- `GitHubRepo`: Target repository (default: `naga-nandyala/azure-cli-pkg-1`)
- `ReleaseTag`: Git tag (default: `v{version}`)
- `IsPrerelease`: Mark as pre-release

**Stages:**
1. **DownloadArtifacts**: Get notarized PKG from build artifacts
2. **CreateGitHubRelease**: Publish to GitHub using service connection
3. **Summary**: Display release information

**Key Features:**
- Uses `GitHubRelease@1` task (built-in Azure task)
- Automatically uses service connection token
- No manual PAT management needed
- Publishes release notes from repository

**Status:** ✅ PRODUCTION - Successfully published v2.0.0

**Trigger:** Manual only

**Lines:** 273 | **Size:** 8.9 KB

---

### 5. **macos-pkg-homebrew-update.yml** 🍺 HOMEBREW FORMULA UPDATE PIPELINE

**Purpose:** Generate Homebrew formula and commit directly to tap repository

**Input:**
- Notarized PKG from GitHub release

**Process:**
1. **Download stapled PKG** from build artifacts
2. **Calculate SHA256 checksum** of PKG file
3. **Generate Homebrew formula** (Ruby DSL):
   ```ruby
   class AzureCliPr < Formula
     desc "Microsoft Azure CLI - Official command-line interface"
     homepage "https://learn.microsoft.com/cli/azure/"
     url "https://github.com/.../azure-cli-{version}-macos-arm64-notarized.pkg"
     sha256 "..."
     
     def install
       system "pkgutil", "--expand", cached_download, buildpath/"azure-cli.unpkg"
       payload = Dir[buildpath/"azure-cli.unpkg"/"*.pkg"].first
       system "tar", "-xzf", "#{payload}/Payload", "-C", prefix
       bin.install_symlink prefix/"usr/local/bin/az"
     end
     
     test do
       system "#{bin}/az", "--version"
     end
   end
   ```
4. **Checkout Homebrew tap** repository
5. **Commit formula** directly to main branch
6. **Push changes** to GitHub

**Output:**
- Updated formula file in `naga-nandyala/homebrew-mycli-app`
- Committed directly to main (no PR)

**Authentication:**
- Uses repository resources with service connection token
- Token accessed via: `$(resources.repositories['homebrewtap'].token)`

**Parameters:**
- `NotarizationBuildId`: Build ID of notarization pipeline
- `AzureCliVersion`: Version number
- `GitHubRepo`: Main repository
- `HomebrewTapRepo`: Tap repository (default: `naga-nandyala/homebrew-mycli-app`)
- `FormulaName`: Formula class name (default: `azure-cli-pr`)

**Stages:**
1. **DownloadStapledPkg**: Get notarized PKG
2. **GenerateFormula**: Create Ruby formula file
3. **CommitToHomebrew**: Push directly to tap main branch
4. **Summary**: Display completion status

**Formula Style Guidelines Applied:**
- ✅ Field order: `desc` → `homepage` → `url` → `sha256`
- ✅ No redundant `version` line (detected from URL)
- ✅ No deprecated `bottle :unneeded`
- ✅ No problematic `caveats` method
- ✅ Passes `brew audit --formula`

**Key Improvements from Earlier Versions:**
- Changed from PR creation to direct commit workflow
- Fixed detached HEAD issue with `git checkout -B main origin/main`
- Fixed formula style to pass brew audit
- Uses printf for file generation (avoids YAML heredoc issues)

**Status:** ✅ PRODUCTION - Formula passes audit

**Trigger:** Manual only

**Lines:** 310 | **Size:** 10.8 KB

---

### 6. **macos-pkg-install-test.yml** ✅ VALIDATION & TESTING PIPELINE

**Purpose:** Comprehensive testing of Homebrew formula and offline PKG installation

**Input:**
- Published GitHub release with PKG
- Published Homebrew formula in tap

**Process:**

**Stage 1: TestHomebrewFormula** (Parallel Jobs)
- **Job 1: TestOnMacOS** (Homebrew installation)
  1. Tap the Homebrew repository
  2. Install formula: `brew install azure-cli-pr`
  3. Verify `az` command works
  4. Test basic commands: `--help`, `version`, `extension list`
  5. **Cleanup**: `brew uninstall azure-cli-pr; brew untap`
  
- **Job 2: TestOfflineInstall** (Direct PKG installation)
  1. Download PKG from GitHub release
  2. Verify HTTP status code (must be 200)
  3. Verify file size (must be > 1MB)
  4. Verify signature: `pkgutil --check-signature`
  5. Verify notarization: `spctl -a -vv -t install`
  6. Install: `sudo installer -pkg azure-cli.pkg -target /`
  7. Verify `az` command works
  8. Test basic commands
  9. **Cleanup**: `sudo rm -f /usr/local/bin/az; sudo rm -rf /usr/local/az`

**Stage 2: TestFormulaValidation**
1. Run `brew audit --formula azure-cli-pr`
2. Show `brew info azure-cli-pr`
3. Show `brew cat azure-cli-pr`
4. Test `brew fetch` (dry run)

**Stage 3: TestSummary**
- Display comprehensive test results
- Show installation instructions for end users
- Always runs (even if tests fail)

**Output:**
- Validation report with pass/fail status
- User installation instructions

**Parameters:**
- `AzureCliVersion`: Version to test (default: 2.0.0)
- `HomebrewTapRepo`: Tap repository
- `FormulaName`: Formula name (default: azure-cli-pr)
- `GitHubRepo`: Main repository
- `ReleaseTag`: Release tag (default: v2.0.0)

**Key Features:**
- ✅ Parallel execution (Homebrew + PKG tests run simultaneously)
- ✅ Complete cleanup after each test
- ✅ Security verification (signature + notarization)
- ✅ File integrity checks
- ✅ Formula style validation

**Status:** ✅ ALL TESTS PASSING

**Trigger:** Manual only

**Lines:** 488 | **Size:** 14.4 KB

---

## Verification Pipelines (Optional/Testing)

### 7. **macos-pkg-sig-verify.yml** 🔍 SIGNATURE VERIFICATION PIPELINE

**Purpose:** Download and verify PKG signature at all levels (for testing)

**Input:**
- PKG file URL (can be any public PKG)

**Process:**
1. Download PKG from URL
2. Verify PKG signature: `pkgutil --check-signature`
3. Extract and verify all internal binary signatures
4. Report signature chain and certificate details

**Use Case:**
- Testing signature validity
- Debugging signing issues
- Comparing signature chains

**Trigger:** Manual only

**Lines:** 290 | **Size:** 13.2 KB

---

### 8. **macos-pkg-notarize-verify.yml** ✓ NOTARIZATION VERIFICATION PIPELINE

**Purpose:** Verify that a PKG has been properly notarized by Apple

**Input:**
- Notarized PKG from build artifacts (via SourceBuildId)

**Process:**
1. Download notarized PKG
2. Verify signature: `pkgutil --check-signature`
3. Verify notarization: `spctl -a -vv -t install`
4. Verify stapling: `stapler validate`
5. Check bundle ID matches expected value
6. Report detailed verification results

**Output:**
- Verification report with pass/fail status
- Certificate chain details
- Notarization status

**Parameters:**
- `SourceBuildId`: Build ID of notarization pipeline
- `SourcePipelineName`: Pipeline name
- `AzureCliVersion`: Version
- `ExpectedBundleId`: Expected bundle ID

**Use Case:**
- Validate notarization succeeded
- Verify stapling is correct
- Pre-release validation

**Trigger:** Manual only

**Lines:** 583 | **Size:** 20.3 KB

---

## Archived Pipelines

The following pipelines were experimental or alternative approaches and have been archived to `.azure-pipelines/_archive/`:

1. **macos-pkg-sign.yml** - Simple PKG signing using OneBranch (wrapper only, no binary signing)
2. **macos-pkg-sign-release.yml** - Simple PKG signing using ESRP directly (wrapper only)
3. **azure-cli-macos-pkg-signing.yml** - OneBranch signing from GitHub releases
4. **templates/sign-macos-pkg.yml** - OneBranch signing template

**Why Archived:**
- Only sign PKG wrapper, not internal binaries
- Insufficient for Apple notarization requirements
- Replaced by `macos-pkg-sign-all.yml` which signs everything

---

## Authentication & Security

### Service Connections

**GitHub Service Connection: `github.com_naga-nandyala`**
- Type: OAuth
- Used by:
  - `macos-pkg-github-release-publish.yml` (GitHubRelease@1 task)
  - `macos-pkg-homebrew-update.yml` (repository resources)
- Connection ID: `c997eb5-f053-421e-9d80-6de1f0ec6f08`

### Variable Groups

**AME ESRP Variable Group**
- Used by: `macos-pkg-sign-all.yml`, `macos-pkg-notarize.yml`
- Contains:
  - `ESRPAppClientId`
  - `ESRPAppTenantId`
  - `ESRPKVName`
  - `ESRPAuthCertName`
  - `ESRPSignCertName`
- Purpose: ESRP signing and notarization credentials

---

## Parameter Reference

### Common Parameters Across Pipelines

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `AzureCliVersion` | string | 2.0.0 | Version number for Azure CLI |
| `GitHubRepo` | string | naga-nandyala/azure-cli-pkg-1 | Main GitHub repository |
| `HomebrewTapRepo` | string | naga-nandyala/homebrew-mycli-app | Homebrew tap repository |
| `FormulaName` | string | azure-cli-pr | Homebrew formula class name |
| `BundleId` | string | com.microsoft.azure.cli | macOS bundle identifier |
| `OfficialBuild` | boolean | true | Enable ESRP signing/notarization |
| `SourceBuildId` | string | - | Build ID to download artifacts from |
| `SourcePipelineName` | string | - | Pipeline name to download from |

---

## Execution Sequence

### Manual Execution Order:

1. Run **macos-pkg-build.yml** → Note Build ID (e.g., 282071)
2. Run **macos-pkg-sign-all.yml** with SourceBuildId=282071
   - Note Build ID (e.g., 282373)
3. Run **macos-pkg-notarize.yml** with SourceBuildId=282373
   - Note Build ID (e.g., 283737)
4. Run **macos-pkg-github-release-publish.yml** with NotarizationBuildId=283737
5. Run **macos-pkg-homebrew-update.yml** with NotarizationBuildId=283737
6. Run **macos-pkg-install-test.yml** to validate everything

### Automated Chaining (Future):

Could be chained using pipeline triggers, but currently all are manual for control.

---

## Troubleshooting Guide

### Common Issues & Solutions

**Issue: "Unsigned binaries found inside PKG"**
- **Cause:** Used simple signing pipeline instead of `macos-pkg-sign-all.yml`
- **Solution:** Always use `macos-pkg-sign-all.yml` which signs ALL binaries

**Issue: "Notarization failed"**
- **Cause:** Not all binaries were signed before notarization
- **Solution:** Ensure `macos-pkg-sign-all.yml` completed successfully before notarizing

**Issue: "brew audit fails with style warnings"**
- **Cause:** Formula doesn't follow Homebrew style guidelines
- **Solution:** Check field order (desc → homepage → url → sha256), remove redundant version line

**Issue: "Detached HEAD" during git push in Homebrew update**
- **Cause:** Repository resource checkout creates detached HEAD
- **Solution:** Use `git checkout -B main origin/main` before committing

**Issue: "PKG download only 9 bytes"**
- **Cause:** Wrong filename in download URL
- **Solution:** Use correct filename: `azure-cli-{version}-macos-arm64-notarized.pkg`

**Issue: "GitHubRelease task fails with 401 Unauthorized"**
- **Cause:** Service connection not configured or expired
- **Solution:** Use `GitHubRelease@1` task with service connection (not curl with PAT)

---

## Approaches Tried & Evolution

### Authentication Evolution

**Attempt 1: Personal Access Token (PAT)**
- Tried using GitHub PAT in variable groups
- Problems: Manual token management, expiration issues, 401 errors with curl
- **Abandoned**

**Attempt 2: GitHubRelease@1 Task with Service Connection** ✅
- Uses OAuth-based service connection
- Built-in Azure task with automatic authentication
- No manual token management
- **Current approach - works perfectly**

### Homebrew Workflow Evolution

**Attempt 1: Create Pull Request**
- Generate formula and create PR to tap
- Problems: Extra manual step to merge PR
- **Changed to direct commit**

**Attempt 2: Direct Commit** ✅
- Commit directly to main branch
- Faster workflow, no manual intervention
- Fixed detached HEAD issue
- **Current approach**

### Formula Generation Evolution

**Attempt 1: YAML Heredoc**
- Used YAML multi-line strings for Ruby code
- Problems: YAML parsing errors with Ruby interpolation syntax
- **Changed to printf**

**Attempt 2: Printf-based Generation** ✅
- Use bash printf to write formula file
- Avoids YAML parsing conflicts
- **Current approach**

### Formula Style Evolution

**Attempt 1: With version line and bottle**
- Problems: Redundant version, deprecated bottle syntax
- Failed `brew audit`
- **Removed unnecessary fields**

**Attempt 2: Minimal compliant formula** ✅
- Only essential fields in correct order
- Passes `brew audit --formula`
- **Current approach**

### Signing Strategy Evolution

**Attempt 1: OneBranch wrapper-only signing**
- Only signed PKG file itself
- Problems: Apple notarization rejected unsigned internal binaries
- **Replaced with comprehensive signing**

**Attempt 2: ESRP comprehensive signing** ✅
- Extracts PKG, signs ALL binaries, repacks, signs wrapper
- Passes Apple notarization
- **Current production approach**

---

## Success Metrics

### Release v2.0.0 Validation ✅

- ✅ GitHub release published successfully
- ✅ PKG files available for download
- ✅ Homebrew formula updated and committed
- ✅ Formula passes `brew audit --formula`
- ✅ Homebrew installation test: **PASSED**
- ✅ Offline PKG installation test: **PASSED**
- ✅ Formula validation test: **PASSED**
- ✅ All cleanup steps successful
- ✅ End-to-end workflow validated

### User Installation Commands

```bash
# Homebrew installation
brew tap naga-nandyala/homebrew-mycli-app
brew install azure-cli-pr

# Offline PKG installation
curl -L -o azure-cli.pkg https://github.com/naga-nandyala/azure-cli-pkg-1/releases/download/v2.0.0/azure-cli-2.0.0-macos-arm64-notarized.pkg
sudo installer -pkg azure-cli.pkg -target /
```

---

## Future Improvements

### Potential Enhancements

1. **Automated Pipeline Chaining**
   - Use pipeline triggers to auto-run subsequent stages
   - Reduce manual Build ID passing

2. **Universal Binary Support**
   - Combine ARM64 and x86_64 into single universal PKG
   - Simplify distribution (one file instead of two)

3. **Release Notes Automation**
   - Auto-generate changelog from git commits
   - Include in GitHub release description

4. **Homebrew Cask Support**
   - Create Homebrew Cask formula for GUI installation
   - Simpler one-click installation for users

5. **Notification Integration**
   - Send notifications on pipeline completion/failure
   - Integration with Teams/Slack

6. **Version Bump Automation**
   - Auto-increment version numbers
   - Tag releases automatically

---

## Repository Structure

```
.azure-pipelines/
├── macos-pkg-build.yml                      # 1. Build unsigned PKG
├── macos-pkg-sign-all.yml                   # 2. Sign all binaries + PKG
├── macos-pkg-notarize.yml                   # 3. Notarize with Apple
├── macos-pkg-github-release-publish.yml     # 4. Publish GitHub release
├── macos-pkg-homebrew-update.yml            # 5. Update Homebrew formula
├── macos-pkg-install-test.yml               # 6. Validate installation
├── macos-pkg-sig-verify.yml                 # Optional: Signature testing
├── macos-pkg-notarize-verify.yml            # Optional: Notarization testing
└── _archive/                                # Archived experimental pipelines
    ├── macos-pkg-sign.yml
    ├── macos-pkg-sign-release.yml
    ├── azure-cli-macos-pkg-signing.yml
    └── sign-macos-pkg.yml
```

---

## Contact & Maintenance

**Pipeline Owner:** Development Team  
**Last Updated:** November 24, 2025  
**Pipeline Version:** 2.0 (Service Connection-based)  
**Current Status:** Production Ready ✅

For issues or questions, refer to the troubleshooting guide above or review pipeline run logs in Azure DevOps.
