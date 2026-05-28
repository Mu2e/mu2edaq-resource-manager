#!/usr/bin/env bash
# Bootstrap the Mu2e DAQ Resource Manager: create the Python virtual
# environment and install/update Python dependencies.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env (does not override variables already set in the environment).
# shellcheck source=scripts/load_env.sh
. "$SCRIPT_DIR/load_env.sh"

VENV_DIR="${RM_VENV:-$PROJECT_DIR/venv}"
PYTHON="${PYTHON:-python3}"
REQUIREMENTS="$PROJECT_DIR/requirements.txt"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Error: '$PYTHON' not found on PATH. Set PYTHON=/path/to/python3 and retry." >&2
    exit 1
fi

# Require Python >= 3.9 (per project compatibility target).
"$PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 9):
    sys.exit("Error: Python 3.9 or newer is required, found %d.%d" % sys.version_info[:2])
PY

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
else
    echo "Using existing virtual environment in $VENV_DIR"
fi

VENV_PY="$VENV_DIR/bin/python"
if [ ! -x "$VENV_PY" ]; then
    # Windows (Git Bash / MSYS) layout.
    VENV_PY="$VENV_DIR/Scripts/python.exe"
fi

echo "Upgrading pip"
"$VENV_PY" -m pip install --upgrade pip

if [ -f "$REQUIREMENTS" ]; then
    echo "Installing dependencies from $REQUIREMENTS"
    "$VENV_PY" -m pip install --upgrade -r "$REQUIREMENTS"
else
    echo "Warning: $REQUIREMENTS not found, skipping dependency install." >&2
fi

echo ""
echo "Bootstrap complete."
echo "  Activate with: source \"$VENV_DIR/bin/activate\""
echo "  Start server:  scripts/start_server.sh"
