"""Project-wide path and runtime defaults."""

from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
ASSETS_ROOT = PROJECT_ROOT / "assets"
TOOLS_ROOT = PROJECT_ROOT / "tools"
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts" / "runs"
TESTS_ROOT = PROJECT_ROOT / "tests"

DEFAULT_PROBE_TIMEOUT_SECONDS = 20
DEFAULT_SMOKE_GUI_DURATION_MS = 250

