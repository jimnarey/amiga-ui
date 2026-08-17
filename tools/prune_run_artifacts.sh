#!/usr/bin/env bash
# Prune old local probe/run artifacts under artifacts/runs/, keeping the
# most recent N run directories (default 20). These are gitignored,
# local-only diagnostic output (invocation, stdout/stderr, vamos log,
# result summary) — safe to delete once any useful findings have been
# carried forward into the relevant docs (see docs/apps/<app>/run-log.md).

set -euo pipefail

keep="${1:-20}"
runs_dir="artifacts/runs"

if [[ ! "$keep" =~ ^[0-9]+$ || "$keep" -lt 1 ]]; then
  echo "Usage: ./tools/prune_run_artifacts.sh [positive-runs-to-keep]" >&2
  exit 2
fi

if [[ ! -d "$runs_dir" ]]; then
  echo "No $runs_dir directory found; nothing to prune."
  exit 0
fi

mapfile -t all_runs < <(ls -1 "$runs_dir" | sort)
total="${#all_runs[@]}"

if (( total <= keep )); then
  echo "$total run(s) in $runs_dir, keeping up to $keep; nothing to prune."
  exit 0
fi

to_remove=("${all_runs[@]:0:$((total - keep))}")

echo "Removing $((total - keep)) of $total run(s) in $runs_dir, keeping the most recent $keep:"
for run in "${to_remove[@]}"; do
  echo "  $run"
  rm -rf -- "${runs_dir:?}/${run:?}"
done
