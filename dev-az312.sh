#!/bin/bash
# Development helper script to run Azure CLI from source using Python 3.12
# This uses PYTHONPATH instead of editable install to avoid namespace package issues

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv312"

# Activate the venv and set PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR/src/azure-cli:$SCRIPT_DIR/src/azure-cli-core"
"$VENV_DIR/bin/python" -m azure.cli "$@"
