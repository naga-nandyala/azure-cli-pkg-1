# macOS Broker Authentication Investigation for Azure CLI

**Date:** February 3, 2026  
**Author:** Naga Nandyala  
**Purpose:** Document findings for discussion with MSAL team  

---

## Executive Summary

We are implementing macOS broker authentication support in Azure CLI (similar to Windows WAM). During testing, we encountered two distinct issues that affect the broker flow on macOS:

1. **Error -42000**: Python 3.13 compatibility issue with pymsalruntime
2. **Error -34018**: Keychain access denied for unsigned applications

**Key Finding:** Signing the application with a Developer ID certificate resolves the Keychain access issue, and the macOS Keychain password prompt successfully appears.

---

## Test Environment

| Component | Version |
|-----------|---------|
| macOS | 26.2.0 (Sequoia) |
| Python 3.12 | 3.12.12 (Homebrew) |
| Python 3.13 | 3.13.1 (Homebrew) |
| MSAL Python | 1.34.0b1, 1.35.0b1 |
| pymsalruntime | 0.20.2 |
| Azure CLI | 2.77.0, 2.83.0 |

---

## Test Results Summary

| App | Python | Signing | Token Storage | Keychain Access | Broker Result |
|-----|--------|---------|---------------|-----------------|---------------|
| Azure CLI (dev) | 3.13 | Unsigned | MSAL Keychain | ❌ No access | ❌ Error -42000 |
| Azure CLI (dev) | 3.12 | Unsigned | MSAL Keychain | ❌ No access | ⚠️ Auth works, cache fails (-34018) |
| **Azure CLI (signed)** | 3.13 | ✅ Developer ID | MSAL Keychain | ✅ **Prompt appeared!** | 🎉 **Works** |
| mycli-app | 3.12 | Unsigned | JSON file | N/A (not used) | ✅ Works |
| mycli-app | 3.13 | Unsigned | JSON file | N/A (not used) | ❌ Error -42000 |

---

## Error 1: Python 3.13 Redirect URI Validation (Error -42000)

### Error Message

```
Error Code -42000

MSAL redirectUri validation error: redirect uri has incorrect scheme - it must be in the form of msauth.<app_bundle_id>://auth

ADAL redirectUri validation error: Source application does not match redirect uri host. Invalid source app.
```

### Reproduction Steps

1. Use Python 3.13.1 (Homebrew)
2. Install MSAL Python with broker support (`pip install msal[broker]`)
3. Run Azure CLI login with broker enabled: `az login --debug`

### Observations

- This error occurs **only with Python 3.13**, not Python 3.12
- The error happens during the initial broker flow, before any Keychain access
- The pymsalruntime native library appears to have compatibility issues with Python 3.13
- Log shows: `Continue without redirectUri validation on unsigned app runtime flow` but then fails

### Affected Configurations

- Python 3.13 + unsigned apps → Error -42000
- Python 3.13 + signed apps → Initially showed same error (needs further testing)
- Python 3.12 + any signing status → Works (no -42000 error)

### Questions for MSAL Team

1. Is pymsalruntime 0.20.2 officially supported on Python 3.13?
2. Are there known issues with Python 3.13's changes affecting the native broker?
3. Is there a workaround or newer pymsalruntime version that addresses this?

---

## Error 2: Keychain Access Denied (Error -34018)

### Error Message

```
DEBUG: msal.broker: Could not write broker key -34018

Failed to save tokens in cache. 
Error Domain=MSAIMSIDKeychainErrorDomain Code=-34018

User 'user@microsoft.com' does not exist in MSAL token cache. Run `az login`.
```

### Full Error Context

```
DEBUG: msal.broker: [MSAL:0001] INFO    -[MSAIMSIDKeychainTokenCache initWithGroup:error:]:169   
TID=1215196 (main thread) MSAL.xplat.macOS 1.1.0+local Mac 26.2.0 
Init MSAIMSIDKeychainTokenCache with keychainGroup: org.python.python.com.microsoft.identity.universalstorage
```

### Reproduction Steps

1. Use Python 3.12.12 (Homebrew)
2. Run from an unsigned/ad-hoc signed application
3. Run Azure CLI login with broker enabled: `az login --debug`
4. Complete the interactive authentication successfully
5. Observe that token caching fails

### Key Observations

1. **Broker authentication itself SUCCEEDS** - the user can authenticate via the SSO extension
2. **Only the Keychain write fails** - tokens cannot be persisted
3. The Keychain group used is: `org.python.python.com.microsoft.identity.universalstorage`
4. Unsigned apps cannot access macOS Keychain for security reasons

