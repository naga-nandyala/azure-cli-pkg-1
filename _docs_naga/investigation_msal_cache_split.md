# Investigation: MSAL token cache split — broker vs non-broker stores

| | |
|---|---|
| **Date** | 2026-03-10 |
| **Tester** | naganandyala@microsoft.com |
| **Machine** | ARM64, macOS 26.3.1 (Build 25D2128) |
| **CLI version** | azure-cli 2.84.0 (cask install via naga-nandyala/mycli-app) |
| **Status** | **CONFIRMED — reproduced in both directions** |

---

## Error observed

During S3-3 of the bug bash, after switching from a broker-based login (S3-2) to `enable_broker_on_mac=false`, the following error appeared:

```
User 'naganandyala@microsoft.com' does not exist in MSAL token cache. Run `az login`.
```

This happened even though `az login` had visibly printed:

```
A web browser has been opened at https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize.
Please continue the login in the web browser.
Retrieving tenants and subscriptions for the selection...
```

So login appeared to complete (exit 0), then the error fired during subscription retrieval.

---

## Confirmed reproduction (both directions)

### Direction 1: broker → non-broker (S3-2 → S3-3)

1. `az login` with `enable_broker_on_mac=true` (default) → silent SSO via Company Portal → token in **broker keychain**
2. `az config set core.enable_broker_on_mac=false`
3. `az logout` → no-op (non-broker PCA can't see keychain tokens)
4. `az login` (browser) → Apple SSO extension intercepts, writes token back to **keychain**
5. `get_user_credential(username)` with non-broker PCA → `get_accounts()` checks **local file cache** → empty → **error**

### Direction 2: non-broker → broker (S3-3 → S3-4)

1. `az login` with `enable_broker_on_mac=false` (browser) → token in **local file cache** (`~/.azure/msal_token_cache.bin`)
2. `az config set core.enable_broker_on_mac=true`
3. `az logout` → no-op (broker-mode PCA can't see file cache tokens)
4. `az login` (broker) → Company Portal SSO presents account, stores token in **keychain**
5. `get_user_credential(username)` with broker-mode PCA → `get_accounts()` checks **keychain** → account not found (or mis-keyed) → **error**

Even after deleting `~/.azure/msal_token_cache.json` and `.bin` manually, the direction-2 error persists, confirming the state corruption is keychain-side, not file-side.

---

## Reproduction steps (as observed)

1. `az login` with broker enabled (default) → silent SSO via Company Portal → **token stored in macOS SSO keychain**
2. `az config set core.enable_broker_on_mac=false`
3. `az logout` → no-op (see below)
4. `az login` → browser opens → Apple SSO extension auto-completes (token stored back in broker keychain) → error raised during `get_user_credential`

---

## Root cause trace

**Code path:** `_profile.py` → `identity.py` → `msal_credentials.py`

### Step 1 — Broker login (S3-2) writes to the wrong store for non-broker reads

`identity.login_with_auth_code()` / broker path → `MSAL` stores tokens via the macOS SSO extension (Company Portal keychain), **not** in `~/.azure/msal_token_cache.bin`.

### Step 2 — `az logout` with `enable_broker_on_mac=false` is a no-op against broker tokens

```python
# identity.py
def logout_user(self, username):
    accounts = self._msal_app.get_accounts(username)  # ← non-broker PublicClientApplication
    for account in accounts:
        self._msal_app.remove_account(account)
```

A non-broker `PublicClientApplication` (constructed with `enable_broker_on_mac=False`) only sees `~/.azure/msal_token_cache.bin`. Broker keychain entries are invisible to it → `get_accounts()` returns empty → no accounts removed → broker tokens remain alive.

### Step 3 — Browser `az login` stores back into broker keychain

macOS Apple Platform SSO extension (`com.microsoft.CompanyPortalMac.ssoextension`) is registered OS-wide via `pluginkit`. It intercepts `acquire_token_interactive` at the OS level even when the CLI sets `enable_broker_on_mac=False`. The acquired token is written into the broker-managed keychain, not the local file cache.

### Step 4 — `get_user_credential` can't find the account

```python
# _profile.py line ~197
credential = identity.get_user_credential(username)

# identity.py line 242
def get_user_credential(self, username):
    return UserCredential(self.client_id, username, **self._msal_public_app_kwargs)
    # _msal_public_app_kwargs has enable_broker_on_mac=False

# msal_credentials.py line 35-42
class UserCredential:
    def __init__(self, client_id, username, **kwargs):
        self._msal_app = PublicClientApplication(client_id, **kwargs)
        # enable_broker_on_mac=False → only reads local file cache
        accounts = self._msal_app.get_accounts(username)
        if not accounts:
            raise CLIError("User '{}' does not exist in MSAL token cache...".format(username))
```

`~/.azure/msal_token_cache.bin` is empty (all tokens are in the keychain) → `get_accounts()` returns `[]` → error raised.

---

## Key insight

There are **two separate token stores** on macOS with broker:

| Store | Used when | Managed by |
|---|---|---|
| macOS SSO keychain | `enable_broker_on_mac=True` (or when Apple SSO ext intercepts) | Company Portal / Apple Platform SSO |
| `~/.azure/msal_token_cache.bin` | `enable_broker_on_mac=False` (explicit non-broker) | CLI / MSAL file serialization |

The `enable_broker_on_mac` flag controls which store the **CLI reads from**, but it does **not** prevent the macOS Apple Platform SSO extension from intercepting and writing to the keychain.

---

## Reproduction checklist (to confirm)

Run each step in order in a clean terminal with no active session:

```bash
# 1. Ensure broker is enabled and do a fresh login
az config set core.enable_broker_on_mac=true
az logout 2>/dev/null || true
az login
az account show --output table

# 2. Flip to non-broker
az config set core.enable_broker_on_mac=false

# 3. Logout (should be a no-op against broker tokens)
az logout

# 4. Login via browser
az login

# 5. Observe: does the error appear?
az account show --output table
```

Expected if bug is present: error `User 'X' does not exist in MSAL token cache` after step 4.

---

## Potential fix direction

`az logout` should detect if broker tokens exist (i.e., check both stores) and clear the broker keychain entry even when `enable_broker_on_mac=False`, or at minimum warn the user that a broker session is still active.

Alternatively, `get_user_credential` could fall back to trying the broker store if the non-broker store returns empty.

---

## Related files

- [`src/azure-cli-core/azure/cli/core/auth/msal_credentials.py`](../src/azure-cli-core/azure/cli/core/auth/msal_credentials.py) — line 42, error raised
- [`src/azure-cli-core/azure/cli/core/auth/identity.py`](../src/azure-cli-core/azure/cli/core/auth/identity.py) — line 242, `get_user_credential`; line 204, `logout_user`
- [`src/azure-cli-core/azure/cli/core/_profile.py`](../src/azure-cli-core/azure/cli/core/_profile.py) — line 197, `get_user_credential` called after login
