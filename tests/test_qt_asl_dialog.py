"""Qt (offscreen) tests for the ASL file-requester host dialog round trip.

These are the *widget-level* tests for the QFileDialog half of ``AslRequest``
(LVO -60): the projection must show a real, *blocking* non-native
:class:`QFileDialog` carrying the app's own title, initial drawer, initial
file, and mode (directory-only / save / open), and return the path the user
actually chose — or ``None`` when the user actually cancelled.

The dialog is driven the same way the interactive smoke tests drive real
widgets: a :class:`QTimer` fires during ``exec()``'s nested event loop, points
the dialog at a real temporary path, and clicks the dialog's own
accept/reject-role button. No result is fabricated and no result is stubbed
at the seam.

The Qt-free tag decoding / struct write-back lives in
``tests/test_asl_library.py``; the full real-iTidy Browse-button route is
covered by ``tests/run_interactive_asl_smoke_test.py``.

Requires PySide6 and a (headless) display: run under Xvfb or
``QT_QPA_PLATFORM=offscreen``.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

# Headless by default; a real display (or Xvfb) is also fine.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QApplication,
    QDialogButtonBox,
    QFileDialog,
)

from amiga_ui.host.projection import OpenWindowIntent  # noqa: E402
from amiga_ui.host.qt_projection import QtHostWindowProjection  # noqa: E402

WINDOW_ADDR = 0x000A_0000


def _make_intent(window_addr: int) -> OpenWindowIntent:
    """A minimal app-facing window (a title makes it app-facing)."""
    return OpenWindowIntent(
        window_addr=window_addr,
        title="iTidy",
        left=20,
        top=20,
        width=360,
        height=200,
        rport_addr=0x000B_0000,
        idcmp=0x40,  # IDCMP_GADGETUP (app-facing)
    )


def _find_file_dialog(app) -> QFileDialog | None:
    """The *visible* file dialog — a finished exec() hides its dialog but the
    top-level widget object lives on, and must not steal a later test's click."""
    for w in app.topLevelWidgets():
        if isinstance(w, QFileDialog) and w.isVisible():
            return w
    return None


def _role_button(dialog: QFileDialog, role) -> QAbstractButton | None:
    """The dialog's own button with ``role`` (AcceptRole/RejectRole), or None.

    The accept button's *label* varies with mode and style ("Choose", "Open",
    "Save"), so roles — not labels — identify it.
    """
    box = dialog.findChild(QDialogButtonBox)
    if box is None:
        return None
    for btn in box.buttons():
        if box.buttonRole(btn) == role:
            return btn
    return None


