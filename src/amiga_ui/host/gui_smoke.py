"""Minimal Qt Widgets smoke test used by the CLI and shell wrapper."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel

from ..config import DEFAULT_SMOKE_GUI_DURATION_MS


def run_smoke_gui(duration_ms: int = DEFAULT_SMOKE_GUI_DURATION_MS) -> int:
    """Create a tiny window, print its details, and exit shortly after."""

    app = QApplication(sys.argv)

    label = QLabel("amiga-ui headless GUI smoke test")
    label.setWindowTitle("amiga-ui smoke test")
    label.resize(320, 120)
    label.show()
    app.processEvents()

    geometry = label.frameGeometry()
    screen = label.screen()
    screen_name = "unknown"
    screen_geometry = "unknown"
    if screen is not None:
        screen_name = screen.name()
        rect = screen.geometry()
        screen_geometry = f"{rect.width()}x{rect.height()}@({rect.x()},{rect.y()})"

    print("GUI smoke test window created:")
    print(f"- platform: {QGuiApplication.platformName()}")
    print(f"- display: {os.environ.get('DISPLAY', '<unset>')}")
    print(f"- qt_qpa_platform: {os.environ.get('QT_QPA_PLATFORM', '<unset>')}")
    print(f"- title: {label.windowTitle()}")
    print(f"- frame_geometry: {geometry.width()}x{geometry.height()}@({geometry.x()},{geometry.y()})")
    print(f"- visible: {label.isVisible()}")
    print(f"- screen: {screen_name}")
    print(f"- screen_geometry: {screen_geometry}")

    QTimer.singleShot(duration_ms, app.quit)
    return app.exec()
