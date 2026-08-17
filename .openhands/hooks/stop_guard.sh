#!/usr/bin/env bash

set -euo pipefail

project_dir="${OPENHANDS_PROJECT_DIR:-$PWD}"
cd "$project_dir"

source tools/lib/stop_marker.sh

state_dir=".openhands/state"
marker_path="$state_dir/allow-stop.json"
quality_gate=".openhands/hooks/quality_gate.sh"
max_age_seconds=900

deny() {
  printf '{"decision":"deny","reason":"%s"}\n' "$1"
  exit 2
}

if [[ ! -f "$marker_path" ]]; then
  deny "The task still appears to be in progress. A text-only narration or progress message is not completion. If more work remains, continue by making the next tool call. Only stop after explicitly creating the stop marker with ./tools/openhands_allow_stop.sh."
fi

if ! mapfile -t marker_fields < <(stop_marker_read "$marker_path"); then
  rm -f "$marker_path"
  deny "The stop marker was malformed. Recreate it with ./tools/openhands_allow_stop.sh immediately before an intentional stop."
fi

reason="${marker_fields[0]:-}"
marker_branch="${marker_fields[1]:-}"
marker_age="${marker_fields[2]:-}"

current_branch="$(git branch --show-current 2>/dev/null || true)"

if ! stop_marker_valid_reason "$reason"; then
  rm -f "$marker_path"
  deny "The stop marker used an unknown reason. Use one of: complete, needs-user, blocked."
fi

if [[ -n "$marker_branch" && -n "$current_branch" && "$marker_branch" != "$current_branch" ]]; then
  rm -f "$marker_path"
  deny "The stop marker was created on a different branch. Recreate it immediately before the intentional stop on the current branch."
fi

if [[ -z "$marker_age" || ! "$marker_age" =~ ^-?[0-9]+$ ]]; then
  rm -f "$marker_path"
  deny "The stop marker age could not be validated. Recreate it with ./tools/openhands_allow_stop.sh."
fi

if (( marker_age < 0 || marker_age > max_age_seconds )); then
  rm -f "$marker_path"
  deny "The stop marker is stale. Recreate it immediately before the intentional stop."
fi

rm -f "$marker_path"

if [[ "$reason" == "complete" ]]; then
  exec "$quality_gate"
fi

exit 0
