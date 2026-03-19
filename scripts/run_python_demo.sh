#!/usr/bin/env bash
# Run the Python demo client
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

BASE_URL="${1:-http://localhost:8080}"

exec python3 "$PROJECT_DIR/client/demo_client.py" "$BASE_URL"
