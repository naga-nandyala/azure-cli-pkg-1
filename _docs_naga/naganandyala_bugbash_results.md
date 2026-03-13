# Azure CLI macOS Bug Bash — Results Log

| | |
|---|---|
| **Tester** | naganandyala |
| **Machine** | arm64 — macOS macOS 26.3.1 (Build 25D2128) |
| **Hostname** | Nagas-MacBook-Pro |
| **Date** | 2026-03-13 |
| **Cask source** | `naga-nandyala/mycli-app` |
| **Version under test** | 2.84.0 |
| **Plan doc** | [bugbash_tests.md](bugbash_tests.md) |

Status legend: `PASS` `FAIL` `SKIP` `BLOCKED` `PASS (telemetry pending)`

---

## Section 1 — Current state (homebrew-core baseline)

### S1-1: Installation check — PASS

```
/opt/homebrew/bin/az
azure-cli                         2.84.0

core                              2.84.0
telemetry                          1.1.0

Extensions:
azure-devops                       1.0.2

Dependencies:
msal                            1.35.0b1
azure-mgmt-resource               24.0.0

Python location '/opt/homebrew/Cellar/azure-cli/2.84.0/libexec/bin/python'
Config directory '/Users/naganandyala/.azure'
Extensions directory '/Users/naganandyala/.azure/cliextensions'

Python (Darwin) 3.13.12 (main, Feb  3 2026, 17:53:27) [Clang 17.0.0 (clang-1700.6.3.2)]

Legal docs and information: aka.ms/AzureCliLegal


Your CLI is up-to-date.
==> azure-cli ✔: stable 2.84.0 (bottled), HEAD
Microsoft Azure CLI 2.0
https://docs.microsoft.com/cli/azure/overview
Installed
/opt/homebrew/Cellar/azure-cli/2.84.0 (16,351 files, 356.4MB) *
	Poured from bottle using the formulae.brew.sh API on 2026-03-13 at 11:41:02
From: https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/a/azure-cli.rb
License: MIT
==> Dependencies
Build: pkgconf ✔, rust ✘
Required: libsodium ✔, libyaml ✔, openssl@3 ✔, python@3.13 ✔
==> Options
--HEAD
				Install HEAD version
==> Analytics
install: 31,159 (30 days), 97,559 (90 days), 435,130 (365 days)
install-on-request: 31,117 (30 days), 97,396 (90 days), 434,605 (365 days)
build-error: 124 (30 days)
azure-cli
```

Found homebrew-core install at /opt/homebrew/Cellar/azure-cli/2.84.0 on arm64.

### S1-2: Capture extensions and config — PASS

```
Experimental    ExtensionType    Name          Path                                                  
 Preview    Version                                                                                  
--------------  ---------------  ------------  ----------------------------------------------------- 
---------  ---------                                                                                False           whl              azure-devops  /Users/naganandyala/.azure/cliextensions/azure-devops 
False      1.0.2                                                                                    total 0
drwxr-xr-x@  3 naganandyala  staff   96 Mar 13 11:31 .
drwxr-xr-x@ 19 naganandyala  staff  608 Mar 13 11:31 ..
drwxr-xr-x@  8 naganandyala  staff  256 Mar 13 11:31 azure-devops
[cloud]
name = AzureCloud

[core]
first_run = yes

az_survey.json                           config
az.json                                  extensionCommandTree.json
az.sess                                  logs
azuredevops                              ms-azuretools.vscode-azureresourcegroups
azureProfile.json                        msal_http_cache.bin
cliextensions                            msal_token_cache.json
clouds.config                            telemetry
commandIndex.json                        versionCheck.json
commands
```

Captured baseline extension list, ~/.azure/config, and ~/.azure directory contents.

### S1-3: Login and run a command against azclitools — PENDING

```
(output will be captured here)
```

### S1-4: Uninstall homebrew-core azure-cli — PENDING

```
(output will be captured here)
```

---

## Section 2 — New install via homebrew-cask

### S2-1: Tap and inspect cask — PENDING

```
(output will be captured here)
```

### S2-2: Install cask — PENDING

```
(output will be captured here)
```

### S2-3: Verify signatures — PENDING

```
(output will be captured here)
```

### S2-4: Basic functionality — PENDING

```
(output will be captured here)
```

