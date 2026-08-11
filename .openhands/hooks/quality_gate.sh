#!/usr/bin/env bash

set -euo pipefail

project_dir="${OPENHANDS_PROJECT_DIR:-$PWD}"
cd "$project_dir"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

deny() {
  printf '{"decision":"deny","reason":"%s"}\n' "$1"
  exit 2
}

current_branch="$(git branch --show-current 2>/dev/null || true)"
if [[ "$current_branch" == "main" ]]; then
  deny "This repository should not finish work on main. Switch to development, then use a feature branch for changes."
fi

if [[ "$current_branch" == "development" ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    deny "Do not finish with unmerged work on development. Move the change to a feature branch and merge back only after it passes the quality gates."
  fi
fi

if ! uv run pre-commit run --all-files 2>&1; then
  deny "pre-commit checks failed. Fix formatting, lint, or type-check issues before finishing."
fi

if ! uv run python -m unittest 2>&1; then
  deny "The unit test suite failed. Fix the failures before finishing."
fi

if ! uv run python tests/run_gui_smoke_test.py 2>&1; then
  deny "The headless GUI smoke test failed. Fix the Xvfb or Qt path before finishing."
fi

exit 0
