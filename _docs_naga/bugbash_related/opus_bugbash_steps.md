# Azure CLI macOS Bug Bash — Opus Execution Steps

> Single source of truth for a VS Code Copilot (Claude Opus) session.
> Read this file top to bottom and execute each STEP in order. Do not skip ahead.

## Execution Contract

1. Execute STEPs in strict numeric order. Never jump ahead.
2. Run each code block in the terminal and capture all output verbatim.
3. After each STEP, record the result as `PASS`, `FAIL`, `SKIP`, or `BLOCKED`.
4. `[auto]` — Run commands and auto-evaluate against pass criteria. No user input needed.
5. `[interactive]` — Warn the user what will happen (login prompt, dialog, etc.), run the command, wait for it to finish, then ask the user to confirm what they observed.
6. `[destructive]` — Print the warning text and ask "Proceed? (yes/no)" before running. If the user says no, mark SKIP.
7. `[manual]` — Tell the user what to do. Wait for them to report the result.
8. If a step FAILs, stop and ask the user whether to continue or abort.
9. Do NOT modify commands unless a command is clearly wrong for the detected architecture.
10. Do NOT use heredoc syntax (`cat << EOF`) — it will fail in this environment.
11. Never fabricate output. Record actual output only.
12. Preserve `~/.azure` at all times unless a step explicitly says otherwise.

## Session Variables

Track these throughout the session. Set them in STEP 0.1 and reference in later steps.

| Variable | Set in | Description |
|----------|--------|-------------|
| `ARCH` | 0.1 | `arm64` or `x86_64` |
| `BREW_PREFIX` | 0.1 | `/opt/homebrew` (arm64) or `/usr/local` (x86_64) |
| `OS_VERSION` | 0.1 | macOS version string |
| `USERNAME` | 0.1 | `whoami` output |
| `HOSTNAME` | 0.1 | `hostname -s` output |
| `DATE` | 0.1 | `YYYY-MM-DD` |
| `NON_HB_PYTHON` | 5.5 | Path to non-Homebrew Python 3.13 (if available) |
| `AZ_OFFLINE_BIN` | 5.2 | Path to offline az binary |

## Test Metadata

| Key | Value |
|-----|-------|
| Cask source | `naga-nandyala/homebrew-mycli-app` |
| Cask tap name | `naga-nandyala/mycli-app` |
| Release repo | `naga-nandyala/azure-cli-latest` |
| Version under test | `2.84.0` |
| azclitools tenant | `ed94de55-1f87-4278-9651-525e7ba467d6` |
| azclitools org | `https://dev.azure.com/azclitools` |
| Platforms | macOS ARM64 and Intel |

---

## Section 0 — Session Setup

### STEP 0.1 [auto] Detect machine info and set session variables

```bash
echo "ARCH: $(uname -m)"
echo "OS: $(sw_vers -productName) $(sw_vers -productVersion) (Build $(sw_vers -buildVersion))"
echo "USER: $(whoami)"
echo "HOSTNAME: $(hostname -s)"
echo "DATE: $(date +%Y-%m-%d)"

if [ "$(uname -m)" = "arm64" ]; then
  echo "BREW_PREFIX=/opt/homebrew"
else
  echo "BREW_PREFIX=/usr/local"
fi
```

Pass criteria: All variables are visible and captured. Store ARCH, BREW_PREFIX, USERNAME, HOSTNAME, DATE for use in later steps.

### STEP 0.2 [auto] Create scratch directory for debug logs

```bash
mkdir -p /tmp/az-bugbash
echo "Scratch path: /tmp/az-bugbash"
```

Pass criteria: `/tmp/az-bugbash` exists.

---

## Section 1 — Current State (homebrew-core baseline)

Capture the existing homebrew-core install state before making any changes.

### STEP 1.1 [auto] Check current azure-cli installation

```bash
which az
az --version
brew info azure-cli 2>/dev/null || echo "azure-cli formula not installed"
brew list --formula | grep azure-cli
```

Pass criteria: `azure-cli` formula is listed and version is visible. Note the install prefix (`$BREW_PREFIX/Cellar/azure-cli/...`).

### STEP 1.2 [auto] Snapshot extensions and config

```bash
az extension list --output table
ls -la ~/.azure/cliextensions/ 2>/dev/null || echo "no cliextensions dir"
cat ~/.azure/config 2>/dev/null || echo "no config file"
ls ~/.azure/
```

Pass criteria: Output captured. Save this snapshot — you will compare against it after install/uninstall cycles.

