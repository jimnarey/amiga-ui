"""Minimal git operations the driver needs.

Deliberately does not create, switch, or merge branches: the quality gate
(agent/gate.py -> tools/lib/quality_checks.sh) already refuses to pass on
`main` or a dirty `development`, so being on the right branch first is a
precondition the caller/human satisfies -- the same way it already is for
the OpenHands and Goose harnesses, which don't auto-branch either.

Also deliberately requires explicit paths rather than `git add -A`, so a
commit can never sweep in unrelated working-tree changes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def commit(message: str, paths: list[str]) -> None:
    if not paths:
        raise ValueError("commit() requires at least one explicit path; refuses to git add -A")
    subprocess.run(["git", "add", *paths], cwd=PROJECT_ROOT, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=PROJECT_ROOT, check=True)
