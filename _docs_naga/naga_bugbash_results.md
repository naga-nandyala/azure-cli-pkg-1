# Azure CLI macOS Bug Bash — Results Log

| | |
|---|---|
| **Tester** | naganandyala |
| **Machine** | ARM64 — macOS 26.3.1 (Build 25D2128) |
| **Date** | 2026-03-10 |
| **Cask source** | `naga-nandyala/mycli-app` |
| **Version under test** | 2.84.0 |
| **Plan doc** | [bugbash.md](bugbash.md) |

Status legend: `PASS` `FAIL` `SKIP` `PENDING` `BLOCKED`

---

## Section 1 — Current state (homebrew-core baseline)

### S1-1: Installation check — PASS

```
which az        → /opt/homebrew/bin/az
az --version    → azure-cli 2.84.0
                   core 2.84.0 / telemetry 1.1.0
                   Python 3.13.12 at /opt/homebrew/Cellar/azure-cli/2.84.0/libexec/bin/python
brew info       → Installed: /opt/homebrew/Cellar/azure-cli/2.84.0 (16,351 files, 356.4MB)
brew list       → azure-cli (formula confirmed)
```

Install prefix: `/opt/homebrew/Cellar/azure-cli/2.84.0` ✓

### S1-2: Capture extensions and config — PASS

**Extensions present:**

| Name | Type | Version | Path |
|---|---|---|---|
| account | whl | 0.2.5 | `~/.azure/cliextensions/account` |
| azure-devops | whl | 1.0.2 | `~/.azure/cliextensions/azure-devops` |

**Config (`~/.azure/config`):**
```
[cloud]
name = AzureCloud

[extension]
dev_sources =
```

**`~/.azure` directory contents:**
```
az.json                    commandIndex.json          msal_http_cache.bin
az.sess                    commands                   msal_token_cache.json
az_survey.json             config                     telemetry
azureProfile.json          extensionCommandTree.json  versionCheck.json
cliextensions              logs
clouds.config              ms-azuretools.vscode-azureresourcegroups
```

No `core.login_experience_v2` set in config — broker default will apply after cask install.

### S1-3: Login and run a command against azclitools — PASS

Logged in as `naganandyala@microsoft.com` on tenant `ed94de55-1f87-4278-9651-525e7ba467d6`
(`azclitools20260204.onmicrosoft.com` / Azure Client Tools 2026-02-04).

ADO org: `https://dev.azure.com/azclitools` — authenticated via `az devops login` with AAD access token.

```
ID                                    Name                  Visibility
------------------------------------  --------------------  ------------
5352b365-6294-4667-90c8-273f4599ccc2  1ESPipelineTemplates  Private
b5336d23-77d8-49b8-9327-6c483cc524dd  internal              Organization
097329d9-69cd-476b-a442-b4a342325ac2  OneBranch.Pipelines   Private
5147fa83-336e-44ef-bbe0-c86b8ae86cbb  public                Public
9b6b54d1-85ce-4ff5-8faa-608b4a183fc6  release               Organization
```

Note: correct org is `azclitools` (not `azclienttools` — plan doc corrected).

### S1-4: Uninstall homebrew-core azure-cli — PASS

```
brew uninstall azure-cli
→ Uninstalled /opt/homebrew/Cellar/azure-cli/2.84.0 (16,870 files, 362.7MB)
→ Autoremoved 4 unneeded formulae: libsodium, libyaml, mpdecimal, python@3.13

which az          → PASS: az removed
brew list formula → PASS: formula removed
~/.azure/         → PASS: retained (config, logs, cliextensions, msal caches all present)
cliextensions/    → PASS: account + azure-devops both retained
```

---

## Section 2 — New install via homebrew-cask

### S2-1: Tap and inspect cask — PASS (with findings)

