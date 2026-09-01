#!/usr/bin/env bash

set -euo pipefail

project_dir="${OPENHANDS_PROJECT_DIR:-$PWD}"
cd "$project_dir"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

source tools/lib/quality_checks.sh

deny() {
  printf '{"decision":"deny","reason":"%s"}\n' "$1"
  exit 2
}

if ! quality_checks_run; then
  deny "$QUALITY_CHECK_REASON"
fi

exit 0
