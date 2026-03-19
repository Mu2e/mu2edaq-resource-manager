#!/usr/bin/env bash
# Start the Mu2e DAQ Resource Manager server
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

HOST="${RM_HOST:-0.0.0.0}"
PORT="${RM_PORT:-8080}"
CONFIG="${RM_CONFIG:-$PROJECT_DIR/config/resources.yaml}"
STATE="${RM_STATE:-$PROJECT_DIR/config/state.json}"

echo "Starting Mu2e DAQ Resource Manager"
echo "  Config: $CONFIG"
echo "  State:  $STATE"
echo "  Listen: http://$HOST:$PORT"
echo ""

exec python3 "$PROJECT_DIR/server/app.py" \
    --host "$HOST" \
    --port "$PORT" \
    --config "$CONFIG" \
    --state "$STATE"
