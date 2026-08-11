#!/usr/bin/env bash

set -euo pipefail

missing=0
missing_labels=()

check_tool() {
  local label="$1"
  shift 1
  if "$@" >/dev/null 2>&1; then
    echo "[ok] ${label}"
  else
    echo "[missing] ${label}"
    missing=1
    missing_labels+=("${label}")
  fi
}

echo "Checking required host dependencies..."

check_tool \
  "7z command available" \
  7z -h

check_tool \
  "Xvfb command available" \
  Xvfb -help

if [[ "${missing}" -ne 0 ]]; then
  echo
  echo "Missing dependencies:"
  for label in "${missing_labels[@]}"; do
    echo "- ${label}"
  done
  exit 1
fi

echo
echo "All required host dependencies were found."
