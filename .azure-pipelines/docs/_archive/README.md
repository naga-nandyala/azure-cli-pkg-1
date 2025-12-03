# Archived Documentation

This directory contains documentation for deprecated or superseded approaches.

## Archived Files

### AZURE-DEVOPS-PIPELINE-SETUP.md
- **Archived Date**: 2025-12-04
- **Reason**: Referenced deprecated pipeline `azure-cli-macos-pkg-signing.yml` which is now in `.azure-pipelines/_archive/`
- **Replaced By**: See [MACOS_PKG_PIPELINES.md](../MACOS_PKG_PIPELINES.md) for current comprehensive pipeline documentation
- **Description**: Setup guide for the old hybrid GitHub Actions + Azure DevOps signing approach

### NOTARIZATION_PIPELINE_UPDATES.md
- **Archived Date**: 2025-12-04
- **Reason**: Migration guide for a specific build transition (Build #282182 → #282373)
- **Description**: Documented the update from `macos-pkg-sign-release` to `macos-pkg-sign-all` pipeline
- **Historical Value**: Shows the evolution from simple PKG signing to comprehensive binary signing

## Current Documentation

For current macOS PKG pipeline documentation, see:

- **[MACOS_PKG_PIPELINES.md](../../MACOS_PKG_PIPELINES.md)** - Complete pipeline system documentation
- **[AZURE-DEVOPS-SETUP.md](../AZURE-DEVOPS-SETUP.md)** - Azure DevOps setup guide (updated)
- **[SIGNING-PROCESS.md](../SIGNING-PROCESS.md)** - Technical signing process details
