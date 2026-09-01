#!/usr/bin/env bash
set -euo pipefail

project_dir="${AMIGA_UI_PROJECT_DIR:-$PWD}"
cd "$project_dir"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

printf '[bootstrap] syncing Python dependencies
'
uv sync --group dev

printf '[bootstrap] checking required host dependencies
'
./check_dependencies.sh

current_branch="$(git branch --show-current 2>/dev/null || true)"
if [[ -n "$current_branch" ]]; then
  printf '[bootstrap] current branch: %s
' "$current_branch"
fi

mkdir -p artifacts/runs

cat <<'EOF'

[bootstrap] next recommended commands:
  uv run amiga-ui check
  uv run python tools/docs_triage.py
  uv run python tools/generate_api_index.py
  uv run python tools/analyze_target_failure.py --latest
  uv run python tests/run_gui_smoke_test.py
  uv run amiga-ui probe amiga_apps/itidy1classic/binary/extracted/iTidy
EOF
