"""Helpers for running commands through the repo's Xvfb wrapper."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ..config import PROJECT_ROOT, TOOLS_ROOT


def xvfb_wrapper_path() -> Path:
    """Return the path to the repo-managed Xvfb wrapper."""

    return TOOLS_ROOT / "run_with_xvfb.sh"


def run_with_xvfb(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    text: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """Run a command through the shell wrapper that provisions Xvfb."""

    merged_env = os.environ.copy()
    if env is not None:
        merged_env.update(env)
    return subprocess.run(
        [str(xvfb_wrapper_path()), *command],
        cwd=PROJECT_ROOT if cwd is None else cwd,
        env=merged_env,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        check=False,
    )

