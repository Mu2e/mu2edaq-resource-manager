#!/usr/bin/env bash
#
# stop-mu2edaq-resource-manager.sh - standardized Mu2e control-room stop
# script. Top-level entry point expected by the control room
# (`crs-app stop resource-manager`). Delegates to scripts/stop_server.sh,
# which stops the daemon-mode server via its pid file.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "$SCRIPT_DIR/scripts/stop_server.sh" "$@"
