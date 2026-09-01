#!/usr/bin/env bash
# Record why the bespoke agent/ driver is intentionally ending a unit of
# work. Reuses tools/lib/stop_marker.sh's shared logic with its own state
# directory. Legacy harness stop helpers are preserved under .deprecated/.

set -euo pipefail

source tools/lib/stop_marker.sh

reason="${1:-}"
shift || true

if ! stop_marker_valid_reason "$reason"; then
  echo "Usage: ./tools/bespoke_agent_allow_stop.sh {complete|needs-user|blocked} [note]" >&2
  exit 1
fi

stop_marker_write ".agent/state" "$reason" "${*:-}"