```
brew tap naga-nandyala/mycli-app
→ Cloned to /opt/homebrew/Library/Taps/naga-nandyala/homebrew-mycli-app
→ Tapped 14 casks, 10 formulae (37 files, 307.4KB)
→ HEAD: 35360aae3f2412d5c4a3bf5e94ce8f246038fcab (last commit: 3 hours ago)
```

Cask file contents verified. `depends_on formula: "python@3.13"` ✓. URL points to `naga-nandyala/azure-cli-latest` releases ✓.

**⚠️ Finding 1 — Version mismatch**: Cask shows `version "2.83.0"` but homebrew-core baseline was `2.84.0`. The tap repo needs to be updated.

**⚠️ Finding 2 — Stale commented-out code**: The cask file contains a large block of commented-out old cask code below a `DELETE below content after cask upgrade test` marker. This dead code should be removed before shipping.
### S2-2: Install — PASS

```
brew install --cask naga-nandyala/mycli-app/azure-cli
→ Downloaded azure-cli-2.84.0-macos-arm64.tar.gz (45.8 MB) — sha256 verified
→ Installed dependencies: mpdecimal 4.0.1, python@3.13 (3.13.12_1)
→ Linked Binary 'az' to '/opt/homebrew/bin/az'
→ azure-cli was successfully installed!
```

Install location: `/opt/homebrew/Caskroom/azure-cli/2.84.0/` ✓
Symlink: `/opt/homebrew/bin/az -> /opt/homebrew/Caskroom/azure-cli/2.84.0/bin/az` ✓

### S2-3: Verify signatures — PASS

`az` binary is a shell script launcher (`#!/usr/bin/env bash`) — codesign does not apply to scripts.

MSAL runtime dylib signature:
```
codesign -dv --verbose=4 libmsalruntime_arm64.dylib
→ Authority=Developer ID Application: Microsoft Corporation (UBF8T346G9)
→ Authority=Developer ID Certification Authority
→ Authority=Apple Root CA
→ TeamIdentifier=UBF8T346G9
→ Format=Mach-O thin (arm64), runtime-hardened
```

Note: `com.apple.quarantine` xattr is present on the symlink (set by macOS download quarantine). `az --version` runs without GateKeeper prompt — quarantine does not block execution for non-app-bundle binaries.

### S2-4: Basic functionality — PASS

```
az --version    → azure-cli 2.84.0 / core 2.84.0 / telemetry 1.1.0
                   Extensions: account 0.2.5, azure-devops 1.0.2
az account show → Already logged in (credentials from S1 preserved)
                   Tenant: azclitools20260204.onmicrosoft.com
                   Subscription: Azure CLI (88939486-3f56-4b35-bd43-5d6b34df022f)
```

No Python tracebacks. Clean output. ✓

**⚠️ Finding 3 — SyntaxWarning from azure.batch**: On `az extension remove --name account` a `SyntaxWarning: invalid escape sequence '\ '` was emitted from `azure/batch/models/_models.py`. This is a Python 3.13 strict-mode warning (backslash escapes in docstrings). Non-blocking but worth noting for the azure-batch package maintainers.

### S2-5: Verify old extensions still work — PASS

```
az extension list --output table
→ account       0.2.5  ~/.azure/cliextensions/account       (whl)
→ azure-devops  1.0.2  ~/.azure/cliextensions/azure-devops  (whl)

az devops project list --org https://dev.azure.com/azclitools
→ 5 projects returned (no re-install needed, no version mismatch errors)
```

Extensions from homebrew-core install survived cask install with no re-install required. ✓

### S2-6: Install a new extension, then uninstall it — PASS

`account` was already installed (retained from S1). Removed, re-added, and removed again to validate the cycle:

```
az extension remove --name account  → removed cleanly (SyntaxWarning from azure.batch observed — see Finding 3)
az extension add --name account     → installed to ~/.azure/cliextensions/account (0.2.5)
az extension show --name account    → Type: whl, Version: 0.2.5, Path: ~/.azure/cliextensions/account
az extension remove --name account  → removed cleanly
az extension list                   → only azure-devops remaining ✓
```

