"""Creation and writing of run artifact directories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import ARTIFACTS_ROOT


@dataclass(frozen=True)
class RunArtifacts:
    """Paths for the files produced by one command run."""

    root: Path
    stdout_path: Path
    stderr_path: Path
    result_path: Path
    invocation_path: Path
    vamos_log_path: Path
    runtime_root: Path


def create_run_artifacts(command_name: str, target_name: str | None = None) -> RunArtifacts:
    """Create a timestamped artifact directory."""

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    label = command_name if target_name is None else f"{command_name}-{target_name}"
    root = ARTIFACTS_ROOT / f"{timestamp}-{label}"
    root.mkdir(parents=True, exist_ok=False)
    runtime_root = root / "runtime"
    runtime_root.mkdir()
    return RunArtifacts(
        root=root,
        stdout_path=root / "stdout.txt",
        stderr_path=root / "stderr.txt",
        result_path=root / "result.json",
        invocation_path=root / "invocation.json",
        vamos_log_path=root / "vamos.log",
        runtime_root=runtime_root,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write indented JSON with a trailing newline."""

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

