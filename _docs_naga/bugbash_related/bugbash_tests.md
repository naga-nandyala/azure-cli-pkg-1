# Azure CLI macOS Bug Bash — Test Definitions

> This file is designed for both human reading AND automated execution by VS Code Copilot.
> Use the prompt `.github/prompts/run_bugbash.prompt.md` to run these tests automatically.

| | |
|---|---|
| **Cask source** | `naga-nandyala/homebrew-mycli-app` |
| **Release repo** | `naga-nandyala/azure-cli-latest` |
| **Version** | 2.84.0 |
| **azclitools tenant** | `ed94de55-1f87-4278-9651-525e7ba467d6` |
| **azclitools org** | `https://dev.azure.com/azclitools` |

Run on both **ARM64** and **Intel** machines. Work through sections in order.

---

## Section 1 — Current state (homebrew-core baseline)

Capture the state of the existing homebrew-core install before touching anything.

---

### S1-1: Installation check `[auto]`

**Commands:**

```bash
which az
az --version
brew info azure-cli 2>/dev/null || echo "azure-cli formula not installed"
brew list --formula | grep azure-cli
```

**Pass criteria:** Output contains `azure-cli` and a version number. Install prefix is under `/opt/homebrew/Cellar/azure-cli/` (ARM64) or `/usr/local/Cellar/azure-cli/` (Intel).

---

### S1-2: Capture extensions and config `[auto]`

**Commands:**

```bash
az extension list --output table
ls -la ~/.azure/cliextensions/ 2>/dev/null || echo "no cliextensions dir"
cat ~/.azure/config 2>/dev/null || echo "no config file"
ls ~/.azure/
```

**Pass criteria:** Commands complete. Record the extension list, config contents, and ~/.azure contents for later comparison.

---

### S1-3: Login and run a command against azclitools `[interactive]`

**User action:** A browser or broker login prompt will appear. Complete the login and select the azclitools tenant if prompted.

**Commands:**

```bash
az login
az account show --output table
az extension add --name azure-devops 2>/dev/null || true
az devops project list --org https://dev.azure.com/azclitools --output table
```

**Pass criteria:** Login succeeds, `az account show` returns account info, project list returns results from azclitools org.

---

### S1-4: az upgrade `[auto]`

**Commands:**

```bash
az upgrade 2>&1
```

**Pass criteria:** Command reports already up-to-date or completes an upgrade without errors. No Python tracebacks.

---

### S1-5: Reinstall homebrew-core formula `[auto]`

**Commands:**

```bash
brew reinstall azure-cli && az --version
```

**Verify:**

```bash
az extension list --output table
cat ~/.azure/config 2>/dev/null || echo "no config file"
```

**Pass criteria:** Reinstall completes without errors. `az --version` shows expected version. Config and extensions are intact.

---

### S1-6: Uninstall homebrew-core azure-cli `[destructive]`

**Warning:** This will remove the current azure-cli installation.

**Commands:**

```bash
brew uninstall azure-cli
```

**Verify:**

```bash
which az && echo "FAIL: az still on PATH" || echo "PASS: az removed"
brew list --formula | grep azure-cli && echo "FAIL: formula remains" || echo "PASS: formula removed"
ls ~/.azure/ && echo "PASS: ~/.azure retained" || echo "FAIL: ~/.azure gone"
ls ~/.azure/cliextensions/ 2>/dev/null && echo "PASS: extensions dir retained" || echo "NOTE: no extensions dir"
```

**Pass criteria:** `az` removed from PATH, formula gone, `~/.azure` directory and all contents (config, extensions) retained.

---

## Section 2 — New install via homebrew-cask

---

### S2-1: Tap and inspect cask `[auto]`

**Commands:**

```bash
brew tap naga-nandyala/mycli-app https://github.com/naga-nandyala/homebrew-mycli-app
brew tap-info naga-nandyala/mycli-app
brew info --cask naga-nandyala/mycli-app/azure-cli
cat $(brew --repository naga-nandyala/mycli-app)/Casks/azure-cli.rb
```

**Pass criteria:** Tap lists correctly, cask shows version 2.84.0, URL points to `naga-nandyala/azure-cli-latest` releases.

---

### S2-2: Install cask `[auto]`

**Commands:**

```bash
brew install --cask naga-nandyala/mycli-app/azure-cli
```

**Verify:**

