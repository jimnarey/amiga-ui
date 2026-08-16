#!/usr/bin/env bash
# Record why a Goose autonomous run is intentionally ending. Read by
# tools/goose_quality_gate.sh, which the .goose/recipes/autonomous-dev.yaml
# retry.checks step runs before letting the run finish.

set -euo pipefail

reason="${1:-}"
shift || true

case "$reason" in
  complete|needs-user|blocked)
    ;;
  *)
    echo "Usage: ./tools/goose_allow_stop.sh {complete|needs-user|blocked} [note]" >&2
    exit 1
    ;;
esac

note="${*:-}"
state_dir=".goose/state"
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
