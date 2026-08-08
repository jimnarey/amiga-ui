"""Minimal PySide6 GUI smoke test for the headless display wrapper."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel


def _print_window_summary(label: QLabel) -> None:
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
    print(
        "- frame_geometry: "
        f"{geometry.width()}x{geometry.height()}@({geometry.x()},{geometry.y()})"
    )
    print(f"- visible: {label.isVisible()}")
    print(f"- screen: {screen_name}")
    print(f"- screen_geometry: {screen_geometry}")


def main() -> int:
    app = QApplication(sys.argv)

    label = QLabel("amiga-ui headless GUI smoke test")
    label.setWindowTitle("amiga-ui smoke test")
    label.resize(320, 120)
    label.show()
    app.processEvents()
    _print_window_summary(label)

    QTimer.singleShot(250, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
