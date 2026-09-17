"""Qt (offscreen) tests for the ASL file/directory dialog round trip."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog

from amiga_ui.host.projection import OpenWindowIntent
from amiga_ui.host.qt_projection import QtHostWindowProjection


WINDOW_ADDR = 0x000A_0000


def _make_intent():
    return OpenWindowIntent(
        window_addr=WINDOW_ADDR,
        title="iTidy",
        left=20, top=20, width=360, height=200,
        rport_addr=0x000B_0000, idcmp=0x40,
    )


def _find_dialog(app):
    for w in app.topLevelWidgets():
        if isinstance(w, QFileDialog):
            return w
    return None


class QtASLDialogTest(unittest.TestCase):
    app = None
    
    @classmethod
    def setUpClass(cls):
        existing = QApplication.instance()
        cls.app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)
    
    def _project(self):
        projection = QtHostWindowProjection(self.app, event_source=None)
        projection.open_window(_make_intent())
        return projection
    
    def test_directory_selection_shows_dialog(self):
        projection = self._project()
        dialog = _find_dialog(self.app)
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.fileMode(), QFileDialog.Directory)
        projection.close_window(WINDOW_ADDR)


if __name__ == "__main__":
    unittest.main()
