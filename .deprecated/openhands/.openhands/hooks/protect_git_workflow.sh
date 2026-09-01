#!/usr/bin/env bash

set -euo pipefail

project_dir="${OPENHANDS_PROJECT_DIR:-$PWD}"
cd "$project_dir"

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"
current_branch="$(git branch --show-current 2>/dev/null || true)"

deny() {
  printf '{"decision":"deny","reason":"%s"}\n' "$1"
  exit 2
}

if [[ "$command" == *"git branch -d"* ]] || [[ "$command" == *"git branch -D"* ]]; then
  deny "Branch deletion is disabled for this repository. Keep branches after merge."
fi

if [[ "$command" == *"git push"* ]] && [[ "$command" == *"--delete"* ]]; then
  deny "Branch deletion is disabled for this repository. Keep branches after merge."
fi

if [[ "$command" == git\ commit* ]]; then
  if [[ -z "$current_branch" || "$current_branch" == "main" || "$current_branch" == "development" ]]; then
    deny "Create or switch to a feature branch before committing. Do not commit directly on main or development."
  fi
fi

if [[ "$command" == git\ checkout\ -b* ]]; then
  if [[ -n "$current_branch" && "$current_branch" != "development" ]]; then
    deny "Create new feature branches from development. If the previous blocker branch is complete, merge it into development first, then create the next branch from there."
  fi
fi

if [[ "$command" == git\ merge* ]]; then
  if [[ "$current_branch" == "main" ]]; then
    deny "Do not merge work into main during routine development. Merge accepted work into development instead."
  fi
  if [[ -n "$current_branch" && "$current_branch" != "development" && "$current_branch" != "main" ]]; then
    deny "Finish routine merges by checking out development and merging the accepted feature branch there."
  fi
fi

exit 0
