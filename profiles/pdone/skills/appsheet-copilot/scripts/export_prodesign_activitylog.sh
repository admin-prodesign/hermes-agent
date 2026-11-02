#!/usr/bin/env bash
# Canonical documentation: [[syntheses/appsheet-data-capture-map|AppSheet Data Capture Map]]
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="/home/prodesign/.openclaw/workspace/.venvs/appsheet-copilot"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
SCRIPT_PY="$SKILL_DIR/scripts/export_prodesign_activitylog.py"

if [[ ! -x "$PYTHON_BIN" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$PIP_BIN" install -q requests openpyxl
exec "$PYTHON_BIN" "$SCRIPT_PY" "$@"
