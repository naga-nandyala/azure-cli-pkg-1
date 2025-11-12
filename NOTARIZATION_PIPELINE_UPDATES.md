# Notarization Pipeline Updates

## Summary
Updated `macos-pkg-notarize.yml` to consume the **fully-signed PKG** from the `macos-pkg-sign-all` pipeline (Build #282373).

## Changes Made

### 1. Updated Source Build Parameters
```yaml
# BEFORE:
SourceBuildId: '282182'
SourcePipelineName: 'macos-pkg-sign-release'

# AFTER:
SourceBuildId: '282373'
SourcePipelineName: 'macos-pkg-sign-all'
```

### 2. Updated Artifact Name
```yaml
# BEFORE:
artifactName: 'signed-macos-pkg'

# AFTER:
artifactName: 'fully-signed-macos-pkg'
```
This matches the artifact published by `macos-pkg-sign-all` in Stage 4.

### 3. Updated PKG File Pattern
```yaml
# BEFORE:
Pattern: 'azure-cli-*-macos-arm64-signed.pkg'

# AFTER:
Pattern: '*fully-signed.pkg'
```
This matches the filename: `azure-cli-2.0.0-macos-arm64-fully-signed.pkg`

### 4. Updated File Search Logic
- Changed from looking for `*-signed.pkg` to `*fully-signed.pkg`
- Updated rename logic: `fully-signed.pkg` → `notarized.pkg`
- Added better error handling and file detection fallbacks

## Pipeline Flow

### Before (Old):
```
macos-pkg-sign-release (Build 282182)
  └─ signed-macos-pkg artifact
      └─ azure-cli-*-signed.pkg
          ↓
macos-pkg-notarize (downloads artifact)
  └─ Apple Notarization via ESRP
      └─ notarized-macos-pkg artifact
```

### After (Current):
```
macos-pkg-sign-all (Build 282373)
  ├─ Stage 1: Extract binaries
  ├─ Stage 2: Sign binaries (ZIP workaround)
  ├─ Stage 3: Repackage PKG with signed binaries
  └─ Stage 4: Sign PKG container
      └─ fully-signed-macos-pkg artifact
          └─ azure-cli-2.0.0-macos-arm64-fully-signed.pkg
              ↓
macos-pkg-notarize (downloads artifact from Build 282373)
  ├─ Downloads: azure-cli-2.0.0-macos-arm64-fully-signed.pkg (~48 MB)
  ├─ ESRP Operation: MacAppNotarize (Apple notarization service)
  └─ Outputs: azure-cli-2.0.0-macos-arm64-notarized.pkg
      └─ notarized-macos-pkg artifact
```

## Artifact URL
The fully-signed PKG is downloaded from:
```
https://artprodwus21.artifacts.visualstudio.com/A7b238909-6802-4b65-b90d-184bca47f458/
9b6b54d1-85ce-4ff5-8faa-608b4a183fc6/_apis/artifact/
cGlwZWxpbmVhcnRpZmFjdDovL2F6Y2xpdG9vbHMvcHJvamVjdElkLzliNmI1NGQxLTg1Y2UtNGZmNS04ZmFhLTYwOGI0YTE4M2ZjNi9idWlsZElkLzI4MjM3My9hcnRpZmFjdE5hbWUvZnVsbHktc2lnbmVkLW1hY29zLXBrZw2/
content?format=file&subPath=%2Fazure-cli-2.0.0-macos-arm64-fully-signed.pkg
```

## What Gets Notarized

The PKG being notarized now has **three levels of signing** completed:

### Level 1: PKG Container ✅
- Signed in Stage 4 of `macos-pkg-sign-all`
- Signature: Developer ID Installer (from ESRP)

### Level 2: Component PKG ✅
- Component PKG inside distribution PKG
- Also signed with Developer ID Installer

### Level 3: Individual Binaries ✅
- All ~150 dylibs and executables
- Signed in Stage 2 using ZIP workaround
- Signature: Developer ID Application + Runtime hardening

## Notarization Process

### What Happens:
1. **Download**: Gets fully-signed PKG from Build 282373
2. **Prepare**: Copies PKG to workspace for ESRP
3. **Notarize**: ESRP submits to Apple's notary service
   - Apple scans for malicious content
   - Verifies all signatures
   - Issues notarization ticket
   - Returns notarized PKG (ticket may be stapled)
4. **Verify**: Runs on macOS to confirm notarization
   - `pkgutil --check-signature` - Checks signatures
   - `spctl -a -vv -t install` - Checks notarization
   - `stapler validate` - Checks stapled ticket

### Final Output:
**Artifact**: `notarized-macos-pkg`
- File: `azure-cli-2.0.0-macos-arm64-notarized.pkg`
- Status: ✅ Fully signed + ✅ Apple notarized
- Ready for: Public distribution to macOS users

## Usage

### Running the Pipeline:
```bash
# Parameters (defaults now correct):
SourceBuildId: 282373  # The macos-pkg-sign-all build
SourcePipelineName: macos-pkg-sign-all
AzureCliVersion: 2.0.0
BundleId: com.microsoft.azure.cli
OfficialBuild: true  # Enables ESRP notarization
```

### Verifying the Result:
```bash
# Download the notarized PKG artifact
# Then on macOS:

# Check signature
pkgutil --check-signature azure-cli-2.0.0-macos-arm64-notarized.pkg

# Check notarization
spctl -a -vv -t install azure-cli-2.0.0-macos-arm64-notarized.pkg

# Check stapled ticket
stapler validate azure-cli-2.0.0-macos-arm64-notarized.pkg

# Test installation
sudo installer -pkg azure-cli-2.0.0-macos-arm64-notarized.pkg -target /
```

## Benefits

### For Distribution:
- ✅ macOS Gatekeeper allows installation without warnings
- ✅ No "unidentified developer" prompts
- ✅ Users can install via double-click
- ✅ Enterprise deployment tools accept it

### For Security:
- ✅ All binaries signed with Developer ID
- ✅ Runtime hardening enabled (can't load unsigned code)
- ✅ PKG container signed (prevents tampering)
- ✅ Apple-verified (notarization scan passed)

### For Compliance:
- ✅ Meets macOS Catalina+ requirements
- ✅ Follows Apple best practices
- ✅ Traceable to Microsoft identity
- ✅ Full audit trail via ESRP

## Next Steps

1. **Test the Pipeline**:
   - Run `macos-pkg-notarize.yml` with default parameters
   - Monitor for successful ESRP notarization
   - Download and verify the notarized PKG

2. **Validate on macOS**:
   - Install the notarized PKG
   - Run `az --version` to verify
   - Check all commands work correctly

3. **Production Release**:
   - Once verified, this PKG can be distributed publicly
   - Upload to download servers
   - Update installation documentation

## Troubleshooting

### If Download Fails:
- Verify Build 282373 has `fully-signed-macos-pkg` artifact
- Check artifact is ~48 MB (not bytes/KB)
- Ensure pipeline has access to source build

### If Notarization Fails:
- Check ESRP connection (`ame_esrp_connection`)
- Verify Bundle ID is correct: `com.microsoft.azure.cli`
- Check PKG is fully signed before notarization
- Review ESRP task logs for Apple errors

### If Verification Fails:
- Use `pkgutil --check-signature` first
- Then `spctl` to check notarization
- Notarization can take time to propagate
- Stapling may occur separately

## Files Modified

- `.azure-pipelines/macos-pkg-notarize.yml`
  - Updated default parameters (Build ID, pipeline name)
  - Changed artifact name to `fully-signed-macos-pkg`
  - Updated file patterns to match new naming
  - Enhanced error handling and logging

## Testing Commands

```powershell
# Verify the PKGs locally (Windows)
.\verify-pipeline-pkgs.ps1

# Or with custom paths:
.\verify-pipeline-pkgs.ps1 `
  -Pkg1 ".\azure-cli-2.0.0-macos-arm64-fully-signed.pkg" `
  -Pkg2 ".\azure-cli-2.0.0-macos-arm64-notarized.pkg"
```

```bash
# On macOS - full verification
pkgutil --check-signature azure-cli-2.0.0-macos-arm64-notarized.pkg
spctl -a -vv -t install azure-cli-2.0.0-macos-arm64-notarized.pkg
stapler validate azure-cli-2.0.0-macos-arm64-notarized.pkg

# Extract and check binary signatures
xar -xf azure-cli-2.0.0-macos-arm64-notarized.pkg
cd azure-cli-component-2.0.0-macos-arm64.pkg
cat Payload | gunzip -dc | cpio -i
codesign -vv --deep --strict <path-to-binary>
```