```bash
which az
az --version
ls -la /opt/homebrew/Caskroom/azure-cli/ 2>/dev/null || ls -la /usr/local/Caskroom/azure-cli/ 2>/dev/null
```

**Pass criteria:** `az` resolves, version is 2.84.0, install lives under Caskroom.

---

### S2-3: Verify signatures `[auto]`

**Commands:**

```bash
AZ_BIN=$(which az)
codesign -dv --verbose=4 "${AZ_BIN}" 2>&1 | grep -E "Authority|TeamIdentifier|Signature"
spctl --assess --type execute --verbose "${AZ_BIN}" 2>&1
```

**Pass criteria:** Signed by Microsoft (`Developer ID Application: Microsoft Corporation`), Gatekeeper assessment passes.

---

### S2-4: Basic functionality `[auto]`

**Commands:**

```bash
az --version
az find "create a storage account"
az account show 2>&1 | head -10
```

**Pass criteria:** Commands exit cleanly or with auth-only errors. No Python tracebacks or import failures.

---

### S2-5: Verify old extensions still work `[auto]`

**Commands:**

```bash
az extension list --output table
az devops project list --org https://dev.azure.com/azclitools --output table
```

**Pass criteria:** Extensions from S1-2 are still listed, azure-devops extension returns project list. No re-install needed.

**Note:** If login has expired, this becomes an `[interactive]` test — user will need to `az login` first.

---

### S2-6: Install a new extension, then uninstall it `[auto]`

**Commands:**

```bash
az extension add --name account
az extension list --output table
az extension show --name account
az extension remove --name account
az extension list --output table
```

**Pass criteria:** Extension installs to `~/.azure/cliextensions/`, shows correctly, removes cleanly.

---

### S2-7: az upgrade `[auto]`

**Commands:**

```bash
az upgrade 2>&1
```

**Pass criteria:** Cask-installed CLI handles the self-update path without errors. Reports up-to-date or completes upgrade. No Python tracebacks.

---

### S2-8: Reinstall and upgrade simulation `[auto]`

**Commands:**

```bash
brew reinstall --cask naga-nandyala/mycli-app/azure-cli
az --version
brew upgrade --cask naga-nandyala/mycli-app/azure-cli 2>&1
az --version
```

**Pass criteria:** Both commands complete without errors or broken symlinks. Version remains 2.84.0.

---

### S2-9: Uninstall cask `[destructive]`

**Warning:** This will remove the cask-installed azure-cli.

**Commands:**

```bash
brew uninstall --cask naga-nandyala/mycli-app/azure-cli
```

**Verify:**

```bash
which az && echo "FAIL: az still on PATH" || echo "PASS: az removed"
ls /opt/homebrew/Caskroom/azure-cli 2>/dev/null && echo "FAIL: Caskroom dir remains" || echo "PASS: Caskroom cleaned"
ls ~/.azure/ && echo "PASS: ~/.azure retained" || echo "FAIL: ~/.azure gone"
ls ~/.azure/cliextensions/ 2>/dev/null && echo "PASS: extensions retained" || echo "NOTE: no extensions dir"
```

**Pass criteria:** `az` removed, Caskroom directory gone, `~/.azure` and extensions retained.

---

## Section 3 — Broker authentication

Re-install the cask before running broker tests:

```bash
brew install --cask naga-nandyala/mycli-app/azure-cli 2>/dev/null || true
```

---

### S3-1: Check Company Portal `[auto]`

**Commands:**

```bash
ls /Applications/Company\ Portal.app 2>/dev/null && echo "FOUND" || echo "NOT INSTALLED"
defaults read /Applications/Company\ Portal.app/Contents/Info CFBundleShortVersionString 2>/dev/null || echo "version read failed"
```

**Pass criteria:** Company Portal is present. Version is recorded.

---

### S3-2: Broker auto-invoked on az login (config = default) `[interactive]`

**User action:** A login prompt will appear. Note whether it is the **macOS broker dialog** (Company Portal / SSO) or a **browser tab**. Complete the login.

**Commands:**

```bash
az logout 2>/dev/null || true
az config get core.login_experience_v2 2>/dev/null || echo "not set (defaults to broker on macOS)"
az login
az account show --output table
```

**After command completes, ask the user:** "Did the login open via the macOS broker (Company Portal SSO dialog) or via a browser tab?"

**Pass criteria:** Broker UI launched (not browser), login succeeded, account shown.

