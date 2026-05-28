#!/usr/bin/env bash
# Start the Mu2e DAQ Resource Manager server.
#
# Runs in the foreground by default. Pass -d/--daemon (or set RM_DAEMON=1) to
# run detached in the background; a PID file is written so stop_server.sh can
# stop it later.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env (does not override variables already set in the environment).
# shellcheck source=scripts/load_env.sh
. "$SCRIPT_DIR/load_env.sh"

VENV_DIR="${RM_VENV:-$PROJECT_DIR/venv}"
VENV_PY="$VENV_DIR/bin/python"
if [ ! -x "$VENV_PY" ]; then
    # Windows (Git Bash / MSYS) layout.
    VENV_PY="$VENV_DIR/Scripts/python.exe"
fi
if [ ! -x "$VENV_PY" ]; then
    echo "Error: virtual environment not found in $VENV_DIR. Run scripts/bootstrap.sh first." >&2
    exit 1
fi

HOST="${RM_HOST:-0.0.0.0}"
PORT="${RM_PORT:-8080}"
CONFIG="${RM_CONFIG:-$PROJECT_DIR/config/resources.yaml}"
STATE="${RM_STATE:-$PROJECT_DIR/config/state.json}"
RUN_DIR="${RM_RUN_DIR:-$PROJECT_DIR/run}"
PIDFILE="${RM_PIDFILE:-$RUN_DIR/resource-manager.pid}"
LOGFILE="${RM_LOG:-$RUN_DIR/resource-manager.log}"

# Daemon mode: enabled by -d/--daemon or RM_DAEMON.
DAEMON=0
case "${RM_DAEMON:-0}" in
    1|true|TRUE|yes|YES|on|ON) DAEMON=1 ;;
esac

# Pull -d/--daemon out of the argument list; forward everything else to app.py.
ARGS=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        -d|--daemon) DAEMON=1; shift ;;
        --) shift; while [ "$#" -gt 0 ]; do ARGS+=("$1"); shift; done ;;
        *) ARGS+=("$1"); shift ;;
    esac
done

echo "Starting Mu2e DAQ Resource Manager"
echo "  Config: $CONFIG"
echo "  State:  $STATE"
echo "  Listen: http://$HOST:$PORT"
if [ "${#ARGS[@]}" -gt 0 ]; then
    echo "  Extra args (override the above): ${ARGS[*]}"
fi

if [ "$DAEMON" -eq 1 ]; then
    mkdir -p "$RUN_DIR"
    # Refuse to start a second instance if one is already running.
    if [ -f "$PIDFILE" ]; then
        OLD_PID="$(cat "$PIDFILE" 2>/dev/null || true)"
        if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
            echo "Error: server already running (PID $OLD_PID, pidfile $PIDFILE)." >&2
            exit 1
        fi
        echo "  Removing stale pidfile $PIDFILE (PID ${OLD_PID:-unknown} not running)."
        rm -f "$PIDFILE"
    fi
    echo "  Mode:   daemon"
    echo "  PID:    $PIDFILE"
    echo "  Log:    $LOGFILE"
    echo ""
    nohup "$VENV_PY" "$PROJECT_DIR/server/app.py" \
        --host "$HOST" \
        --port "$PORT" \
        --config "$CONFIG" \
        --state "$STATE" \
        ${ARGS[@]+"${ARGS[@]}"} >> "$LOGFILE" 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PIDFILE"
    echo "Started in daemon mode (PID $SERVER_PID). Stop with scripts/stop_server.sh"
else
    echo "  Mode:   foreground"
    echo ""
    exec "$VENV_PY" "$PROJECT_DIR/server/app.py" \
        --host "$HOST" \
        --port "$PORT" \
        --config "$CONFIG" \
        --state "$STATE" \
        ${ARGS[@]+"${ARGS[@]}"}
fi
