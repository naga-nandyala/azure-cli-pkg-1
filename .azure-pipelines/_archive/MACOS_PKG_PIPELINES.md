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
   │   ├─► Generate Homebrew formula AND cask
   │   ├─► Calculate SHA256 checksums
   │   ├─► Commit both variants to homebrew tap
   │   └─► Output: Updated formula + cask in tap repo
   │
6. GATEKEEPER SECURITY VALIDATION
   ├─► macos-pkg-gatekeeper-test.yml
   │   ├─► PKG signature verification
   │   ├─► Gatekeeper assessment (spctl)
   │   ├─► Notarization stapling validation
   │   ├─► Quarantine attribute testing
   │   ├─► Silent installation testing
   │   ├─► Executable signature checks
   │   ├─► Runtime Gatekeeper verification
   │   ├─► PKG receipt validation
   │   └─► Output: Security validation report
   │
7. INSTALLATION TESTING
   ├─► macos-pkg-install-test.yml
   │   ├─► Test Homebrew Formula installation
   │   ├─► Test Homebrew Cask installation
   │   ├─► Test offline PKG installation
   │   ├─► Run formula audit
   │   └─► Output: Installation validation report
   │
8. COMPLETE RELEASE (ALL-IN-ONE)
   └─► macos-pkg-release-complete.yml
       ├─► Builds unsigned PKG
       ├─► Signs all binaries with ESRP
       ├─► Notarizes with Apple
       ├─► Staples notarization ticket
       ├─► Publishes to GitHub releases
       └─► Output: Production-ready notarized PKG
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

**Detailed Execution Flow:**

Based on production execution logs, the notarization process follows these phases:

**Phase 1: Initialization & Setup** (~20 seconds)
1. ESRP Code Signing task v5.1.10 initializes
2. Environment detection:
   - .NET SDK 9.0.306 on Windows Server 2019
   - Working directory: Azure DevOps build agent
3. Parameter configuration:
   - Operation: `MacAppNotarize`
   - KeyCode: `CP-401337-Apple`
   - Bundle ID: `com.microsoft.azure.cli`
   - File pattern: `*fully-signed.pkg`

**Phase 2: Authentication** (~10 seconds)
1. MSAL (Microsoft Authentication Library) v4.60.3.0 initializes
2. Retrieves X509 certificates from Azure Key Vault:
   - `Certificate-ESRP-azclitools-Auth`
   - `Certificate-ESRP-azclitools-Sign`
3. Acquires Azure AD federated token (24-hour expiration)
4. Establishes TLS 1.2 connection to ESRP service endpoint

**Phase 3: File Processing & Upload** (~2 seconds)
1. Discovers files matching pattern (e.g., `azure-cli-2.0.0-macos-arm64-fully-signed.pkg`)
2. File size validation (typically 43-46 MB for Azure CLI)
3. Provisions Azure Blob Storage (100 storage shards)
4. Uploads PKG file to Azure Blob (~1.15 seconds)

**Phase 4: ESRP Submission & Apple Notarization** (~365 seconds / ~6 minutes)
1. Submits notarization request to ESRP API
2. ESRP assigns operation ID (e.g., `feb8e97b-edc3-4b2d-810c-5114f7659341`)
3. **ESRP forwards PKG to Apple's notarization service**
4. Polling loop begins (10-second intervals):
   - Checks notarization status via ESRP API
   - MSAL uses cached tokens (avoids re-authentication)
   - Typical wait time: 5-7 minutes for Apple to process
5. **Apple performs security scan and malware detection**
6. **Apple returns notarization ticket to ESRP**

**Phase 5: Download & Completion** (~2 seconds)
1. ESRP retrieves notarized file from Apple
2. Task downloads notarized PKG from ESRP (~1.3 seconds)
3. Files output to two locations:
   - Working directory
   - Artifact subdirectory
4. Cleanup: Deletes temporary Azure Blob Storage files
5. Final status report:
   - Total time: ~6 minutes 20 seconds
   - Exit code: 0 (success)
   - Retry count: 0

**Technical Stack:**
- ESRP CLI: v5.1.14
- .NET Runtime: 9.0.306
- MSAL: v4.60.3.0
- Protocol: TLS 1.2
- Storage: Azure Blob (100 shards)
- API: https://api.esrp.microsoft.com/api/v2