---

### S3-3: Disable broker → browser fallback `[interactive]`

**User action:** A browser tab should open for login (not broker). Complete the login.

**Commands:**

```bash
az logout
az config set core.login_experience_v2=off
az config get core.login_experience_v2
az login
az account show --output table
```

**After command completes, ask the user:** "Did the login open via a browser tab (not broker)?"

**Pass criteria:** Browser-based login opened (not broker UI), login succeeded.

---

### S3-4: Re-enable broker → broker invoked again `[interactive]`

**User action:** The broker dialog should appear again. Complete the login.

**Commands:**

```bash
az logout
az config set core.login_experience_v2=on
az config get core.login_experience_v2
az login
az account show --output table
```

**After command completes, ask the user:** "Did the login use the broker (Company Portal SSO) again?"

**Pass criteria:** Broker UI opened, login succeeded.

---

### S3-5: No Company Portal + config=true → browser fallback `[destructive]` `[interactive]`

**Warning:** This test removes Company Portal. You MUST reinstall it immediately after.

**Commands (uninstall):**

```bash
az logout
sudo rm -rf /Applications/Company\ Portal.app
ls /Applications/Company\ Portal.app 2>/dev/null && echo "still present" || echo "REMOVED"
az config get core.login_experience_v2
az login
az account show --output table
```

**After login completes, ask the user:** "Did it fall back gracefully to browser login?"

**Mandatory recovery — run immediately after:**

```bash
# User must open Mac App Store and install Microsoft Intune Company Portal
# Then verify:
ls /Applications/Company\ Portal.app 2>/dev/null && echo "REINSTALLED" || echo "STILL MISSING — must reinstall"
pluginkit -m -v 2>/dev/null | grep com.microsoft.CompanyPortalMac.ssoextension
```

**Pass criteria:** Azure CLI fell back to browser (no crash), login succeeded, Company Portal reinstalled after test.

---

### S3-6: Login into azclitools tenant `[interactive]`

**User action:** Complete the broker/browser login.

**Commands:**

```bash
az logout
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6
az devops project list --org https://dev.azure.com/azclitools --output table
```

**Pass criteria:** Broker acquires token scoped to azclitools tenant, project list returns.

---

## Section 4 — Telemetry verification

> Telemetry is available ~1 hour after login events. Record CorrelationIds now and verify later.

---

### ST-1: Successful broker login `[interactive]`

**Commands:**

```bash
az logout 2>/dev/null || true
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6 --debug 2>&1 | tee /tmp/st1_debug.log | grep -E "correlation.id|CorrelationId|telemetry" | head -20
az account show --output table
```

**Capture:** The CorrelationId from debug output. Mark as `PASS (telemetry pending)`.

**Verify later (KQL):** `EnableBrokerOnMac=True`, `BrokerAppUsed=true`, `MsalIsSuccessful=true`, `ActionResult=Success`

---

### ST-2: Cancelled broker login `[interactive]`

**User action:** When the broker/SSO dialog appears, click **Cancel** or close it.

**Commands:**

```bash
az logout 2>/dev/null || true
az login --tenant ed94de55-1f87-4278-9651-525e7ba467d6 --debug 2>&1 | tee /tmp/st2_debug.log | grep -E "correlation.id|CorrelationId" | head -5
```

**Capture:** CorrelationId. Mark as `PASS (telemetry pending)`.

**Verify later (KQL):** `MsalIsSuccessful=false`, `ActionResult=Failure`, `error_type=AuthenticationError`

---

### ST-3: Non-broker login contrast `[interactive]`

**Commands:**

```bash
az logout 2>/dev/null || true
az config set core.login_experience_v2=off
az login --debug 2>&1 | tee /tmp/st3_debug.log | grep -E "correlation.id|CorrelationId" | head -5
az account show --output table
az config set core.login_experience_v2=on
```

**Capture:** CorrelationId. Mark as `PASS (telemetry pending)`.

**Verify later:** This record should NOT appear in broker-filtered KQL query.

---

### ST-4: Verify installer field `[auto]`

**Commands:**

```bash
az --version --debug 2>&1 | grep -i installer | head -5
az account show --output table --debug 2>&1 | grep -i installer | head -5
```

**Pass criteria:** `installer` field shows `HOMEBREW_CASK` (not `HOMEBREW`). Mark as `PASS (telemetry pending)` for backend confirmation.

---

