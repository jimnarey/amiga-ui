#!/usr/bin/env bash
# Record why a Goose autonomous run is intentionally ending. Read by
# tools/goose_quality_gate.sh, which the .goose/recipes/autonomous-dev.yaml
# retry.checks step runs before letting the run finish.

set -euo pipefail

source tools/lib/stop_marker.sh

reason="${1:-}"
shift || true

if ! stop_marker_valid_reason "$reason"; then
  echo "Usage: ./tools/goose_allow_stop.sh {complete|needs-user|blocked} [note]" >&2
  exit 1
fi

stop_marker_write ".goose/state" "$reason" "${*:-}"