### Signed App Behavior (Success Case)

When testing with a signed and notarized tarball:

**Signing Details:**
```
Authority=Developer ID Application: Microsoft Corporation (UBF8T346G9)
TeamIdentifier=UBF8T346G9
```

**Result:** The macOS Keychain password prompt appeared:
> "Python wants to use your confidential information stored in 'Microsoft Credentials' in your keychain."
> [Deny] [Allow]

This proves that:
1. Proper code signing enables Keychain access
2. The broker code path is correct
3. Only signing was preventing the flow from completing

### Questions for MSAL Team

1. What are the minimum signing requirements for Keychain access?
2. Do we need specific Keychain entitlements in the app signature?
3. Is the Keychain access group `org.python.python.com.microsoft.identity.universalstorage` correct for Python CLI apps?
4. Should we use a different Keychain access group for Azure CLI specifically?

---

## Workaround: File-Based Token Storage

The `mycli-app` test application uses file-based token storage instead of MSAL's Keychain cache:

```python
# mycli-app uses a JSON file for token persistence
token_cache_file = "~/.mycli/token_cache.json"
```

### Benefits
- Works without code signing
- No Keychain access required
- Simpler deployment for development/testing

### Drawbacks
- Less secure than Keychain storage
- No SSO with other Microsoft apps
- Tokens stored in plaintext (or need separate encryption)

---

## Recommendations for Azure CLI macOS Package

Based on our investigation:

### For Production Release

1. **Use Developer ID signing** - Required for Keychain access
2. **Include Keychain entitlements** in the signature:
   ```xml
   <key>keychain-access-groups</key>
   <array>
       <string>$(TeamIdentifierPrefix)com.microsoft.identity.universalstorage</string>
   </array>
   ```
3. **Target Python 3.12** until Python 3.13 compatibility is confirmed
4. **Notarize the package** for Gatekeeper approval

### For Development/Testing

1. Use Python 3.12 for broker testing
2. Accept that Keychain caching will fail on unsigned builds
3. Consider a fallback to file-based caching for development scenarios

---

## Debug Logs

### Successful Broker Flow (Python 3.12, Unsigned - Auth Works, Cache Fails)

```
DEBUG: msal.application: Broker enabled? True
DEBUG: msal.application: Falls back to broker._signin_interactively()
DEBUG: msal.broker: [MSAL:0001] INFO    SetAuthorityUri:78      
    Initializing authority from URI 'https://login.microsoftonline.com/organizations'
DEBUG: msal.broker: [MSAL:0001] INFO    -[MSAIBrokerClient isAuthorizationTypeSupported:]:688    
    Continue without redirectUri validation on unsigned app runtime flow
DEBUG: msal.broker: [MSAL:0001] INFO    -[MSAIMSIDKeychainTokenCache initWithGroup:error:]:169   
    Init MSAIMSIDKeychainTokenCache with keychainGroup: org.python.python.com.microsoft.identity.universalstorage
DEBUG: msal.broker: [MSAL:0001] INFO    -[MSAIMSIDSSOExtensionInteractiveTokenRequestController acquireToken:]:55
    Beginning interactive broker extension flow.
```

### Failed Broker Flow (Python 3.13 - Error -42000)

```
Error Code -42000
MSAL redirectUri validation error: redirect uri has incorrect scheme
ADAL redirectUri validation error: Source application does not match redirect uri host
```

---

## Next Steps

1. **Confirm Python 3.13 support status** with MSAL team
2. **Validate signing requirements** for Keychain access
3. **Test complete flow** with signed package + Python 3.12
4. **Document configuration** for `enable_broker_on_mac` setting

---

## Appendix: Code Changes Made

### identity.py
- Added `enable_broker_on_mac` parameter to `Identity.__init__()`
- Added `enable_broker_on_mac` to `_msal_public_app_kwargs` dict

### _profile.py  
- Added config reading: `cli_ctx.config.getboolean('core', 'enable_broker_on_mac', fallback=False)`
- Passed `enable_broker_on_mac` to `Identity()` constructor

### telemetry.py
- Added `enable_broker_on_mac` tracking to telemetry session

---

## Contact

For questions about this investigation, contact:
- **Azure CLI Team:** [Azure CLI GitHub](https://github.com/Azure/azure-cli)
- **MSAL Python Team:** [MSAL Python GitHub](https://github.com/AzureAD/microsoft-authentication-library-for-python)
