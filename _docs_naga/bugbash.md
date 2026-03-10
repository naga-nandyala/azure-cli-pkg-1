# Azure CLI macOS Bug Bash — naga-nandyala cask + broker auth

| | |
|---|---|
| **Cask source** | `naga-nandyala/homebrew-mycli-app` |
| **Release repo** | `naga-nandyala/azure-cli-latest` |
| **Version** | 2.84.0 |
| **Changes under test** | homebrew-cask install approach + broker-based authentication |

Run on both **ARM64** and **Intel** machines. Work through sections in order — each section's end state is the start state for the next.

---

## Table of Contents

- [Azure CLI macOS Bug Bash — naga-nandyala cask + broker auth](#azure-cli-macos-bug-bash--naga-nandyala-cask--broker-auth)
  - [Table of Contents](#table-of-contents)
  - [Section 1 — Current state (homebrew-core baseline)](#section-1--current-state-homebrew-core-baseline)
    - [S1-1: Installation check](#s1-1-installation-check)
    - [S1-2: Capture extensions and config](#s1-2-capture-extensions-and-config)
    - [S1-3: Login and run a command against azclitools](#s1-3-login-and-run-a-command-against-azclitools)
    - [S1-4: Uninstall homebrew-core azure-cli](#s1-4-uninstall-homebrew-core-azure-cli)
  - [Section 2 — New install via homebrew-cask](#section-2--new-install-via-homebrew-cask)
    - [S2-1: Tap and inspect cask](#s2-1-tap-and-inspect-cask)
    - [S2-2: Install](#s2-2-install)
    - [S2-3: Verify signatures](#s2-3-verify-signatures)
    - [S2-4: Basic functionality](#s2-4-basic-functionality)
    - [S2-5: Verify old extensions still work](#s2-5-verify-old-extensions-still-work)
    - [S2-6: Install a new extension, then uninstall it](#s2-6-install-a-new-extension-then-uninstall-it)
    - [S2-7: Reinstall and upgrade simulation](#s2-7-reinstall-and-upgrade-simulation)
    - [S2-8: Uninstall cask](#s2-8-uninstall-cask)
  - [Section 3 — Broker authentication](#section-3--broker-authentication)
    - [S3-1: Check Company Portal](#s3-1-check-company-portal)
    - [S3-2: Broker auto-invoked on az login (config = default)](#s3-2-broker-auto-invoked-on-az-login-config--default)
    - [S3-3: Disable broker (config = false) → falls back to browser](#s3-3-disable-broker-config--false--falls-back-to-browser)
    - [S3-4: Re-enable broker (config = true) → broker invoked again](#s3-4-re-enable-broker-config--true--broker-invoked-again)
    - [S3-5: Uninstall Company Portal but config = true → falls back to browser](#s3-5-uninstall-company-portal-but-config--true--falls-back-to-browser)
    - [S3-6: Login into azclitools tenant](#s3-6-login-into-azclitools-tenant)
  - [Section 4 — Telemetry verification](#section-4--telemetry-verification)
    - [ST-1: Capture a successful broker login](#st-1-capture-a-successful-broker-login)
    - [ST-2: Capture a cancelled broker login](#st-2-capture-a-cancelled-broker-login)
    - [ST-3: Non-broker login — contrast record](#st-3-non-broker-login--contrast-record)
    - [ST-4: Verify installer field for cask install](#st-4-verify-installer-field-for-cask-install)
    - [ST-5: MSAL version fields present](#st-5-msal-version-fields-present)
    - [KQL query](#kql-query)
  - [Section 5 — Offline install (tarball, non-Homebrew Python)](#section-5--offline-install-tarball-non-homebrew-python)
    - [S5-1: Download and extract tarball](#s5-1-download-and-extract-tarball)
    - [S5-2: Verify signatures on the tarball binary](#s5-2-verify-signatures-on-the-tarball-binary)
    - [S5-3: Confirm az fails without AZ\_PYTHON](#s5-3-confirm-az-fails-without-az_python)
    - [S5-4: Install Python from a non-Homebrew location](#s5-4-install-python-from-a-non-homebrew-location)
    - [S5-5: Run az with non-Homebrew Python](#s5-5-run-az-with-non-homebrew-python)
    - [S5-6: Verify old extensions work in offline mode](#s5-6-verify-old-extensions-work-in-offline-mode)
    - [S5-7: Cleanup](#s5-7-cleanup)
  - [Section 6 — Restore homebrew-core azure-cli](#section-6--restore-homebrew-core-azure-cli)
  - [Result Tracking](#result-tracking)

---

## Section 1 — Current state (homebrew-core baseline)

Capture the state of the existing homebrew-core install before touching anything.

### S1-1: Installation check

```bash
which az
az --version
brew info azure-cli 2>/dev/null || echo "azure-cli formula not installed"
brew list --formula | grep azure-cli
```

Note the version, install prefix (should be under `/opt/homebrew/Cellar/azure-cli/`), and Python in use.

### S1-2: Capture extensions and config

```bash
# Extensions
az extension list --output table
ls -la ~/.azure/cliextensions/ 2>/dev/null || echo "no cliextensions dir"

# Config
cat ~/.azure/config 2>/dev/null || echo "no config file"
ls ~/.azure/
```

Save this output — you'll verify it survives uninstall.

### S1-3: Login and run a command against azclitools

```bash
az login
# Select the azclitools tenant when prompted

az account show --output table

# If azdo extension not already installed, add it
az extension add --name azure-devops 2>/dev/null || true

# Verify access
az devops project list --org https://dev.azure.com/azclitools --output table
```

Expected: Login succeeds, project list returns. Note the extension was installed or was already present.

### S1-4: Uninstall homebrew-core azure-cli

```bash
brew uninstall azure-cli
```

Verify:

```bash
which az && echo "FAIL: az still on PATH" || echo "PASS: az removed"
brew list --formula | grep azure-cli && echo "FAIL: formula remains" || echo "PASS: formula removed"

# ~/.azure MUST be retained
ls ~/.azure/ && echo "PASS: ~/.azure retained" || echo "FAIL: ~/.azure gone"
az extension list 2>/dev/null || echo "INFO: az not callable (expected)"
ls ~/.azure/cliextensions/ 2>/dev/null && echo "PASS: extensions dir retained" || echo "NOTE: no extensions dir"
```

Expected: `az` removed from PATH, formula gone, `~/.azure` directory and all its contents (config, extensions) untouched.

---

## Section 2 — New install via homebrew-cask

### S2-1: Tap and inspect cask

```bash
brew tap naga-nandyala/mycli-app

# Inspect tap
brew tap-info naga-nandyala/mycli-app
brew info --cask naga-nandyala/mycli-app/azure-cli

# View the raw cask file
cat $(brew --repository naga-nandyala/mycli-app)/Casks/azure-cli.rb
```

Expected: Tap lists correctly, cask shows version 2.84.0, URL points to `naga-nandyala/azure-cli-latest` releases, `depends_on formula: "python@3.13"`.

### S2-2: Install

```bash
brew install --cask naga-nandyala/mycli-app/azure-cli
```

Verify:

```bash
which az
az --version
ls -la /opt/homebrew/Caskroom/azure-cli/
```

Expected: `az` resolves, version prints as 2.84.0, install lives under `/opt/homebrew/Caskroom/azure-cli/2.84.0/`.

### S2-3: Verify signatures

```bash
AZ_BIN=$(which az)
INSTALL_DIR=/opt/homebrew/Caskroom/azure-cli/2.84.0

# Check the launcher itself
codesign -dv --verbose=4 "${AZ_BIN}" 2>&1 | grep -E "Authority|TeamIdentifier|Signature"

# Check the embedded Python-running binary (if present)
find "${INSTALL_DIR}" -name "*.dylib" -o -name "python*" | head -5 | \
  xargs -I{} codesign -dv {} 2>&1 | grep -E "Authority|not signed"

# Gatekeeper assessment on the tarball contents
spctl --assess --type execute --verbose "${AZ_BIN}" 2>&1
```

Expected: Signed by Microsoft (`Developer ID Application: Microsoft Corporation`), Gatekeeper assessment passes (accepted).

### S2-4: Basic functionality

```bash
az --version
az find "create a storage account"
az account show 2>&1 | head -10     # "not logged in" is fine — look for Python/import errors only
```

Expected: Commands exit cleanly or with auth-only errors — no Python tracebacks or import failures.

### S2-5: Verify old extensions still work

The `~/.azure/cliextensions/` directory was retained from the homebrew-core install.

```bash
az extension list --output table

# Run the azure-devops extension that was installed pre-uninstall
az devops project list --org https://dev.azure.com/azclitools --output table
```

Expected: Extension is still listed and functional — no re-install needed, no version mismatch errors.

### S2-6: Install a new extension, then uninstall it

```bash
az extension add --name account
az extension list --output table
az extension show --name account
az extension remove --name account
az extension list --output table
```

Expected: Extension installs to `~/.azure/cliextensions/`, works, removes cleanly.

### S2-7: Reinstall and upgrade simulation

```bash
# Reinstall over existing
brew reinstall --cask naga-nandyala/mycli-app/azure-cli
az --version

# Upgrade (will be a no-op if no newer version, but must not error)
brew upgrade --cask naga-nandyala/mycli-app/azure-cli 2>&1
az --version
```

Expected: Both commands complete without errors or broken symlinks.

### S2-8: Uninstall cask

```bash
brew uninstall --cask naga-nandyala/mycli-app/azure-cli
```

Verify:

```bash
which az && echo "FAIL: az still on PATH" || echo "PASS: az removed"
ls /opt/homebrew/Caskroom/azure-cli 2>/dev/null && echo "FAIL: Caskroom dir remains" || echo "PASS: Caskroom cleaned"
ls ~/.azure/ && echo "PASS: ~/.azure retained" || echo "FAIL: ~/.azure gone"
ls ~/.azure/cliextensions/ 2>/dev/null && echo "PASS: extensions retained" || echo "NOTE: no extensions dir"
```

Expected: `az` removed, Caskroom directory gone, `~/.azure` and extensions retained.

---

## Section 3 — Broker authentication

Re-install the cask before running broker tests (if not already installed from Section 2):

```bash
brew install --cask naga-nandyala/mycli-app/azure-cli 2>/dev/null || true
```

### S3-1: Check Company Portal

Verify the Microsoft Company Portal app is installed and note its version — the broker depends on it.

```bash
# Check via Spotlight / Applications
ls /Applications/Company\ Portal.app 2>/dev/null && echo "FOUND" || echo "NOT INSTALLED"

# Get version
defaults read /Applications/Company\ Portal.app/Contents/Info CFBundleShortVersionString 2>/dev/null \
  || echo "version read failed"
```

Expected: Company Portal is present. Record the version.

### S3-2: Broker auto-invoked on az login (config = default)

With a fresh logout, verify `az login` opens the broker UI automatically without any extra flags.

```bash
az logout 2>/dev/null || true

# Check current broker config (should be unset or true — broker on by default)
az config get core.enable_broker_on_mac 2>/dev/null || echo "not set (defaults to broker enabled on macOS)"

az login
```

Expected: macOS Company Portal / Microsoft Identity Broker UI launches — not a browser tab, not a device-code prompt.

After login completes:

```bash
az account show --output table
az account get-access-token --output json | python3 -c "
import json, sys
t = json.load(sys.stdin)
print('tokenType :', t.get('tokenType'))
print('expiresOn :', t.get('expiresOn'))
print('tenant    :', t.get('tenant'))
"
```

Expected: Token acquired via broker, subscription returned.

### S3-3: Disable broker (config = false) → falls back to browser

```bash
az logout

# Disable broker
az config set core.enable_broker_on_mac=false
az config get core.enable_broker_on_mac

az login
```

Expected: Browser-based login opens (not the broker UI).

```bash
az account show --output table
```

Expected: Login succeeds via browser, account accessible.

### S3-4: Re-enable broker (config = true) → broker invoked again

```bash
az logout

# Re-enable broker
az config set core.enable_broker_on_mac=true
az config get core.enable_broker_on_mac

az login
```

Expected: Broker UI (Company Portal) opens again — not browser.

```bash
az account show --output table
```

Expected: Login succeeds via broker.

### S3-5: Uninstall Company Portal but config = true → falls back to browser

```bash
az logout

# Uninstall Company Portal
sudo rm -rf /Applications/Company\ Portal.app
ls /Applications/Company\ Portal.app 2>/dev/null && echo "still present" || echo "REMOVED"

# Config still set to broker
az config get core.enable_broker_on_mac

az login
```

Expected: Azure CLI detects broker is unavailable and falls back gracefully to browser-based login — no crash, no unhelpful error.

```bash
az account show --output table
```

Expected: Login succeeds via browser fallback.

> ⚠️ **Mandatory — do not skip**: Company Portal is a **required component on Microsoft enterprise laptops**. It enforces device compliance, delivers the Enterprise SSO extension, and is governed by IT policy. Uninstalling it was a deliberate test step — you must reinstall it immediately before continuing. Leaving an enterprise machine without Company Portal is a compliance and security gap.

**Reinstall Company Portal:**

1. Open the **Mac App Store** and search for **Microsoft Intune Company Portal**.
2. Install and launch it — sign in with your corporate account if prompted.
3. Verify the SSO extension is re-registered:

```bash
pluginkit -m -v | grep com.microsoft.CompanyPortalMac.ssoextension
```

Expected: Extension is listed with an enabled status. **Do not proceed to S3-6 until this output appears.**

### S3-6: Login into azclitools tenant

```bash
az logout
az login --tenant <azclitools-tenant-id>
az devops project list --org https://dev.azure.com/azclitools --output table
```

Expected: Broker acquires token scoped to azclitools tenant, project list returns.

---

## Section 4 — Telemetry verification

Verify that the expected telemetry fields are emitted after broker and non-broker logins.

> **Note — how to check**: Azure CLI posts telemetry asynchronously. Telemetry is typically available in the backend within ~1 hour. After running each step below, query the backend using the KQL query at the end of this section. Use the `CorrelationId` printed in `--debug` output (or the timestamp range) to isolate your records.

Prerequisite: cask install from S2-2 in place, broker re-enabled (`core.login_experience_v2=on`), Company Portal installed (Section 3 complete).

### ST-1: Capture a successful broker login

```bash
az logout 2>/dev/null || true

# Run login with --debug to capture correlation ID
az login --tenant <azclitools-tenant-id> --debug 2>&1 | grep -E "correlation.id|CorrelationId|telemetry" | head -20

# Note the correlation ID from debug output
az account show --output table
```

Record the `CorrelationId` from debug output. After ~1 hour, query the backend (see KQL below) and verify:

| Field | Expected value |
|---|---|
| `EnableBrokerOnMac` | `True` |
| `MsalApiName` | `SignInInteractively` |
| `BrokerAppUsed` | `true` |
| `MsalIsSuccessful` | `true` |
| `ActionResult` | `Success` |
| `error_type` | `None` |
| `loginexperiencev2` | `True` |
| `RawCommand` | `login` |
| `OsType` | `darwin` |

### ST-2: Capture a cancelled broker login

```bash
az logout 2>/dev/null || true

# Start broker login, then dismiss/cancel the SSO dialog
az login --tenant <azclitools-tenant-id> --debug 2>&1 | grep -E "correlation.id|CorrelationId" | head -5
```

When the macOS SSO / Keychain broker dialog appears, click **Cancel** or close it.

Record the `CorrelationId`. After ~1 hour, verify:

| Field | Expected value |
|---|---|
| `EnableBrokerOnMac` | `True` |
| `MsalApiName` | `SignInInteractively` |
| `BrokerAppUsed` | `true` |
| `MsalIsSuccessful` | `false` |
| `ActionResult` | `Failure` |
| `error_type` | `AuthenticationError` |
| `api_status_code` (in MsalRuntime) | `StatusInternal::UserCanceled` |

### ST-3: Non-broker login — contrast record

```bash
az logout 2>/dev/null || true
az config set core.login_experience_v2=off

az login --debug 2>&1 | grep -E "correlation.id|CorrelationId" | head -5
```

Complete the browser login. Record the `CorrelationId`. After ~1 hour, verify:

| Field | Expected value |
|---|---|
| `EnableBrokerOnMac` | `False` (or absent — this row would NOT appear in the broker-filtered query) |
| `loginexperiencev2` | `False` |
| `BrokerAppUsed` | `false` or absent |

> The KQL query below filters `enablebrokeronmac =~ "true"` — this record should **not** appear in broker query results. Confirm by checking the raw query without the broker filter.

```bash
# Restore broker config after this test
az config set core.login_experience_v2=on
```

### ST-4: Verify installer field for cask install

The `installer` property in telemetry records the install method. Run any `az` command and check the emitted value.

```bash
az --version --debug 2>&1 | grep -i installer | head -5
az account show --output table --debug 2>&1 | grep -i installer | head -5
```

After ~1 hour, query backend and check:

| Field | Expected value | Note |
|---|---|---|
| `context.default.azurecli.installer` | `HOMEBREW_CASK` | Confirm it is NOT `HOMEBREW` (formula value) |
| `context.default.vs.core.os.platform` | `macos-X.X-arm64-...` (ARM64) or `macos-X.X-x86_64-...` (Intel) | Matches machine |
| `CoreVersion` | `2.84.0` | Matches cask version |

> **If `installer` still shows `HOMEBREW`**: note as a bug — the cask packaging should set a distinct installer identifier so cask-sourced installs can be distinguished in telemetry.

### ST-5: MSAL version fields present

After a successful broker login (ST-1), confirm MSAL version fields are populated (not empty/null):

| Field | Expected |
|---|---|
| `MsalVersion` | Non-empty string (e.g. `9.0.0`) |
| `MsalRuntimeVersion` | Non-empty string (e.g. `0.20.2`) |

If either is empty, note as a gap — these fields are needed to track MSAL/broker SDK version adoption.

### KQL query

Run in the `RawEventsAzCli` workspace. Scope to your machine and the time window of your tests:

```kql
RawEventsAzCli
| where tostring(Properties["context.default.azurecli.enablebrokeronmac"]) =~ "true"
| extend
    MsalTelemetryRaw = tostring(Properties["context.default.azurecli.msaltelemetry"])
| extend
    MsalTelemetry = parse_json(MsalTelemetryRaw)
| extend
    MsalRuntime = MsalTelemetry.msalruntime_telemetry
| extend
    MsalApiName        = tostring(MsalRuntime.api_name),
    BrokerAppUsed      = tostring(MsalRuntime.broker_app_used),
    MsalIsSuccessful   = tostring(MsalRuntime.is_successful),
    MsalVersion        = tostring(MsalRuntime.msal_version),
    MsalRuntimeVersion = tostring(MsalRuntime.msalruntime_version)
| extend
    EnableBrokerOnMac = tostring(Properties["context.default.azurecli.enablebrokeronmac"]),
    RawCommand        = tostring(Properties["context.default.azurecli.rawcommand"]),
    CoreVersion       = tostring(Properties["context.default.azurecli.coreversion"])
| project-reorder MsalApiName, BrokerAppUsed, MsalIsSuccessful, MsalVersion, MsalRuntimeVersion,
    EventTimestamp, RawCommand, Params, OsType, EnableBrokerOnMac, CoreVersion,
    UserId, MachineId, *
```

To check non-broker records (ST-3), remove the `where` filter or negate it:

```kql
RawEventsAzCli
| where tostring(Properties["context.default.azurecli.enablebrokeronmac"]) !~ "true"
| extend RawCommand = tostring(Properties["context.default.azurecli.rawcommand"])
| extend Installer  = tostring(Properties["context.default.azurecli.installer"])
| extend LoginV2    = tostring(Properties["context.default.azurecli.loginexperiencev2"])
| project EventTimestamp, RawCommand, Installer, LoginV2, OsType, *
```

---

## Section 5 — Offline install (tarball, non-Homebrew Python)

Test the raw tarball with a Python that has no relationship to Homebrew.

### S5-1: Download and extract tarball

```bash
VERSION=2.84.0
ARCH=$(uname -m)   # arm64 or x86_64
TARBALL="azure-cli-${VERSION}-macos-${ARCH}.tar.gz"

curl -L -o /tmp/${TARBALL} \
  "https://github.com/naga-nandyala/azure-cli-latest/releases/download/azure-cli-${VERSION}/${TARBALL}"

rm -rf /tmp/az-offline && mkdir /tmp/az-offline
tar -xzf /tmp/${TARBALL} -C /tmp/az-offline

ls -la /tmp/az-offline/bin/az
```

### S5-2: Verify signatures on the tarball binary

```bash
codesign -dv --verbose=4 /tmp/az-offline/bin/az 2>&1 | grep -E "Authority|TeamIdentifier|Signature"
spctl --assess --type execute --verbose /tmp/az-offline/bin/az 2>&1
```

Expected: Signed by Microsoft, Gatekeeper assessment passes.

### S5-3: Confirm az fails without AZ_PYTHON

```bash
/tmp/az-offline/bin/az --version 2>&1 | head -5
```

Expected: Exits with a human-readable error message — NOT a Python traceback.

### S5-4: Install Python from a non-Homebrew location

```bash
# Option A: python.org installer (recommended — download manually from https://www.python.org/downloads/)
# After install, it lands at:
ls /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 2>/dev/null && \
  echo "python.org Python found" || echo "not installed yet"

# Option B: pyenv (if available)
which pyenv && pyenv install 3.13.1 && pyenv shell 3.13.1 && which python3
```

Use whichever Python is available from a non-Homebrew source. Record the path:

```bash
NON_HB_PYTHON=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
# or: NON_HB_PYTHON="$HOME/.pyenv/versions/3.13.1/bin/python3"

${NON_HB_PYTHON} --version
```

### S5-5: Run az with non-Homebrew Python

```bash
AZ_PYTHON="${NON_HB_PYTHON}" /tmp/az-offline/bin/az --version
AZ_PYTHON="${NON_HB_PYTHON}" /tmp/az-offline/bin/az find "create storage account"
```

Expected: `az --version` succeeds, shows 2.84.0. No errors about missing packages.

### S5-6: Verify old extensions work in offline mode

```bash
AZ_PYTHON="${NON_HB_PYTHON}" /tmp/az-offline/bin/az extension list --output table
AZ_PYTHON="${NON_HB_PYTHON}" /tmp/az-offline/bin/az devops project list \
  --org https://dev.azure.com/azclitools --output table
```

Expected: Extensions in `~/.azure/cliextensions/` load correctly under the tarball install.

### S5-7: Cleanup

```bash
# Remove the non-Homebrew Python if it was installed only for this test
# python.org: sudo rm -rf /Library/Frameworks/Python.framework/Versions/3.13
# pyenv:      pyenv uninstall 3.13.1

rm -rf /tmp/az-offline /tmp/${TARBALL}
```

---

## Section 6 — Restore homebrew-core azure-cli

Return the machine to its original state.

```bash
# Remove the test cask if still installed
brew uninstall --cask naga-nandyala/mycli-app/azure-cli 2>/dev/null || true
brew untap naga-nandyala/mycli-app 2>/dev/null || true

# Reinstall from homebrew-core
brew install azure-cli

# Verify
which az
az --version
az extension list --output table
```

Expected: Homebrew-core azure-cli back in place, pre-existing extensions still present and functional.

---

## Result Tracking

| Test | Description | ARM64 | Intel | Notes |
|------|-------------|-------|-------|-------|
| S1-1 | Current install check | | | |
| S1-2 | Capture extensions/config | | | |
| S1-3 | Login + azclitools project list | | | |
| S1-4 | Uninstall homebrew-core, ~/.azure retained | | | |
| S2-1 | Tap + inspect cask | | | |
| S2-2 | Cask install, verify location | | | |
| S2-3 | Verify signatures | | | |
| S2-4 | Basic az commands | | | |
| S2-5 | Old extensions still work | | | |
| S2-6 | New extension install/uninstall | | | |
| S2-7 | Reinstall + upgrade simulation | | | |
| S2-8 | Cask uninstall, ~/.azure retained | | | |
| S3-1 | Company Portal present + version | | | |
| S3-2 | Broker auto-invoked (default config) | | | |
| S3-3 | Config=false → browser login | | | |
| S3-4 | Config=true → broker login | | | |
| S3-5 | No Company Portal + config=true → browser fallback | | | |
| S3-6 | Broker login to azclitools tenant | | | |
| ST-1 | Successful broker login — telemetry fields | | | |
| ST-2 | Cancelled broker login — `UserCanceled` telemetry | | | |
| ST-3 | Non-broker login — absent from broker query | | | |
| ST-4 | `installer` field reflects cask (not formula) | | | |
| ST-5 | `MsalVersion` + `MsalRuntimeVersion` populated | | | |
| S5-1 | Tarball download + extract | | | |
| S5-2 | Signatures on tarball binary | | | |
| S5-3 | az fails without AZ_PYTHON | | | |
| S5-4 | Non-Homebrew Python install | | | |
| S5-5 | az works with non-Homebrew Python | | | |
| S5-6 | Old extensions work in tarball mode | | | |
| S5-7 | Cleanup | | | |
| S6 | Restore homebrew-core | | | |

Status: `PASS` / `FAIL` / `SKIP`
