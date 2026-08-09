"""Helpers for locating repo-managed application and binary assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import ASSETS_ROOT, PROJECT_ROOT


@dataclass(frozen=True)
class AssetCheck:
    """Summary for a single required repo asset."""

    label: str
    path: Path
    exists: bool
    required: bool = True


@dataclass(frozen=True)
class AssetInventory:
    """Count real files and placeholders in one asset directory."""

    label: str
    directory: Path
    present_count: int
    placeholder_count: int


def project_relative(path: Path) -> str:
    """Render a path relative to the repo root when possible."""

    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def required_asset_checks() -> list[AssetCheck]:
    """Return the small set of assets needed for the initial tooling loop."""

    return [
        AssetCheck(
            label="iTidy extracted binary",
            path=PROJECT_ROOT / "amiga_apps/itidy1classic/binary/extracted/iTidy",
            exists=(PROJECT_ROOT / "amiga_apps/itidy1classic/binary/extracted/iTidy").is_file(),
        ),
        AssetCheck(
            label="ClassAct 3.3 archive",
            path=ASSETS_ROOT / "libs/classact33.lha",
            exists=(ASSETS_ROOT / "libs/classact33.lha").is_file(),
            required=False,
        ),
    ]


def asset_inventory() -> list[AssetInventory]:
    """Return counts for the copyrighted asset directories."""

    inventories: list[AssetInventory] = []
    for label, relative_dir, suffixes in (
        ("ADF images", "adf", (".adf",)),
        ("Kickstart ROMs", "roms", (".rom",)),
    ):
        directory = ASSETS_ROOT / relative_dir
        present_count = sum(
            1
            for path in directory.iterdir()
            if path.is_file() and not path.name.endswith(".placeholder") and path.suffix.lower() in suffixes
        )
        placeholder_count = sum(
            1 for path in directory.iterdir() if path.is_file() and path.name.endswith(".placeholder")
        )
        inventories.append(
            AssetInventory(
                label=label,
                directory=directory,
                present_count=present_count,
                placeholder_count=placeholder_count,
            )
        )
    return inventories