### S2-7: Reinstall and upgrade simulation — PASS

```
brew reinstall --cask naga-nandyala/mycli-app/azure-cli
→ sha256 verified, unlinked old symlink, purged, re-installed, re-linked
→ azure-cli was successfully installed!

az --version  → 2.84.0 ✓

brew upgrade --cask naga-nandyala/mycli-app/azure-cli
→ Warning: Not upgrading azure-cli, the latest version is already installed ✓
```

No broken symlinks. Both reinstall and upgrade-no-op complete cleanly. ✓

### S2-8: Uninstall cask — PASS

```
brew uninstall --cask naga-nandyala/mycli-app/azure-cli
→ Unlinked /opt/homebrew/bin/az
→ Purged /opt/homebrew/Caskroom/azure-cli/2.84.0
→ Autoremoved 2 unneeded formulae: mpdecimal, python@3.13

which az             → PASS: az removed
/opt/homebrew/Caskroom/azure-cli  → PASS: Caskroom cleaned
~/.azure/            → PASS: retained (all files intact)
~/.azure/cliextensions/ → PASS: azure-devops retained
```

`~/.azure` and remaining extensions (`azure-devops 1.0.2`) preserved through uninstall. ✓

---

## Section 3 — Broker authentication

### S3-1: Check Company Portal — PASS

```
/Applications/Company Portal.app  → FOUND
version: 5.2602.0

pluginkit -m -i com.microsoft.CompanyPortalMac.ssoextension
→ com.microsoft.CompanyPortalMac.ssoextension(5.2602.0) 
   /Applications/Company Portal.app/Contents/PlugIns/CompanyPortalSSOExtension.appex
```

Company Portal 5.2602.0 present. macOS SSO extension `com.microsoft.CompanyPortalMac.ssoextension` registered. ✓

### S3-2: Broker auto-invoked on az login (config = default) — PASS

`core.enable_broker_on_mac` unset (defaults to `true`). `az login` silently SSO'd via Company Portal broker — no browser tab opened, no device-code prompt. Token acquired:

```
tokenType : Bearer
expiresOn : 2026-03-10 16:43:02.000000
tenant    : 72f988bf-86f1-41af-91ab-2d7cd011db47
```

Broker SSO used existing macOS SSO session from Company Portal (registered via pluginkit). No interactive prompt needed. ✓

### S3-3: Disable broker (config = false) → falls back to browser — PASS (with Investigation Note)

```
az config set core.enable_broker_on_mac=false
az login
→ "A web browser has been opened at https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize"
```

Browser opened correctly — broker was not invoked. ✓

**⚠️ Investigation Note — MSAL token cache split between broker and non-broker stores**

When running `az login` with `enable_broker_on_mac=false` immediately after a broker-based session (S3-2), the following error appeared:

```
User 'naganandyala@microsoft.com' does not exist in MSAL token cache. Run `az login`.
```

**Root cause trace** (`_profile.py` → `identity.py` → `msal_credentials.py`):

1. S3-2 broker login stored tokens in the **macOS SSO keychain** (via Company Portal SSO extension), not in `~/.azure/msal_token_cache.bin`.
2. `az logout` with `enable_broker_on_mac=false` creates a non-broker `PublicClientApplication` → only sees the local file cache → broker keychain tokens untouched → effectively a no-op logout.
3. `az login` (browser) completes — Apple SSO extension intercepts and stores the token back in the broker-side keychain (OS-level intercept regardless of the CLI flag).
4. `identity.get_user_credential(username)` with `enable_broker_on_mac=false` creates a new `UserCredential` backed by a non-broker `PublicClientApplication` → calls `get_accounts('naganandyala@microsoft.com')` → local file cache empty → raises the error.

