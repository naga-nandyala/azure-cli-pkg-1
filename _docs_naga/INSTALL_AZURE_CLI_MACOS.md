# Install Azure CLI on macOS

## Option 1 — Homebrew Cask (Recommended)

### Prerequisites

- macOS (Apple Silicon or Intel)
- [Homebrew](https://brew.sh/) installed
- uninstall existing azure-cli installed via homebrew-core. This can be done by running the following command:
  
  ```bash
  brew uninstall azure-cli
  ```

### Install

```bash
brew update && brew install --cask azure-cli
```

### Verify

```bash
az --version
```

### Upgrade

```bash
brew upgrade --cask azure-cli
```

### Uninstall

```bash
brew uninstall --cask azure-cli
```

---

## Option 2 — Offline / Tarball (Air-Gapped Environments)

For environments where Homebrew is not available or internet access is restricted.

### Prerequisites

- macOS (Apple Silicon or Intel)
- Python 3.13 installed via any method (python.org, pyenv, etc.)

### 1. Download the tarball

On a machine with internet access, download the latest release from the [Azure CLI releases page](https://github.com/Azure/azure-cli/releases):

```bash
# Replace <version> with the desired version (e.g. 2.85.0)
# Replace <arch> with your architecture: arm64 (Apple Silicon) or x86_64 (Intel)
# e.g. azure-cli-2.84.0-macos-arm64.tar.gz or azure-cli-2.84.0-macos-x86_64.tar.gz

curl -L -o azure-cli-<version>-macos-<arch>.tar.gz \
  "https://github.com/Azure/azure-cli/releases/download/azure-cli-<version>/azure-cli-<version>-macos-<arch>.tar.gz"
```

### 2. Transfer to the offline machine

Copy the tarball via USB drive, secure file transfer, etc.

### 3. Extract to installation directory

```bash
sudo mkdir -p /target_directory_path
sudo tar -xzf azure-cli-<version>-macos-<arch>.tar.gz -C /target_directory_path
```

### 4. Install Python 3.13 (if not already installed)


### 5. Set environment variables

Add to `~/.zshrc` or `~/.bashrc`:

```bash
export AZ_PYTHON="/path_of_where_python_is_installed"
export PATH="/target_directory_path/bin:$PATH"
```

Reload:

```bash
source ~/.zshrc
```

### 6. Verify

```bash
az --version
```

### Upgrade (offline)

Download the new tarball, extract over the existing directory:

```bash
sudo tar -xzf azure-cli-<version>-macos-<arch>.tar.gz -C /target_directory_path
```

### Uninstall (offline)

```bash
sudo rm -rf /target_directory_path
```

Remove the `AZ_PYTHON` and `PATH` lines from `~/.zshrc`.

---
