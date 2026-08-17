#!/usr/bin/env bash

set -euo pipefail

project_dir="${OPENHANDS_PROJECT_DIR:-$PWD}"
cd "$project_dir"

source tools/lib/stop_marker.sh

reason="${1:-}"
shift || true

if ! stop_marker_valid_reason "$reason"; then
  echo "Usage: ./tools/openhands_allow_stop.sh {complete|needs-user|blocked} [note]" >&2
  exit 1
fi

stop_marker_write ".openhands/state" "$reason" "${*:-}"