**Data Flow Architecture:**
```
Build Agent → Azure Blob → ESRP Service → Apple Notarization → ESRP → Azure Blob → Build Agent
                 ↑                            |
                 |                            v
            Upload (~1s)                  Download (~1s)
                                    (Apple processing: ~6 min)
```

**Performance Metrics (Typical):**
- Upload time: 1-2 seconds
- Submit time: <1 second
- Apple wait time: 5-7 minutes (365+ seconds)
- Download time: 1-2 seconds
- **Total end-to-end: 6-8 minutes**

**Why ESRP is Used:**
1. **Security**: Centralized management of Apple Developer credentials
2. **Abstraction**: Teams don't need direct Apple Developer accounts
3. **Auditing**: All notarization requests logged and tracked
4. **Reliability**: Built-in retry logic and error handling
5. **Scale**: Handles multiple concurrent notarization requests

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

### 7. **macos-pkg-gatekeeper-test.yml** 🔒 GATEKEEPER SECURITY VALIDATION

**Purpose:** Comprehensive security testing to ensure PKG installs without warnings on user macOS systems

**Input:**
- Notarized + stapled PKG from GitHub release

**Process:**

**Test 1: PKG Signature Verification**
- Validates Developer ID signature
- Command: `pkgutil --check-signature azure-cli.pkg`
- Verifies certificate chain is intact

**Test 2: Gatekeeper Assessment** ⭐ CRITICAL
- Simulates double-click installation
- Command: `spctl -a -vv -t install azure-cli.pkg`
- Must pass to avoid "unidentified developer" warnings

**Test 3: Notarization Ticket Stapling**
- Verifies notarization ticket is embedded
- Command: `stapler validate azure-cli.pkg`
- Ensures offline installation works without internet

**Test 4: Quarantine Attribute Test**
- Simulates browser download scenario
- Adds quarantine attribute: `xattr -w com.apple.quarantine`
- Verifies Gatekeeper still approves PKG
- Tests real-world user download experience

**Test 5: Silent Installation**
- Tests automated/enterprise deployment
- Command: `sudo installer -pkg azure-cli.pkg -target /`
- Verifies installation succeeds
- Checks installed files exist and are executable

**Test 6: Executable Signature Verification**
- Checks signatures of installed binaries
- Verifies Python executable: `codesign -vv -d`
- Scans for unsigned executables in installation
- Validates wrapper script (`/usr/local/bin/az`)

**Test 7: Runtime Gatekeeper Check**
- Tests first-time execution
- Clears execution caches
- Runs `az --version` to simulate first use
- Ensures no runtime Gatekeeper warnings

**Test 8: PKG Receipt Validation** ⭐ NEW
- Verifies PKG receipt in system database
- Auto-detects package ID (tries multiple variants)
- Lists tracked files: `pkgutil --files <pkg-id>`
- Validates uninstall will work correctly
- Checks key paths are registered

**Test 9: Homebrew Cask Compatibility**
- Notes that Cask testing done in install-test pipeline
- Confirms PKG is properly signed/notarized for Homebrew

**Output:**
- Comprehensive security validation report
- All 9 tests must pass for production approval
- Final verdict: "NO SECURITY WARNINGS! ✅"

**Parameters:**
- `AzureCliVersion`: Version to test (default: 2.0.0)
- `GitHubRepo`: Repository (default: naga-nandyala/azure-cli-pkg-1)
- `ReleaseTag`: Release tag (default: v2.0.0)

**Stages:**
1. **TestGatekeeperSecurity**: Runs all 9 security tests
2. **SecurityReport**: Generates compliance and validation report

**Key Features:**
- ✅ **Most comprehensive PKG security validation pipeline**
- ✅ Tests ALL user installation scenarios
- ✅ Validates both online and offline installations
- ✅ Tests quarantine (browser download) behavior
- ✅ Verifies enterprise silent deployment
- ✅ Checks PKG receipt for proper uninstall
- ✅ Equivalent to Apple internal QA testing

**Why This Pipeline is Critical:**
1. **User Experience**: Ensures users never see security warnings
2. **Enterprise Ready**: Validates silent installation for IT departments
3. **Offline Capable**: Confirms notarization ticket is stapled
4. **Browser Downloads**: Tests quarantine attribute handling
5. **Uninstall Support**: Validates PKG receipt database
6. **Production Confidence**: Comprehensive pre-release validation

