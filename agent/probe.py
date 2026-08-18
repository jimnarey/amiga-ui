"""Runs the project's own probe CLI and reads back its result.json.

Deliberately shells out to ``uv run amiga-ui probe`` rather than importing
src/amiga_ui/cli.py's internals: the probe's real, restricted output
contract is its result.json schema, not its private functions, and this
keeps the agent package decoupled from launcher implementation details it
doesn't own.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .blockers import BlockerCategory, deterministic_category, require_known_status

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ProbeResult:
    status: str
    ok: bool
    artifact_root: Path
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def signature(self) -> str:
        """A comparable "what's currently blocking" key.

        Matches the same coarse standard docs/apps/itidy/run-log.md entries
        already describe by hand ("advances startup to graphics.library"):
        the first-failure status (plus whatever distinguishing detail the
        launcher captured) either changed or it didn't. Nothing more precise
        than that actually exists in the launcher's output yet.
        """

        distinguishing = self.details.get("missing_library") or self.details.get("diagnostic_summary") or ""
        return f"{self.status}:{distinguishing}"

    @property
    def category(self) -> BlockerCategory | None:
        """The category the launcher's status already tells us for certain, if any.

        None means either "completed" (not a blocker) or "ambiguous" (the
        launcher can't tell) -- callers must distinguish those explicitly,
        see agent/driver.py.
        """

        return deterministic_category(self.status)

    def read_log_excerpt(self, *, max_chars: int = 4000) -> str:
        """Real log content for the classifier/fixer to reason and quote
        from, tail-truncated per file. Returns "" if nothing was captured --
        deliberately not a placeholder sentinel, so agent/llm.py's grounding
        check can treat "no source_text" as "grounding not applicable" (see
        ClassifierDeps) rather than requiring evidence against a message
        that isn't real log content. Callers building prompt text should
        supply their own "nothing captured" framing if they want one; see
        agent/driver.py's _classification_prompt.

        Without this, a prompt built only from ``details`` (the result.json
        payload) can be nearly empty for an ambiguous status like
        "app_failed" -- the specific detectors in cli.py's
        _classify_probe_outcome didn't match anything, so its ``details``
        dict is just {}. Asking a model to "quote the exact log lines" with
        nothing concrete to quote from is a guaranteed way to get fabricated
        evidence, not a model flaw -- see docs/apps/itidy/run-log.md's
        2026-08-18 entry for a real example of exactly that happening.
        """

        parts: list[str] = []
        for name in ("vamos.log", "stderr.txt", "stdout.txt"):
            path = self.artifact_root / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                parts.append(f"--- {name} (last {max_chars} chars) ---\n{text[-max_chars:]}")
        return "\n\n".join(parts)


def run_probe(target_binary: str, *, timeout: int | None = None, direct: bool = True) -> ProbeResult:
    """Runs `amiga-ui probe` and returns the freshly written result.

    ``direct=True`` by default: it works without Xvfb, which is the more
    portable default for an unattended driver. Pass ``direct=False`` to
    exercise the Xvfb-wrapped path instead.
    """

    before = _latest_artifact_root()
    command = ["uv", "run", "amiga-ui", "probe", target_binary]
    if direct:
        command.append("--direct")
    if timeout is not None:
        command.extend(["--timeout", str(timeout)])
    subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return _read_latest_result(before)


def _latest_artifact_root() -> Path | None:
    runs_dir = PROJECT_ROOT / "artifacts" / "runs"
    if not runs_dir.is_dir():
        return None
    candidates = sorted(runs_dir.iterdir())
    return candidates[-1] if candidates else None


def _read_latest_result(previous_latest: Path | None) -> ProbeResult:
    runs_dir = PROJECT_ROOT / "artifacts" / "runs"
    candidates = sorted(runs_dir.iterdir()) if runs_dir.is_dir() else []
    if not candidates or candidates[-1] == previous_latest:
        raise RuntimeError("probe did not produce a new artifacts/runs/ directory")
    latest = candidates[-1]
    payload = json.loads((latest / "result.json").read_text(encoding="utf-8"))
    status = payload["status"]
    require_known_status(status)
    return ProbeResult(status=status, ok=payload["ok"], artifact_root=latest, details=payload)
