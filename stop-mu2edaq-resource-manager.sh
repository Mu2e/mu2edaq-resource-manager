#!/usr/bin/env bash
# Stop the Mu2e DAQ Resource Manager.
set -uo pipefail

PID_FILE="/tmp/mu2edaq-resource-manager.pid"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  PID=$(cat "$PID_FILE")
  # start_server.sh execs python, so the PID is the server itself,
  # but kill the process group to be safe with shells in between.
  kill "$PID" 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "Resource Manager stopped (PID $PID)."
else
  PIDS=$(pgrep -f "server/app.py" || true)
  if [[ -n "$PIDS" ]]; then
    kill $PIDS 2>/dev/null || true
    echo "Resource Manager stopped (found by name)."
  else
    echo "Resource Manager is not running."
  fi
  rm -f "$PID_FILE" 2>/dev/null || true
fi
exit 0