### STEP 1.3 [interactive] Login and validate azclitools access

A login prompt (broker or browser) will appear. Complete the login and select the azclitools tenant if prompted.

```bash
az login
az account show --output table
az extension add --name azure-devops 2>/dev/null || true
az devops project list --org https://dev.azure.com/azclitools --output table
```

Pass criteria: Login succeeds, account info returned, project list shows results from azclitools org.

### STEP 1.4 [destructive] Uninstall homebrew-core azure-cli

Warning: This removes the current azure-cli formula installation.

```bash
brew uninstall azure-cli
```

Verify:

```bash
which az && echo "FAIL: az still on PATH" || echo "PASS: az removed"
brew list --formula | grep azure-cli && echo "FAIL: formula remains" || echo "PASS: formula removed"
ls ~/.azure/ && echo "PASS: ~/.azure retained" || echo "FAIL: ~/.azure gone"
ls ~/.azure/cliextensions/ 2>/dev/null && echo "PASS: extensions dir retained" || echo "NOTE: no extensions dir"
```

Pass criteria: `az` removed from PATH, formula gone, `~/.azure` directory and all contents (config, extensions) intact.

---

## Section 2 — New Install via Homebrew Cask

### STEP 2.1 [auto] Tap and inspect cask

```bash
brew tap naga-nandyala/mycli-app https://github.com/naga-nandyala/homebrew-mycli-app
brew tap-info naga-nandyala/mycli-app
brew info --cask naga-nandyala/mycli-app/azure-cli
cat "$(brew --repository naga-nandyala/mycli-app)/Casks/azure-cli.rb"
```

Pass criteria: Tap added, cask metadata shows version 2.84.0, URL points to `naga-nandyala/azure-cli-latest` releases.

### STEP 2.2 [auto] Install cask

```bash
brew install --cask naga-nandyala/mycli-app/azure-cli
which az
az --version
ls -la "$BREW_PREFIX/Caskroom/azure-cli/" 2>/dev/null
```

Pass criteria: `az` resolves, version is 2.84.0, install lives under `$BREW_PREFIX/Caskroom/azure-cli/`.

### STEP 2.3 [auto] Verify code signature and Gatekeeper

```bash
AZ_BIN=$(which az)
codesign -dv --verbose=4 "$AZ_BIN" 2>&1 | grep -E "Authority|TeamIdentifier|Signature"
spctl --assess --type execute --verbose "$AZ_BIN" 2>&1
```

Pass criteria: Signed by `Developer ID Application: Microsoft Corporation`, Gatekeeper assessment accepted.

### STEP 2.4 [auto] Basic command health check

```bash
az --version
az find "create a storage account"
az account show 2>&1 | head -10
```

Pass criteria: No Python tracebacks or import errors. Auth-only errors ("not logged in") are acceptable.

### STEP 2.5 [auto] Existing extension compatibility

```bash
az extension list --output table
az devops project list --org https://dev.azure.com/azclitools --output table
```

Pass criteria: Extensions from STEP 1.2 still listed and functional without reinstall.

Note: If login expired, user will need to `az login` first — this becomes interactive.

### STEP 2.6 [auto] New extension install/remove cycle

```bash
az extension add --name account
az extension list --output table
az extension show --name account
az extension remove --name account
az extension list --output table
```

Pass criteria: Extension installs to `~/.azure/cliextensions/`, shows correctly, removes cleanly.

### STEP 2.7 [auto] Reinstall and upgrade simulation

```bash
brew reinstall --cask naga-nandyala/mycli-app/azure-cli
az --version
brew upgrade --cask naga-nandyala/mycli-app/azure-cli 2>&1
az --version
```

Pass criteria: Both complete without errors or broken symlinks. Version stays 2.84.0.

### STEP 2.8 [destructive] Uninstall cask and verify user data retention

Warning: This removes the cask-installed azure-cli.

```bash
brew uninstall --cask naga-nandyala/mycli-app/azure-cli
```

Verify:

```bash
which az && echo "FAIL: az still on PATH" || echo "PASS: az removed"
ls "$BREW_PREFIX/Caskroom/azure-cli" 2>/dev/null && echo "FAIL: Caskroom dir remains" || echo "PASS: Caskroom cleaned"
ls ~/.azure/ && echo "PASS: ~/.azure retained" || echo "FAIL: ~/.azure gone"
ls ~/.azure/cliextensions/ 2>/dev/null && echo "PASS: extensions retained" || echo "NOTE: no extensions dir"
```

