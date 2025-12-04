# PKG Versioning Design - Homebrew-Inspired Approach

## Overview

This document describes the proposed versioning system for Azure CLI PKG installer, inspired by Homebrew's Cellar versioning pattern. The goal is to enable side-by-side version installations, easy rollback, and atomic upgrades while maintaining Microsoft's standard installation path.

## Current vs Proposed Structure

### Current Installation Structure

```
/usr/local/microsoft/azure-cli/
├── bin/
│   └── python
└── lib/
    └── python3.13/

/usr/local/bin/
└── az (shell script launcher)
```

**Limitations:**
- ❌ No side-by-side versions
- ❌ No easy rollback
- ❌ Destructive upgrades
- ❌ No version switching capability

### Proposed Installation Structure

```
/usr/local/microsoft/azure-cli/
├── 2.80.0/
│   ├── bin/
│   │   └── python
│   └── lib/
│       └── python3.13/
├── 2.81.0/
│   ├── bin/
│   │   └── python
│   └── lib/
│       └── python3.13/
├── current -> 2.81.0/  (symlink to active version)
└── cleanup-old-versions.sh

/usr/local/bin/
└── az (shell script launcher)
```

**Benefits:**
- ✅ Side-by-side versions (like Homebrew's Cellar)
- ✅ Easy rollback (change `current` symlink)
- ✅ Atomic upgrades (new version installed before old is touched)
- ✅ Simple cleanup (users can remove old versions when ready)
- ✅ Single launcher (`/usr/local/bin/az` works for any version)
- ✅ Version switching capability for advanced users

## Implementation Details

### 1. Shell Script Launcher (`/usr/local/bin/az`)

**Current:**
```bash
#!/usr/bin/env bash
/usr/local/microsoft/azure-cli/bin/python -Im azure.cli "$@"
```

**Proposed:**
```bash
#!/usr/bin/env bash
INSTALL_ROOT="/usr/local/microsoft/azure-cli"

# Use 'current' symlink to find active version
if [ -L "$INSTALL_ROOT/current" ]; then
    CURRENT_VERSION=$(readlink "$INSTALL_ROOT/current")
    exec "$INSTALL_ROOT/$CURRENT_VERSION/bin/python" -Im azure.cli "$@"
else
    # Fallback for legacy non-versioned installations
    exec "$INSTALL_ROOT/bin/python" -Im azure.cli "$@"
fi
```

### 2. PKG Installation Scripts

#### preinstall Script

```bash
#!/bin/bash

INSTALL_ROOT="/usr/local/microsoft/azure-cli"
NEW_VERSION="__VERSION__"  # Replaced during build (e.g., 2.81.0)

echo "Installing Azure CLI ${NEW_VERSION}..."

# Preserve existing version if 'current' symlink exists
if [ -L "$INSTALL_ROOT/current" ]; then
    OLD_VERSION=$(readlink "$INSTALL_ROOT/current")
    echo "Existing version detected: $OLD_VERSION"
    echo "Old version will be preserved in: $INSTALL_ROOT/$OLD_VERSION"
else
    echo "No existing installation detected"
fi

# Remove 'current' symlink (will be recreated in postinstall)
rm -f "$INSTALL_ROOT/current"

# Handle migration from non-versioned installation
if [ -d "$INSTALL_ROOT/bin" ] && [ ! -d "$INSTALL_ROOT/2."* ]; then
    echo "Migrating from non-versioned installation..."
    
    # Detect old version from installed CLI
    if [ -f "$INSTALL_ROOT/bin/python" ]; then
        OLD_VERSION=$("$INSTALL_ROOT/bin/python" -Im azure.cli --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
        
        if [ "$OLD_VERSION" != "unknown" ]; then
            echo "Detected old version: $OLD_VERSION"
            # Move old installation to versioned directory
            mkdir -p "$INSTALL_ROOT.tmp"
            mv "$INSTALL_ROOT"/* "$INSTALL_ROOT.tmp/" 2>/dev/null || true
            mkdir -p "$INSTALL_ROOT/$OLD_VERSION"
            mv "$INSTALL_ROOT.tmp"/* "$INSTALL_ROOT/$OLD_VERSION/"
            rm -rf "$INSTALL_ROOT.tmp"
            echo "Migration complete: $OLD_VERSION preserved"
        fi
    fi
fi

exit 0
```

#### postinstall Script

```bash
#!/bin/bash

INSTALL_ROOT="/usr/local/microsoft/azure-cli"
NEW_VERSION="__VERSION__"  # Replaced during build (e.g., 2.81.0)

echo "Finalizing Azure CLI ${NEW_VERSION} installation..."

# Create 'current' symlink pointing to new version
if [ -d "$INSTALL_ROOT/$NEW_VERSION" ]; then
    ln -sf "$NEW_VERSION" "$INSTALL_ROOT/current"
    echo "✓ Active version set to: $NEW_VERSION"
    echo "✓ Symlink: $INSTALL_ROOT/current -> $NEW_VERSION"
else
    echo "ERROR: Version directory not found: $INSTALL_ROOT/$NEW_VERSION"
    exit 1
fi

# Verify installation
if [ -L "$INSTALL_ROOT/current" ]; then
    ACTIVE_VERSION=$(readlink "$INSTALL_ROOT/current")
    echo ""
    echo "Azure CLI $NEW_VERSION installed successfully!"
    echo "Installation path: $INSTALL_ROOT/$NEW_VERSION"
    echo "Active version: $ACTIVE_VERSION"
    echo ""
    echo "Verify installation: az --version"
    echo ""
    
    # List all installed versions
    echo "Installed versions:"
    for version_dir in "$INSTALL_ROOT"/2.*/; do
        if [ -d "$version_dir" ]; then
            VERSION=$(basename "$version_dir")
            if [ "$VERSION" == "$ACTIVE_VERSION" ]; then
                echo "  • $VERSION (active)"
            else
                SIZE=$(du -sh "$version_dir" 2>/dev/null | cut -f1)
                echo "  • $VERSION ($SIZE)"
            fi
        fi
    done
    echo ""
    echo "To remove old versions, run:"
    echo "  $INSTALL_ROOT/cleanup-old-versions.sh"
else
    echo "ERROR: Failed to create 'current' symlink"
    exit 1
fi

exit 0
```

### 3. Cleanup Utility Script

**File:** `/usr/local/microsoft/azure-cli/cleanup-old-versions.sh`

```bash
#!/bin/bash

INSTALL_ROOT="/usr/local/microsoft/azure-cli"

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "This script requires sudo privileges to remove old versions."
    echo "Please run: sudo $0"
    exit 1
fi

# Get current active version
if [ ! -L "$INSTALL_ROOT/current" ]; then
    echo "ERROR: No active version found (missing 'current' symlink)"
    exit 1
fi

CURRENT_VERSION=$(readlink "$INSTALL_ROOT/current")

echo "================================================"
echo "Azure CLI Cleanup Utility"
echo "================================================"
echo ""
echo "Current active version: $CURRENT_VERSION"
echo ""
echo "Installed versions:"
echo ""

# List all versions with sizes
TOTAL_SIZE=0
OLD_VERSIONS=()

for version_dir in "$INSTALL_ROOT"/2.*/; do
    if [ -d "$version_dir" ]; then
        VERSION=$(basename "$version_dir")
        SIZE_KB=$(du -sk "$version_dir" | cut -f1)
        SIZE_HUMAN=$(du -sh "$version_dir" | cut -f1)
        
        if [ "$VERSION" == "$CURRENT_VERSION" ]; then
            echo "  ✓ $VERSION ($SIZE_HUMAN) [ACTIVE - will not be removed]"
        else
            echo "  ✗ $VERSION ($SIZE_HUMAN) [can be removed]"
            OLD_VERSIONS+=("$VERSION")
            TOTAL_SIZE=$((TOTAL_SIZE + SIZE_KB))
        fi
    fi
done

echo ""

# If no old versions found
if [ ${#OLD_VERSIONS[@]} -eq 0 ]; then
    echo "No old versions to remove. Only the active version ($CURRENT_VERSION) is installed."
    exit 0
fi

# Calculate total space to free
TOTAL_SIZE_HUMAN=$(echo "$TOTAL_SIZE" | awk '{printf "%.1f MB", $1/1024}')

echo "Total disk space to free: $TOTAL_SIZE_HUMAN"
echo ""
echo "WARNING: This will permanently delete ${#OLD_VERSIONS[@]} old version(s)."
echo ""
read -p "Proceed with cleanup? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Removing old versions..."

# Remove old versions
for VERSION in "${OLD_VERSIONS[@]}"; do
    echo "  Removing $VERSION..."
    rm -rf "$INSTALL_ROOT/$VERSION"
    if [ $? -eq 0 ]; then
        echo "    ✓ Removed successfully"
    else
        echo "    ✗ Failed to remove"
    fi
done

echo ""
echo "Cleanup complete!"
echo "Active version: $CURRENT_VERSION"
echo ""
```

### 4. PKG Build Script Changes

Update your PKG build script to install to versioned directory:

```python
# In scripts/release/macos/build_pkg_installer.py or equivalent

import os
import re

def get_cli_version():
    """Extract version from azure-cli package"""
    version_file = 'src/azure-cli/azure/cli/__main__.py'
    with open(version_file, 'r') as f:
        content = f.read()
        match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
        if match:
            return match.group(1)
    raise ValueError("Could not determine CLI version")

def build_pkg():
    version = get_cli_version()
    
    # Set versioned installation root
    install_root = f"/usr/local/microsoft/azure-cli/{version}"
    
    # Update preinstall/postinstall scripts with actual version
    with open('preinstall.sh', 'r') as f:
        preinstall = f.read().replace('__VERSION__', version)
    with open('preinstall.sh', 'w') as f:
        f.write(preinstall)
    
    with open('postinstall.sh', 'r') as f:
        postinstall = f.read().replace('__VERSION__', version)
    with open('postinstall.sh', 'w') as f:
        f.write(postinstall)
    
    # Build PKG with versioned install location
    # ... rest of PKG build logic
```

### 5. Homebrew Cask Formula

Update your Homebrew Cask to support versioned installations:

```ruby
cask "azure-cli-pkg" do
  version "2.81.0"
  sha256 "..."
  
  url "https://github.com/naga-nandyala/azure-cli-pkg-1/releases/download/v#{version}/azure-cli-#{version}.pkg"
  name "Azure CLI"
  desc "Microsoft Azure Command-Line Interface"
  homepage "https://docs.microsoft.com/cli/azure/"

  pkg "azure-cli-#{version}.pkg"

  postflight do
    # Show installation summary
    system_command "/bin/echo",
                   args: ["Azure CLI #{version} installed to /usr/local/microsoft/azure-cli/#{version}/"]
  end

  uninstall_preflight do
    # Show what version is being removed
    current = system_command("/usr/bin/readlink",
                             args: ["/usr/local/microsoft/azure-cli/current"],
                             print_stderr: false).stdout.strip
    ohai "Removing Azure CLI active version: #{current}"
  end

  uninstall pkgutil: "com.microsoft.azure.cli",
            delete:  [
              "/usr/local/bin/az",
              "/usr/local/microsoft/azure-cli/current",
            ]

  # Note: We don't delete version directories to allow manual cleanup
  
  zap trash: "~/.azure",
      rmdir: "/usr/local/microsoft/azure-cli"

  caveats <<~EOS
    Azure CLI #{version} has been installed to:
      /usr/local/microsoft/azure-cli/#{version}/

    Active version is managed via symlink:
      /usr/local/microsoft/azure-cli/current -> #{version}

    Multiple versions can coexist. To remove old versions:
      sudo /usr/local/microsoft/azure-cli/cleanup-old-versions.sh

    To manually switch versions (advanced):
      sudo ln -sf <version> /usr/local/microsoft/azure-cli/current
  EOS
end
```

### Understanding Homebrew Cask Lifecycle Hooks

Homebrew Cask provides several hooks that run at different stages. Here's what each does and when they execute:

#### 1. `postflight` Block

**When it runs:**
- ✅ After PKG installation completes (during `brew install --cask` or `brew upgrade --cask`)
- ❌ Does NOT run during `brew uninstall --cask`

**Purpose:**
- Display information to the user
- Verify installation was successful
- Show helpful next steps
- Log installation details

**Example in our Cask:**
```ruby
postflight do
  # Show installation summary
  system_command "/bin/echo",
                 args: ["Azure CLI #{version} installed to /usr/local/microsoft/azure-cli/#{version}/"]
end
```

**What this does:**
1. Runs AFTER the PKG's postinstall script completes
2. Prints a message showing where the new version was installed
3. Could optionally verify files exist, check symlinks, etc.

**Important Notes:**
- Runs with user privileges (NOT sudo) unless you explicitly use `sudo: true`
- Can execute shell commands using `system_command`
- Output is shown to user during installation
- Should be quick (don't do heavy operations here)

**Advanced postflight example:**
```ruby
postflight do
  # Verify installation
  current_link = "/usr/local/microsoft/azure-cli/current"
  if File.symlink?(current_link)
    target = File.readlink(current_link)
    puts "✓ Active version: #{target}"
  else
    opoo "Warning: 'current' symlink not found"
  end
  
  # Check if az command works
  system_command "/usr/local/bin/az",
                 args: ["--version"],
                 print_stdout: true,
                 print_stderr: true
end
```

#### 2. `uninstall_preflight` Block

**When it runs:**
- ✅ BEFORE uninstallation begins (during `brew uninstall --cask`)
- ✅ BEFORE upgrade begins (during `brew upgrade --cask`)
- ❌ Does NOT run during fresh `brew install --cask`

**Purpose:**
- Display what's about to be removed
- Give users a chance to back up data
- Show warnings or important information
- Verify state before removal

**Example in our Cask:**
```ruby
uninstall_preflight do
  # Show what version is being removed
  current = system_command("/usr/bin/readlink",
                           args: ["/usr/local/microsoft/azure-cli/current"],
                           print_stderr: false).stdout.strip
  ohai "Removing Azure CLI active version: #{current}"
end
```

**What this does:**
1. Reads the `current` symlink to see which version is active
2. Displays it to the user with `ohai` (info message in Homebrew style)
3. Helps user understand what's happening

**Important Notes:**
- Runs BEFORE the PKG's preinstall script during upgrades
- Runs BEFORE uninstall actions during removal
- Can read system state but shouldn't modify anything
- Good for displaying warnings or backing up user data

**Advanced uninstall_preflight example:**
```ruby
uninstall_preflight do
  current_link = "/usr/local/microsoft/azure-cli/current"
  
  if File.symlink?(current_link)
    current_version = File.readlink(current_link)
    ohai "Current Azure CLI version: #{current_version}"
    
    # Count total versions
    versions_dir = "/usr/local/microsoft/azure-cli"
    if Dir.exist?(versions_dir)
      version_count = Dir.glob("#{versions_dir}/2.*").length
      if version_count > 1
        opoo "You have #{version_count} versions installed."
        puts "Only the launcher and 'current' symlink will be removed."
        puts "To remove all versions, run: brew uninstall --zap --cask azure-cli-pkg"
      end
    end
  else
    opoo "No active Azure CLI installation found"
  end
end
```

#### 3. `uninstall` Directives

**When they run:**
- ✅ During `brew uninstall --cask` (NOT during upgrade)
- ❌ Do NOT run during `brew upgrade --cask`

**Purpose:**
- Actually remove files and packages
- Clean up system state

**Our configuration:**
```ruby
uninstall pkgutil: "com.microsoft.azure.cli",  # Removes PKG receipt
          delete:  [                            # Deletes specific files
            "/usr/local/bin/az",
            "/usr/local/microsoft/azure-cli/current",
          ]
```

**What each directive does:**

**`pkgutil:`**
- Removes the PKG receipt from macOS package database
- Does NOT delete any files
- Just tells macOS the package is "uninstalled"

**`delete:`**
- Removes specific files/symlinks
- In our case:
  - `/usr/local/bin/az` - The launcher script
  - `/usr/local/microsoft/azure-cli/current` - The active version symlink
- **Note:** We deliberately DON'T delete version directories (2.80.0/, 2.81.0/, etc.)

**Why we don't delete version directories in `uninstall`:**
- Follows Homebrew philosophy: "Don't delete user data"
- Allows users to manually inspect/recover files
- Versions can be large - users should explicitly choose to remove them
- Uses `zap` for complete removal instead

#### 4. `zap` Directive

**When it runs:**
- ✅ Only when user runs `brew uninstall --zap --cask azure-cli-pkg`
- User must explicitly request this (aggressive cleanup)

**Purpose:**
- Remove ALL traces of the application
- Delete user data, caches, preferences
- Complete system cleanup

**Our configuration:**
```ruby
zap trash: "~/.azure",                          # User's Azure config/cache
    rmdir: "/usr/local/microsoft/azure-cli"     # All version directories
```

**What this does:**
- `trash:` moves `~/.azure` to Trash (user can recover if needed)
- `rmdir:` removes the entire `/usr/local/microsoft/azure-cli/` directory tree
  - This includes ALL versions (2.80.0/, 2.81.0/, etc.)
  - This is the "nuclear option"

### Complete Installation/Upgrade/Uninstall Flow

#### Fresh Install: `brew install --cask azure-cli-pkg`

```
1. Download PKG
2. Run PKG installer
   ├─ PKG preinstall script
   ├─ PKG payload extraction → /usr/local/microsoft/azure-cli/2.81.0/
   └─ PKG postinstall script → creates 'current' symlink
3. Run Cask postflight block
   └─ Show success message
```

#### Upgrade: `brew upgrade --cask azure-cli-pkg`

```
1. Download new PKG (2.82.0)
2. Run Cask uninstall_preflight block
   └─ Show current version (2.81.0)
3. Run PKG installer
   ├─ PKG preinstall script → detects existing 2.81.0, preserves it
   ├─ PKG payload extraction → /usr/local/microsoft/azure-cli/2.82.0/
   └─ PKG postinstall script → updates 'current' symlink to 2.82.0
4. Run Cask postflight block
   └─ Show new version installed
   
Result: Both 2.81.0/ and 2.82.0/ exist, 'current' points to 2.82.0
```

#### Uninstall: `brew uninstall --cask azure-cli-pkg`

```
1. Run Cask uninstall_preflight block
   └─ Show what will be removed
2. Run Cask uninstall directives
   ├─ Remove PKG receipt (pkgutil)
   ├─ Delete /usr/local/bin/az
   └─ Delete /usr/local/microsoft/azure-cli/current symlink

Result: Versions (2.81.0/, 2.82.0/) remain, but az command and symlink removed
```

#### Complete Removal: `brew uninstall --zap --cask azure-cli-pkg`

```
1. Run Cask uninstall_preflight block
2. Run Cask uninstall directives (same as above)
3. Run Cask zap directive
   ├─ Move ~/.azure to Trash
   └─ Remove /usr/local/microsoft/azure-cli/ directory (all versions)

Result: Everything removed
```

### Best Practices for Cask Hooks

1. **postflight**: Keep it informational, don't modify system
2. **uninstall_preflight**: Warn users, show what's about to happen
3. **uninstall**: Remove minimal files (launcher + symlink only)
4. **zap**: Remove everything including user data

This design gives users control while following Homebrew conventions! 🎯

## User Experience Scenarios

### Scenario 1: Fresh Installation

```bash
# User installs 2.81.0
$ brew install --cask azure-cli-pkg

# Result:
/usr/local/microsoft/azure-cli/
├── 2.81.0/
└── current -> 2.81.0/

$ az --version
azure-cli                         2.81.0
```

### Scenario 2: Upgrade Installation

```bash
# User has 2.80.0, installs 2.81.0
$ brew upgrade --cask azure-cli-pkg

# Result:
/usr/local/microsoft/azure-cli/
├── 2.80.0/       # Preserved
├── 2.81.0/       # New
└── current -> 2.81.0/  # Updated

$ az --version
azure-cli                         2.81.0

# Old version preserved for rollback
$ ls -l /usr/local/microsoft/azure-cli/
drwxr-xr-x  2.80.0/
drwxr-xr-x  2.81.0/
lrwxr-xr-x  current -> 2.81.0/
```

### Scenario 3: Rollback to Previous Version

```bash
# User wants to rollback from 2.81.0 to 2.80.0
$ sudo ln -sf 2.80.0 /usr/local/microsoft/azure-cli/current

$ az --version
azure-cli                         2.80.0
```

### Scenario 4: Cleanup Old Versions

```bash
# User wants to free up disk space
$ sudo /usr/local/microsoft/azure-cli/cleanup-old-versions.sh

Azure CLI Cleanup Utility
================================================

Current active version: 2.81.0

Installed versions:

  ✓ 2.81.0 (346MB) [ACTIVE - will not be removed]
  ✗ 2.80.0 (345MB) [can be removed]

Total disk space to free: 345.0 MB

WARNING: This will permanently delete 1 old version(s).

Proceed with cleanup? [y/N] y

Removing old versions...
  Removing 2.80.0...
    ✓ Removed successfully

Cleanup complete!
Active version: 2.81.0
```

## Migration from Non-Versioned Installation

For users upgrading from the old non-versioned PKG installer, the preinstall script automatically detects and migrates:

**Before upgrade:**
```
/usr/local/microsoft/azure-cli/
├── bin/
└── lib/
```

**After upgrade (automatic migration):**
```
/usr/local/microsoft/azure-cli/
├── 2.80.0/     # Old installation moved here
├── 2.81.0/     # New installation
└── current -> 2.81.0/
```

The migration is transparent to the user - the `az` command continues to work without interruption.

## Comparison with Homebrew

| Feature | Homebrew Cellar | Proposed PKG Design |
|---------|----------------|---------------------|
| Versioned directories | `/opt/homebrew/Cellar/azure-cli/2.81.0/` | `/usr/local/microsoft/azure-cli/2.81.0/` |
| Active version management | Symlinks in `/opt/homebrew/bin/` | Symlink at `/usr/local/microsoft/azure-cli/current` |
| Side-by-side versions | ✅ Yes | ✅ Yes |
| Automatic cleanup | `brew cleanup` | `cleanup-old-versions.sh` |
| Version switching | `brew switch` (deprecated) | Manual symlink update |
| Rollback capability | ✅ Yes | ✅ Yes |
| Upgrade behavior | Preserves old version | Preserves old version |

## Homebrew Cask Upgrade Behavior

### What Happens During `brew upgrade --cask azure-cli-pkg`

When a user runs `brew upgrade --cask azure-cli-pkg`, Homebrew performs these steps:

1. **Check for Updates**
   ```bash
   # Homebrew checks if cask version is newer than installed version
   Current installed: 2.80.0
   Available version: 2.81.0
   → Upgrade needed
   ```

2. **Download New PKG**
   ```bash
   # Downloads new PKG from GitHub releases
   ==> Downloading azure-cli-2.81.0.pkg
   ✔ Downloaded to /Users/user/Library/Caches/Homebrew/downloads/
   ```

3. **Run Uninstall Steps** (from current cask version)
   ```bash
   # Runs uninstall_preflight block (if defined)
   # Does NOT run uninstall pkgutil or delete steps during upgrade
   # Only runs these during full uninstall (brew uninstall --cask)
   ```

4. **Install New PKG**
   ```bash
   # Runs the new PKG installer
   sudo installer -pkg azure-cli-2.81.0.pkg -target /
   
   # PKG's preinstall script runs:
   # - Detects existing installation
   # - Preserves old version (2.80.0)
   # - Prepares for new version installation
   
   # PKG payload is installed:
   # - Files copied to /usr/local/microsoft/azure-cli/2.81.0/
   
   # PKG's postinstall script runs:
   # - Updates 'current' symlink: current -> 2.81.0/
   # - Launcher /usr/local/bin/az continues to work
   ```

5. **Run Postflight** (from new cask version)
   ```bash
   # Runs postflight block (if defined)
   # Can verify installation, show messages, etc.
   ```

6. **Update Cask Metadata**
   ```bash
   # Homebrew records new version in its database
   /opt/homebrew/Caskroom/azure-cli-pkg/2.81.0/
   ```

### Key Differences: Cask Upgrade vs Cask Uninstall

| Action | `brew upgrade --cask` | `brew uninstall --cask` |
|--------|----------------------|------------------------|
| Downloads new PKG | ✅ Yes | ❌ No |
| Runs PKG installer | ✅ Yes | ❌ No |
| Runs `uninstall pkgutil` | ❌ No | ✅ Yes |
| Runs `uninstall delete` | ❌ No | ✅ Yes |
| Preserves old versions | ✅ Yes (via PKG scripts) | ❌ No |
| Runs `uninstall_preflight` | ✅ Yes | ✅ Yes |
| Runs `postflight` | ✅ Yes | ❌ No |

### Important: Cask Does NOT Handle Version Cleanup

**Homebrew Cask does not automatically remove old versions.** Each PKG installation is independent:

```bash
# After multiple upgrades:
/usr/local/microsoft/azure-cli/
├── 2.79.0/  ← Left by PKG installer
├── 2.80.0/  ← Left by PKG installer
├── 2.81.0/  ← Current version
└── current -> 2.81.0/

# User must manually clean up:
/usr/local/microsoft/azure-cli/cleanup-old-versions.sh
# OR manually:
sudo rm -rf /usr/local/microsoft/azure-cli/2.79.0
sudo rm -rf /usr/local/microsoft/azure-cli/2.80.0
```

### Why This Matters for PKG Design

1. **PKG preinstall must NOT delete old versions** - Let them accumulate like Homebrew Cellar
2. **PKG postinstall just updates `current` symlink** - Simple atomic switch
3. **Provide cleanup utility** - Users decide when to remove old versions
4. **Cask `uninstall` should offer cleanup** - Remove launcher and optionally all versions

### Recommended Cask `uninstall` Strategy

**Option 1: Remove only launcher and current symlink** (Conservative)
```ruby
uninstall delete: [
  "/usr/local/bin/az",
  "/usr/local/microsoft/azure-cli/current",
]

caveats "Versioned installations remain in /usr/local/microsoft/azure-cli/
To completely remove all versions:
  sudo rm -rf /usr/local/microsoft/azure-cli"
```

**Option 2: Remove everything** (Clean)
```ruby
uninstall pkgutil: "com.microsoft.azure.cli",
          delete:  [
            "/usr/local/bin/az",
            "/usr/local/microsoft/azure-cli",
          ]
```

**Recommendation**: Use Option 1 during testing, Option 2 for production. This matches Homebrew's philosophy of "leave data behind unless explicitly asked to remove."

## Benefits Summary

1. **User Control**: Users decide when to remove old versions
2. **Safety**: Old versions preserved for rollback
3. **Disk Space**: Users can see exactly how much space each version uses
4. **Consistency**: Follows familiar Homebrew patterns
5. **Flexibility**: Advanced users can switch versions manually
6. **Simplicity**: Single `/usr/local/bin/az` launcher works for all versions
7. **Atomic Upgrades**: New version fully installed before switching
8. **Cask-Friendly**: Works seamlessly with `brew upgrade --cask` workflow

## Testing Checklist

- [ ] Fresh install creates versioned directory
- [ ] Upgrade preserves old version
- [ ] `current` symlink updates correctly
- [ ] Launcher script works with versioned paths
- [ ] Cleanup script removes only old versions
- [ ] Rollback works by changing symlink
- [ ] Migration from non-versioned installation works
- [ ] Homebrew Cask uninstall removes launcher and current symlink
- [ ] `zap` command removes all versions
- [ ] Multiple upgrades (2.80 -> 2.81 -> 2.82) work correctly
