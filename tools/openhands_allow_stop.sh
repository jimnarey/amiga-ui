#!/usr/bin/env bash

set -euo pipefail

project_dir="${OPENHANDS_PROJECT_DIR:-$PWD}"
cd "$project_dir"

reason="${1:-}"
shift || true

case "$reason" in
  complete|needs-user|blocked)
    ;;
  *)
    echo "Usage: ./tools/openhands_allow_stop.sh {complete|needs-user|blocked} [note]" >&2
    exit 1
    ;;
esac

note="${*:-}"
state_dir=".openhands/state"
marker_path="$state_dir/allow-stop.json"
created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
branch="$(git branch --show-current 2>/dev/null || true)"

mkdir -p "$state_dir"

python3 - "$marker_path" "$reason" "$created_at" "$branch" "$note" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "reason": sys.argv[2],
    "created_at": sys.argv[3],
    "branch": sys.argv[4],
}
if sys.argv[5]:
    payload["note"] = sys.argv[5]

path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

echo "Created stop marker at $marker_path for reason: $reason"
