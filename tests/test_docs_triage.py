import tempfile
import unittest
from pathlib import Path

from amiga_ui.docs_triage import DocEntry, read_doc_entries, suggest_docs


class DocsTriageReadTest(unittest.TestCase):
    def test_reads_titles_statuses_and_sections_from_front_matter_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            docs_root = root / "docs"
            (docs_root / "runtime").mkdir(parents=True)
            (docs_root / "runtime" / "vamos-overview.md").write_text(
                """---
title: "Vamos Overview"
status: draft
depends_on:
  - "../architecture/overview.md"
citations_used: []
---

# Vamos Overview

Body text.
""",
                encoding="utf-8",
            )

            entries = read_doc_entries(docs_root)

            self.assertEqual(
                entries,
                [
                    DocEntry(
                        rel_path="runtime/vamos-overview.md",
                        section="runtime",
                        title="Vamos Overview",
                        status="draft",
                        depends_on=("../architecture/overview.md",),
                    )
                ],
            )


class DocsTriageSuggestTest(unittest.TestCase):
    def test_prefers_title_and_path_matches_for_suggestions(self) -> None:
        entries = [
            DocEntry(
                rel_path="runtime/vamos-overview.md",
                section="runtime",
                title="Vamos Overview",
                status="draft",
                depends_on=(),
            ),
            DocEntry(
                rel_path="host-gui/testing-host-ui.md",
                section="host-gui",
                title="Testing Host UI Code",
                status="draft",
                depends_on=(),
            ),
            DocEntry(
                rel_path="apps/itidy/runbook.md",
                section="apps",
                title="iTidy Runbook",
                status="draft",
                depends_on=(),
            ),
        ]

        suggestions = suggest_docs(entries, ["vamos", "runtime"])

        self.assertEqual(
            suggestions,
            [
                DocEntry(
                    rel_path="runtime/vamos-overview.md",
                    section="runtime",
                    title="Vamos Overview",
                    status="draft",
                    depends_on=(),
                )
            ],
        )

    def test_supports_common_task_terms_via_aliases(self) -> None:
        entries = [
            DocEntry(
                rel_path="runtime/vamos-overview.md",
                section="runtime",
                title="Vamos Overview",
                status="draft",
                depends_on=(),
            ),
            DocEntry(
                rel_path="workflows/error-driven-porting.md",
                section="workflows",
                title="Error Driven Porting",
                status="draft",
                depends_on=(),
            ),
            DocEntry(
                rel_path="apps/itidy/runbook.md",
                section="apps",
                title="iTidy Runbook",
                status="draft",
                depends_on=(),
            ),
        ]

        suggestions = suggest_docs(entries, ["launcher", "probe"])

        self.assertEqual(
            suggestions,
            [
                DocEntry(
                    rel_path="runtime/vamos-overview.md",
                    section="runtime",
                    title="Vamos Overview",
                    status="draft",
                    depends_on=(),
                ),
                DocEntry(
                    rel_path="workflows/error-driven-porting.md",
                    section="workflows",
                    title="Error Driven Porting",
                    status="draft",
                    depends_on=(),
                ),
                DocEntry(
                    rel_path="apps/itidy/runbook.md",
                    section="apps",
                    title="iTidy Runbook",
                    status="draft",
                    depends_on=(),
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
