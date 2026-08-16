"""Probe target metadata derived from an arbitrary host-side Amiga binary path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProbeTarget:
    """Metadata needed to probe an Amiga executable under vamos."""

    name: str
    amiga_binary: str
    host_binary_path: Path
    app_volume_root: Path


def resolve_probe_target(binary_path: Path) -> ProbeTarget:
    """Build probe metadata for a host-side Amiga executable.

    The executable's containing directory becomes the `app:` volume, so any
    supporting files it expects to find alongside itself stay reachable.
    """

    resolved = binary_path.resolve()
    return ProbeTarget(
        name=resolved.stem,
        amiga_binary=f"app:{resolved.name}",
        host_binary_path=resolved,
        app_volume_root=resolved.parent,
    )


def resolve_host_binary(binary_path: Path) -> tuple[str, str]:
    """Return the same binary with both an absolute and a relative path.

    This helper supports probe args that need the volume name but want to
    pass system paths to vamos.
    """
    resolved = binary_path.resolve()
    return (str(resolved), binary_path.as_posix())