Pass criteria: `az` removed, Caskroom directory gone, `~/.azure` and extensions retained.

---

## Section 3 — Broker Authentication

### STEP 3.0 [auto] Ensure cask is installed for broker tests

```bash
brew install --cask naga-nandyala/mycli-app/azure-cli 2>/dev/null || true
which az && echo "az available" || echo "FAIL: az not found"
```

Pass criteria: `az` is available.

### STEP 3.1 [auto] Check Company Portal presence and version

```bash
ls /Applications/Company\ Portal.app 2>/dev/null && echo "FOUND" || echo "NOT INSTALLED"
defaults read /Applications/Company\ Portal.app/Contents/Info CFBundleShortVersionString 2>/dev/null || echo "version read failed"
```

Pass criteria: Company Portal is present. Version recorded.

### STEP 3.2 [interactive] Default login should use broker

A login prompt will appear. Observe whether it is the macOS broker dialog (Company Portal SSO) or a browser tab. Complete the login.

```bash
az logout 2>/dev/null || true
az config get core.login_experience_v2 2>/dev/null || echo "not set (defaults to broker)"
az login
az account show --output table
```

After command finishes, ask user: "Did the login open via the macOS broker (Company Portal SSO dialog) or via a browser tab?"

Pass criteria: Broker UI launched (not browser), login succeeded, account shown.

### STEP 3.3 [interactive] Disable broker — should fall back to browser

A browser tab should open for login (not broker). Complete the login.

```bash
az logout
az config set core.login_experience_v2=off
az config get core.login_experience_v2
az login
az account show --output table
```

After command finishes, ask user: "Did the login open in a browser tab (not broker)?"

Pass criteria: Browser-based login opened, login succeeded.

### STEP 3.4 [interactive] Re-enable broker — should return to broker path

The broker dialog should appear again. Complete the login.

```bash
az logout
az config set core.login_experience_v2=on
az config get core.login_experience_v2
az login
az account show --output table
```

After command finishes, ask user: "Did the login switch back to broker UI (Company Portal SSO)?"

Pass criteria: Broker UI opened, login succeeded.

### STEP 3.5 [destructive, interactive] Remove Company Portal — verify graceful fallback

Warning: This removes Company Portal. You MUST reinstall it immediately after (STEP 3.6).

```bash
az logout
sudo rm -rf /Applications/Company\ Portal.app
ls /Applications/Company\ Portal.app 2>/dev/null && echo "still present" || echo "REMOVED"
az config get core.login_experience_v2
az login
az account show --output table
```

After login, ask user: "Did Azure CLI fall back to browser cleanly (no crash, no unhelpful error)?"

Pass criteria: Browser fallback worked, login succeeded, no crash.

### STEP 3.6 [interactive, required recovery] Reinstall Company Portal

This is a mandatory recovery step. Do NOT skip this.

User action required:
1. Open the Mac App Store and search for "Microsoft Intune Company Portal".
2. Install and launch it — sign in with corporate account if prompted.

Then verify:

```bash
ls /Applications/Company\ Portal.app 2>/dev/null && echo "REINSTALLED" || echo "STILL MISSING — must reinstall"
pluginkit -m -v 2>/dev/null | grep com.microsoft.CompanyPortalMac.ssoextension
```

Pass criteria: Company Portal reinstalled, SSO extension is registered. Do NOT proceed to STEP 3.7 until this passes.

### STEP 3.7 [interactive] Login directly to azclitools tenant

```bash
az logout
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6
az devops project list --org https://dev.azure.com/azclitools --output table
```

Pass criteria: Tenant-scoped login succeeds, project list returns.

---

## Section 4 — Telemetry Verification

Telemetry data takes ~1 hour to appear in the backend. Capture CorrelationIds now and verify later via KQL.

### STEP 4.1 [interactive] Capture successful broker login telemetry

Complete the login when prompted.

```bash
az logout 2>/dev/null || true
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6 --debug 2>&1 | tee /tmp/az-bugbash/st1_debug.log | grep -E "correlation.id|CorrelationId|telemetry" | head -20
az account show --output table
```

Pass criteria: CorrelationId captured from debug output. Mark `PASS (telemetry pending)`.

Expected backend fields: `EnableBrokerOnMac=True`, `BrokerAppUsed=true`, `MsalIsSuccessful=true`, `ActionResult=Success`

### STEP 4.2 [interactive] Capture cancelled login telemetry

When the broker/SSO dialog appears, click Cancel or close it.