### ST-5: MSAL version fields `[manual]`

This test is verified via KQL after ST-1 completes.

**Pass criteria (check KQL after ~1 hour):** `MsalVersion` is non-empty, `MsalRuntimeVersion` is non-empty.

**KQL query for all telemetry tests:**

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
    CoreVersion       = tostring(Properties["context.default.azurecli.coreversion"])
| project-reorder MsalApiName, BrokerAppUsed, MsalIsSuccessful, MsalVersion, MsalRuntimeVersion,
    EventTimestamp, RawCommand, Params, OsType, EnableBrokerOnMac, CoreVersion, UserId, MachineId, *
```

---

## Section 5 — Offline install (tarball, non-Homebrew Python)

---

### S5-1: Download and extract tarball `[auto]`

**Commands:**

```bash
VERSION=2.84.0
ARCH=$(uname -m)
TARBALL="azure-cli-${VERSION}-macos-${ARCH}.tar.gz"
curl -L -o /tmp/${TARBALL} "https://github.com/naga-nandyala/azure-cli-latest/releases/download/azure-cli-${VERSION}/${TARBALL}"
rm -rf /tmp/az-offline && mkdir /tmp/az-offline
tar -xzf /tmp/${TARBALL} -C /tmp/az-offline
ls -la /tmp/az-offline/bin/az
```

**Pass criteria:** Tarball downloads, extracts, and `/tmp/az-offline/bin/az` exists.

---

### S5-2: Verify signatures on tarball binary `[auto]`

**Commands:**

```bash
codesign -dv --verbose=4 /tmp/az-offline/bin/az 2>&1 | grep -E "Authority|TeamIdentifier|Signature"
spctl --assess --type execute --verbose /tmp/az-offline/bin/az 2>&1
```

**Pass criteria:** Signed by Microsoft, Gatekeeper passes.

---

### S5-3: Confirm az fails without AZ_PYTHON `[auto]`

**Commands:**

```bash
/tmp/az-offline/bin/az --version 2>&1 | head -5
```

**Pass criteria:** Exits with a human-readable error (not a Python traceback).

---

### S5-4: Install non-Homebrew Python `[manual]`

**User action:** Install Python 3.13 from a non-Homebrew source (python.org or pyenv).

**Check commands:**

```bash
ls /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 2>/dev/null && echo "python.org Python found" || echo "not found"
which pyenv 2>/dev/null && pyenv versions 2>/dev/null || echo "pyenv not available"
```

**Ask the user for the Python path** and store it as `NON_HB_PYTHON`.

**Pass criteria:** A non-Homebrew Python 3.13 is available. If not available, mark SKIP.

---

### S5-5: Run az with non-Homebrew Python `[auto]`

**Depends on:** S5-4. If S5-4 was SKIP, mark this SKIP too.

**Commands (substitute the Python path from S5-4):**

```bash
AZ_PYTHON="<NON_HB_PYTHON>" /tmp/az-offline/bin/az --version
AZ_PYTHON="<NON_HB_PYTHON>" /tmp/az-offline/bin/az find "create storage account"
```

**Pass criteria:** `az --version` shows 2.84.0, no missing-package errors.

---

### S5-6: Verify old extensions in offline mode `[auto]`

**Depends on:** S5-4. If S5-4 was SKIP, mark this SKIP too.

**Commands:**

```bash
AZ_PYTHON="<NON_HB_PYTHON>" /tmp/az-offline/bin/az extension list --output table
AZ_PYTHON="<NON_HB_PYTHON>" /tmp/az-offline/bin/az devops project list --org https://dev.azure.com/azclitools --output table
```

**Pass criteria:** Extensions from `~/.azure/cliextensions/` load correctly, project list returns.

---

### S5-7: Cleanup `[auto]`

**Commands:**

```bash
rm -rf /tmp/az-offline /tmp/azure-cli-*.tar.gz
```

**Pass criteria:** Temp files removed.

---

## Section 6 — Restore homebrew-core azure-cli

---

### S6: Restore original state `[auto]`

**Commands:**

```bash
brew uninstall --cask naga-nandyala/mycli-app/azure-cli 2>/dev/null || true
brew untap naga-nandyala/mycli-app 2>/dev/null || true
brew install azure-cli
which az
az --version
az extension list --output table
```

**Pass criteria:** Homebrew-core azure-cli back in place, pre-existing extensions still present and functional.