### S2-5: Verify old extensions still work — PENDING

```
(output will be captured here)
```

### S2-6: Install a new extension, then uninstall it — PENDING

```
(output will be captured here)
```

### S2-7: Reinstall and upgrade simulation — PENDING

```
(output will be captured here)
```

### S2-8: Uninstall cask — PENDING

```
(output will be captured here)
```

---

## Section 3 — Broker authentication

### S3-1: Check Company Portal — PENDING

```
(output will be captured here)
```

### S3-2: Broker auto-invoked on az login (config = default) — PENDING

```
(output will be captured here)
```

### S3-3: Disable broker → browser fallback — PENDING

```
(output will be captured here)
```

### S3-4: Re-enable broker → broker invoked again — PENDING

```
(output will be captured here)
```

### S3-5: No Company Portal + config=true → browser fallback — PENDING

```
(output will be captured here)
```

### S3-6: Login into azclitools tenant — PENDING

```
(output will be captured here)
```

---

## Section 4 — Telemetry verification

### ST-1: Successful broker login — PENDING

```
(output will be captured here)
```

**CorrelationId:** (to be captured)

### ST-2: Cancelled broker login — PENDING

```
(output will be captured here)
```

**CorrelationId:** (to be captured)

### ST-3: Non-broker login contrast — PENDING

```
(output will be captured here)
```

**CorrelationId:** (to be captured)

### ST-4: Verify installer field — PENDING

```
(output will be captured here)
```

### ST-5: MSAL version fields — PENDING

Verified via KQL after ST-1. Fields to check: `MsalVersion`, `MsalRuntimeVersion`.

---

## Section 5 — Offline install (tarball, non-Homebrew Python)

### S5-1: Download and extract tarball — PENDING

```
(output will be captured here)
```

### S5-2: Verify signatures on tarball binary — PENDING

```
(output will be captured here)
```

### S5-3: Confirm az fails without AZ_PYTHON — PENDING

```
(output will be captured here)
```

### S5-4: Install non-Homebrew Python — PENDING

```
(output will be captured here)
```

### S5-5: Run az with non-Homebrew Python — PENDING

```
(output will be captured here)
```

### S5-6: Verify old extensions in offline mode — PENDING

```
(output will be captured here)
```

### S5-7: Cleanup — PENDING

```
(output will be captured here)
```

---

## Section 6 — Restore homebrew-core azure-cli

### S6: Restore original state — PENDING

```
(output will be captured here)
```

---

## Result Summary

| Test | Description | Result | Notes |
|------|-------------|--------|-------|
| S1-1 | Installation check | | |
| S1-2 | Capture extensions/config | | |
| S1-3 | Login + azclitools project list | | |
| S1-4 | Uninstall homebrew-core, ~/.azure retained | | |
| S2-1 | Tap + inspect cask | | |
| S2-2 | Cask install, verify location | | |
| S2-3 | Verify signatures | | |
| S2-4 | Basic az commands | | |
| S2-5 | Old extensions still work | | |
| S2-6 | New extension install/uninstall | | |
| S2-7 | Reinstall + upgrade simulation | | |
| S2-8 | Cask uninstall, ~/.azure retained | | |
| S3-1 | Company Portal present + version | | |
| S3-2 | Broker auto-invoked (default config) | | |
| S3-3 | Config=off → browser login | | |
| S3-4 | Config=on → broker login | | |
| S3-5 | No Company Portal + config=on → browser fallback | | |
| S3-6 | Broker login to azclitools tenant | | |
| ST-1 | Successful broker login — telemetry fields | | |
| ST-2 | Cancelled broker login — UserCanceled telemetry | | |
| ST-3 | Non-broker login — absent from broker query | | |
| ST-4 | `installer` field reflects cask (not formula) | | |
| ST-5 | `MsalVersion` + `MsalRuntimeVersion` populated | | |
| S5-1 | Tarball download + extract | | |
| S5-2 | Signatures on tarball binary | | |
| S5-3 | az fails without AZ_PYTHON | | |
| S5-4 | Non-Homebrew Python install | | |
| S5-5 | az works with non-Homebrew Python | | |
| S5-6 | Old extensions work in tarball mode | | |
| S5-7 | Cleanup | | |
| S6 | Restore homebrew-core | | |