```bash
az logout 2>/dev/null || true
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6 --debug 2>&1 | tee /tmp/az-bugbash/st2_debug.log | grep -E "correlation.id|CorrelationId" | head -5
```

Pass criteria: CorrelationId captured. Mark `PASS (telemetry pending)`.

Expected backend fields: `MsalIsSuccessful=false`, `ActionResult=Failure`, `error_type=AuthenticationError`

### STEP 4.3 [interactive] Capture non-broker contrast telemetry

Complete the browser login when prompted.

```bash
az logout 2>/dev/null || true
az config set core.login_experience_v2=off
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6 --debug 2>&1 | tee /tmp/az-bugbash/st3_debug.log | grep -E "correlation.id|CorrelationId|telemetry" | head -20
az account show --output table
az config set core.login_experience_v2=on
```

Pass criteria: CorrelationId captured, config restored to `on`. Mark `PASS (telemetry pending)`.

This record should NOT appear in broker-filtered KQL results.

### STEP 4.4 [auto] Verify installer field in debug output

```bash
az --version --debug 2>&1 | grep -i installer | head -5
az account show --output table --debug 2>&1 | grep -i installer | head -5
```

Pass criteria: `installer` field shows `HOMEBREW_CASK` (not `HOMEBREW`). If it still shows `HOMEBREW`, note as a bug.

### STEP 4.5 [manual] KQL backend verification (deferred)

This step is performed later (~1 hour after STEP 4.1–4.3). Use the KQL query below in your `RawEventsAzCli` workspace. Substitute the CorrelationIds captured in STEPs 4.1–4.3.

```kql
RawEventsAzCli
| where tostring(Properties["context.default.azurecli.enablebrokeronmac"]) =~ "true"
| extend MsalTelemetryRaw = tostring(Properties["context.default.azurecli.msaltelemetry"])
| extend MsalTelemetry = parse_json(MsalTelemetryRaw)
| extend MsalRuntime = MsalTelemetry.msalruntime_telemetry
| extend
    MsalApiName        = tostring(MsalRuntime.api_name),
    BrokerAppUsed      = tostring(MsalRuntime.broker_app_used),
    MsalIsSuccessful   = tostring(MsalRuntime.is_successful),
    MsalVersion        = tostring(MsalRuntime.msal_version),
    MsalRuntimeVersion = tostring(MsalRuntime.msalruntime_version)
| extend
    EnableBrokerOnMac = tostring(Properties["context.default.azurecli.enablebrokeronmac"]),
    RawCommand        = tostring(Properties["context.default.azurecli.rawcommand"]),
    CoreVersion       = tostring(Properties["context.default.azurecli.coreversion"]),
    Installer         = tostring(Properties["context.default.azurecli.installer"])
| project-reorder MsalApiName, BrokerAppUsed, MsalIsSuccessful, MsalVersion, MsalRuntimeVersion,
    EventTimestamp, RawCommand, Params, OsType, EnableBrokerOnMac, CoreVersion, Installer,
    UserId, MachineId, *
```

Pass criteria:
- ST1: `BrokerAppUsed=true`, `MsalIsSuccessful=true`
- ST2: `MsalIsSuccessful=false`, error markers present
- ST3: Should NOT appear in broker-filtered query
- `MsalVersion` and `MsalRuntimeVersion` are non-empty
- `Installer` shows `HOMEBREW_CASK`

---

## Section 5 — Offline Install (tarball + non-Homebrew Python)

### STEP 5.1 [destructive] Remove all Homebrew azure-cli installs

Warning: This removes both formula and cask installs if present.

```bash
brew uninstall azure-cli 2>/dev/null || true
brew uninstall --cask naga-nandyala/mycli-app/azure-cli 2>/dev/null || true
which az && echo "NOTE: az still present from another source" || echo "az removed"
```

Pass criteria: No active Homebrew azure-cli install.

### STEP 5.2 [auto] Download and extract architecture-specific tarball

The download URL includes the machine architecture. This is auto-detected.

```bash
VERSION=2.84.0
ARCH=$(uname -m)
TARBALL="azure-cli-${VERSION}-macos-${ARCH}.tar.gz"
curl -fL -o /tmp/${TARBALL} "https://github.com/naga-nandyala/azure-cli-latest/releases/download/azure-cli-${VERSION}/${TARBALL}"
rm -rf /tmp/az-offline && mkdir /tmp/az-offline
tar -xzf /tmp/${TARBALL} -C /tmp/az-offline
ls -la /tmp/az-offline/bin/az
```