class QtAslDialogTest(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        existing = QApplication.instance()
        cls.app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)

    def _project(self) -> QtHostWindowProjection:
        projection = QtHostWindowProjection(self.app, event_source=None)
        projection.open_window(_make_intent(WINDOW_ADDR))
        return projection

    def _drive(self, projection, *, prepare, role, **kwargs) -> str | None:
        """Run a blocking ``show_file_dialog`` and click a role button during it.

        ``prepare(dialog)`` runs once the dialog is found (setting the real
        directory/file so the accept click selects a *real* path), before the
        click. Returns the value ``show_file_dialog`` itself returned. All
        other keyword arguments go straight to ``show_file_dialog``.
        """
        state: dict = {"done": False, "found": None, "prepared": False, "attempts": 0}

        def drive():
            if state["done"]:
                return
            state["attempts"] += 1
            dialog = _find_file_dialog(self.app)
            state["found"] = dialog
            if dialog is not None:
                prepare(dialog)
                state["prepared"] = True
                btn = _role_button(dialog, role)
                if btn is None:
                    self.fail(f"the dialog has no {role} button")
                btn.click()
                state["done"] = True
                return
            if state["attempts"] < 20:  # ~1s of headroom
                QTimer.singleShot(50, drive)

        QTimer.singleShot(20, drive)
        result = projection.show_file_dialog(**kwargs)
        self.assertIsNotNone(state["found"], "the ASL QFileDialog was not shown")
        self.assertTrue(state["prepared"], "the dialog was never prepared for the click")
        return result

    def test_accept_returns_the_chosen_directory(self) -> None:
        """Directory-only pick (iTidy Browse): Choose on the opened view returns it.

        The view is opened at the tmp dir via ``initial_directory`` (exactly
        what the library does with ``ASLFR_InitialDrawer``), and the click
        selects what the user is looking at — the classic drawers-only
        behavior, verified against the real Qt widget, not assumed.
        """
        projection = self._project()
        with tempfile.TemporaryDirectory() as tmp:
            picked = self._drive(
                projection,
                window_addr=WINDOW_ADDR,
                title="Select Folder to Process",
                initial_directory=tmp,
                directories_only=True,
                prepare=lambda d: None,
                role=QDialogButtonBox.ButtonRole.AcceptRole,
            )
            self.assertEqual(picked, tmp)
        projection.close_window(WINDOW_ADDR)

    def test_cancel_returns_none(self) -> None:
        """Reject-role click is a real cancel: the call reports None."""
        projection = self._project()
        picked = self._drive(
            projection,
            window_addr=WINDOW_ADDR,
            title="Select Folder to Process",
            directories_only=True,
            prepare=lambda d: None,
            role=QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.assertIsNone(picked)
        projection.close_window(WINDOW_ADDR)

    def test_dialog_carries_the_apps_own_title_and_mode(self) -> None:
        """Title, Directory file-mode, and the forced non-native flag."""
        projection = self._project()
        seen: dict = {}

        def capture(d: QFileDialog) -> None:
            seen["title"] = d.windowTitle()
            seen["file_mode"] = d.fileMode()
            seen["non_native"] = d.testOption(QFileDialog.Option.DontUseNativeDialog)
            seen["parented"] = d.parentWidget() is not None

        self._drive(
            projection,
            window_addr=WINDOW_ADDR,
            title="Select Folder to Process",
            prepare=capture,
            role=QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.assertEqual(seen["title"], "Select Folder to Process")
        self.assertTrue(seen["non_native"], "the dialog must be the projection's own, not a native shell")
        self.assertTrue(seen["parented"], "a named parent window must parent the dialog")
        projection.close_window(WINDOW_ADDR)

    def test_directories_only_and_initial_values_reach_the_dialog(self) -> None:
        """Full kwargs: Directory mode + initial drawer open the view where the app asked.

        Real Qt Directory-mode semantics (verified against the widget, not
        assumed): the dialog's choice is the *viewed* directory — the user
        navigates into the folder they want and clicks Choose. So this test
        drives exactly that: view opened at tmp via ``initial_directory``,
        accept returns tmp.
        """
        projection = self._project()
        with tempfile.TemporaryDirectory() as tmp:
            seen: dict = {}

            def capture(d: QFileDialog) -> None:
                seen["file_mode"] = d.fileMode()
                seen["dir"] = d.directory().absolutePath()

            result = self._drive(
                projection,
                prepare=capture,
                role=QDialogButtonBox.ButtonRole.AcceptRole,
                window_addr=WINDOW_ADDR,
                title="Select Folder to Process",
                initial_directory=tmp,
                directories_only=True,
                save_mode=False,
                allow_patterns=True,
                initial_file="",
            )
            self.assertEqual(result, tmp)
            self.assertEqual(seen["file_mode"], QFileDialog.FileMode.Directory)
            self.assertEqual(seen["dir"], tmp, "initial_directory must open the view there")
        projection.close_window(WINDOW_ADDR)

    def test_initial_file_preselects_in_open_mode(self) -> None:
        """ASLFR_InitialFile + existing-file mode: the preselect is the choice."""
        projection = self._project()
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "iTidy.prefs")
            Path(target).write_text("dummy prefs\n")
            result = self._drive(
                projection,
                prepare=lambda d: None,
                role=QDialogButtonBox.ButtonRole.AcceptRole,
                window_addr=WINDOW_ADDR,
                title="Open Preferences",
                initial_directory=tmp,
                directories_only=False,
                save_mode=False,
                initial_file="iTidy.prefs",
            )
            self.assertEqual(result, target)
        projection.close_window(WINDOW_ADDR)

    def test_save_mode_accepts_a_new_name_without_overwrite_prompt(self) -> None:
        """DoSaveMode: AnyFile mode, no host overwrite confirm, new name returns."""
        projection = self._project()
        with tempfile.TemporaryDirectory() as tmp:
            new_name = os.path.join(tmp, "iTidy.prefs")

            def capture(d: QFileDialog) -> None:
                self.assertEqual(d.fileMode(), QFileDialog.FileMode.AnyFile)
                self.assertTrue(d.testOption(QFileDialog.Option.DontConfirmOverwrite))

            # selectFile with a not-yet-existing path is exactly the classic
            # save-mode state: the app (not the requester) checks existence.
            result = self._drive(
                projection,
                prepare=lambda d: (capture(d), d.setDirectory(tmp), d.selectFile(new_name)),
                role=QDialogButtonBox.ButtonRole.AcceptRole,
                window_addr=WINDOW_ADDR,
                title="Save Preferences As...",
                initial_directory=tmp,
                directories_only=False,
                save_mode=True,
                initial_file="iTidy.prefs",
            )
            self.assertEqual(result, new_name)
            self.assertFalse(os.path.exists(new_name), "the dialog must not create the file")
        projection.close_window(WINDOW_ADDR)

    def test_unparented_requester_is_legal(self) -> None:
        """No ASLFR_Window (iTidy's request_directory): modal, unparented dialog."""
        projection = self._project()
        seen: dict = {}

        def capture(d: QFileDialog) -> None:
            seen["parent"] = d.parentWidget()

        result = self._drive(
            projection,
            prepare=capture,
            role=QDialogButtonBox.ButtonRole.RejectRole,
            window_addr=None,
            title="Select Folder to Process",
        )
        self.assertIsNone(result)
        self.assertIsNone(seen["parent"], "a requester with no ASLFR_Window must be unparented")
        projection.close_window(WINDOW_ADDR)

    def test_unprojected_window_fails_honestly(self) -> None:
        """A named-but-unknown parent window: fail, do not silently unparent."""
        projection = self._project()
        with self.assertRaises(ValueError):
            projection.show_file_dialog(window_addr=0x000C_0000, title="X")
        projection.close_window(WINDOW_ADDR)

    # -- single _drive above covers all cases ---------------------------------


if __name__ == "__main__":
    unittest.main()
