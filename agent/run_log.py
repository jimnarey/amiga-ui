"""Appends run-outcome entries to docs/apps/<app>/run-log.md, matching the
existing hand-written entry format (see docs/apps/itidy/run-log.md's own
"Entries" section: newest entry last, do not edit or delete earlier ones).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def append_run_log_entry(
    app: str,
    *,
    title: str,
    observed: str,
    change: str,
    next_step: str,
) -> Path:
    run_log_path = PROJECT_ROOT / "docs" / "apps" / app / "run-log.md"
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    entry = f"\n### {date} — {title}\n\n- Observed: {observed}\n- Change: {change}\n- Next: {next_step}\n"
    with run_log_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    return run_log_path
