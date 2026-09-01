import json
import tempfile
import unittest
from pathlib import Path

from amiga_ui.failure_analyzer import analyze_artifact, render_text


class FailureAnalyzerTest(unittest.TestCase):
    def test_resolves_defaulted_calls_with_api_index_and_flags_ui_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            artifact = root / "artifacts" / "runs" / "20260901T120000Z-probe-iTidy"
            artifact.mkdir(parents=True)
            (artifact / "result.json").write_text(
                json.dumps({"status": "app_failed", "ok": False, "returncode": 20}),
                encoding="utf-8",
            )
            (artifact / "stdout.txt").write_text(
                "Could not get visual info\nFailed to open GUI window\n",
                encoding="utf-8",
            )
            (artifact / "vamos.log").write_text(
                "12:00 lib:WARNING:  ? CALL: (gadtools.library)   42 UNKNOWN(#6) "
                "from PC=00abcd -> d0=0 (default)\n"
                "12:00 dos: INFO:  Open: name='ENV:sys/font.prefs' (old/1005/rb+) -> None\n",
                encoding="utf-8",
            )
            api_index = root / "api-index.json"
            api_index.write_text(
                json.dumps(
                    {
                        "libraries": [
                            {
                                "name": "gadtools.library",
                                "functions": [
                                    {
                                        "bias": 42,
                                        "name": "GetVisualInfoA",
                                        "ui_obligation": "host-ui-required",
                                        "implemented": False,
                                        "autodoc_url": "https://example.invalid/GetVisualInfoA.html",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            analysis = analyze_artifact(artifact, api_index_path=api_index)

            self.assertEqual(analysis.priority, "visible-ui-blocker")
            self.assertEqual(analysis.defaulted_calls[0].function, "UNKNOWN(#6)")
            self.assertEqual(analysis.defaulted_calls[0].resolved_function, "GetVisualInfoA")
            self.assertEqual(analysis.defaulted_calls[0].ui_obligation, "host-ui-required")
            self.assertEqual(analysis.missing_paths, [{"path": "ENV:sys/font.prefs", "count": 1}])
            self.assertIn("fake handle is not success", " ".join(analysis.recommended_next_steps))

    def test_text_report_includes_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            artifact = Path(temp_dir_name)
            (artifact / "result.json").write_text("{}", encoding="utf-8")
            (artifact / "stdout.txt").write_text("", encoding="utf-8")
            (artifact / "vamos.log").write_text("", encoding="utf-8")

            report = render_text(analyze_artifact(artifact, api_index_path=artifact / "missing.json"))

            self.assertIn("Recommended next steps:", report)
            self.assertIn("Regenerate the API index", report)


if __name__ == "__main__":
    unittest.main()
