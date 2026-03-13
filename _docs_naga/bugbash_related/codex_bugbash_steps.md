# Azure CLI macOS Bug Bash - Codex Source of Truth

This document is the single source of truth for a Copilot/Codex execution session.
Run steps strictly in order, one by one, and do not skip sections.

## Execution Contract

1. Execute steps in numeric order only.
2. After each step, record result as `PASS`, `FAIL`, `SKIP`, or `BLOCKED`.
3. If a step fails, stop and ask whether to continue.
4. For `interactive` steps, wait for user confirmation before marking the step complete.
5. For `destructive` steps, print a warning and wait for explicit user confirmation before running commands.
6. Do not modify commands unless a command is clearly incompatible with the current machine.
7. Preserve `~/.azure` state where called out.

## Test Metadata

- Cask source: `naga-nandyala/mycli-app`
- Release repo: `naga-nandyala/azure-cli-latest`
- Version under test: `2.84.0`
- azclitools tenant: `ed94de55-1f87-4278-9651-525e7ba467d6`
- azclitools org: `https://dev.azure.com/azclitools`
- Platforms: macOS ARM64 and Intel

## Session Setup

### STEP 0.1 [auto] Detect machine and set install root

```bash
uname -m
sw_vers

if [ "$(uname -m)" = "arm64" ]; then
  export BREW_PREFIX=/opt/homebrew
else
  export BREW_PREFIX=/usr/local
fi

echo "BREW_PREFIX=$BREW_PREFIX"
```

Pass criteria: machine architecture and macOS version are visible; `BREW_PREFIX` resolves correctly.

### STEP 0.2 [auto] Create working notes directory

```bash
mkdir -p /tmp/az-bugbash
echo "Notes path: /tmp/az-bugbash"
```

Pass criteria: `/tmp/az-bugbash` exists.

## Section 1 - Current State (homebrew-core baseline)

### STEP 1.1 [auto] Installation check

```bash
which az
az --version
brew info azure-cli 2>/dev/null || echo "azure-cli formula not installed"
brew list --formula | grep azure-cli
```

Pass criteria: `azure-cli` formula presence and version are visible.

### STEP 1.2 [auto] Capture extensions and config

```bash
az extension list --output table
ls -la ~/.azure/cliextensions/ 2>/dev/null || echo "no cliextensions dir"
cat ~/.azure/config 2>/dev/null || echo "no config file"
ls ~/.azure/
```

Pass criteria: extension list and `~/.azure` config snapshot captured.

### STEP 1.3 [interactive] Login and validate azclitools access

```bash
az login
az account show --output table
az extension add --name azure-devops 2>/dev/null || true
az devops project list --org https://dev.azure.com/azclitools --output table
```

Pass criteria: login succeeds and azclitools projects list returns.

### STEP 1.4 [destructive] Uninstall homebrew-core azure-cli

Warning: removes current formula install.

```bash
brew uninstall azure-cli

which az && echo "FAIL: az still on PATH" || echo "PASS: az removed"
brew list --formula | grep azure-cli && echo "FAIL: formula remains" || echo "PASS: formula removed"
ls ~/.azure/ && echo "PASS: ~/.azure retained" || echo "FAIL: ~/.azure gone"
ls ~/.azure/cliextensions/ 2>/dev/null && echo "PASS: extensions dir retained" || echo "NOTE: no extensions dir"
```

Pass criteria: `az` is removed and `~/.azure` remains intact.

## Section 2 - New Install via Cask

### STEP 2.1 [auto] Tap and inspect cask

```bash
brew tap naga-nandyala/mycli-app https://github.com/naga-nandyala/homebrew-mycli-app
brew tap-info naga-nandyala/mycli-app
brew info --cask naga-nandyala/mycli-app/azure-cli
cat "$(brew --repository naga-nandyala/mycli-app)/Casks/azure-cli.rb"
```

Pass criteria: cask metadata points to target release source and expected version.

### STEP 2.2 [auto] Install cask

```bash
brew install --cask naga-nandyala/mycli-app/azure-cli
which az
az --version
ls -la "$BREW_PREFIX/Caskroom/azure-cli/" 2>/dev/null
```

Pass criteria: `az` is installed from Caskroom and reports target version.

### STEP 2.3 [auto] Verify signature and Gatekeeper

```bash
AZ_BIN=$(which az)
codesign -dv --verbose=4 "$AZ_BIN" 2>&1 | grep -E "Authority|TeamIdentifier|Signature"
spctl --assess --type execute --verbose "$AZ_BIN" 2>&1
```

Pass criteria: signed by Microsoft and Gatekeeper accepts execution.

### STEP 2.4 [auto] Basic command health

```bash
az --version
az find "create a storage account"
az account show 2>&1 | head -10
```

Pass criteria: no Python import/traceback errors.

### STEP 2.5 [auto] Existing extension compatibility

```bash
az extension list --output table
az devops project list --org https://dev.azure.com/azclitools --output table
```

Pass criteria: prior extensions still work without reinstall.

