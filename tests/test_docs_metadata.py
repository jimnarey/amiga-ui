import re
from pathlib import Path
import unittest

from tests.docs_metadata_helper import parse_front_matter


_SOURCE_ID_RE = re.compile(r"^\|\s*`(S\d+)`\s*\|")


class _DocMetadata:
    def __init__(self, title: str, status: str, depends_on: tuple[str, ...], citations_used: tuple[str, ...]) -> None:
        self.title = title
        self.status = status
        self.depends_on = depends_on
        self.citations_used = citations_used


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _docs_root() -> Path:
    return _project_root() / "docs"


def _iter_doc_paths(root: Path) -> list[Path]:
    return sorted(root.rglob("*.md"))


def _load_doc_metadata(path: Path) -> _DocMetadata:
    data = parse_front_matter(path.read_text(encoding="utf-8"))
    return _DocMetadata(
        title=_require_str(data, "title"),
        status=_require_str(data, "status"),
        depends_on=_require_list(data, "depends_on"),
        citations_used=_require_list(data, "citations_used"),
    )


def _load_source_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _SOURCE_ID_RE.match(line)
        if match:
            ids.add(match.group(1))
    return ids


def _resolve_dependency(doc_path: Path, dependency: str) -> Path:
    return (doc_path.parent / dependency).resolve()


def _require_str(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"front matter key {key!r} must be a string")
    return value


def _require_list(data: dict[str, object], key: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"front matter key {key!r} must be a list of strings")
    return tuple(value)


class DocsMetadataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.docs_root = _docs_root()
        cls.doc_paths = _iter_doc_paths(cls.docs_root)
        cls.source_ids = _load_source_ids(cls.docs_root / "sources.md")

    def test_all_declared_dependencies_resolve_to_real_docs_files(self) -> None:
        docs_root_resolved = self.docs_root.resolve()

        for doc_path in self.doc_paths:
            metadata = _load_doc_metadata(doc_path)
            for dependency in metadata.depends_on:
                with self.subTest(doc=str(doc_path.relative_to(self.docs_root)), dependency=dependency):
                    resolved = _resolve_dependency(doc_path, dependency)
                    self.assertTrue(resolved.is_file(), f"missing dependency target: {dependency}")
                    self.assertEqual(resolved.suffix, ".md", f"dependency is not a markdown file: {dependency}")
                    self.assertTrue(
                        str(resolved).startswith(str(docs_root_resolved)),
                        f"dependency escapes docs root: {dependency}",
                    )

    def test_all_declared_citations_resolve_to_real_source_entries(self) -> None:
        for doc_path in self.doc_paths:
            metadata = _load_doc_metadata(doc_path)
            for citation in metadata.citations_used:
                with self.subTest(doc=str(doc_path.relative_to(self.docs_root)), citation=citation):
                    self.assertIn(citation, self.source_ids)


if __name__ == "__main__":
    unittest.main()
