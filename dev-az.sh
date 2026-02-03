#!/bin/bash
# Development script to run az CLI from source with editable install support

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}/src/azure-cli:${SCRIPT_DIR}/src/azure-cli-core:${PYTHONPATH}"

# Run az CLI
"${SCRIPT_DIR}/.venv/bin/python" -m azure.cli "$@"
