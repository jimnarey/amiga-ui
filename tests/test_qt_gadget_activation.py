"""Qt (offscreen) tests for the projected-gadget activation seam.

These are the *widget-level* tests for the interactive route:

- a projected BUTTON (:class:`QtGadgetButton`) records its real Amiga window /
  gadget addresses (identity keys, never dereferenced by the host),
- a click on the projected button is wired (address-based, generically) through
  the projection to the event bridge's ``gadget_up`` — the semantic path
  (``gadget_up`` -> real IntuiMessage on the real UserPort -> notify) is covered
  in ``tests/test_event_bridge.py``, and the full real-iTidy Exit route is
  covered by ``tests/run_interactive_exit_smoke_test.py``.

It also verifies the low-level Amiga library implementations stay Qt-free
(headless-safe): importing them in a clean subprocess never pulls in PySide6.

Requires PySide6 and a (headless) display: run under Xvfb or
``QT_QPA_PLATFORM=offscreen``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from typing import ClassVar

# Headless by default; a real display (or Xvfb) is also fine.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from amiga_ui.config import PROJECT_ROOT  # noqa: E402
from amiga_ui.host.projection import (  # noqa: E402
    GadgetDescription,
    KIND_BUTTON,
    OpenWindowIntent,
)
from amiga_ui.host.qt_projection import QtGadgetButton, QtHostWindowProjection  # noqa: E402

WINDOW_ADDR = 0x000A0000
GADGET_ADDR = 0x000C0000


def _make_button_intent(window_addr: int, gadget_addr: int, label: str = "Exit") -> OpenWindowIntent:
    return OpenWindowIntent(
        window_addr=window_addr,
        title="Test Window",
        left=20,
        top=20,
        width=320,
        height=120,
        rport_addr=0x000B0000,
        idcmp=0x40,  # IDCMP_GADGETUP
        has_menu_strip=False,
        gadgets=(
            GadgetDescription(
                gadget_addr=gadget_addr,
                gadget_id=1,
                kind_name=KIND_BUTTON,
                kind=1,
                left=10,
                top=10,
                width=60,
                height=22,
                label=label,
            ),
        ),
    )


class _FakeBridge:
    """Records the address-based ``gadget_up`` calls the projection routes to it."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def gadget_up(self, window_addr: int, gadget_addr: int, **kwargs) -> None:
        self.calls.append((window_addr, gadget_addr, kwargs))


class QtGadgetButtonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app = QApplication.instance()
        cls.app = app if isinstance(app, QApplication) else QApplication(sys.argv)

    def test_button_records_amiga_addresses(self) -> None:
        button = QtGadgetButton("Exit", WINDOW_ADDR, GADGET_ADDR)
        self.assertEqual(button.amiga_window_addr, WINDOW_ADDR)
        self.assertEqual(button.amiga_gadget_addr, GADGET_ADDR)
        self.assertEqual(button.text(), "Exit")
        self.assertIsInstance(button, QPushButton)


class QtProjectionActivationTest(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        existing = QApplication.instance()
        cls.app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)

    def _project(self, bridge, hook=None):
        projection = QtHostWindowProjection(self.app, event_source=bridge, window_projected_hook=hook)
        projection.open_window(_make_button_intent(WINDOW_ADDR, GADGET_ADDR))
        return projection

    def _button(self, projection) -> QtGadgetButton:
        pw = next(iter(projection.windows.values()))
        return next(w for w in pw.gadget_widgets if isinstance(w, QtGadgetButton))

    def test_open_window_builds_address_recording_button(self) -> None:
        projection = self._project(_FakeBridge())
        self.assertEqual(len(projection.windows), 1)
        button = self._button(projection)
        self.assertEqual(button.amiga_window_addr, WINDOW_ADDR)
        self.assertEqual(button.amiga_gadget_addr, GADGET_ADDR)
        self.assertEqual(button.text(), "Exit")
        projection.close_window(WINDOW_ADDR)

    def test_button_click_routes_to_bridge_with_real_addresses(self) -> None:
        bridge = _FakeBridge()
        projection = self._project(bridge)
        self._button(projection).click()  # a real Qt click (emits ``clicked``)
        # The generic, address-based activation: the bridge gets the button's
        # recorded real Amiga window + gadget addresses.
        self.assertEqual(bridge.calls, [(WINDOW_ADDR, GADGET_ADDR, {})])
        projection.close_window(WINDOW_ADDR)

    def test_window_projected_hook_is_called_with_window_addr(self) -> None:
        seen: list[int] = []
        self._project(_FakeBridge(), hook=lambda addr: seen.append(addr))
        self.assertEqual(seen, [WINDOW_ADDR])

    def test_button_without_event_source_is_display_only(self) -> None:
        projection = QtHostWindowProjection(self.app, event_source=None)
        projection.open_window(_make_button_intent(WINDOW_ADDR, GADGET_ADDR))
        button = self._button(projection)
        button.click()  # no bridge wired: must not raise
        projection.close_window(WINDOW_ADDR)


class VamosQtFreeTest(unittest.TestCase):
    """The low-level Amiga library implementations stay Qt-free (headless-safe).

    Importing the vamos compatibility layer in a clean process must never pull
    in PySide6/shiboken6 — this is what keeps plain (non-GUI) probes
    display-free. Checked in a subprocess so the current process's Qt import
    (from the projection tests above) does not contaminate the result.
    """

    def test_vamos_import_graph_is_qt_free_in_subprocess(self) -> None:
        code = (
            "import sys\n"
            "import amiga_ui.vamos.exec_library\n"
            "import amiga_ui.vamos.event_bridge\n"
            "import amiga_ui.vamos.intuition_library\n"
            "import amiga_ui.vamos.gadtools_library\n"
            "import amiga_ui.vamos.launcher\n"
            "loaded = any(m.startswith(('PySide6', 'shiboken6')) for m in sys.modules)\n"
            "print('QT_LOADED=' + str(loaded))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self.assertIn(
            "QT_LOADED=False",
            completed.stdout,
            msg=f"stdout={completed.stdout!r} stderr={completed.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
