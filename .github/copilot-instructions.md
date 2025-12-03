# Azure CLI - AI Agent Instructions

## Project Overview
This is the **Azure CLI** codebase - Microsoft's cross-platform command-line tool for managing Azure resources. The project focuses on both the CLI product itself and macOS PKG distribution infrastructure with ESRP signing and Apple notarization.

## Architecture

### Core Structure
- **`src/azure-cli/`** - Main CLI package with command modules
- **`src/azure-cli-core/`** - Core framework (command loading, auth, profiles)
- **`src/azure-cli-telemetry/`** - Telemetry collection
- **`src/azure-cli-testsdk/`** - Testing framework for CLI tests

### Command Module Pattern
Commands live in `src/azure-cli/azure/cli/command_modules/{service}/`:
```
command_modules/storage/
├── __init__.py          # Module loader (inherits AzCommandsLoader)
├── commands.py          # Command registration (load_command_table)
├── custom.py            # Custom command implementations
├── _params.py           # Parameter definitions
├── aaz/                 # Auto-generated AAZ commands (aaz-dev-tools)
│   └── latest/          # Latest API version
└── tests/
    └── latest/          # Test files
```

**Two command authoring approaches:**
1. **AAZ (Atomic Azure)** - Auto-generated from REST specs via `aaz-dev-tools` (preferred for CRUD)
2. **Custom** - Hand-written in `custom.py` for complex logic

## Critical Workflows

### Developer Setup
**DO NOT use `scripts/dev_setup.py`** - it's deprecated. Instead:
```powershell
# Create venv and install azdev
python -m venv env
env\Scripts\activate
pip install azdev

# Set up development environment
azdev setup -c
```

### Testing Commands
```powershell
# Discover tests
azdev test --discover

# Run module tests
azdev test storage --live

# Run specific test
azdev test test_storage_account_create

# Replay failed tests
azdev test --src-file test_failures.txt
```

### Building Packages
```powershell
# Build wheels for CI
scripts/ci/build.sh   # Creates artifacts/build/*.whl

# Windows MSI
build_scripts/windows/scripts/build.cmd

# macOS PKG
python scripts/release/macos/build_pkg_installer.py
```

## macOS PKG Distribution Pipeline (CRITICAL)

### Pipeline Overview
Located in `.azure-pipelines/macos-pkg-*.yml` - **9-stage production workflow**:

1. **Build** (`macos-pkg-build.yml`) - Create unsigned PKG for ARM64/x86_64
2. **Sign** (`macos-pkg-sign-all.yml`) - ESRP signs all Mach-O binaries + PKG wrapper
3. **Notarize** (`macos-pkg-notarize.yml`) - Apple notarization via ESRP (~6 min)
4. **Publish** (`macos-pkg-github-release-publish.yml`) - GitHub release creation
5. **Homebrew** (`macos-pkg-homebrew-update.yml`) - Generate Formula + Cask, commit to tap
6. **Gatekeeper Tests** (`macos-pkg-gatekeeper-test.yml`) - 9 security validations
7. **Install Tests** (`macos-pkg-install-test.yml`) - Test Formula/Cask/offline installs
8. **Complete** (`macos-pkg-release-complete.yml`) - All-in-one pipeline (stages 1-6)

### Key Technical Details
- **ESRP Integration**: Uses `EsrpCodeSigning@5` task with KeyCode `CP-401337-Apple`
- **Binary Detection**: `file` command to identify Mach-O binaries (not Linux ELF)
- **Homebrew Dual Delivery**: 
  - Formula extracts PKG to Cellar
  - Cask installs PKG natively to `/usr/local/microsoft/azure-cli`
- **Gatekeeper Tests**: 9 comprehensive checks including `spctl`, quarantine, stapling
- **Documentation**: `.azure-pipelines/MACOS_PKG_PIPELINES.md` (1026 lines)

### ESRP Notarization Flow
```
Build Agent → Azure Blob → ESRP API → Apple Notary → ESRP → Agent
              (1-2s)       (~6 min)    (scan)        (1-2s)
```

## Project Conventions

### Code Generation
- **AAZ commands**: Generated via `aaz-dev-tools` from Azure REST API specs
- **SDK updates**: Use `scripts/trim_sdk.py` to remove unused versions
- **Model patching**: `build_scripts/windows/scripts/patch_models_v2.py` for multi-api

### Testing Patterns
- Inherit from `ScenarioTest` (in `azure.cli.testsdk`)
- Use decorators: `@ResourceGroupPreparer`, `@StorageAccountPreparer`
- Record/playback mode for live tests (recordings stored as YAML)
- Test profile targeting: `AZURE_CLI_TEST_TARGET_PROFILE=latest`

### Version Detection
- CLI version in `src/azure-cli/azure/cli/__main__.py` → `__version__`
- Extract via: `cat src/azure-cli/azure/cli/__main__.py | grep __version__`

### Entry Points
- **Batch**: `az.bat` / **Bash**: `az` script
- **PowerShell**: `azps.ps1` (sets `AZ_INSTALLER=MSI`)
- All invoke: `python -IBm azure.cli`

## macOS PKG Pipeline Parameters

When working with pipelines, common parameters:
- `SourceBuildId` / `UnsignedBuildId` - References upstream build
- `AzureCliVersion` - Version string (e.g., `2.0.0`)
- `BundleId` - macOS bundle ID (`com.microsoft.azure.cli`)
- `GitHubRepo` - Target repository (`naga-nandyala/azure-cli-pkg-1`)
- `HomebrewTapRepo` - Tap repository (`naga-nandyala/homebrew-mycli-app`)
- `FormulaName` - Homebrew formula class name (`azure-cli-pr`)

## Key Files Reference

| File | Purpose |
|------|---------|
| `scripts/install_full.sh` | Full CLI installation in venv |
| `scripts/trim_sdk.py` | Remove unused SDK versions |
| `scripts/ci/build.sh` | Build wheels for CI/CD |
| `build_scripts/windows/scripts/build.cmd` | Windows MSI build |
| `scripts/release/macos/build_pkg_installer.py` | macOS PKG build |
| `.azure-pipelines/MACOS_PKG_PIPELINES.md` | Complete pipeline docs |
| `doc/authoring_command_modules/README.md` | Module authoring guide |
| `doc/authoring_tests.md` | Test authoring guide |

## Common Pitfalls

1. **Don't modify AAZ-generated code** - Regenerate via `aaz-dev-tools` instead
2. **Profile awareness** - Code must work across Azure Stack/Gov/China profiles
3. **Homebrew patches** - See `src/azure-cli-core/azure/cli/core/extension/_homebrew_patch.py`
4. **ESRP tasks require YAML** - Classic pipelines don't support them
5. **Binary signing** - Only sign Mach-O executables, skip Python source files

## Sprint Review Context (Current Focus)

**Status**: Exploring macOS PKG signing/notarization via ESRP tasks for broker support delivery.

**Early Findings**:
- ESRP tasks compatible with macOS signing requirements
- Notarization workflow integration feasible  
- Gatekeeper approval process achievable
- Multiple distribution methods (Homebrew Cask, offline PKG) can share same notarized PKG

**Next Steps**: Complete ESRP signing POC, validate end-to-end pipeline, finalize Gatekeeper validation approach.
