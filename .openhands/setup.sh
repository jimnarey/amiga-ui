#!/usr/bin/env bash

set -euo pipefail

project_dir="${OPENHANDS_PROJECT_DIR:-$PWD}"
cd "$project_dir"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

echo "[setup] syncing Python dependencies"
uv sync --group dev

echo "[setup] checking required host dependencies"
./check_dependencies.sh

current_branch="$(git branch --show-current 2>/dev/null || true)"
if [[ -n "$current_branch" && "$current_branch" != "development" ]]; then
  if git show-ref --verify --quiet refs/heads/development; then
    echo "[setup] switching to existing development branch"
    git checkout development
  else
    echo "[setup] creating development branch from ${current_branch}"
    git checkout -b development
  fi
fi

mkdir -p artifacts/runs

echo
echo "[setup] next recommended commands:"
echo "  uv run amiga-ui check"
echo "  uv run python tests/run_gui_smoke_test.py"
echo "  git checkout -b feature/<short-topic>"
echo "  uv run amiga-ui probe itidy"