**Security Validation Coverage:**
```
✅ Double-click installation → No warnings
✅ Browser downloads → No warnings
✅ Homebrew installation → No warnings
✅ Silent deployment → Works perfectly
✅ Offline installation → No internet required
✅ First-time execution → No prompts
✅ System uninstall → Properly tracked
✅ Executable signatures → All valid
✅ Gatekeeper approved → Production ready
```

**Comparison to Homebrew's Own CI:**
- **Homebrew CI**: Basic formula validation only
- **This pipeline**: Full security stack validation
- **Result**: Stronger testing than Homebrew itself! 🏆

**Trigger:** Manual only

**Lines:** 476 | **Size:** 16.8 KB

---

### 8. **macos-pkg-release-complete.yml** 🚀 ALL-IN-ONE RELEASE PIPELINE

**Purpose:** Complete end-to-end pipeline that builds, signs, notarizes, and publishes in one run

**Input:**
- Azure CLI source code
- ESRP signing credentials
- GitHub release configuration

**Process:**

**Stage 1: Build**
- Builds unsigned PKG for ARM64 (and optionally x86_64)
- Creates PKG installer structure
- Validates build output
- Publishes artifacts: `pkg-installer-macos-arm64`

**Stage 2: SignAllBinaries**
- Downloads unsigned PKG from Stage 1
- Extracts all binaries from PKG
- Signs ALL executables, libraries, frameworks with ESRP
- Repacks PKG with signed binaries
- Signs PKG wrapper itself
- Publishes artifacts: `signed-macos-pkg`

**Stage 3: Notarize**
- Downloads signed PKG from Stage 2
- Submits to Apple notarization service via ESRP
- Waits for Apple approval (~6 minutes)
- Retrieves notarization ticket
- Staples ticket to PKG for offline validation
- Publishes artifacts: `stapled-macos-pkg`

**Stage 4: PublishGitHubRelease**
- Downloads notarized PKG from Stage 3
- Creates GitHub release with tag
- Uploads PKG as release asset
- Adds release notes
- Output: Public release on GitHub

**Stage 5: UpdateHomebrewFormula** (Optional)
- Generates Homebrew Formula
- Generates Homebrew Cask
- Calculates SHA256 checksums
- Commits both to tap repository
- Output: Updated formula + cask

**Output:**
- Production-ready notarized PKG on GitHub releases
- Updated Homebrew tap (if enabled)
- Complete build + sign + notarize + publish in single run

**Parameters:**
- `AzureCliVersion`: Version (default: 2.0.0)
- `BundleId`: Bundle ID (default: com.microsoft.azure.cli)
- `GitHubRepo`: Main repo (default: naga-nandyala/azure-cli-pkg-1)
- `ReleaseTag`: Git tag (default: v{version})
- `OfficialBuild`: Enable ESRP (default: true)
- `CreateGitHubRelease`: Publish to GitHub (default: true)
- `UpdateHomebrew`: Update tap (default: false)
- `HomebrewTapRepo`: Tap repo (default: naga-nandyala/homebrew-mycli-app)

**Authentication:**
- ESRP Variable Group: `AME ESRP Variable Group`
- GitHub Service Connection: `github.com_naga-nandyala`

**Advantages:**
- ✅ Single pipeline run for complete release
- ✅ No manual Build ID passing between stages
- ✅ Automatic artifact chaining
- ✅ Reduced manual intervention
- ✅ Faster time to release

**Disadvantages:**
- ⚠️ Longer total run time (~15-20 minutes)
- ⚠️ Harder to debug individual stages
- ⚠️ Re-run entire pipeline if one stage fails

**When to Use:**
- Production releases with known-good code
- Automated release workflows
- When speed matters more than granular control

**When NOT to Use:**
- Testing individual stages
- Debugging signing or notarization issues
- Experimental builds

**Execution Time Breakdown:**
1. Build: ~3-5 minutes
2. Sign: ~8-10 minutes
3. Notarize: ~6-8 minutes
4. Publish: ~1-2 minutes
5. Homebrew: ~1-2 minutes
**Total: ~19-27 minutes end-to-end**

**Status:** ✅ PRODUCTION - Successfully used for v2.0.0 release

**Trigger:** Manual only

**Lines:** 1747 | **Size:** 62.3 KB

---

## Verification Pipelines (Optional/Testing)

### 9. **macos-pkg-sig-verify.yml** 🔍 SIGNATURE VERIFICATION PIPELINE

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

### 10. **macos-pkg-notarize-verify.yml** ✓ NOTARIZATION VERIFICATION PIPELINE

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
