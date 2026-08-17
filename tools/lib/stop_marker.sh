#!/usr/bin/env bash
# Shared helpers for writing and reading the harness stop marker
# (<state_dir>/allow-stop.json). Sourced by tools/openhands_allow_stop.sh,
# tools/goose_allow_stop.sh, .openhands/hooks/stop_guard.sh, and
# tools/goose_quality_gate.sh. Not meant to be invoked directly.
#
# Assumes the sourcing script's working directory is the repository root.

stop_marker_valid_reason() {
  case "$1" in
    complete|needs-user|blocked) return 0 ;;
    *) return 1 ;;
  esac
}

# stop_marker_write <state_dir> <reason> <note>
# Writes the marker and prints a one-line confirmation.
stop_marker_write() {
  local state_dir="$1" reason="$2" note="$3"
  local marker_path="$state_dir/allow-stop.json"
  local created_at branch
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
}

# stop_marker_read <marker_path>
# On success, prints four lines: reason, branch, age_seconds, note.
# Returns non-zero (with no reliable output) if the marker is missing,
# unreadable, or malformed — callers should treat that as "unusable" and
# fall back to their own reason-based validation of the (possibly empty)
# fields, matching this function's existing callers.
stop_marker_read() {
  local marker_path="$1"
  [[ -f "$marker_path" ]] || return 1

  python3 - "$marker_path" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])

try:
    payload = json.loads(path.read_text(encoding="utf-8"))
    reason = payload["reason"]
    created_at = payload["created_at"]
    branch = payload.get("branch", "")
    note = payload.get("note", "")
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
except Exception:
    sys.exit(1)

now = datetime.now(timezone.utc)
age_seconds = int((now - created).total_seconds())

print(reason)
print(branch)
print(age_seconds)
print(note)
PY
}
