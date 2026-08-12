"""Lightweight documentation inventory and suggestion helpers."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from .config import PROJECT_ROOT

DOCS_ROOT = PROJECT_ROOT / "docs"
_TOKEN_RE = re.compile(r"[a-z0-9_.:/-]+")
_TOKEN_ALIASES = {
    "launcher": {"runtime", "vamos", "path", "configuration", "tracing", "porting"},
    "probe": {"runbook", "porting", "tracing", "runtime", "vamos"},
    "gui": {"host", "widgets", "widget", "qt", "menus", "dialogs", "requesters"},
    "menu": {"menus", "dialogs", "requesters", "host", "gui"},
    "requester": {"requesters", "dialogs", "menus", "host", "gui"},
    "itidy": {"itidy", "apps", "runbook", "compatibility", "dependencies"},
    "library": {"libraries", "library", "cards", "runtime", "structs"},
    "assets": {"assets", "adf", "rom", "toolkits", "documentation"},
    "docs": {"sources", "workflow", "workflows", "research", "documentation"},
}


@dataclass(frozen=True)
class DocEntry:
    """One documentation file described by path and front matter only."""

    rel_path: str
    section: str
    title: str
    status: str
    depends_on: tuple[str, ...]


def read_doc_entries(root: Path = DOCS_ROOT) -> list[DocEntry]:
    """Load markdown inventory using filenames and front matter only."""

    entries: list[DocEntry] = []
    for path in sorted(root.rglob("*.md")):
        metadata = _read_front_matter(path)
        rel_path = path.relative_to(root).as_posix()
        entries.append(
            DocEntry(
                rel_path=rel_path,
                section=_section_for_path(rel_path),
                title=_require_string(metadata, "title"),
                status=_require_string(metadata, "status"),
                depends_on=_require_string_list(metadata, "depends_on"),
            )
        )
    return entries


def suggest_docs(entries: list[DocEntry], terms: list[str]) -> list[DocEntry]:
    """Return entries whose path/title best match the given terms."""

    tokens = _tokenize_terms(terms)
    if not tokens:
        return []

    ranked: list[tuple[int, int, str, DocEntry]] = []
    for entry in entries:
        title_tokens = _tokenize_text(entry.title)
        path_tokens = _tokenize_text(entry.rel_path)
        section_tokens = _tokenize_text(entry.section)
        score = 0
        matched = 0
        for token in tokens:
            expanded_tokens = {token, *_TOKEN_ALIASES.get(token, set())}
            if _any_token_matches(expanded_tokens, title_tokens):
                score += 4
                matched += 1
                continue
            if _any_token_matches(expanded_tokens, path_tokens):
                score += 3
                matched += 1
                continue
            if _any_token_matches(expanded_tokens, section_tokens):
                score += 2
                matched += 1
        if matched:
            ranked.append((matched, score, entry.rel_path, entry))

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in ranked]


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for docs triage."""

    parser = argparse.ArgumentParser(
        prog="docs-triage",
        description="Inspect documentation inventory using markdown paths and front matter only.",
    )
    parser.add_argument(
        "--section",
        help="limit output to one top-level docs section such as runtime, host-gui, or apps",
    )
    parser.add_argument(
        "--suggest",
        nargs="+",
        help="rank likely relevant docs by matching the given terms against titles and paths",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for docs triage."""

    parser = build_parser()
    args = parser.parse_args(argv)
    entries = read_doc_entries()

    if args.suggest:
        _print_suggestions(entries, args.suggest, args.section)
        return 0

    _print_inventory(entries, args.section)
    return 0


def _print_inventory(entries: list[DocEntry], section_filter: str | None) -> None:
    filtered = _filter_by_section(entries, section_filter)
    if section_filter:
        print(f"Documentation inventory for section: {section_filter}")
    else:
        print("Documentation inventory (front matter only)")
    for line in _section_summary_lines(filtered):
        print(line)
    print()
    print("Suggested next step:")
    print("  Read docs/README.md, then read in full only the small set of docs relevant to the immediate task.")
    print("  Use --suggest <terms> to find likely candidates by filename and title.")


def _print_suggestions(entries: list[DocEntry], terms: list[str], section_filter: str | None) -> None:
    filtered = _filter_by_section(entries, section_filter)
    suggestions = suggest_docs(filtered, terms)
    print(f"Suggested docs for: {' '.join(terms)}")
    if not suggestions:
        print("  No matching docs found.")
        return
    for entry in suggestions[:12]:
        print(f"  - {entry.rel_path} [{entry.status}] — {entry.title}")


def _filter_by_section(entries: list[DocEntry], section_filter: str | None) -> list[DocEntry]:
    if section_filter is None:
        return entries
    return [entry for entry in entries if entry.section == section_filter]


def _section_summary_lines(entries: list[DocEntry]) -> list[str]:
    section_map: dict[str, list[DocEntry]] = {}
    for entry in entries:
        section_map.setdefault(entry.section, []).append(entry)

    lines: list[str] = []
    for section in sorted(section_map):
        section_entries = section_map[section]
        lines.append(f"- {section}: {len(section_entries)} docs")
        for entry in section_entries[:5]:
            lines.append(f"  - {entry.rel_path} [{entry.status}] — {entry.title}")
        if len(section_entries) > 5:
            lines.append(f"  - ... {len(section_entries) - 5} more")
    return lines


def _read_front_matter(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        first_line = handle.readline()
        if first_line.strip() != "---":
            raise ValueError(f"{path} is missing YAML front matter")

        data: dict[str, object] = {}
        current_list_key: str | None = None
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if line.strip() == "---":
                return data

            if line.startswith("  - "):
                if current_list_key is None:
                    raise ValueError(f"{path} has a list item before a list key")
                value = line[4:].strip()
                value = _strip_quotes(value)
                existing = data.setdefault(current_list_key, [])
                if not isinstance(existing, list):
                    raise ValueError(f"{path} front matter key {current_list_key!r} is not a list")
                existing.append(value)
                continue

            current_list_key = None
            if ":" not in line:
                raise ValueError(f"{path} has an invalid front matter line: {line}")

            key, raw_value = line.split(":", 1)
            key = key.strip()
            value = raw_value.strip()
            if value == "":
                data[key] = []
                current_list_key = key
                continue
            if value == "[]":
                data[key] = []
                continue
            data[key] = _strip_quotes(value)

    raise ValueError(f"{path} has unterminated YAML front matter")


def _require_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"front matter key {key!r} must be a string")
    return value


def _require_string_list(data: dict[str, object], key: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"front matter key {key!r} must be a list of strings")
    return tuple(value)


def _section_for_path(rel_path: str) -> str:
    parts = rel_path.split("/", 1)
    if len(parts) == 1:
        return "root"
    return parts[0]


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _tokenize_terms(terms: list[str]) -> list[str]:
    return _tokenize_text(" ".join(terms))


def _tokenize_text(text: str) -> set[str]:
    lowered = text.casefold()
    tokens = set(_TOKEN_RE.findall(lowered))
    for separator in ("/", "-", "_", "."):
        for token in list(tokens):
            if separator in token:
                tokens.update(part for part in token.split(separator) if part)
    return tokens


def _any_token_matches(query_tokens: set[str], entry_tokens: set[str]) -> bool:
    for query_token in query_tokens:
        for entry_token in entry_tokens:
            if query_token == entry_token or query_token in entry_token or entry_token in query_token:
                return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
