#!/usr/bin/env bash
# Start the Mu2e DAQ Resource Manager server.
#
# Runs in the foreground by default. Pass -d/--daemon (or set RM_DAEMON=1) to
# run detached in the background; a PID file is written so stop_server.sh can
# stop it later.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PROG="$(basename "$0")"

# Load .env (does not override variables already set in the environment).
# shellcheck source=scripts/load_env.sh
. "$SCRIPT_DIR/load_env.sh"

usage() {
    cat <<EOF
Usage: $PROG [-d|--daemon] [-h|--help] [SERVER_OPTIONS...]

Start the Mu2e DAQ Resource Manager server. Runs in the foreground by
default; use -d/--daemon to run detached in the background with a PID file.

Options:
  -d, --daemon   Run as a background daemon. Writes a PID file and log under
                 RM_RUN_DIR and refuses to start a second instance.
                 Equivalent to setting RM_DAEMON=1.
  -h, --help     Show this help and exit.

Any other arguments are forwarded to the server
(server/mu2e-resource-manager.py) and override the environment-derived
values, e.g.: $PROG --port 9000
Run "python3 server/mu2e-resource-manager.py --help" (or pass them after a
"--") to see the full list of server options.

Environment variables (may also be set in a .env file at the project root):
  RM_HOST        Bind host (default: 0.0.0.0)
  RM_PORT        Bind port (default: 8080)
  RM_CONFIG      Resource definition YAML (default: config/resources.yaml)
  RM_STATE       Reservation state JSON (default: config/state.json)
  RM_DAEMON      Start in daemon mode when truthy (1/true/yes/on)
  RM_RUN_DIR     Directory for the pidfile and log (default: run/)
  RM_PIDFILE     PID file path (default: \$RM_RUN_DIR/resource-manager.pid)
  RM_LOG         Daemon log file (default: \$RM_RUN_DIR/resource-manager.log)
  RM_VENV        Virtual environment directory (default: venv/)

Stop a daemon-mode server with scripts/stop_server.sh.
EOF
}

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

# Pull our own options out of the argument list; forward everything else to
# the server. Everything after "--" is forwarded verbatim.
ARGS=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        -d|--daemon) DAEMON=1; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; while [ "$#" -gt 0 ]; do ARGS+=("$1"); shift; done ;;
        *) ARGS+=("$1"); shift ;;
    esac
done

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
    nohup "$VENV_PY" "$PROJECT_DIR/server/mu2e-resource-manager.py" \
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
    exec "$VENV_PY" "$PROJECT_DIR/server/mu2e-resource-manager.py" \
        --host "$HOST" \
        --port "$PORT" \
        --config "$CONFIG" \
        --state "$STATE" \
        ${ARGS[@]+"${ARGS[@]}"}
fi
