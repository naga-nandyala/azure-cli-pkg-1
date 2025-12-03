# Azure DevOps Pipeline Setup Guide

This guide walks you through setting up the Azure CLI macOS PKG signing pipeline in Azure DevOps.

## Overview

- **Azure DevOps Organization**: https://dev.azure.com/azclitools/public
- **GitHub Repository**: https://github.com/naga-nandyala/azure-cli-pkg-1
- **Pipeline**: `.azure-pipelines/azure-cli-macos-pkg-signing.yml`

The pipeline will:
1. Download unsigned PKG files from GitHub releases
2. Sign them using OneBranch/ESRP with Apple Developer ID certificate
3. Upload signed PKGs back to GitHub releases

---

## 🚀 Setup Steps

### **Step 1: Create Service Connection to GitHub**

This allows Azure DevOps to access your GitHub repository.

1. Go to your Azure DevOps project: https://dev.azure.com/azclitools/public
2. Navigate to **Project Settings** (bottom left gear icon) → **Service connections**
3. Click **New service connection** → Select **GitHub**
4. Choose authentication method:
   - **Option A - OAuth (Recommended)**:
     - Click "Authorize" and sign in to your GitHub account
     - Approve the Azure Pipelines app
   - **Option B - Personal Access Token**:
     - Go to https://github.com/settings/tokens
     - Click **Generate new token (classic)**
     - Give it a name: `Azure DevOps - azclitools`
     - Select scopes: `repo` (full control of private repositories)
     - Click **Generate token**
     - Copy the token (you won't see it again!)
     - Paste it into Azure DevOps
5. **Service connection name**: `github-naga-nandyala` (or your preferred name)
6. **Description**: `Connection to naga-nandyala GitHub account for azure-cli-pkg-1`
7. Check **✓ Grant access permission to all pipelines**
8. Click **Save**

---

### **Step 2: Create Variable Groups**

Variable groups store secrets and configuration values used by the pipeline.

#### **2a. Create `github-integration` Variable Group**

This group contains the GitHub PAT for downloading and uploading release assets.

1. Go to **Pipelines** → **Library** → **+ Variable group**
2. **Variable group name**: `github-integration`
3. **Description**: `GitHub integration tokens and settings`
4. Click **+ Add** to add a variable:
   - **Name**: `GITHUB_PAT`
   - **Value**: Your GitHub Personal Access Token
     - If you don't have one yet:
       1. Go to https://github.com/settings/tokens
       2. Click **Generate new token (classic)**
       3. Name: `Azure DevOps PKG Signing Pipeline`
       4. Expiration: Choose based on your security policy (90 days recommended)
       5. Select scopes:
          - ✓ `repo` (Full control of private repositories)
          - ✓ `write:packages` (Upload packages to GitHub Package Registry)
       6. Click **Generate token**
       7. **COPY THE TOKEN IMMEDIATELY** (you can't see it again)
     - Paste the token into the Value field
     - Click the **🔒 lock icon** to make it a secret variable
5. **Permissions**: Leave default (accessible to all pipelines in the project)
6. Click **Save**

#### **2b. Create `mscodehub-macos-package-signing` Variable Group**

This group contains the ESRP signing certificate code.

1. Go to **Pipelines** → **Library** → **+ Variable group**
2. **Variable group name**: `mscodehub-macos-package-signing`
3. **Description**: `ESRP certificate codes for macOS package signing`
4. Click **+ Add** to add a variable:
   - **Name**: `KeyCode`
   - **Value**: `CP-401337-Apple`
     - This is the standard Microsoft certificate code for macOS Developer ID signing
     - **If you have a custom certificate code from your ESRP team, use that instead**
     - Contact your organization's ESRP admin if unsure
   - **Do NOT lock this variable** (it's not a secret, just a certificate identifier)
5. Click **Save**

---

### **Step 3: Set Up OneBranch Repository Access**

Your pipeline uses OneBranch templates for governed builds and signing.

#### **Option A: OneBranch Already Available (Most Common)**

If your organization already uses OneBranch:

1. Go to **Project Settings** → **Repositories**
2. Look for `OneBranch.Pipelines` or `GovernedTemplates` repository
3. If it exists, you're all set! ✅

#### **Option B: Request OneBranch Access (If Not Available)**

If you don't have access yet:

1. **Internal Microsoft employees**:
   - Visit: https://aka.ms/onebranch
   - Follow the onboarding process
   - Join the OneBranch Teams channel
   - Request access to the `GovernedTemplates` repository

2. **External partners**:
   - Contact your Microsoft partner liaison
   - Request OneBranch access for your Azure DevOps organization
   - They will help provision the templates repository

#### **Option C: Verify OneBranch Service Connection**

1. Go to **Project Settings** → **Service connections**
2. Look for a connection named `OneBranch` or `GovernedTemplates`
3. Verify it's marked as **Ready**

#### **Troubleshooting OneBranch Access**

If you encounter issues, your pipeline will fail with:
```
Repository not found: OneBranch.Pipelines/GovernedTemplates
```

**Solutions**:
- Verify your Azure DevOps organization is registered with OneBranch
- Check if templates are in a different project
- Contact: onebranch-support@microsoft.com (internal) or your Microsoft contact (external)

---

### **Step 4: Create the Pipeline**

Now create the pipeline from your YAML file.

1. Go to **Pipelines** → **Pipelines** → **New pipeline** (or **Create Pipeline**)
2. **Where is your code?** → Select **GitHub**
3. **Authenticate to GitHub**:
   - If prompted, authorize Azure Pipelines to access GitHub
   - This uses the service connection you created in Step 1
4. **Select a repository** → Choose `naga-nandyala/azure-cli-pkg-1`
5. **Configure your pipeline** → Select **Existing Azure Pipelines YAML file**
6. **Select existing YAML file**:
   - **Branch**: `main`
   - **Path**: `/.azure-pipelines/azure-cli-macos-pkg-signing.yml`
   - Click **Continue**
7. **Review your pipeline YAML** → You'll see the pipeline configuration
8. **⚠️ Don't run yet!** Click the dropdown next to **Run** → Select **Save**
   - This saves the pipeline without running it (we'll configure parameters first)
9. **Rename the pipeline** (optional but recommended):
   - Click **⋮** (three dots) → **Rename/move**
   - New name: `Azure CLI - macOS PKG Signing`
   - Click **Save**

---

### **Step 5: Configure Pipeline Permissions**

Set up proper permissions for the pipeline to access resources.

1. Go to the saved pipeline → Click **Edit**
2. Click **⋮** (three dots in top right) → **Settings** → **Triggers**
3. **Configure settings**:

   **General Tab**:
   - **Pipeline triggers**: Disabled (manual trigger only)
   - **Build queue**: Default

   **YAML Tab**:
   - **Get sources**: Ensure GitHub repository is selected
   - **Default branch for manual and scheduled builds**: `main`

   **Variables Tab**:
   - Verify variable groups are accessible:
     - `github-integration` ✓
     - `mscodehub-macos-package-signing` ✓

   **Retention Tab**:
   - Keep default settings

4. Click **Save**

5. **Grant Resource Access** (if prompted):
   - When you first run the pipeline, you may be asked to grant access to:
     - Variable groups
     - Service connections
     - Repositories
   - Click **View** → **Permit** for each resource

---

### **Step 6: Test GitHub Release Download**

Before running the full pipeline, verify your GitHub release is ready.

1. Go to your GitHub releases: https://github.com/naga-nandyala/azure-cli-pkg-1/releases

2. **Verify you have a release** with:
   - **Tag name**: `azure-cli-pkg-v2.76.0` (or your version)
   - **Release title**: Any title (e.g., "Azure CLI 2.76.0 - Unsigned PKG")
   - **Assets**: Must include BOTH:
     - `azure-cli-2.76.0-macos-arm64.pkg` (ARM64 architecture)
     - `azure-cli-2.76.0-macos-x86_64.pkg` (Intel architecture)

3. **If you don't have a release yet**:
   - Create one from your GitHub Actions workflow
   - Or manually create a release and upload the PKG files
   - Tag format must match: `azure-cli-pkg-v{VERSION}`

4. **Verify file names match exactly**:
   - Format: `azure-cli-{VERSION}-macos-{ARCH}.pkg`
   - Example: `azure-cli-2.76.0-macos-arm64.pkg`

---

### **Step 7: Run Your First Pipeline**

Now you're ready to run the signing pipeline!

1. Go to **Pipelines** → **Pipelines** → Select your pipeline
2. Click **Run pipeline** button (top right)
3. **Fill in the parameters**:

   | Parameter | Value | Example |
   |-----------|-------|---------|
   | **GitHubReleaseTag** | The exact tag name from your GitHub release | `azure-cli-pkg-v2.76.0` |
   | **GitHubRepo** | Your GitHub repository in `owner/repo` format | `naga-nandyala/azure-cli-pkg-1` |
   | **AzureCliVersion** | Version number (without 'v' prefix) | `2.76.0` |
   | **OfficialBuild** | ✓ Checked (enables OneBranch official signing) | `true` |
   | **UploadToGitHub** | ✓ Checked (uploads signed PKGs back to release) | `true` |

4. **Verify parameters** are correct
5. Click **Run**

---

### **Step 8: Monitor the Pipeline**

Watch your pipeline run through 3 stages:

#### **Stage 1: download_unsigned_pkg** (~2-3 minutes)

What happens:
- Connects to GitHub API
- Downloads release information
- Downloads both PKG files (ARM64 + x86_64)
- Verifies downloads succeeded
- Publishes artifacts for next stage

**Expected output**:
```
✅ azure-cli-2.76.0-macos-arm64.pkg - 43.47 MB
✅ azure-cli-2.76.0-macos-x86_64.pkg - 43.47 MB
```

**Common issues**:
- ❌ `Release not found` → Check tag name matches exactly
- ❌ `Asset not found` → Verify PKG files exist in release
- ❌ `401 Unauthorized` → Check GITHUB_PAT is valid and has correct scopes

#### **Stage 2: sign_macos_pkg** (~5-10 minutes)

What happens:
- Runs TWO parallel jobs (one per architecture)
- Downloads unsigned PKGs from Stage 1
- Compresses PKG into ZIP (OneBranch requirement)
- Calls ESRP signing service with `MacAppDeveloperSign` operation
- Signs PKG with Apple Developer ID certificate
- Notarizes PKG with Apple (automatic with MacAppDeveloperSign)
- Extracts signed PKG from ZIP
- Generates SHA256 checksums
- Creates signing reports
- Publishes signed artifacts

**Expected output**:
```
Job: sign_macos_pkg_arm64
  ✅ Signed PKG extracted successfully
  ✅ azure-cli-2.76.0-macos-arm64-signed.pkg - 43.47 MB

Job: sign_macos_pkg_x86_64
  ✅ Signed PKG extracted successfully
  ✅ azure-cli-2.76.0-macos-x86_64-signed.pkg - 43.47 MB
```

**Common issues**:
- ❌ `KeyCode not found` → Verify `mscodehub-macos-package-signing` variable group has `KeyCode`
- ❌ `ESRP signing failed` → Contact your ESRP admin, verify certificate is active
- ❌ `OneBranch template not found` → See Step 3 troubleshooting

#### **Stage 3: publish_signed_pkg** (~2-3 minutes)

What happens:
- Downloads signed PKGs from both architecture jobs
- Collects all signed artifacts
- Generates final SHA256 checksums
- (If enabled) Uploads signed PKGs to GitHub release as new assets
- Publishes final artifacts for download

**Expected output**:
```
✅ azure-cli-2.76.0-macos-arm64-signed.pkg
✅ azure-cli-2.76.0-macos-arm64-signed.pkg.sha256
✅ azure-cli-2.76.0-macos-x86_64-signed.pkg
✅ azure-cli-2.76.0-macos-x86_64-signed.pkg.sha256
```

**GitHub release will have NEW assets**:
- `azure-cli-2.76.0-macos-arm64-signed.pkg`
- `azure-cli-2.76.0-macos-arm64-signed.pkg.sha256`
- `azure-cli-2.76.0-macos-x86_64-signed.pkg`
- `azure-cli-2.76.0-macos-x86_64-signed.pkg.sha256`

---

## 📋 Pre-Flight Checklist

Before running the pipeline, verify:

- [ ] **Step 1**: GitHub service connection created and working
- [ ] **Step 2a**: `github-integration` variable group exists with `GITHUB_PAT` (secret)
- [ ] **Step 2b**: `mscodehub-macos-package-signing` variable group exists with `KeyCode`
- [ ] **Step 3**: OneBranch templates repository is accessible
- [ ] **Step 4**: Pipeline created from YAML file
- [ ] **Step 5**: Pipeline permissions configured
- [ ] **Step 6**: GitHub release exists with unsigned PKG files
- [ ] **Step 7**: Pipeline parameters ready (release tag, version, repo)

---

## ⚠️ Troubleshooting Common Issues

### **Issue 1: OneBranch Templates Not Found**

**Error message**:
```
Repository not found: OneBranch.Pipelines/GovernedTemplates
```

**Cause**: Your Azure DevOps organization doesn't have access to OneBranch templates.

**Solutions**:
1. **Verify OneBranch registration**:
   - Check if your organization is registered: https://aka.ms/onebranch
   - Internal Microsoft: Join OneBranch program
   - External partners: Contact Microsoft liaison

2. **Check repository name**:
   - Go to **Project Settings** → **Repositories**
   - Look for `OneBranch.Pipelines`, `GovernedTemplates`, or similar
   - If named differently, update pipeline YAML line 62:
     ```yaml
     - repository: onebranchTemplates
       type: git
       name: YourOrg/YourTemplatesRepo  # Update this
       ref: refs/heads/main
     ```

3. **Temporary workaround** (non-production testing only):
   - Contact me to create a simplified version without OneBranch
   - ⚠️ This won't have official Microsoft signing!

---

### **Issue 2: Signing Fails - "KeyCode not found"**

**Error message**:
```
ERROR: KeyCode variable is not defined
```

**Cause**: The `KeyCode` variable is not set in the variable group.

**Solutions**:
1. **Verify variable group**:
   - Go to **Pipelines** → **Library**
   - Open `mscodehub-macos-package-signing`
   - Verify variable `KeyCode` exists
   - Value should be: `CP-401337-Apple` or your custom code

2. **Check variable group permissions**:
   - Ensure pipeline has access to the variable group
   - Go to variable group → **Pipeline permissions**
   - Add your pipeline if not listed

3. **Verify correct certificate code**:
   - Standard code: `CP-401337-Apple` (macOS Developer ID)
   - Alternative: `CP-401337` (generic Apple signing)
   - Custom: Contact your ESRP admin for the correct code

---

### **Issue 3: GitHub Download Fails - Authentication Error**

**Error message**:
```
❌ 401 Unauthorized
```
or
```
❌ API rate limit exceeded
```

**Cause**: GitHub PAT is missing, invalid, or lacks correct scopes.

**Solutions**:
1. **Verify GITHUB_PAT exists**:
   - Go to **Pipelines** → **Library** → `github-integration`
   - Verify `GITHUB_PAT` variable exists and is marked as secret (🔒)

2. **Check PAT scopes**:
   - Go to https://github.com/settings/tokens
   - Find your token (or create a new one)
   - Required scopes:
     - ✓ `repo` (full control)
     - ✓ `write:packages` (for uploading)
   - Regenerate if scopes are wrong

3. **Check PAT expiration**:
   - Tokens expire based on your setting (7, 30, 60, 90 days, or never)
   - Create a new token if expired
   - Update variable group with new token

4. **For private repositories**:
   - Ensure PAT has access to private repos
   - Verify repository is accessible with the token

---

### **Issue 4: GitHub Upload Fails**

**Error message**:
```
⚠️ Upload failed: 422 Unprocessable Entity
```
or
```
Asset already exists
```

**Cause**: Signed PKG assets already exist in the release.

**Solutions**:
1. **Delete existing signed assets**:
   - Go to GitHub release
   - Delete any `*-signed.pkg` files
   - Re-run the pipeline

2. **Use a different release**:
   - Create a new release with a new tag
   - Update pipeline parameters

3. **Disable upload** (test mode):
   - Set parameter `UploadToGitHub` to `false`
   - Signed PKGs will only be in Azure DevOps artifacts

---

### **Issue 5: PKG Files Not Found**

**Error message**:
```
❌ Asset not found: azure-cli-2.76.0-macos-arm64.pkg
```

**Cause**: PKG file names don't match expected pattern.

**Solutions**:
1. **Verify exact file names** in GitHub release:
   - Must match: `azure-cli-{VERSION}-macos-{ARCH}.pkg`
   - Example: `azure-cli-2.76.0-macos-arm64.pkg`
   - Case-sensitive!

2. **Check version parameter**:
   - Ensure `AzureCliVersion` parameter matches PKG file names
   - Example: If file is `azure-cli-2.76.0-macos-arm64.pkg`, version is `2.76.0`

3. **Update pipeline if needed**:
   - If your PKG naming is different, update lines 132-134 in main YAML:
     ```yaml
     $pkgFiles = @(
       "your-custom-name-{VERSION}-arm64.pkg",
       "your-custom-name-{VERSION}-x86_64.pkg"
     )
     ```

---

### **Issue 6: Signing Validation Fails**

**Error message**:
```
Code signing validation failed
```

**Cause**: Signed PKG doesn't pass signature verification.

**Solutions**:
1. **Check signing operation**:
   - Verify `MacAppDeveloperSign` is the correct operation for your certificate
   - Some certificates may require `MacAppDistributionSign` instead

2. **Verify certificate is active**:
   - Contact your ESRP admin
   - Verify Apple Developer ID certificate is not expired or revoked

3. **Review signing logs**:
   - Download pipeline artifacts
   - Check `signing-report-{arch}.txt` for details

---

## 🔍 Verifying Signed PKGs

After the pipeline completes successfully, verify the signed PKGs:

### **1. Download Signed PKGs**

**From Azure DevOps**:
1. Go to pipeline run → **Summary** tab
2. Scroll down to **Published artifacts**
3. Download `signed-macos-pkg` artifact
4. Extract ZIP to get signed PKG files

**From GitHub Release**:
1. Go to: https://github.com/naga-nandyala/azure-cli-pkg-1/releases
2. Find your release
3. Download `azure-cli-{VERSION}-macos-{ARCH}-signed.pkg`

### **2. Verify Checksums** (Optional)

On macOS or Linux:
```bash
# Download both PKG and .sha256 files
shasum -a 256 -c azure-cli-2.76.0-macos-arm64-signed.pkg.sha256
# Should output: azure-cli-2.76.0-macos-arm64-signed.pkg: OK
```

On Windows (PowerShell):
```powershell
$hash = Get-FileHash -Path "azure-cli-2.76.0-macos-arm64-signed.pkg" -Algorithm SHA256
$expectedHash = Get-Content "azure-cli-2.76.0-macos-arm64-signed.pkg.sha256" | Select-Object -First 1 | Split-String " " | Select-Object -First 1
if ($hash.Hash -eq $expectedHash) { "✅ Checksum verified" } else { "❌ Checksum mismatch" }
```

### **3. Verify Signature** (macOS Required)

On macOS, verify the signed PKG:

```bash
# Check signature
pkgutil --check-signature azure-cli-2.76.0-macos-arm64-signed.pkg

# Expected output:
# Package "azure-cli-2.76.0-macos-arm64-signed.pkg":
#    Status: signed by a developer certificate issued by Apple
#    Certificate Chain:
#     1. Developer ID Installer: Microsoft Corporation (...)
#     2. Developer ID Certification Authority
#     3. Apple Root CA
```

### **4. Verify Notarization** (macOS Required)

Check if Apple has notarized the PKG:

```bash
# Check notarization status
stapler validate azure-cli-2.76.0-macos-arm64-signed.pkg

# Expected output:
# The validate action worked!
```

### **5. Test Installation** (macOS Required)

Install and verify the signed PKG works:

```bash
# Install (will show security prompt)
sudo installer -pkg azure-cli-2.76.0-macos-arm64-signed.pkg -target /

# Verify installation
az --version

# Should output: azure-cli 2.76.0
```

Gatekeeper should NOT block installation (no "unidentified developer" warning).

---

## 📊 Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub Release                           │
│  Unsigned PKGs: azure-cli-{VERSION}-macos-{arm64|x86_64}.pkg    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Download
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Stage 1: download_unsigned_pkg                      │
│  - Download from GitHub API (using GITHUB_PAT)                   │
│  - Verify file integrity                                         │
│  - Publish artifacts: unsigned-pkg-files                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Artifacts
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Stage 2: sign_macos_pkg                             │
│                                                                   │
│  ┌─────────────────────┐       ┌──────────────────────┐         │
│  │  Job: ARM64         │       │  Job: x86_64         │         │
│  │  - Compress to ZIP  │       │  - Compress to ZIP   │         │
│  │  - ESRP signing     │       │  - ESRP signing      │         │
│  │  - Extract signed   │       │  - Extract signed    │         │
│  │  - Generate SHA256  │       │  - Generate SHA256   │         │
│  └─────────┬───────────┘       └──────────┬───────────┘         │
│            │                              │                      │
│            │ Artifacts                    │ Artifacts            │
└────────────┼──────────────────────────────┼──────────────────────┘
             │                              │
             └──────────────┬───────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│           Stage 3: publish_signed_pkg                            │
│  - Collect all signed PKGs                                       │
│  - Generate final checksums                                      │
│  - Upload to GitHub release (if enabled)                         │
│  - Publish artifacts: signed-macos-pkg                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Upload (optional)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub Release                           │
│  NEW Assets:                                                     │
│  - azure-cli-{VERSION}-macos-arm64-signed.pkg                   │
│  - azure-cli-{VERSION}-macos-arm64-signed.pkg.sha256            │
│  - azure-cli-{VERSION}-macos-x86_64-signed.pkg                  │
│  - azure-cli-{VERSION}-macos-x86_64-signed.pkg.sha256           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Best Practices

1. **Rotate GitHub PATs regularly**:
   - Set expiration to 90 days or less
   - Create calendar reminder to regenerate
   - Update variable group when regenerated

2. **Limit PAT scopes**:
   - Only grant `repo` scope (not `admin`)
   - Don't use personal PAT for production (create a service account)

3. **Protect variable groups**:
   - Restrict access to authorized pipelines only
   - Don't share PATs in logs or commit them to code

4. **Monitor pipeline runs**:
   - Review pipeline logs for security warnings
   - Check for unexpected downloads or uploads

5. **Use separate releases for testing**:
   - Test with dev releases before signing production PKGs
   - Use different tags (e.g., `azure-cli-pkg-v2.76.0-test`)

---

## 📞 Support Contacts

- **OneBranch Support**: onebranch-support@microsoft.com (Microsoft internal)
- **ESRP Support**: Contact your organization's security team
- **Azure DevOps Support**: https://developercommunity.visualstudio.com/
- **GitHub Support**: https://support.github.com/

---

## 🎉 Success Criteria

Your pipeline is working correctly when:

✅ All 3 stages complete successfully  
✅ Signed PKGs are uploaded to GitHub release  
✅ SHA256 checksums are generated  
✅ `pkgutil --check-signature` shows Apple Developer ID  
✅ `stapler validate` confirms notarization  
✅ PKG installs on macOS without Gatekeeper warnings  
✅ `az --version` shows correct version after installation

---

## 📚 Additional Resources

- **OneBranch Documentation**: https://aka.ms/onebranch
- **ESRP Documentation**: Contact your ESRP admin for internal docs
- **Azure Pipelines YAML**: https://learn.microsoft.com/azure/devops/pipelines/yaml-schema
- **GitHub Actions to Azure Pipelines**: https://learn.microsoft.com/azure/devops/pipelines/migrate/from-github-actions
- **macOS Code Signing**: https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution

---

**Last Updated**: 2025-11-11  
**Pipeline Version**: 1.0  
**Maintainer**: Your name/team
