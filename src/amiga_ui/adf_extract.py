"""Extract operator-supplied Amiga ADF images into local reference trees."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .assets import project_relative
from .config import ASSETS_ROOT, PROJECT_ROOT

DEFAULT_ADF_DIR = ASSETS_ROOT / "adf"
DEFAULT_OUTPUT_ROOT = ASSETS_ROOT / "extracted" / "adf"


@dataclass(frozen=True)
class AdfExtraction:
    """Result for one ADF extraction attempt."""

    adf_path: str
    output_dir: str
    ok: bool
    returncode: int
    file_count: int
    error: str = ""


def discover_adf_images(adf_dir: Path = DEFAULT_ADF_DIR) -> list[Path]:
    """Return real ADF images, excluding placeholder inventory files."""

    if not adf_dir.is_dir():
        return []
    return sorted(
        path
        for path in adf_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".adf"
        and not path.name.startswith("_")
        and not path.name.endswith(".placeholder")
    )


def extraction_output_dir(adf_path: Path, output_root: Path = DEFAULT_OUTPUT_ROOT) -> Path:
    """Return the per-image extraction directory for an ADF path."""

    return output_root / adf_path.stem


def extract_adf(
    adf_path: Path,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    force: bool = False,
    dry_run: bool = False,
) -> AdfExtraction:
    """Extract one ADF with amitools' xdftool read-only unpack command."""

    adf_path = adf_path.resolve()
    out_dir = extraction_output_dir(adf_path, output_root).resolve()

    if not adf_path.is_file():
        return AdfExtraction(
            adf_path=project_relative(adf_path),
            output_dir=project_relative(out_dir),
            ok=False,
            returncode=1,
            file_count=0,
            error="ADF image does not exist",
        )

    if out_dir.exists():
        if not force:
            return AdfExtraction(
                adf_path=project_relative(adf_path),
                output_dir=project_relative(out_dir),
                ok=False,
                returncode=1,
                file_count=_count_files(out_dir),
                error="output directory already exists; pass --force to replace it",
            )
        if not dry_run:
            shutil.rmtree(out_dir)

    command = [
        sys.executable,
        "-m",
        "amitools.tools.xdftool",
        "-r",
        str(adf_path),
        "unpack",
        str(out_dir),
    ]

    if dry_run:
        return AdfExtraction(
            adf_path=project_relative(adf_path),
            output_dir=project_relative(out_dir),
            ok=True,
            returncode=0,
            file_count=0,
            error="dry run: " + " ".join(command),
        )

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)
    error = completed.stderr.strip() or completed.stdout.strip()
    return AdfExtraction(
        adf_path=project_relative(adf_path),
        output_dir=project_relative(out_dir),
        ok=completed.returncode == 0,
        returncode=completed.returncode,
        file_count=_count_files(out_dir),
        error="" if completed.returncode == 0 else error,
    )


def extract_adfs(
    adfs: list[Path],
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    force: bool = False,
    dry_run: bool = False,
) -> list[AdfExtraction]:
    """Extract multiple ADF images."""

    return [extract_adf(path, output_root=output_root, force=force, dry_run=dry_run) for path in adfs]


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for child in path.rglob("*") if child.is_file())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adf-dir",
        type=Path,
        default=DEFAULT_ADF_DIR,
        help="directory containing operator-supplied .adf images",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="directory where extracted ADF reference trees are written",
    )
    parser.add_argument(
        "--adf",
        action="append",
        type=Path,
        default=[],
        help="specific ADF image to extract; may be repeated; defaults to all images in --adf-dir",
    )
    parser.add_argument("--force", action="store_true", help="replace existing per-image extraction directories")
    parser.add_argument("--dry-run", action="store_true", help="show what would be extracted without writing files")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    adfs = args.adf or discover_adf_images(args.adf_dir)
    results = extract_adfs(adfs, output_root=args.output_root, force=args.force, dry_run=args.dry_run)

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    else:
        if not results:
            print(f"No ADF images found in {project_relative(args.adf_dir)}")
        for result in results:
            prefix = "[ok]" if result.ok else "[failed]"
            print(f"{prefix} {result.adf_path} -> {result.output_dir} ({result.file_count} files)")
            if result.error:
                print(f"  {result.error}")

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
