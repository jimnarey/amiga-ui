#!/usr/bin/env python3
"""Fetch AmigaOS 3 developer AutoDoc indexes and function pages."""

from __future__ import annotations

import argparse
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DEFAULT_TARGETS = (
    "exec.library",
    "dos.library",
    "intuition.library",
    "graphics.library",
    "layers.library",
    "gadtools.library",
    "asl.library",
    "icon.library",
    "workbench.library",
    "utility.library",
    "iffparse.library",
    "diskfont.library",
    "locale.library",
    "datatypes.library",
    "commodities.library",
    "keymap.library",
    "rexxsyslib.library",
    "bullet.library",
    "timer.device",
    "input.device",
    "console.device",
    "clipboard.device",
)

BASE_URL = "https://developer.amigaos3.net/autodocs/"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


def fetch(url: str, output: Path, *, timeout: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "amiga-ui-resource-fetcher/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-run resource fetcher
        output.write_bytes(response.read())


def function_links(index_html: str, index_url: str) -> list[str]:
    parser = LinkParser()
    parser.feed(index_html)
    parsed_index = urlparse(index_url)
    links: set[str] = set()
    for href in parser.hrefs:
        absolute = urljoin(index_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc != parsed_index.netloc:
            continue
        if not parsed.path.startswith(parsed_index.path):
            continue
        if not parsed.path.endswith(".html"):
            continue
        if parsed.path.endswith("/index.html"):
            continue
        links.add(absolute)
    return sorted(links)


def fetch_target(target: str, output_root: Path, *, index_only: bool, timeout: int, delay: float) -> list[Path]:
    index_url = urljoin(BASE_URL, f"{target}/")
    target_dir = output_root / target
    index_path = target_dir / "index.html"
    fetch(index_url, index_path, timeout=timeout)
    written = [index_path]
    if index_only:
        return written

    html = index_path.read_text(encoding="utf-8", errors="replace")
    for link in function_links(html, index_url):
        name = Path(urlparse(link).path).name
        out_path = target_dir / name
        fetch(link, out_path, timeout=timeout)
        written.append(out_path)
        if delay > 0:
            time.sleep(delay)
    return written


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root", type=Path, default=Path(__file__).resolve().parent / "amigaos3-developer" / "autodocs"
    )
    parser.add_argument(
        "--target", action="append", default=[], help="AutoDoc target, e.g. intuition.library; may be repeated"
    )
    parser.add_argument("--index-only", action="store_true", help="fetch only index pages")
    parser.add_argument("--keep-going", action="store_true", help="continue when an optional target fails")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--delay", type=float, default=0.05, help="small politeness delay between function pages")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    targets = args.target or list(DEFAULT_TARGETS)
    failures = 0
    for target in targets:
        try:
            written = fetch_target(
                target, args.output_root, index_only=args.index_only, timeout=args.timeout, delay=args.delay
            )
        except Exception as exc:  # pragma: no cover - network failure path
            failures += 1
            print(f"[failed] {target}: {exc}", file=sys.stderr)
            if not args.keep_going:
                return 1
            continue
        print(f"[ok] {target}: {len(written)} files")
    return 1 if failures and not args.keep_going else 0


if __name__ == "__main__":
    raise SystemExit(main())
