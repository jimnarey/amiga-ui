#!/usr/bin/env bash
# Shared "is this branch actually merge/finish-ready" checks: branch
# hygiene, pre-commit, unit tests, GUI smoke test. Sourced by
# active or legacy harness wrappers. Not meant to be invoked directly.
#
# Assumes the sourcing script's working directory is the repository root.

# quality_checks_run
# Runs the checks in order, stopping at the first failure. Tool output goes
# straight to the caller's stdout/stderr as it runs. On failure, sets
# QUALITY_CHECK_REASON to a human-readable explanation and returns 1. On
# success, returns 0.
quality_checks_run() {
  QUALITY_CHECK_REASON=""
  local current_branch
  current_branch="$(git branch --show-current 2>/dev/null || true)"

  if [[ "$current_branch" == "main" ]]; then
    QUALITY_CHECK_REASON="Do not finish work on main. Switch to development, then use a feature branch for changes."
    return 1
  fi

  if [[ "$current_branch" == "development" ]]; then
    if ! git diff --quiet || ! git diff --cached --quiet; then
      QUALITY_CHECK_REASON="Do not finish with unmerged work sitting on development. Move the change to a feature branch and merge back only after it passes the quality gates."
      return 1
    fi
  fi

  if ! uv run pre-commit run --all-files 2>&1; then
    QUALITY_CHECK_REASON="pre-commit checks failed. Fix formatting, lint, or type-check issues before finishing."
    return 1
  fi

  if ! uv run python -m unittest 2>&1; then
    QUALITY_CHECK_REASON="The unit test suite failed. Fix the failures before finishing."
    return 1
  fi

  if ! uv run python tests/run_gui_smoke_test.py 2>&1; then
    QUALITY_CHECK_REASON="The headless GUI smoke test failed. Fix the Xvfb or Qt path before finishing."
    return 1
  fi

  return 0
}