### STEP 2.6 [auto] New extension install/remove cycle

```bash
az extension add --name account
az extension list --output table
az extension show --name account
az extension remove --name account
az extension list --output table
```

Pass criteria: extension installs and removes cleanly.

### STEP 2.7 [auto] Reinstall and upgrade simulation

```bash
brew reinstall --cask naga-nandyala/mycli-app/azure-cli
az --version
brew upgrade --cask naga-nandyala/mycli-app/azure-cli 2>&1
az --version
```

Pass criteria: no broken links or command failures.

### STEP 2.8 [destructive] Uninstall cask and verify retention

Warning: removes cask install.

```bash
brew uninstall --cask naga-nandyala/mycli-app/azure-cli

which az && echo "FAIL: az still on PATH" || echo "PASS: az removed"
ls "$BREW_PREFIX/Caskroom/azure-cli" 2>/dev/null && echo "FAIL: Caskroom dir remains" || echo "PASS: Caskroom cleaned"
ls ~/.azure/ && echo "PASS: ~/.azure retained" || echo "FAIL: ~/.azure gone"
ls ~/.azure/cliextensions/ 2>/dev/null && echo "PASS: extensions retained" || echo "NOTE: no extensions dir"
```

Pass criteria: cask removed; `~/.azure` retained.

## Section 3 - Broker Authentication

### STEP 3.0 [auto] Ensure cask installed for broker tests

```bash
brew install --cask naga-nandyala/mycli-app/azure-cli 2>/dev/null || true
```

Pass criteria: `az` available.

### STEP 3.1 [auto] Check Company Portal presence and version

```bash
ls /Applications/Company\ Portal.app 2>/dev/null && echo "FOUND" || echo "NOT INSTALLED"
defaults read /Applications/Company\ Portal.app/Contents/Info CFBundleShortVersionString 2>/dev/null || echo "version read failed"
```

Pass criteria: Company Portal present and version known.

### STEP 3.2 [interactive] Default login experience should use broker

```bash
az logout 2>/dev/null || true
az config get core.login_experience_v2 2>/dev/null || echo "not set"
az login
az account show --output table
```

Ask user: Did login open as broker UI (Company Portal SSO) rather than browser?

Pass criteria: broker-based sign-in path succeeds.

### STEP 3.3 [interactive] Disable broker and verify browser fallback

```bash
az logout
az config set core.login_experience_v2=off
az config get core.login_experience_v2
az login
az account show --output table
```

Ask user: Did login open in a browser tab?

Pass criteria: browser login path succeeds with broker disabled.

### STEP 3.4 [interactive] Re-enable broker and verify broker path returns

```bash
az logout
az config set core.login_experience_v2=on
az config get core.login_experience_v2
az login
az account show --output table
```

Ask user: Did login switch back to broker UI?

Pass criteria: broker login path restored.

### STEP 3.5 [destructive, interactive] Remove Company Portal and verify graceful fallback

Warning: removes Company Portal. Reinstall immediately after this test.

```bash
az logout
sudo rm -rf /Applications/Company\ Portal.app
ls /Applications/Company\ Portal.app 2>/dev/null && echo "still present" || echo "REMOVED"
az config get core.login_experience_v2
az login
az account show --output table
```

Ask user: Did Azure CLI fall back to browser cleanly without crash?

Pass criteria: browser fallback works when Company Portal is missing.

### STEP 3.6 [interactive, required recovery] Reinstall Company Portal and verify extension

User action required:

1. Install Microsoft Intune Company Portal from Mac App Store.
2. Launch and sign in if prompted.

Then run:

```bash
ls /Applications/Company\ Portal.app 2>/dev/null && echo "REINSTALLED" || echo "STILL MISSING"
pluginkit -m -v 2>/dev/null | grep com.microsoft.CompanyPortalMac.ssoextension
```

Pass criteria: app restored and SSO extension listed.

### STEP 3.7 [interactive] Login directly to azclitools tenant

```bash
az logout
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6
az devops project list --org https://dev.azure.com/azclitools --output table
```

Pass criteria: tenant-scoped login and azclitools project listing succeed.

## Section 4 - Telemetry Verification

Note: telemetry often appears within about 1 hour.

### STEP 4.1 [interactive] Capture successful broker login telemetry

```bash
az logout 2>/dev/null || true
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6 --debug 2>&1 | tee /tmp/az-bugbash/st1_debug.log | grep -E "correlation.id|CorrelationId|telemetry" | head -20
az account show --output table
```

Pass criteria: correlation ID captured from debug output.

### STEP 4.2 [interactive] Capture cancelled login telemetry

User action: cancel the broker/browser login when prompted.

```bash
az logout 2>/dev/null || true
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6 --debug 2>&1 | tee /tmp/az-bugbash/st2_debug.log | grep -E "correlation.id|CorrelationId" | head -5
```

Pass criteria: correlation ID captured for cancelled flow.

### STEP 4.3 [interactive] Capture non-broker contrast telemetry

