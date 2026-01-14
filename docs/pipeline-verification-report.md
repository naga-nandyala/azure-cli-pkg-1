# Pipeline Configuration Verification Report

## Comparison: macos-tarball-signing-test.yml vs macos-pkg-release-complete.yml

**Date**: 2024
**Purpose**: Verify tar.gz signing pipeline matches the working PKG pipeline configuration

---

## ✅ CORRECT CONFIGURATIONS

### 1. Service Connection
- **Status**: ✅ Correct
- **Value**: `'ame_esrp_connection'`
- **Reference**: PKG line 391

### 2. Variable Names
- **Status**: ✅ Correct
- **Values**:
  - `$(ESRPAppClientId)`
  - `$(ESRPAppTenantId)`
  - `$(ESRPKVName)`
  - `$(ESRPAuthCertName)`
  - `$(ESRPSignCertName)`
- **Reference**: PKG lines 392-396

### 3. ESRP KeyCode
- **Status**: ✅ Correct
- **Value**: `"CP-401337-Apple"`
- **Reference**: PKG line 404

### 4. Operation Codes
- **Status**: ✅ Correct
- **Signing**: `"MacAppDeveloperSign"`
- **Notarization**: `"MacAppNotarize"`
- **Reference**: PKG lines 405, 848

### 5. JSON Structure
- **Status**: ✅ Correct
- **Order**: KeyCode → OperationCode → ToolName → ToolVersion → Parameters
- **Reference**: PKG lines 403-410

### 6. Session Timeouts
- **Status**: ✅ Correct
- **Signing**: `SessionTimeout: '120'` (line 410 in PKG)
- **Notarization**: `SessionTimeout: '60'` (line 856 in PKG)
- **Implementation**: Tar.gz pipeline matches these values

### 7. Concurrency Settings
- **Status**: ✅ Correct
- **MaxConcurrency**: `'50'`
- **MaxRetryAttempts**: `'5'`
- **Reference**: PKG lines 411-412

### 8. Hardening Parameters
- **Status**: ✅ Correct
- **Value**: `"Hardening": "--options=runtime"`
- **Reference**: PKG line 408

### 9. BundleId for Notarization
- **Status**: ✅ Correct
- **Value**: `"BundleId": "${{ parameters.BundleId }}"`
- **Reference**: PKG line 851

---

## 🔍 KEY DIFFERENCES (BY DESIGN)

### 1. Pattern Matching Format

**PKG Pipeline (line 399)**:
```yaml
Pattern: '*.zip'
```
- Single-line string format
- Matches ZIP archives (one per binary)

**Tar.gz Pipeline (lines 238-242)**:
```yaml
Pattern: |
  **/python3.13
  **/python3
  **/python
  **/*.dylib
  **/*.so
```
- Multi-line YAML format
- Matches specific file patterns directly
- **Note**: Multi-line format is valid YAML and commonly used in Azure Pipelines

**Analysis**: Both formats are valid. The PKG approach is more robust (ZIP-per-file), but the tar.gz approach is simpler for testing purposes.

### 2. Signing Approach

**PKG Pipeline**:
- Creates individual ZIP file for each binary
- Signs ZIP archives
- Extracts signed binaries from ZIPs

**Tar.gz Pipeline**:
- Extracts all binaries to flat directory
- Signs binaries directly using pattern matching
- Copies signed binaries back to original structure

**Analysis**: PKG approach is production-grade; tar.gz approach is acceptable for testing/demonstration.

### 3. File Structure Handling

**PKG Pipeline**:
- Maintains file mapping JSON
- Precise reconstruction of original structure
- More error handling

**Tar.gz Pipeline**:
- Simpler: copy unsigned structure, then overlay signed files
- Less metadata tracking
- Adequate for test purposes

---

## ⚠️ CONSIDERATIONS

### Pattern Matching in ESRP

The PKG pipeline uses a simple glob (`*.zip`) because:
1. Each binary is already in its own ZIP file
2. ESRP can reliably find all ZIPs
3. No risk of missing files

The tar.gz pipeline uses multi-pattern matching because:
1. Files are in a flat directory
2. Need to match multiple file types
3. Python executable has multiple symlink names

**Recommendation**: Current approach should work, but monitor ESRP logs for any pattern matching issues.

### File Size Considerations

**PKG Pipeline**:
- Signs individual 500KB-2MB ZIP files
- ESRP handles one file at a time efficiently

**Tar.gz Pipeline**:
- Signs binaries in place (1-20MB each)
- ESRP may process multiple files concurrently
- MaxConcurrency: 50 should handle this

---

## 📋 VERIFICATION CHECKLIST

- [x] Service connection name matches
- [x] All variable names match
- [x] KeyCode is correct (CP-401337-Apple)
- [x] Operation codes correct (MacAppDeveloperSign, MacAppNotarize)
- [x] JSON structure order matches
- [x] Session timeouts correct (120s signing, 60s notarization)
- [x] Concurrency settings match
- [x] Hardening parameters correct
- [x] BundleId parameter correct for notarization
- [x] Pattern format is valid (though different approach)

---

## ✅ CONCLUSION

**Status**: **PIPELINE IS CORRECTLY CONFIGURED**

All ESRP authentication, operation parameters, and timeouts match the working PKG pipeline. The differences in Pattern format and signing approach are architectural choices, not configuration errors.

**Confidence Level**: High - All critical parameters verified against production PKG pipeline.

**Ready for Execution**: Yes

### What to Watch During Execution

1. **ESRP Signing Stage**: Verify Pattern matching finds all intended files
2. **Notarization Stage**: Ensure ZIP wrapper approach works correctly
3. **Test Stage**: Confirm all three variants behave as expected with quarantine

### If Issues Arise

1. Check ESRP task logs for pattern matching details
2. Verify files are in expected locations before ESRP tasks
3. Confirm ESRP service has permissions for the subscription
4. Review AME ESRP Variable Group values are set correctly

---

## 📚 References

- **PKG Pipeline**: `.azure-pipelines/macos-pkg-release-complete.yml`
  - Binary signing: Lines 383-412
  - PKG signing: Lines 712-737
  - Notarization: Lines 831-856
  
- **Tar.gz Pipeline**: `.azure-pipelines/macos-tarball-signing-test.yml`
  - Binary signing: Lines 229-260
  - Notarization: Lines 466-492

- **ESRP Documentation**: Internal Microsoft ESRP service documentation
- **Apple Developer**: Code signing and notarization requirements

---

*Report generated by verification process comparing tar.gz test pipeline against production PKG pipeline*
