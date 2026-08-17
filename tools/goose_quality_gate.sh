#!/usr/bin/env bash
# Completion gate for the Goose autonomous-dev recipe. Run as the
# retry.checks command in .goose/recipes/autonomous-dev.yaml.
#
# Exit 0 lets `goose run` finish. Exit 1 fails the retry check, which makes
# Goose run on_failure (see the recipe) and restart the recipe with a fresh
# message history — the git working tree is untouched, so the next attempt
# resumes from the same repo state. The rejection reason is written to
# .goose/state/last-rejection.md so the next attempt can read it.
#
# Requires a marker created by tools/goose_allow_stop.sh:
# - reason "complete": full quality gate (pre-commit, unit tests, GUI smoke).
# - reason "blocked" or "needs-user": accepted as-is, no quality gate.
# - no marker at all: rejected — this is what catches a run that stopped
#   with narration instead of doing (or finishing) the work.

set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

state_dir=".goose/state"
marker_path="$state_dir/allow-stop.json"
rejection_path="$state_dir/last-rejection.md"
max_age_seconds=1800

mkdir -p "$state_dir"

reject() {
  local reason="$1"
  {
    echo "# Previous Goose run rejected"
    echo
    echo "$reason"
    echo
    if [[ -x tools/goose_recent_failures.py ]]; then
      tools/goose_recent_failures.py --limit 6 || true
      echo
    fi
    echo "Read this before continuing. If recent tool failures are listed above, change tools or arguments instead of repeating the failed call."
  } > "$rejection_path"
  rm -f "$marker_path"
  echo "$reason" >&2
  exit 1
}

if [[ ! -f "$marker_path" ]]; then
  reject "No stop marker was found. A run must not end on narration alone: if more work remains, keep making tool calls; when the run is genuinely finished, blocked, or needs user input, call ./tools/goose_allow_stop.sh {complete|blocked|needs-user} \"<note>\" before ending the turn."
fi

if ! mapfile -t marker_fields < <(python3 - "$marker_path" <<'PY'
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
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
except Exception:
    sys.exit(1)

now = datetime.now(timezone.utc)
age_seconds = int((now - created).total_seconds())

print(reason)
print(branch)
print(age_seconds)
PY
); then
  reject "The stop marker at $marker_path was malformed. Recreate it with ./tools/goose_allow_stop.sh immediately before ending the turn."
fi

reason="${marker_fields[0]:-}"
marker_branch="${marker_fields[1]:-}"
marker_age="${marker_fields[2]:-}"
current_branch="$(git branch --show-current 2>/dev/null || true)"

case "$reason" in
  complete|needs-user|blocked)
    ;;
  *)
    reject "The stop marker used an unknown reason '$reason'. Use one of: complete, needs-user, blocked."
    ;;
esac

if [[ -n "$marker_branch" && -n "$current_branch" && "$marker_branch" != "$current_branch" ]]; then
  reject "The stop marker was created on branch '$marker_branch' but the repo is now on '$current_branch'. Recreate the marker on the current branch immediately before ending the turn."
fi

if [[ -z "$marker_age" || ! "$marker_age" =~ ^-?[0-9]+$ ]] || (( marker_age < 0 || marker_age > max_age_seconds )); then
  reject "The stop marker is missing, stale, or has an invalid timestamp. Recreate it with ./tools/goose_allow_stop.sh immediately before ending the turn."
fi

if [[ "$reason" != "complete" ]]; then
  rm -f "$marker_path"
  rm -f "$rejection_path"
  echo "Accepted stop reason: $reason"
  exit 0
fi

if [[ "$current_branch" == "main" ]]; then
  reject "Do not finish work on main. Switch to development, then use a feature branch for changes."
fi

if [[ "$current_branch" == "development" ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    reject "Do not finish with unmerged work sitting on development. Move the change to a feature branch and merge back only after it passes the quality gates."
  fi
fi

if ! uv run pre-commit run --all-files 2>&1; then
  reject "pre-commit checks failed. Fix formatting, lint, or type-check issues before finishing."
fi

if ! uv run python -m unittest 2>&1; then
  reject "The unit test suite failed. Fix the failures before finishing."
fi

if ! uv run python tests/run_gui_smoke_test.py 2>&1; then
  reject "The headless GUI smoke test failed. Fix the Xvfb or Qt path before finishing."
fi

rm -f "$marker_path"
rm -f "$rejection_path"
exit 0
