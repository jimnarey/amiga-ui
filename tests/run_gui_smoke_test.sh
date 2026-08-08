#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${project_root}"
./tools/run_with_xvfb.sh uv run python tests/gui_smoke_test.py