The error was transient — once a clean browser login was completed in isolation (without a preceding broker session in the same MSAL app instance), `az account show` returned cleanly.

**TODO**: Reproduce in isolation to confirm — start fresh (`az logout` with broker=true, then flip to false and login) and verify if the MSAL cache split is reliably reproduced.

### S3-4: Re-enable broker → broker invoked again — PASS (with Investigation Note)

After recovery (deleted MSAL cache files, performed clean non-broker browser login), re-enabled broker:

```
az config set core.enable_broker_on_mac=true
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6
→ "Select the account you want to log in with."
→ "Retrieving subscriptions for the selection..."
→ Subscription: Azure CLI (88939486-3f56-4b35-bd43-5d6b34df022f) selected
exit: 0

az group list --output table  → PASS (3 resource groups returned, API call succeeded)
```

Broker SSO succeeded via Company Portal — no browser opened. ✓

**⚠️ Investigation Note — MSAL cache split is mode-transition-dependent**

The MSAL cache split error (documented in [investigation_msal_cache_split.md](investigation_msal_cache_split.md)) was reproduced earlier in this session when switching broker modes multiple times without clearing caches. However, starting from a fresh non-broker login state (MSAL file cache clean, no prior broker keychain tokens from this session), switching to broker mode works because:

- Company Portal SSO extension remains registered and active
- When broker-mode PCA initialises, the SSO extension provides a silent fresh token from the OS credential store
- No stale conflicting store entries exist from a prior broker session

**Conclusion**: S3-4 PASSES in the expected fresh-state scenario. The cache split bug is an edge case specific to repeated back-and-forth mode switching without clearing caches between transitions.

### S3-5: No Company Portal + config=true → browser fallback — FAIL

Pre-conditions: `core.enable_broker_on_mac = true` (already set from S3-4). Company Portal uninstalled:

```
sudo rm -rf "/Applications/Company Portal.app"
→ REMOVED

pluginkit -m -i com.microsoft.CompanyPortalMac.ssoextension
→ (no output) — SSO extension no longer registered

az logout; az login
→ Select the account you want to log in with. ...
→ The authorization attempt failed with a transient error
→ Error was thrown in sourceArea: Broker. Status: Response_Status.Status_TransientError, Error code: 1000, Tag: 508175367
→ Run the command below to authenticate interactively; additional arguments may be added as needed:
   az logout
   az login
exit: 1
```

**Expected**: graceful browser fallback (no crash, no hard exit, browser tab opens).

**Actual**: exit:1 with no browser opened. The CLI's own suggested recovery (`az logout; az login`) loops — it re-invokes `az login` with `enable_broker_on_mac=true` still set, reproducing the identical failure.

No special broker-unavailable handling exists in `aad_error_handler` (`auth/util.py`). The `Status_TransientError` / broker error code 1000 is not detected; the generic recommendation generator produces `az logout; az login` which is circular in this context.

See [investigation_broker_no_fallback.md](investigation_broker_no_fallback.md) for full root cause trace, code locations, and proposed fix directions.

**Workaround**: `az config set core.enable_broker_on_mac=false && az login`

### S3-6: Login into azclitools tenant — PASS

```
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6
→ Broker SSO (Company Portal) — silent, no browser opened
→ Subscription: Azure CLI (88939486-3f56-4b35-bd43-5d6b34df022f) selected
exit: 0

az devops project list --org https://dev.azure.com/azclitools --output table
→ 1ESPipelineTemplates, internal, OneBranch.Pipelines, public, release (5 projects)
exit: 0
```

Broker token acquired for azclitools tenant. ADO project list returned 5 projects. ✓

---

## Section 4 — Telemetry verification

### ST-1: Successful broker login — SKIP
### ST-2: Cancelled broker login — SKIP
### ST-3: Non-broker login contrast — SKIP
### ST-4: installer field for cask — SKIP
### ST-5: MSAL version fields — SKIP

