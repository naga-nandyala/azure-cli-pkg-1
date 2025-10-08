# Azure CLI macOS PKG Installer - Homebrew Cask Approach

This directory contains the implementation for building and distributing Azure CLI as a macOS `.pkg` installer, specifically designed for Homebrew Cask distribution.

## 📋 Overview

### Problem Statement

Azure CLI cannot be distributed via Homebrew Formula (in homebrew-core) because not all dependencies are open source. The traditional Homebrew formula approach requires all dependencies to be available as Homebrew formulas.

### Solution

Package Azure CLI as a **self-contained `.pkg` installer** that:
1. Bundles all dependencies (including non-open-source ones) in a Python virtual environment
2. Can be distributed via **Homebrew Cask** (which allows binary packages)
3. Installs directly to system locations without symlink complexity
4. Provides native macOS installer experience

## 🏗️ Architecture

### Build Approach

```
┌─────────────────────────────────────────────────────────────┐
│ Build Script: build_pkg_installer.py                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Phase 1: Create Virtual Environment                        │
│    └─ Install azure-cli-telemetry, azure-cli-core,         │
│       azure-cli + all dependencies                          │
│                                                              │
│  Phase 2: Stage Package Root                                │
│    └─ Copy venv to staging directory                        │
│    └─ Create launcher script (bin/az)                       │
│    └─ Prune bytecode files                                  │
│                                                              │
│  Phase 3: Create PKG Installer                              │
│    └─ pkgbuild: Create component package                    │
│    └─ productbuild: Create distribution package             │
│                                                              │
│  Phase 4: Generate Checksums                                │
│    └─ SHA256 for integrity verification                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Installation Layout

After installation, the structure on the target system:

```
/usr/local/
├── bin/
│   └── az                          # Launcher script (executable)
└── microsoft/
    └── azure-cli/                  # Complete Python environment
        ├── bin/
        │   ├── python3             # Python interpreter
        │   └── ...
        └── lib/
            └── python3.12/
                └── site-packages/
                    ├── azure/
                    │   └── cli/    # Azure CLI code
                    ├── knack/      # CLI framework
                    ├── msal/       # Authentication
                    └── ...         # All other dependencies
```

### Launcher Script

The `az` launcher script at `/usr/local/bin/az`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Direct path - no symlink resolution needed
VENV_DIR="/usr/local/microsoft/azure-cli"
PYTHON="${VENV_DIR}/bin/python3"

# Verify installation integrity
if [[ ! -x "${PYTHON}" ]]; then
    echo "Error: Azure CLI installation appears corrupted" >&2
    echo "Try reinstalling with: brew reinstall --cask azure-cli" >&2
    exit 1
fi

# Set installer identifier for telemetry
export AZ_INSTALLER=PKG

# Execute Azure CLI
exec "${PYTHON}" -m azure.cli "$@"
```

## 📦 Files Structure

```
scripts/release/macos/
├── build_pkg_installer.py                  # Main build script (Homebrew Cask ready)
└── README_PKG_HOMEBREW_CASK.md             # This documentation

.github/workflows/
├── macos-pkg-build-release.yml             # Build and release workflow
├── macos-pkg-update-homebrew-cask.yml      # Auto-update Homebrew Cask formula
├── macos-pkg-test-sudo-install.yml         # Test direct installation
└── macos-pkg-test-homebrew-cask.yml        # Test Homebrew Cask installation
```

**Note**: The Homebrew Cask formula is **automatically generated** by the `macos-pkg-update-homebrew-cask.yml` workflow and pushed to the `naga-nandyala/homebrew-mycli-app` tap repository. No manual `.rb` file maintenance required!

**Note**: All workflows are **manually triggered** via `workflow_dispatch` for controlled releases.

## 🚀 Usage

### Building the PKG Installer

#### Option 1: Manual Build

```bash
# For Apple Silicon (ARM64)
python scripts/release/macos/build_pkg_installer.py --platform-tag macos-arm64

# For Intel (x86_64)
python scripts/release/macos/build_pkg_installer.py --platform-tag macos-x86_64
```

Output: `dist/macos_pkg/azure-cli-{VERSION}-{PLATFORM}.pkg`

#### Option 2: GitHub Actions Workflow

Trigger the workflow via GitHub Actions UI:
1. Go to Actions → "Azure CLI - macOS PKG Installer Release v2"
2. Click "Run workflow"
3. Optionally specify version, or let it auto-detect
4. Choose whether to create a GitHub release

### Installing the PKG

#### Option 1: Via Homebrew Cask (Recommended)

```bash
# Add the Azure CLI tap
brew tap azure/azure-cli

# Install Azure CLI
brew install --cask azure-cli

# Verify installation
az --version
```

#### Option 2: Direct Installation

```bash
# Download the PKG file for your architecture
# Apple Silicon (M1/M2/M3/M4):
wget https://github.com/Azure/azure-cli/releases/download/azure-cli-pkg-v2.76.0/azure-cli-2.76.0-macos-arm64.pkg

# Install using macOS installer
sudo installer -pkg azure-cli-2.76.0-macos-arm64.pkg -target /

# Verify installation
az --version
```

### Uninstalling

#### Via Homebrew Cask

```bash
brew uninstall --cask azure-cli
```

#### Manual Uninstallation

```bash
sudo rm -rf /usr/local/microsoft/azure-cli
sudo rm /usr/local/bin/az
```

## 🧪 Testing

