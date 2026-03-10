# Investigation: No Browser Fallback When Broker is Configured but Unavailable (S3-5)

| | |
|---|---|
| **Date** | 2026-03-10 |
| **Tester** | naganandyala |
| **Version** | azure-cli 2.84.0 (cask install) |
| **Config** | `core.enable_broker_on_mac = true` |
| **Machine** | ARM64 macOS 26.3.1 |
| **Status** | **BUG CONFIRMED** |

---

## 1. Summary

When `core.enable_broker_on_mac = true` is set but the broker (Company Portal + macOS SSO Extension) is absent, `az login` fails with a transient broker error (exit code 1) and suggests `az logout; az login` as the fix. This suggestion loops — it runs `az login` with broker still enabled, hitting the same error again. There is **no automatic fallback to browser-based login**.

**Expected**: graceful browser fallback or a clear actionable message pointing to `az config set core.enable_broker_on_mac=false`.

**Actual**: exit:1, misleading recovery suggestion.

---

## 2. Reproduction Steps

1. Install azure-cli via cask: `brew install --cask naga-nandyala/mycli-app/azure-cli`
2. Set broker config: `az config set core.enable_broker_on_mac=true`
3. Remove Company Portal: `sudo rm -rf "/Applications/Company Portal.app"`
4. Verify SSO extension gone: `pluginkit -m -i com.microsoft.CompanyPortalMac.ssoextension` → (no output)
5. Run: `az login`

---

## 3. Observed Behaviour

```
$ az login
Select the account you want to log in with. ...
The authorization attempt failed with a transient error
Error was thrown in sourceArea: Broker. Status: Response_Status.Status_TransientError, Error code: 1000, Tag: 508175367
Run the command below to authenticate interactively; additional arguments may be added as needed:
az logout
az login
exit:1
```

Key observations:
- No browser tab opened
- No device-code fallback
- CLI exits with code 1 (hard failure)
- The printed `az logout; az login` recovery path loops — re-runs `az login` with `enable_broker_on_mac=true` still set → same error

---

## 4. Root Cause Trace

### 4.1 Error source — MSAL broker layer

The error originates inside the MSAL runtime (native broker integration), not in AAD. The broker library attempts to use the macOS SSO Extension for acquire-token-interactive and returns a structured error:

```
sourceArea: Broker
Status:     Response_Status.Status_TransientError
Error code: 1000
Tag:        508175367
```

MSAL maps this into its standard result dict with `error` and `error_description` keys and returns it to the CLI.

### 4.2 CLI error handling — `auth/util.py` `check_result` → `aad_error_handler`

`identity.login_with_auth_code()` calls `self._msal_app.acquire_token_interactive(...)` and passes the result to `check_result()`:

```python
# identity.py line 174
result = self._msal_app.acquire_token_interactive(
    scopes, prompt='select_account', ...
    parent_window_handle=self._msal_app.CONSOLE_WINDOW_HANDLE, ...)
return check_result(result)
```

`check_result` in `util.py` (line 130) detects `'error' in result` and calls `aad_error_handler`:

```python
# util.py line 151
if 'error' in result:
    aad_error_handler(result, tenant=tenant, scopes=scopes, claims_challenge=claims_challenge)
```

### 4.3 `aad_error_handler` — no broker-specific case

`aad_error_handler` (lines 22–57) checks `error_codes` for specific AAD codes (e.g. `7000215` for certificate-password confusion). The broker transient error does **not** carry an AAD `error_codes` list — it is a native broker status, not an AAD response. So the function falls into the generic branch:

```python
# util.py lines 48-54
else:
    login_command = _generate_login_command(tenant=tenant, ...)
    login_message = ('Run the command below to authenticate interactively; '
                     'additional arguments may be added as needed:\n'
                     f'{login_command}')
    ...
    recommendation = login_message
```

`_generate_login_command` (lines 59–77) always generates:

```
az logout
az login
```

There is no tenant or scope context here (plain `az login` was called), so the generated recovery command is identical to rerunning the original failing command — **it loops**.

### 4.4 No broker-unavailable detection anywhere in the stack