Pass criteria: Tarball downloaded, extracted, `/tmp/az-offline/bin/az` exists. Store path as `AZ_OFFLINE_BIN=/tmp/az-offline/bin/az`.

### STEP 5.3 [auto] Verify signatures on offline binary

```bash
codesign -dv --verbose=4 /tmp/az-offline/bin/az 2>&1 | grep -E "Authority|TeamIdentifier|Signature"
spctl --assess --type execute --verbose /tmp/az-offline/bin/az 2>&1
```

Pass criteria: Signed by Microsoft, Gatekeeper assessment accepted.

### STEP 5.4 [auto] Confirm az fails without AZ_PYTHON

```bash
unset AZ_PYTHON
/tmp/az-offline/bin/az --version 2>&1 | head -5
```

Pass criteria: Exits with a human-readable error message (not a Python traceback). Non-zero exit code expected.

### STEP 5.5 [manual] Locate or install non-Homebrew Python

User action: Provide a path to a non-Homebrew Python 3.13, or install one from python.org or pyenv.

Check for existing non-Homebrew Python:

```bash
ls /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 2>/dev/null && echo "python.org Python found" || echo "not found"
which pyenv 2>/dev/null && pyenv versions 2>/dev/null || echo "pyenv not available"
```

Ask the user for the Python path and store it as `NON_HB_PYTHON`.

Pass criteria: A non-Homebrew Python 3.13 path is available. If not available, mark SKIP (and also SKIP 5.6 and 5.7).

### STEP 5.6 [auto] Run az with non-Homebrew Python

Depends on: STEP 5.5. If 5.5 was SKIP, mark this SKIP too.

Substitute `<NON_HB_PYTHON>` with the path from STEP 5.5:

```bash
AZ_PYTHON="<NON_HB_PYTHON>" /tmp/az-offline/bin/az --version
AZ_PYTHON="<NON_HB_PYTHON>" /tmp/az-offline/bin/az find "create storage account"
```

Pass criteria: `az --version` shows 2.84.0, no missing-package errors.

### STEP 5.7 [auto] Verify extensions work in offline mode

Depends on: STEP 5.5. If 5.5 was SKIP, mark this SKIP too.

```bash
AZ_PYTHON="<NON_HB_PYTHON>" /tmp/az-offline/bin/az extension list --output table
AZ_PYTHON="<NON_HB_PYTHON>" /tmp/az-offline/bin/az devops project list --org https://dev.azure.com/azclitools --output table
```

Pass criteria: Extensions from `~/.azure/cliextensions/` load correctly, project list returns.

### STEP 5.8 [auto] Cleanup offline artifacts

```bash
rm -rf /tmp/az-offline /tmp/azure-cli-*.tar.gz
unset AZ_PYTHON
```

Pass criteria: Temp files removed, environment variable cleared.

---

## Section 6 — Restore Baseline

### STEP 6.1 [auto] Untap test tap and reinstall homebrew-core azure-cli

```bash
brew untap naga-nandyala/mycli-app 2>/dev/null || true
brew install azure-cli
which az
az --version
```

Pass criteria: Homebrew-core azure-cli restored, version visible.

### STEP 6.2 [auto] Final sanity check

```bash
az extension list --output table
az account show --output table 2>/dev/null || echo "Not logged in (acceptable)"
ls ~/.azure/
```

Pass criteria: Environment is back to a stable, usable state. Extensions intact.

---

## Result Ledger

Fill in while executing. Use `PASS`, `FAIL`, `SKIP`, or `BLOCKED`.

```text
STEP 0.1 -
STEP 0.2 -
STEP 1.1 -
STEP 1.2 -
STEP 1.3 -
STEP 1.4 -
STEP 2.1 -
STEP 2.2 -
STEP 2.3 -
STEP 2.4 -
STEP 2.5 -
STEP 2.6 -
STEP 2.7 -
STEP 2.8 -
STEP 3.0 -
STEP 3.1 -
STEP 3.2 -
STEP 3.3 -
STEP 3.4 -
STEP 3.5 -
STEP 3.6 -
STEP 3.7 -
STEP 4.1 -
STEP 4.2 -
STEP 4.3 -
STEP 4.4 -
STEP 4.5 -
STEP 5.1 -
STEP 5.2 -
STEP 5.3 -
STEP 5.4 -
STEP 5.5 -
STEP 5.6 -
STEP 5.7 -
STEP 5.8 -
STEP 6.1 -
STEP 6.2 -
```
