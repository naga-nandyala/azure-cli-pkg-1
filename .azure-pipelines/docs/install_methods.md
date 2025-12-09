| Stage                               | Action       | Command                                                                     | Notes |
|-------------------------------------|-------------|-----------------------------------------------------------------------------|-------|
| **1️⃣ Initial state (formula-based)** | Install     | `brew update && brew install azure-cli`                                      | Installs the existing Homebrew formula |
|                                     | Upgrade     | `brew update && brew upgrade azure-cli`                                      | Upgrades formula version |
|                                     | Uninstall   | `brew uninstall azure-cli`                                                   | Removes formula installation |
|                                     | Cleanup     | `brew cleanup azure-cli`                                                     | Removes old cached versions |
| **2️⃣ Interim (custom tap + cask)**  | Install     | `brew update && brew tap azure/azure-cli && brew install --cask azure-cli`   | Uses your custom tap with .pkg |
|                                     | Upgrade     | `brew update && brew upgrade --cask azure-cli`                               | Installs new .pkg from tap |
|                                     | Uninstall   | `brew uninstall --cask azure-cli`                                           | Removes current cask version |
|                                     | Full Cleanup (Zap) | `brew uninstall --cask azure-cli --zap`                                    | Removes leftover files & symlinks |
| **3️⃣ Final (official Homebrew Cask)** | Install     | `brew update && brew install --cask azure-cli`                               | Cask now in homebrew-cask core |
|                                     | Upgrade     | `brew update && brew upgrade --cask azure-cli`                               | Updates official cask version |
|                                     | Uninstall   | `brew uninstall --cask azure-cli`                                           | Removes cask installation |
|                                     | Full Cleanup (Zap) | `brew uninstall --cask azure-cli --zap`                                    | Removes leftover files & symlinks |
