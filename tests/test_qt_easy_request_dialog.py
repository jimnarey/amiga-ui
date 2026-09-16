"""Qt (offscreen) tests for the EasyRequestArgs host dialog round trip.

These are the *widget-level* tests for the QMessageBox half of
``EasyRequestArgs`` (LVO 588): the projection must show a real, *blocking*
:class:`QMessageBox` parented to the app's host window, carrying the app's own
title, body text and button labels, and return the index of the button the user
actually clicked. The click is driven the same way the interactive smoke tests
drive real widgets (a :class:`QTimer` that fires during ``exec()``'s nested
event loop), so no result is fabricated.

The Qt-free decode / result-code mapping lives in
``tests/test_easy_request_args.py``; the full real-iTidy LHA-not-found route is
covered by ``tests/run_interactive_lha_smoke_test.py``.

Requires PySide6 and a (headless) display: run under Xvfb or
``QT_QPA_PLATFORM=offscreen``.
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import ClassVar

# Headless by default; a real display (or Xvfb) is also fine.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton  # noqa: E402

from amiga_ui.host.projection import OpenWindowIntent  # noqa: E402
from amiga_ui.host.qt_projection import QtHostWindowProjection  # noqa: E402

WINDOW_ADDR = 0x000A_0000
TITLE = "LHA Not Found"
BODY = "LHA archiver not found in C:, SYS:C/, or SYS:Tools/.\nContinue without backups?"
BUTTONS = ["Continue", "Cancel"]


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


def _find_message_box(app) -> QMessageBox | None:
    """The EasyRequest dialog is a top-level widget (a dialog is), even parented."""
    for w in app.topLevelWidgets():
        if isinstance(w, QMessageBox):
            return w
    return None


def _click_button(box, label: str) -> bool:
    for btn in box.buttons():
        if isinstance(btn, QPushButton) and btn.text() == label:
            btn.click()
            return True
    return False


class QtEasyRequestDialogTest(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        existing = QApplication.instance()
        cls.app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)

    def _project(self) -> QtHostWindowProjection:
        projection = QtHostWindowProjection(self.app, event_source=None)
        projection.open_window(_make_intent(WINDOW_ADDR))
        return projection

    def _show_and_click(self, projection, label: str) -> int:
        """Drive a real click on ``label`` during ``show_easy_request``'s blocking
        ``exec()`` and return the index the call reports.

        The click is posted by a :class:`QTimer` that polls for the dialog (the
        dialog is created synchronously before ``exec()``, so it is found on the
        first poll) and clicks the named button — the same real-widget driving
        the interactive smoke tests use.
        """
        state: dict = {"clicked": False, "found": None, "attempts": 0}

        def click():
            if state["clicked"]:
                return
            state["attempts"] += 1
            box = _find_message_box(self.app)
            state["found"] = box
            if box is not None:
                state["clicked"] = _click_button(box, label)
                return
            if state["attempts"] < 20:  # ~1s of headroom
                QTimer.singleShot(50, click)

        QTimer.singleShot(20, click)
        index = projection.show_easy_request(WINDOW_ADDR, TITLE, BODY, BUTTONS)
        self.assertIsNotNone(state["found"], "the EasyRequest QMessageBox was not shown")
        self.assertTrue(state["clicked"], f"button {label!r} not found on the dialog")
        return index

    def test_continue_returns_index_zero(self) -> None:
        projection = self._project()
        self.assertEqual(self._show_and_click(projection, "Continue"), 0)
        projection.close_window(WINDOW_ADDR)

    def test_cancel_returns_index_one(self) -> None:
        projection = self._project()
        self.assertEqual(self._show_and_click(projection, "Cancel"), 1)
        projection.close_window(WINDOW_ADDR)

    def test_dialog_shows_apps_own_labels(self) -> None:
        projection = self._project()
        seen: dict = {}

        def capture_and_click():
            box = _find_message_box(self.app)
            if box is None:
                self.fail("the EasyRequest QMessageBox was not shown")
            seen["title"] = box.windowTitle()
            seen["text"] = box.text()
            seen["buttons"] = sorted(b.text() for b in box.buttons() if isinstance(b, QPushButton))
            seen["parented"] = box.parentWidget() is not None
            _click_button(box, "Cancel")

        QTimer.singleShot(40, capture_and_click)
        projection.show_easy_request(WINDOW_ADDR, TITLE, BODY, BUTTONS)
        self.assertEqual(seen["title"], TITLE)
        self.assertEqual(seen["text"], BODY)
        self.assertEqual(seen["buttons"], sorted(BUTTONS))
        self.assertTrue(seen["parented"], "the dialog is not parented to the host window")
        projection.close_window(WINDOW_ADDR)

    def test_missing_window_fails_honestly(self) -> None:
        projection = self._project()
        # A window the projection does not have: the dialog cannot be parented,
        # so the call fails rather than showing an unparented top-level.
        with self.assertRaises(ValueError):
            projection.show_easy_request(0x000C_0000, "X", "Y", ["OK"])
        projection.close_window(WINDOW_ADDR)


if __name__ == "__main__":
    unittest.main()