Telemetry section skipped — backend KQL queries require ~1 hour wait and backend access. To be done in a follow-up pass.

---

## Section 5 — Offline install (tarball, non-Homebrew Python)

### S5-1: Download and extract tarball — PASS

Downloaded `azure-cli-2.84.0-macos-arm64.tar.gz` (44 MB) from `naga-nandyala/azure-cli-broker-new` release `azure-cli-2.84.0`. Extracted to `/tmp/az-offline/`. Structure: `bin/az` (symlink → `../libexec/bin/az`), `libexec/{bin,lib,README.txt}`. MSAL dylib present at `libexec/lib/python3.13/site-packages/pymsalruntime/libmsalruntime_arm64.dylib`.

### S5-2: Verify signatures on tarball binary — PASS

```
Format=Mach-O thin (arm64)
Authority=Developer ID Application: Microsoft Corporation (UBF8T346G9)
Authority=Developer ID Certification Authority
Authority=Apple Root CA
TeamIdentifier=UBF8T346G9
```

`spctl --assess --type execute` exit:3 ("rejected: code is valid but does not seem to be an app") — expected for a `.dylib`, not a failure. Signing chain is correct.

### S5-3: az fails without AZ_PYTHON — PASS

Running `/tmp/az-offline/bin/az --version` without `AZ_PYTHON` set printed: `Error: AZ_PYTHON not set. For offline/tarball installs, set AZ_PYTHON to a Python 3.13 path.` exit:0. Error message is clear and actionable.

### S5-4: Install non-Homebrew Python — PASS

Used pyenv-managed Python 3.13.1 at `/Users/naganandyala/.pyenv/versions/3.13.1/bin/python3`. No Python.framework installation present on this machine.

### S5-5: az works with non-Homebrew Python — PASS

```
AZ_PYTHON=/Users/naganandyala/.pyenv/versions/3.13.1/bin/python3 /tmp/az-offline/bin/az --version
```

Output: `azure-cli 2.84.0`, `Python location '...pyenv/versions/3.13.1/bin/python3'`. exit:0.

### S5-6: Old extensions work in tarball mode — PASS

`az extension list` showed `azure-devops 1.0.2` from `~/.azure/cliextensions/` (shared with cask install — same `~/.azure`). `az devops project list --org https://dev.azure.com/azclitools` returned 5 projects. exit:0.

### S5-7: Cleanup — PASS

`rm -rf /tmp/az-offline /tmp/azure-cli-2.84.0-macos-arm64.tar.gz` exit:0.

---

## Section 6 — Restore homebrew-core azure-cli

### S6: Restore — PASS

```
brew uninstall --cask naga-nandyala/mycli-app/azure-cli
brew untap naga-nandyala/mycli-app
brew install azure-cli
```

Cask uninstalled cleanly (python@3.13 + mpdecimal auto-removed). `brew install azure-cli` poured `azure-cli--2.84.0.arm64_tahoe.bottle.tar.gz` from homebrew-core. install exit:0.

`which az` → `/opt/homebrew/bin/az`, `az --version` → 2.84.0 (homebrew-core formula location `/opt/homebrew/Cellar/azure-cli/2.84.0`). `azure-devops 1.0.2` extension retained from `~/.azure/cliextensions/`.

---

## Result Tracking

