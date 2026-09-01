import tempfile
import unittest
from pathlib import Path

from amiga_ui.api_index import ApiTarget, build_library_entry, classify_ui_obligation, render_markdown


class ApiIndexTest(unittest.TestCase):
    def test_builds_library_entry_from_fd_and_marks_ui_obligation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            fd_dir = root / "fd"
            fd_dir.mkdir()
            (fd_dir / "intuition_lib.fd").write_text(
                """##base _IntuitionBase
##bias 30
##public
OpenWindowTagList(newWindow,tagList)(a0/a1)
GetVisualInfoA(screen,tagList)(a0/a1)
##end
""",
                encoding="utf-8",
            )

            entry = build_library_entry(
                ApiTarget("intuition.library", "host-ui-required", "test"),
                docs_root=root,
                fd_dirs=[fd_dir],
            )

            self.assertEqual(entry.fd_source, str(fd_dir / "intuition_lib.fd"))
            self.assertEqual(entry.function_count, 6)
            funcs = {func.name: func for func in entry.functions}
            self.assertEqual(funcs["OpenWindowTagList"].bias, 30)
            self.assertEqual(funcs["OpenWindowTagList"].ui_obligation, "host-ui-required")
            self.assertEqual(funcs["GetVisualInfoA"].ui_obligation, "host-ui-required")

    def test_classifies_non_ui_support(self) -> None:
        self.assertEqual(classify_ui_obligation("utility.library", "FindTagItem"), "stateful-runtime-required")
        self.assertEqual(classify_ui_obligation("exec.library", "Disable"), "support")

    def test_markdown_contains_obligation_column(self) -> None:
        payload = {
            "libraries": [
                {
                    "name": "intuition.library",
                    "role": "host-ui-required",
                    "why": "test",
                    "fd_source": "fd/intuition_lib.fd",
                    "implemented_count": 0,
                    "function_count": 1,
                    "warnings": [],
                    "functions": [
                        {
                            "index": 4,
                            "bias": 30,
                            "name": "OpenWindowTagList",
                            "args": [],
                            "ui_obligation": "host-ui-required",
                            "implementation_file": None,
                            "autodoc_path": None,
                            "autodoc_url": "https://example.invalid/OpenWindowTagList.html",
                        }
                    ],
                }
            ]
        }

        markdown = render_markdown(payload)

        self.assertIn("| Index | Bias | Function | Args | Obligation | Impl status | Impl file | AutoDoc |", markdown)
        self.assertIn("`host-ui-required`", markdown)


if __name__ == "__main__":
    unittest.main()
