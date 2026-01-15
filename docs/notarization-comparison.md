# Notarization Approach Comparison: PKG vs Tar.gz

## Verification Summary

Verified that the tar.gz pipeline's notarization matches the PKG pipeline's proven approach.

---

## PKG Pipeline Notarization (Reference)

### Preparation
```powershell
# Copy signed PKG to workspace
Copy-Item -Path $signedPkg.FullName -Destination $(Pipeline.Workspace) -Force
```

### ESRP Notarization Task
```yaml
- task: SFP.build-tasks.custom-build-task-1.EsrpCodeSigning@5
  displayName: 'ESRP - Notarize ARM64 PKG with Apple'
  inputs:
    ConnectedServiceName: 'ame_esrp_connection'
    AppRegistrationClientId: '$(ESRPAppClientId)'
    AppRegistrationTenantId: '$(ESRPAppTenantId)'
    AuthAKVName: '$(ESRPKVName)'
    AuthCertName: '$(ESRPAuthCertName)'
    AuthSignCertName: '$(ESRPSignCertName)'
    FolderPath: '$(Pipeline.Workspace)'
    Pattern: '*fully-signed.pkg'
    signConfigType: 'inlineSignParams'
    inlineOperation: |
      [
        {
          "KeyCode": "CP-401337-Apple",
          "OperationCode": "MacAppNotarize",
          "ToolName": "sign",
          "ToolVersion": "1.0",
          "Parameters": {
            "BundleId": "$(BundleId)"          # Variable reference
          }
        }
      ]
    SessionTimeout: '60'
    MaxConcurrency: '50'
    MaxRetryAttempts: '5'
```

### Post-Notarization
```powershell
# Collect notarized PKG (sorted by LastWriteTime)
$notarizedPkg = Get-ChildItem -Path "$(Pipeline.Workspace)" -Filter "*fully-signed.pkg" -File | 
                Sort-Object LastWriteTime -Descending | 
                Select-Object -First 1

# Rename and publish
$notarizedName = $notarizedPkg.Name -replace 'fully-signed\.pkg$', 'notarized.pkg'
Copy-Item -Path $notarizedPkg.FullName -Destination $newPath -Force

# Generate SHA256
$hash = Get-FileHash -Path $newPath -Algorithm SHA256
```

### Stapling (PKG-Specific)
```bash
# Staple notarization ticket to PKG
xcrun stapler staple "$PKG_PATH"
xcrun stapler validate "$PKG_PATH"
```

**Note**: Stapling embeds the notarization ticket in the PKG file, allowing fully offline verification. **This is not possible with tar.gz**.

---

## Tar.gz Pipeline Notarization (Updated)

### Preparation
```powershell
# Copy signed tar.gz to workspace
$signedTarball = Get-ChildItem -Path "$(Pipeline.Workspace)/signed-tarball" -Filter "*-signed.tar.gz" | Select-Object -First 1
Copy-Item -Path $signedTarball.FullName -Destination $(Pipeline.Workspace) -Force
```

### ESRP Notarization Task
```yaml
- task: SFP.build-tasks.custom-build-task-1.EsrpCodeSigning@5
  displayName: 'ESRP - Notarize Tar.gz with Apple'
  inputs:
    ConnectedServiceName: 'ame_esrp_connection'
    AppRegistrationClientId: '$(ESRPAppClientId)'
    AppRegistrationTenantId: '$(ESRPAppTenantId)'
    AuthAKVName: '$(ESRPKVName)'
    AuthCertName: '$(ESRPAuthCertName)'
    AuthSignCertName: '$(ESRPSignCertName)'
    FolderPath: '$(Pipeline.Workspace)'
    Pattern: '*-signed.tar.gz'                   # Direct tar.gz pattern
    signConfigType: 'inlineSignParams'
    inlineOperation: |
      [
        {
          "KeyCode": "CP-401337-Apple",
          "OperationCode": "MacAppNotarize",
          "ToolName": "sign",
          "ToolVersion": "1.0",
          "Parameters": {
            "BundleId": "${{ parameters.BundleId }}"   # Parameter reference
          }
        }
      ]
    SessionTimeout: '60'
    MaxConcurrency: '50'
    MaxRetryAttempts: '5'
```

### Post-Notarization
```powershell
# Collect notarized tar.gz (sorted by LastWriteTime)
$notarizedTarball = Get-ChildItem -Path "$(Pipeline.Workspace)" -Filter "*-signed.tar.gz" -File | 
                    Sort-Object LastWriteTime -Descending | 
                    Select-Object -First 1

# Rename and publish
$notarizedName = $notarizedTarball.Name -replace '-signed\.tar\.gz$', '-signed-notarized.tar.gz'
Copy-Item -Path $notarizedTarball.FullName -Destination $newPath -Force

# Generate SHA256
$hash = Get-FileHash -Path $newPath -Algorithm SHA256
```

### Stapling (Not Applicable)
**Cannot staple tar.gz** - notarization ticket stored on Apple's servers only.
- First run requires internet to verify ticket
- Subsequent runs use cached ticket (works offline)