| Test | Description | Result | Notes |
|---|---|---|---|
| S1-1 | Current install check | PASS | 2.84.0 at `/opt/homebrew/Cellar/azure-cli/2.84.0`, Python 3.13.12 |
| S1-2 | Capture extensions/config | PASS | account 0.2.5 + azure-devops 1.0.2 present; config = AzureCloud |
| S1-3 | Login + azclitools project list | PASS | Logged in; project list returned 5 projects. Org corrected to `azclitools` |
| S1-4 | Uninstall homebrew-core, ~/.azure retained | PASS | az removed; ~/.azure + both extensions retained; python@3.13 auto-removed |
| S2-1 | Tap + inspect cask | PASS | Cask fixed (2.83.0 → 2.84.0, dead code removed) before this run; tap resolved correctly |
| S2-2 | Cask install, verify location | PASS | `2.84.0` at `/opt/homebrew/Caskroom/azure-cli/2.84.0/`; deps python@3.13 3.13.12_1 installed |
| S2-3 | Verify signatures | PASS | MSAL dylib signed by Microsoft (UBF8T346G9); `az` is a shell script — codesign N/A |
| S2-4 | Basic az commands | PASS | `az --version` 2.84.0; `az account show` OK. ⚠️ SyntaxWarning from azure.batch (Finding 3) |
| S2-5 | Old extensions still work | PASS | account + azure-devops retained; `az devops project list` returned 5 projects |
| S2-6 | New extension install/uninstall | PASS | Remove → add → remove cycle clean; installs to `~/.azure/cliextensions/` |
| S2-7 | Reinstall + upgrade simulation | PASS | `brew reinstall` clean; `brew upgrade` correctly reports already at latest |
| S2-8 | Cask uninstall, ~/.azure retained | PASS | `az` removed; Caskroom cleaned; `~/.azure` + `azure-devops` extension retained |
| S3-1 | Company Portal present + version | PASS | 5.2602.0; SSO ext `com.microsoft.CompanyPortalMac.ssoextension` registered |
| S3-2 | Broker auto-invoked (default config) | PASS | Silent SSO via Company Portal; Bearer token acquired, no browser/device-code |
| S3-3 | Config=off → browser login | PASS | Browser opened correctly. ⚠️ MSAL cache split issue observed (see S3-3 note) — needs reproduction in isolation |
| S3-4 | Config=on → broker login | PASS | Broker SSO via Company Portal; no browser. ⚠️ Cache split bug is edge case (mode-switching without cache clear) — see investigation_msal_cache_split.md |
| S3-5 | No Company Portal + config=on → browser fallback | FAIL | Broker transient error (code 1000), no browser fallback, recovery suggestion loops. See investigation_broker_no_fallback.md |
| S3-6 | Broker login to azclitools tenant | PASS | Broker token for azclitools tenant; `az devops project list` returned 5 projects |
| ST-1 | Successful broker login — telemetry fields | SKIP | Deferred — requires backend KQL access + ~1h wait |
| ST-2 | Cancelled broker login — UserCanceled telemetry | SKIP | Deferred |
| ST-3 | Non-broker login — absent from broker query | SKIP | Deferred |
| ST-4 | `installer` field reflects cask (not formula) | SKIP | Deferred |
| ST-5 | `MsalVersion` + `MsalRuntimeVersion` populated | SKIP | Deferred |
| S5-1 | Tarball download + extract | PASS | 44 MB from `naga-nandyala/azure-cli-broker-new`; extracted to `/tmp/az-offline/` |
| S5-2 | Signatures on tarball binary | PASS | MSAL dylib signed by Microsoft (UBF8T346G9); spctl exit:3 expected for .dylib |
| S5-3 | az fails without AZ_PYTHON | PASS | Clear error message with instructions; exit:0 |
| S5-4 | Non-Homebrew Python install | PASS | pyenv Python 3.13.1 at `~/.pyenv/versions/3.13.1/bin/python3` |
| S5-5 | az works with non-Homebrew Python | PASS | `az --version` 2.84.0 with pyenv Python; exit:0 |
| S5-6 | Old extensions work in tarball mode | PASS | azure-devops 1.0.2 loaded; `az devops project list` returned 5 projects |
| S5-7 | Cleanup | PASS | `/tmp/az-offline` and tarball removed |
| S6 | Restore homebrew-core | PASS | homebrew-core 2.84.0 reinstalled; azure-devops 1.0.2 extension retained |
