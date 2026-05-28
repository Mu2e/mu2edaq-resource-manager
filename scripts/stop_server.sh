#!/usr/bin/env bash
# Stop the Mu2e DAQ Resource Manager server started in daemon mode.
#
# Reads the PID file written by start_server.sh, sends SIGTERM for a graceful
# shutdown, and escalates to SIGKILL if the process does not exit in time.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env (does not override variables already set in the environment).
# shellcheck source=scripts/load_env.sh
. "$SCRIPT_DIR/load_env.sh"

RUN_DIR="${RM_RUN_DIR:-$PROJECT_DIR/run}"
PIDFILE="${RM_PIDFILE:-$RUN_DIR/resource-manager.pid}"
TIMEOUT="${RM_STOP_TIMEOUT:-10}"

if [ ! -f "$PIDFILE" ]; then
    echo "No pidfile at $PIDFILE; server does not appear to be running in daemon mode."
    echo "If it is running in the foreground, stop it with Ctrl-C in its terminal."
    exit 0
fi

PID="$(cat "$PIDFILE" 2>/dev/null || true)"
if [ -z "$PID" ]; then
    echo "Pidfile $PIDFILE is empty; removing it."
    rm -f "$PIDFILE"
    exit 0
fi

if ! kill -0 "$PID" 2>/dev/null; then
    echo "Process $PID is not running; removing stale pidfile $PIDFILE."
    rm -f "$PIDFILE"
    exit 0
fi

echo "Stopping Mu2e DAQ Resource Manager (PID $PID)..."
kill -TERM "$PID" 2>/dev/null || true

# Wait up to TIMEOUT seconds for a graceful shutdown before forcing it.
waited=0
while kill -0 "$PID" 2>/dev/null; do
    if [ "$waited" -ge "$TIMEOUT" ]; then
        echo "Process did not exit after ${TIMEOUT}s; sending SIGKILL."
        kill -KILL "$PID" 2>/dev/null || true
        sleep 1
        break
    fi
    sleep 1
    waited=$((waited + 1))
done

if kill -0 "$PID" 2>/dev/null; then
    echo "Error: failed to stop process $PID." >&2
    exit 1
fi

rm -f "$PIDFILE"
echo "Stopped."
