"""Probe target metadata for the iTidy application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import PROJECT_ROOT


@dataclass(frozen=True)
class ProbeTarget:
    """Metadata needed to probe an Amiga executable under vamos."""

    name: str
    amiga_binary: str
    host_binary_path: Path
    app_volume_root: Path


def get_probe_target(name: str) -> ProbeTarget:
    """Resolve a supported probe target by name."""

    normalized_name = name.strip().lower()
    if normalized_name != "itidy":
        raise ValueError(f"unknown probe target: {name}")

    app_volume_root = PROJECT_ROOT / "amiga_apps/itidy1classic/binary/extracted"
    return ProbeTarget(
        name="itidy",
        amiga_binary="app:iTidy",
        host_binary_path=app_volume_root / "iTidy",
        app_volume_root=app_volume_root,
    )