---

## Key Differences Summary

| Aspect | PKG Pipeline | Tar.gz Pipeline |
|--------|-------------|-----------------|
| **File Format** | `.pkg` | `.tar.gz` |
| **Direct Notarization** | ✅ Yes | ✅ Yes (fixed - no wrapper needed) |
| **BundleId Reference** | `$(BundleId)` (variable) | `${{ parameters.BundleId }}` (parameter) |
| **Pattern** | `'*fully-signed.pkg'` | `'*-signed.tar.gz'` |
| **Stapling** | ✅ Supported | ❌ Not supported by format |
| **Offline Verification** | ✅ After stapling | ❌ Ticket on Apple servers only |
| **First Run Requirement** | None (stapled) | Internet (to fetch ticket) |
| **Subsequent Runs** | Fully offline | Offline (ticket cached) |

---

## Changes Made

### ❌ Original Approach (Incorrect)
```powershell
# Wrapped tar.gz in ZIP for notarization
Compress-Archive -Path $tarballPath.FullName -DestinationPath "azure-cli-notarize.zip" -Force

# Notarized the ZIP wrapper
Pattern: 'azure-cli-notarize.zip'

# Extracted tar.gz from notarized ZIP
Expand-Archive -Path $wrapperZip -DestinationPath $extractPath
```

**Problems**:
- Unnecessary complexity
- ZIP wrapper adds confusion
- Not clear if notarization applies to inner tar.gz or wrapper

### ✅ Fixed Approach (Correct)
```powershell
# Copy tar.gz directly to workspace
Copy-Item -Path $signedTarball.FullName -Destination $(Pipeline.Workspace) -Force

# Notarize tar.gz directly (just like PKG)
Pattern: '*-signed.tar.gz'

# Collect notarized tar.gz directly
Get-ChildItem -Path "$(Pipeline.Workspace)" -Filter "*-signed.tar.gz"
```

**Benefits**:
- Simple and clear
- Matches PKG pipeline pattern
- Direct notarization of tar.gz (Apple supports this)
- No extraction needed

---

## Verification Checklist

- [x] ESRP configuration matches PKG pipeline
- [x] KeyCode: `CP-401337-Apple` ✓
- [x] OperationCode: `MacAppNotarize` ✓
- [x] SessionTimeout: `'60'` ✓
- [x] MaxConcurrency: `'50'` ✓
- [x] MaxRetryAttempts: `'5'` ✓
- [x] Pattern uses single-line format ✓
- [x] BundleId parameter correctly referenced ✓
- [x] Post-processing matches PKG pattern ✓
- [x] Removed unnecessary ZIP wrapper ✓
- [x] Direct tar.gz notarization ✓

---

## How Notarization Works

### For Both PKG and Tar.gz

1. **Submission**: ESRP submits signed archive to Apple's notarization service
2. **Scanning**: Apple scans for malware and validates signatures
3. **Ticket Generation**: Apple generates notarization ticket with unique ID
4. **Ticket Storage**: Apple stores ticket on their servers

### PKG: Stapling Advantage

```bash
# Embed ticket in PKG
xcrun stapler staple azure-cli.pkg

# Verify stapled ticket
xcrun stapler validate azure-cli.pkg

# Result: PKG contains ticket → works fully offline
```

### Tar.gz: No Stapling

- **Cannot embed ticket** in tar.gz format
- Ticket remains on Apple's servers
- **First run**: macOS fetches ticket from Apple (requires internet)
- **Subsequent runs**: Ticket cached locally (works offline)

### Verification Process (End User)

**PKG (Stapled)**:
```bash
# 1. Check signature
codesign -v azure-cli.pkg

# 2. Check notarization (offline)
spctl -a -v --type install azure-cli.pkg
# Result: "accepted" (reads stapled ticket)
```

**Tar.gz (Not Stapled)**:
```bash
# 1. Extract
tar -xzf azure-cli.tar.gz

# 2. Check signature (offline)
codesign -v bin/python3.13

# 3. Check notarization (requires internet first time)
spctl -a -v --type execute bin/python3.13
# Result: "accepted" (fetches ticket from Apple)

# 4. Subsequent checks work offline (ticket cached)
```

---

## Recommendations

### For Production Distribution

**Best**: Use `.pkg` installer
- ✅ Can be stapled
- ✅ Works completely offline after stapling
- ✅ Better user experience (no internet requirement)

**Acceptable**: Use signed + notarized `.tar.gz`
- ⚠️ Requires internet on first run
- ✅ Subsequent use works offline
- ✅ Good for Homebrew distribution (strips quarantine)

### For Homebrew

**Either works**:
- Homebrew strips quarantine attribute during installation
- Signed + notarized provides authenticity verification
- Unsigned technically works but not recommended

---

## Pipeline Comparison Result

✅ **Notarization approaches now match**:
- Both use direct file notarization (no wrappers)
- Both use identical ESRP configuration
- Both follow same post-processing pattern
- Only difference: PKG adds stapling step (tar.gz can't support it)

**Status**: Ready for testing
