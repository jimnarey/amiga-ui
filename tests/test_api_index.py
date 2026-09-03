import tempfile
import unittest
from pathlib import Path

from amiga_ui.api_index import (
    ApiTarget,
    _discover_fd_dirs,
    build_library_entry,
    classify_target_status,
    classify_ui_obligation,
    render_markdown,
)


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

    def test_discovers_uppercase_fd_dirs_and_versions_functions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            fd_dir = root / "ndk" / "NDK3.2" / "FD"
            fd_dir.mkdir(parents=True)
            (fd_dir / "gadtools_lib.fd").write_text(
                """##base _GadToolsBase
##bias 30
##public
*--- functions in V36 or higher (Release 2.0) ---
GetVisualInfoA(screen,tagList)(a0/a1)
FreeVisualInfo(vi)(a0)
*--- functions in V47 or higher (Release 3.2) ---
SetDesignFontA(vi,tattr,tags)(a0/a1/a2)
##end
""",
                encoding="utf-8",
            )

            self.assertEqual(_discover_fd_dirs(root), [fd_dir])

            entry = build_library_entry(
                ApiTarget("gadtools.library", "host-ui-required", "test"),
                docs_root=root,
                fd_dirs=[fd_dir],
            )

            funcs = {func.name: func for func in entry.functions}
            self.assertEqual(funcs["GetVisualInfoA"].introduced_version, 36)
            self.assertEqual(funcs["GetVisualInfoA"].target_status, "classic-baseline")
            self.assertEqual(funcs["SetDesignFontA"].introduced_version, 47)
            self.assertEqual(funcs["SetDesignFontA"].target_status, "later-classic-reference")

    def test_classifies_non_ui_support(self) -> None:
        self.assertEqual(classify_ui_obligation("utility.library", "FindTagItem"), "stateful-runtime-required")
        self.assertEqual(classify_ui_obligation("exec.library", "Disable"), "support")

    def test_classifies_api_target_status(self) -> None:
        self.assertEqual(classify_target_status(None), "baseline-or-unknown")
        self.assertEqual(classify_target_status(40), "classic-baseline")
        self.assertEqual(classify_target_status(44), "later-classic-optional")
        self.assertEqual(classify_target_status(47), "later-classic-reference")
        self.assertEqual(classify_target_status(50), "out-of-target")

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
                            "introduced_version": 39,
                            "target_status": "classic-baseline",
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

        self.assertIn(
            "| Index | Bias | Function | Args | Min version | Target | Obligation | "
            "Impl status | Impl file | AutoDoc |",
            markdown,
        )
        self.assertIn(
            "| 4 | 30 | `OpenWindowTagList` |  | 39 | `classic-baseline` |",
            markdown,
        )
        self.assertIn("`host-ui-required`", markdown)


if __name__ == "__main__":
    unittest.main()