```bash
az logout
az config set core.login_experience_v2=off
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6 --debug 2>&1 | tee /tmp/az-bugbash/st3_debug.log | grep -E "correlation.id|CorrelationId|telemetry" | head -20
az account show --output table
az config set core.login_experience_v2=on
```

Pass criteria: non-broker correlation ID captured and config restored to `on`.

### STEP 4.4 [auto] KQL template for backend verification

Use the following KQL in your telemetry workspace after ingestion delay:

```kusto
let lookback = 3d;
let corr = dynamic([
  "<ST1-correlation-id>",
  "<ST2-correlation-id>",
  "<ST3-correlation-id>"
]);
RawEvents
| where PreciseTimeStamp > ago(lookback)
| where CorrelationId in (corr)
| project PreciseTimeStamp, CorrelationId, Name, ActionResult, ResultType,
          EnableBrokerOnMac=tobool(CustomDimensions.EnableBrokerOnMac),
          BrokerAppUsed=tobool(CustomDimensions.BrokerAppUsed),
          MsalIsSuccessful=tobool(CustomDimensions.MsalIsSuccessful),
          MsalVersion=tostring(CustomDimensions.MsalVersion),
          MsalRuntimeVersion=tostring(CustomDimensions.MsalRuntimeVersion),
          Installer=tostring(CustomDimensions.installer),
          ErrorType=tostring(CustomDimensions.error_type)
| order by PreciseTimeStamp desc
```

Pass criteria:

- ST1 shows successful broker properties.
- ST2 shows cancelled/failure markers.
- ST3 shows non-broker contrast.
- `MsalVersion` and `MsalRuntimeVersion` are populated.
- Installer reflects cask-based installation where applicable.

## Section 5 - Offline Install (tarball + non-Homebrew Python)

### STEP 5.1 [destructive] Clean existing azure-cli installs

Warning: removes formula and cask installs if present.

```bash
brew uninstall azure-cli 2>/dev/null || true
brew uninstall --cask naga-nandyala/mycli-app/azure-cli 2>/dev/null || true
which az && echo "NOTE: az still present" || echo "az removed"
```

Pass criteria: no active Homebrew azure-cli install.

### STEP 5.2 [auto] Download and extract tarball

```bash
mkdir -p /tmp/az-bugbash/offline && cd /tmp/az-bugbash/offline
curl -fL -o azure-cli.tar.gz https://github.com/naga-nandyala/azure-cli-latest/releases/download/azure-cli-2.84.0/azure-cli-2.84.0.tar.gz
tar -xzf azure-cli.tar.gz
find . -maxdepth 3 -name az -type f | head -5
```

Pass criteria: tarball extracted and `az` binary found.

### STEP 5.3 [auto] Verify signatures on offline binary

```bash
AZ_OFFLINE_BIN=$(find /tmp/az-bugbash/offline -name az -type f | head -1)
codesign -dv --verbose=4 "$AZ_OFFLINE_BIN" 2>&1 | grep -E "Authority|TeamIdentifier|Signature"
spctl --assess --type execute --verbose "$AZ_OFFLINE_BIN" 2>&1
```

Pass criteria: valid signature and accepted assessment.

### STEP 5.4 [auto] Confirm failure without AZ_PYTHON

```bash
unset AZ_PYTHON
"$AZ_OFFLINE_BIN" --version
```

Pass criteria: command fails due to missing Python runtime.

### STEP 5.5 [interactive] Install non-Homebrew Python and set AZ_PYTHON

User action: install Python from a non-Homebrew source (for example python.org installer).

Then run:

```bash
export AZ_PYTHON=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
"$AZ_PYTHON" --version
"$AZ_OFFLINE_BIN" --version
```

Pass criteria: offline `az` works using non-Homebrew Python.

### STEP 5.6 [interactive] Validate extension compatibility in offline mode

```bash
"$AZ_OFFLINE_BIN" extension list --output table
"$AZ_OFFLINE_BIN" devops project list --org https://dev.azure.com/azclitools --output table
```

Pass criteria: extensions remain usable in offline run.

### STEP 5.7 [destructive] Cleanup offline artifacts

```bash
rm -rf /tmp/az-bugbash/offline
unset AZ_PYTHON
```

Pass criteria: offline artifacts removed and environment reset.

## Section 6 - Restore Baseline

### STEP 6.1 [auto] Reinstall homebrew-core azure-cli

```bash
brew install azure-cli
which az
az --version
```

Pass criteria: baseline formula install restored.

### STEP 6.2 [auto] Final sanity check

```bash
az extension list --output table
az account show --output table 2>/dev/null || echo "Not logged in (acceptable)"
ls ~/.azure/
```

Pass criteria: environment is back in stable usable state.

## Result Ledger Template

Use this ledger while executing:

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
STEP 5.1 -
STEP 5.2 -
STEP 5.3 -
STEP 5.4 -
STEP 5.5 -
STEP 5.6 -
STEP 5.7 -
STEP 6.1 -
STEP 6.2 -
```
