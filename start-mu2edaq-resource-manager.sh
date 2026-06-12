#!/usr/bin/env bash
# Start the Mu2e DAQ Resource Manager (top-level standardized launcher).
# CRS_PORT_HTTP (exported by the control room crs-app launcher) overrides
# the port; RM_* variables are honored as before.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="/tmp/mu2edaq-resource-manager.pid"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Resource Manager is already running (PID $(cat "$PID_FILE"))."
  exit 0
fi

export RM_PORT="${CRS_PORT_HTTP:-${RM_PORT:-8080}}"

nohup "$SCRIPT_DIR/scripts/start_server.sh" "$@" \
  >> /tmp/mu2edaq-resource-manager.log 2>&1 &
echo $! > "$PID_FILE"
echo "Resource Manager started (PID $(cat "$PID_FILE"), port $RM_PORT)."
