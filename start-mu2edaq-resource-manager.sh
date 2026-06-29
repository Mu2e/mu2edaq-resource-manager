#!/usr/bin/env bash
#
# start-mu2edaq-resource-manager.sh - standardized Mu2e control-room start
# script. Top-level entry point expected by the control room
# (`crs-app start resource-manager`). Maps CRS_PORT_HTTP -> RM_PORT and starts
# the server in daemon mode via scripts/start_server.sh. Extra arguments are
# forwarded to the underlying script.
#
# Port precedence: CRS_PORT_HTTP env > RM_PORT env > built-in default (8080,
# matching apps.yaml).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export RM_PORT="${CRS_PORT_HTTP:-${RM_PORT:-8080}}"
export RM_DAEMON=1

exec "$SCRIPT_DIR/scripts/start_server.sh" "$@"