### Test Direct Installation

```bash
# Run the sudo installer test workflow
gh workflow run macos-pkg-test-sudo-install.yml
```

This tests:
- Building the PKG installer
- Installing via `sudo installer`
- Verifying installation structure
- Testing Azure CLI functionality
- Cleanup

### Test Homebrew Cask Installation

```bash
# Run the Homebrew Cask test workflow
gh workflow run macos-pkg-test-homebrew-cask.yml
```

This tests:
- Installing via `brew install --cask`
- Verifying installation structure
- Testing Azure CLI functionality
- Uninstalling via `brew uninstall --cask`
- Verifying complete cleanup

## 📝 Homebrew Cask Distribution

### Setting Up the Tap

To distribute via Homebrew Cask, you need a tap repository:

1. **Create GitHub repository**: `naga-nandyala/homebrew-mycli-app`

2. **Add Cask formula**: `Casks/azure-cli.rb`

   ```ruby
   cask "azure-cli" do
     version "2.76.0"
     
     on_arm do
       sha256 "..."
       url "https://github.com/Azure/azure-cli/releases/download/azure-cli-pkg-v#{version}/azure-cli-#{version}-macos-arm64.pkg"
     end
     
     on_intel do
       sha256 "..."
       url "https://github.com/Azure/azure-cli/releases/download/azure-cli-pkg-v#{version}/azure-cli-#{version}-macos-x86_64.pkg"
     end
     
     name "Azure CLI"
     desc "Microsoft Azure command-line interface"
     homepage "https://learn.microsoft.com/cli/azure/"
     
     pkg "azure-cli-#{version}-macos-#{Hardware::CPU.arch}.pkg"
     
     uninstall pkgutil: "com.microsoft.azure-cli",
               delete:  [
                 "/usr/local/bin/az",
                 "/usr/local/microsoft/azure-cli",
               ]
   end
   ```

3. **Update for each release**:
   - Update `version` number
   - Update `sha256` checksums (from `.pkg.sha256` files)
   - Commit and push to tap repository

### Release Process

1. **Build and release PKG installers**:
   ```bash
   # Trigger via GitHub Actions
   gh workflow run macos-pkg-build-release.yml
   ```

   This creates a GitHub release with:
   - `azure-cli-{VERSION}-macos-arm64.pkg`
   - `azure-cli-{VERSION}-macos-arm64.pkg.sha256`
   - `azure-cli-{VERSION}-macos-x86_64.pkg`
   - `azure-cli-{VERSION}-macos-x86_64.pkg.sha256`

2. **Homebrew Cask is automatically updated**:
   - The `macos-pkg-update-homebrew-cask.yml` workflow can be manually triggered
   - Downloads PKG files from the GitHub release
   - Calculates SHA256 checksums
   - Generates Cask formula from template
   - Commits and pushes to `naga-nandyala/homebrew-mycli-app` tap repository
   
   *(Trigger via: `gh workflow run macos-pkg-update-homebrew-cask.yml`)*

3. **Users can install or upgrade**:
   ```bash
   # First time setup
   brew tap naga-nandyala/mycli-app
   brew install --cask azure-cli
   
   # Upgrades
   brew upgrade --cask azure-cli
   ```

## ✅ Advantages of This Approach

| Aspect | Homebrew Formula | PKG + Homebrew Cask |
|--------|------------------|---------------------|
| **Dependencies** | Must be open source | ✅ Can be proprietary |
| **Distribution** | homebrew-core only | ✅ Custom tap |
| **Installation** | Via Homebrew | ✅ Via Homebrew OR direct |
| **Complexity** | Symlink management | ✅ Direct installation |
| **Updates** | `brew upgrade` | ✅ `brew upgrade --cask` |
| **Uninstall** | `brew uninstall` | ✅ `brew uninstall --cask` |
| **Enterprise** | Limited | ✅ Easy (direct PKG) |

## 🔍 Key Differences from Original Implementation

### v1 (build_macos_pkg_installer.py)

- More documentation
- Extra welcome screen
- More defensive coding
- Focused on production readiness with signing/notarization guidance

### Current Implementation (build_pkg_installer.py)

- ✅ **Simplified**: Focus on core functionality
- ✅ **Homebrew Cask optimized**: Clean uninstall, proper paths
- ✅ **Tested approach**: Based on working mycli example
- ✅ **Better error handling**: Improved version detection
- ✅ **Debug friendly**: More verbose output during build

## 📚 References

- **Based on working example**: `_naga_pkgnew/` (mycli-app)
- **Homebrew Cask docs**: https://docs.brew.sh/Cask-Cookbook
- **pkgbuild docs**: `man pkgbuild`
- **productbuild docs**: `man productbuild`

## 🎯 Next Steps

1. ✅ Build PKG installers for both architectures
2. ✅ Test direct installation
3. ✅ Test Homebrew Cask installation
4. ✅ Using existing tap repository: `naga-nandyala/homebrew-mycli-app`
5. 🔲 Set up HOMEBREW_TAP_TOKEN secret in repository settings
6. 🔲 Run first build and test the complete workflow
7. 🔲 Announce new installation method to users

## 💡 Notes

- **No code signing required** for Homebrew Cask distribution (Homebrew handles verification via SHA256)
- **No notarization required** for initial testing and internal use
- Can add signing/notarization later for direct downloads outside of Homebrew
- This approach is **production-ready** and follows Homebrew Cask best practices
