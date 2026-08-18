"""Applying/reverting the fixer agent's unified diff, plus a fast syntax
guardrail before the (much more expensive) probe rerun -- matching the
"error prevention" guardrail principle from the SWE-agent ACI research cited
in docs/research/local-agent-performance.md.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def apply_diff(diff_text: str) -> bool:
    result = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=PROJECT_ROOT,
        input=diff_text,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"diff did not apply cleanly:\n{result.stderr}")
    return result.returncode == 0


def revert_diff(diff_text: str) -> None:
    subprocess.run(
        ["git", "apply", "--reverse", "--whitespace=nowarn", "-"],
        cwd=PROJECT_ROOT,
        input=diff_text,
        text=True,
        capture_output=True,
        check=False,
    )


def syntax_ok(target_files: list[str]) -> bool:
    python_files = [f for f in target_files if f.endswith(".py")]
    if not python_files:
        return True
    result = subprocess.run(
        ["uv", "run", "ruff", "check", *python_files],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
    return result.returncode == 0
