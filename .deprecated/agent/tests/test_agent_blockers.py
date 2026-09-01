"""Guards agent/blockers.py's category routing against drift in the real
launcher code it's anchored to (src/amiga_ui/cli.py::_classify_probe_outcome).

If cli.py's detector chain changes -- a new status added, or an existing one
removed -- these tests should fail loudly rather than let agent/blockers.py
silently fall out of sync with what the launcher actually restricts.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from agent.blockers import (
    KNOWN_PROBE_STATUSES,
    UnknownProbeStatusError,
    ambiguous_categories,
    deterministic_category,
)


class DeterministicRoutingTests(unittest.TestCase):
    def test_statuses_the_launcher_already_resolves_map_without_a_model_call(self) -> None:
        self.assertEqual(deterministic_category("missing_asset"), "host_dependency_or_setup")
        self.assertEqual(deterministic_category("path_setup_failed"), "path_or_runtime_tree")
        self.assertEqual(deterministic_category("missing_library"), "missing_library_or_function")

    def test_ambiguous_statuses_have_no_deterministic_category(self) -> None:
        for status in ("app_failed", "vamos_error", "timeout"):
            self.assertIsNone(deterministic_category(status))
            self.assertGreater(len(ambiguous_categories(status)), 0)

    def test_completed_has_no_deterministic_category_either(self) -> None:
        # Not a blocker at all -- callers (agent/driver.py) must check
        # status == "completed" before reaching classification, this is not
        # the signal that distinguishes "no blocker" from "ambiguous blocker".
        self.assertIsNone(deterministic_category("completed"))

    def test_ambiguous_categories_rejects_completed(self) -> None:
        with self.assertRaises(UnknownProbeStatusError):
            ambiguous_categories("completed")

    def test_unknown_status_raises_instead_of_guessing(self) -> None:
        with self.assertRaises(UnknownProbeStatusError):
            deterministic_category("some_new_status_cli_py_might_add_later")
        with self.assertRaises(UnknownProbeStatusError):
            ambiguous_categories("some_new_status_cli_py_might_add_later")


class LauncherStatusSetDriftGuardTests(unittest.TestCase):
    """Drives the real _classify_probe_outcome detector chain with synthetic
    input for every branch it has, and confirms every status it can produce
    is one KNOWN_PROBE_STATUSES already accounts for."""

    def setUp(self) -> None:
        from amiga_ui import cli

        self.cli = cli

    def _classify(self, returncode: int, log_text: str, stderr_text: str) -> str:
        vamos_log = Path(self._write_tmp("vamos.log", log_text))
        stderr_path = Path(self._write_tmp("stderr.txt", stderr_text))
        classification = self.cli._classify_probe_outcome(returncode, vamos_log, stderr_path)
        return classification.status

    def _write_tmp(self, name: str, text: str) -> Path:
        path = self._tmp_dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_success_is_completed(self) -> None:
        self._tmp_dir = self._make_tmp_dir()
        status = self._classify(0, "", "")
        self.assertEqual(status, "completed")
        self.assertIn(status, KNOWN_PROBE_STATUSES)

    def test_missing_openlibrary_call_is_missing_library(self) -> None:
        self._tmp_dir = self._make_tmp_dir()
        status = self._classify(1, "OpenLibrary: 'icon.library' V0 -> 000000", "")
        self.assertEqual(status, "missing_library")
        self.assertIn(status, KNOWN_PROBE_STATUSES)

    def test_path_setup_failure_string_is_path_setup_failed(self) -> None:
        self._tmp_dir = self._make_tmp_dir()
        status = self._classify(1, "path setup failed!", "")
        self.assertEqual(status, "path_setup_failed")
        self.assertIn(status, KNOWN_PROBE_STATUSES)

    def test_python_traceback_in_stderr_is_vamos_error(self) -> None:
        self._tmp_dir = self._make_tmp_dir()
        status = self._classify(1, "", "Traceback (most recent call last):\n...")
        self.assertEqual(status, "vamos_error")
        self.assertIn(status, KNOWN_PROBE_STATUSES)

    def test_unrecognized_failure_is_app_failed(self) -> None:
        self._tmp_dir = self._make_tmp_dir()
        status = self._classify(1, "some other failure entirely", "")
        self.assertEqual(status, "app_failed")
        self.assertIn(status, KNOWN_PROBE_STATUSES)

    def _make_tmp_dir(self) -> Path:
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)


if __name__ == "__main__":
    unittest.main()
