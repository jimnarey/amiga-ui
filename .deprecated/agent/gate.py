"""Reuses the repo's existing shared quality-check and stop-marker
infrastructure (tools/lib/) rather than reimplementing it -- see
docs/workflows/agent-tool-contract.md, tools/lib/quality_checks.sh, and
tools/lib/stop_marker.sh. This module adds no new verification logic of its
own.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent

StopReason = Literal["complete", "needs-user", "blocked"]


def quality_gate_passes() -> bool:
    """Runs the shared branch-hygiene/pre-commit/unittest/smoke checks. Tool
    output streams straight to this process's stdout/stderr, matching
    tools/lib/quality_checks.sh's own existing behavior.
    """

    script = "set -euo pipefail\nsource tools/lib/quality_checks.sh\nquality_checks_run\n"
    result = subprocess.run(["bash", "-c", script], cwd=PROJECT_ROOT, check=False)
    return result.returncode == 0


def write_stop_marker(reason: StopReason, note: str) -> None:
    """Writes the complete/blocked/needs-user marker vocabulary in this
    driver's own .agent/state/ namespace (see
    tools/bespoke_agent_allow_stop.sh), via a plain argv call -- no shell
    interpolation of `note`, so arbitrary text is always safe here.
    """

    subprocess.run(
        ["tools/bespoke_agent_allow_stop.sh", reason, note],
        cwd=PROJECT_ROOT,
        check=True,
    )
