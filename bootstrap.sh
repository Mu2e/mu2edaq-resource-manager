#!/usr/bin/env bash
# bootstrap.sh -- top-level convenience wrapper. The real bootstrap logic
# lives in scripts/bootstrap.sh; this exists so `./bootstrap.sh` works from
# the repo root, matching the other mu2edaq-* repos.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/scripts/bootstrap.sh" "$@"