There is no code in the CLI auth layer that:
- Checks whether the macOS SSO Extension is registered before attempting broker auth
- Catches the `Status_TransientError / Error code: 1000` pattern and falls back to browser
- Detects the Company Portal SSO extension absence and adjusts the PCA creation flags

The `enable_broker_on_mac` flag is passed through to MSAL's `PublicClientApplication` at construction time (`identity.py` lines 113-118). Once the PCA is created with broker enabled, all interactive acquire-token calls go through the broker path with no runtime fallback.

---

## 5. Code Locations

| File | Line | Relevance |
|---|---|---|
| `auth/identity.py` | 113-118 | `_msal_public_app_kwargs` passes `enable_broker_on_mac` to PCA at construction |
| `auth/identity.py` | 150-174 | `login_with_auth_code` — calls `acquire_token_interactive`, no fallback on error |
| `auth/util.py` | 22-57 | `aad_error_handler` — no case for broker transient / broker-unavailable errors |
| `auth/util.py` | 59-77 | `_generate_login_command` — generates `az logout; az login` (loops when broker stays enabled) |
| `auth/util.py` | 130-161 | `check_result` — routes MSAL errors to `aad_error_handler` unconditionally |

---

## 6. Impact

| Scenario | Impact |
|---|---|
| User has `enable_broker_on_mac=true` (default) and uninstalls Company Portal | `az login` fails, loop suggested, stuck unless user knows to set `enable_broker_on_mac=false` |
| IT wipes Company Portal from managed device (Intune policy change) | All CLI sessions break silently on next token refresh |
| User manually disables the SSO extension via System Preferences | Same failure mode |
| First-time setup: cask installed, broker=true (default), Company Portal never installed | `az login` fails immediately with no useful guidance |

---

## 7. Expected Fix

Two changes are needed:

### Fix 1 — Broker-unavailable detection before login

Before calling `acquire_token_interactive`, check whether the macOS SSO Extension is registered. If not, either:
- Auto-disable broker for this invocation and fall back to browser
- Or emit a clear warning with actionable guidance: `az config set core.enable_broker_on_mac=false`

Possible detection:
```python
import subprocess
result = subprocess.run(
    ['pluginkit', '-m', '-i', 'com.microsoft.CompanyPortalMac.ssoextension'],
    capture_output=True, text=True)
broker_available = bool(result.stdout.strip())
```

### Fix 2 — Specific error handling for broker transient errors

In `aad_error_handler`, detect the broker transient error pattern by checking `error_description` or a broker-specific key in the MSAL result dict, and provide a targeted message:

```python
# Proposed — detect broker failure and guide to browser fallback
if error_description and 'sourceArea: Broker' in error_description:
    recommendation = (
        "The broker (Company Portal / macOS SSO Extension) is unavailable.\n"
        "To log in using a browser instead, run:\n"
        "  az config set core.enable_broker_on_mac=false\n"
        "  az login")
    raise AuthenticationError(error_description, msal_error=error, recommendation=recommendation)
```

### Fix 3 — Correct the recovery suggestion loop

The generated `az logout; az login` recommendation must not be printed when the root cause is `enable_broker_on_mac=true` with broker absent — because rerunning `az login` with the same config reproduces the identical failure.

---

## 8. Workaround (for testers)

```bash
# Disable broker and use browser fallback
az config set core.enable_broker_on_mac=false
az login
```

---

## 9. Relation to MSAL Cache Split Bug

This is a distinct bug from the MSAL cache split issue documented in [investigation_msal_cache_split.md](investigation_msal_cache_split.md).

| | MSAL Cache Split | Broker No Fallback |
|---|---|---|
| **Trigger** | Switching `enable_broker_on_mac` without clearing caches | Company Portal absent while `enable_broker_on_mac=true` |
| **Error** | `User does not exist in MSAL token cache` | `Status_TransientError, Error code: 1000` |
| **Exit code** | 1 | 1 |
| **Recovery loop?** | No — clearing caches resolves it | Yes — suggested `az logout; az login` loops |
| **Fix location** | `_profile.py` / `identity.py` cache coordination | `aad_error_handler` / pre-login detection |
