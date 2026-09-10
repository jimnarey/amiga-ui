"""Qt tests for the GadTools gadget projection (widget half of the boundary).

Complements the Qt-free decode tests (``test_gadget_decode``) by driving the
*host* half with a synthetic :class:`OpenWindowIntent` (no iTidy, no display):
the projection must turn each projectable :class:`GadgetDescription` into the
right widget class at the right geometry with the right text / initial state,
overlay it on the RastPort surface (not remove the group-box rendering), keep
the surface replayable on refresh, and release *only* a closed window's widgets
on close.

Runs on the offscreen Qt platform (no X server).
"""

import os
import unittest
from dataclasses import replace

import shiboken6
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QPushButton

from amiga_ui.host.projection import (
    KIND_BUTTON,
    KIND_CHECKBOX,
    KIND_CYCLE,
    KIND_TEXT,
    GadgetDescription,
    OpenWindowIntent,
)
from amiga_ui.host.qt_projection import QtHostWindowProjection
from amiga_ui.vamos.rastport_state import RastPortRegistry

_QAPP: QApplication | None = None


def _app() -> QApplication:
    global _QAPP
    if _QAPP is not None:
        return _QAPP
    previous = os.environ.get("QT_QPA_PLATFORM")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    _QAPP = app if isinstance(app, QApplication) else QApplication([])
    if previous is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = previous
    return _QAPP


# Construct at import so every widget test can build widgets without an X server.
_app()


def _intent(gadgets=(), **overrides) -> OpenWindowIntent:
    base = OpenWindowIntent(
        window_addr=0x1000,
        title="Test Window",
        left=50,
        top=30,
        width=400,
        height=240,
        rport_addr=0x2000,
        gadgets=tuple(gadgets),
    )
    return replace(base, **overrides)


def _desc(**overrides) -> GadgetDescription:
    base = GadgetDescription(
        gadget_addr=0x0,
        gadget_id=0,
        kind_name=KIND_BUTTON,
        kind=1,
        left=10,
        top=10,
        width=90,
        height=14,
        label="Button",
    )
    return replace(base, **overrides)


class GadgetWidgetClassTest(unittest.TestCase):
    """Each projectable kind maps to the documented widget class."""

    def _classes(self, gadgets) -> list[str]:
        app = _app()
        proj = QtHostWindowProjection(app)
        proj.open_window(_intent(gadgets=gadgets))
        window = proj.host_window(0x1000)
        assert window is not None
        return [type(w).__name__ for w in proj.windows[0x1000].gadget_widgets]

    def test_button_is_push_button(self) -> None:
        self.assertEqual(self._classes([_desc(kind_name=KIND_BUTTON)]), ["QPushButton"])

    def test_checkbox_is_qcheckbox(self) -> None:
        self.assertEqual(self._classes([_desc(kind_name=KIND_CHECKBOX)]), ["QCheckBox"])

    def test_cycle_is_combobox_with_caption(self) -> None:
        self.assertEqual(
            self._classes([_desc(kind_name=KIND_CYCLE, label="Opt:")]),
            ["QComboBox", "QLabel"],
        )

    def test_text_is_label(self) -> None:
        self.assertEqual(self._classes([_desc(kind_name=KIND_TEXT)]), ["QLabel"])

    def test_non_projectable_kind_builds_nothing(self) -> None:
        self.assertEqual(self._classes([_desc(kind_name="context")]), [])


class GadgetWidgetGeometryTest(unittest.TestCase):
    def test_widget_sits_at_gadget_geometry(self) -> None:
        app = _app()
        proj = QtHostWindowProjection(app)
        desc = _desc(kind_name=KIND_BUTTON, left=33, top=44, width=80, height=16)
        proj.open_window(_intent(gadgets=[desc]))
        window = proj.host_window(0x1000)
        assert window is not None
        (button,) = proj.windows[0x1000].gadget_widgets
        self.assertEqual(button.geometry().x(), 33)
        self.assertEqual(button.geometry().y(), 44)
        self.assertEqual(button.geometry().width(), 80)
        self.assertEqual(button.geometry().height(), 16)
        # The gadget widget is a direct child of the host window (an overlay on
        # the surface), not in the window's layout.
        self.assertIs(button.parent(), window)


class GadgetWidgetTextAndStateTest(unittest.TestCase):
    """Widget text and initial state, per kind.

    ``_widget`` returns ``(host_window, widgets)``: the host window reference is
    kept alive for the duration of the assertion so the throwaway projection's
    garbage collection cannot delete the C++ window (and its child widgets)
    mid-test.
    """

    def _widget(self, desc):
        app = _app()
        proj = QtHostWindowProjection(app)
        proj.open_window(_intent(gadgets=[desc]))
        window = proj.host_window(0x1000)
        assert window is not None
        return window, proj.windows[0x1000].gadget_widgets

    def test_button_text_is_label(self) -> None:
        _, (button,) = self._widget(_desc(kind_name=KIND_BUTTON, label="Save"))
        assert isinstance(button, QPushButton)
        self.assertEqual(button.text(), "Save")

    def test_checkbox_text_and_checked_state(self) -> None:
        _, (box,) = self._widget(_desc(kind_name=KIND_CHECKBOX, label="Enable", checked=True))
        assert isinstance(box, QCheckBox)
        self.assertEqual(box.text(), "Enable")
        self.assertTrue(box.isChecked())

        _, (box_off,) = self._widget(_desc(kind_name=KIND_CHECKBOX, label="Disable", checked=False))
        assert isinstance(box_off, QCheckBox)
        self.assertFalse(box_off.isChecked())

    def test_cycle_items_and_active_index(self) -> None:
        _, (combo, caption) = self._widget(
            _desc(
                kind_name=KIND_CYCLE,
                label="Sort:",
                cycle_labels=("Name", "Type", "Date", "Size"),
                cycle_active=2,
            )
        )
        assert isinstance(combo, QComboBox)
        self.assertEqual(combo.count(), 4)
        self.assertEqual([combo.itemText(i) for i in range(4)], ["Name", "Type", "Date", "Size"])
        self.assertEqual(combo.currentIndex(), 2)
        self.assertEqual(combo.currentText(), "Date")
        assert isinstance(caption, QLabel)
        self.assertEqual(caption.text(), "Sort:")

    def test_text_widget_shows_display_text_when_present(self) -> None:
        _, (label,) = self._widget(_desc(kind_name=KIND_TEXT, label="Folder:", text="/tmp/SYS"))
        assert isinstance(label, QLabel)
        self.assertEqual(label.text(), "/tmp/SYS")

    def test_text_widget_falls_back_to_label_when_text_empty(self) -> None:
        # The real folder caption: GTTX_Text is "" so the QLabel shows the label.
        _, (label,) = self._widget(_desc(kind_name=KIND_TEXT, label="Folder:", text=""))
        assert isinstance(label, QLabel)
        self.assertEqual(label.text(), "Folder:")

    def test_disabled_gadget_widget_is_disabled(self) -> None:
        _, (button,) = self._widget(_desc(kind_name=KIND_BUTTON, label="Locked", enabled=False))
        self.assertFalse(button.isEnabled())


class GadgetOverlayAndRefreshTest(unittest.TestCase):
    """The gadgets overlay the RastPort surface; the surface keeps rendering."""

    def test_gadgets_overlay_surface_without_removal(self) -> None:
        app = _app()
        registry = RastPortRegistry()
        rp = 0x2000
        registry.get_or_create(rp).draw_bevel_box(left=15, top=20, width=200, height=120)
        proj = QtHostWindowProjection(app)
        proj.bind_registry(registry)
        intent = _intent(
            rport_addr=rp,
            gadgets=[_desc(kind_name=KIND_BUTTON, label="Browse...", left=300, top=30, width=90, height=14)],
        )
        proj.open_window(intent)
        window = proj.host_window(0x1000)
        assert window is not None
        # The surface is still present and carries the group-box bevel op.
        self.assertIsNotNone(window.surface)
        proj.refresh_window(0x1000)
        state = window.surface.state()
        assert state is not None
        self.assertEqual(state.ops[-1]["op"], "DrawBevelBox")
        # The gadget widget is a live child of the window (an overlay).
        (button,) = proj.windows[0x1000].gadget_widgets
        self.assertIs(button.parent(), window)
        self.assertTrue(shiboken6.isValid(button))

    def test_refresh_does_not_disturb_gadget_widgets(self) -> None:
        app = _app()
        registry = RastPortRegistry()
        rp = 0x2000
        registry.get_or_create(rp).draw_bevel_box(left=5, top=5, width=50, height=30)
        proj = QtHostWindowProjection(app)
        proj.bind_registry(registry)
        intent = _intent(rport_addr=rp, gadgets=[_desc(kind_name=KIND_BUTTON, label="A")])
        proj.open_window(intent)
        button = proj.windows[0x1000].gadget_widgets[0]
        assert isinstance(button, QPushButton)
        pos = button.geometry()
        proj.refresh_window(0x1000)
        proj.refresh_window(0x1000)
        self.assertEqual(button.geometry(), pos)
        self.assertEqual(button.text(), "A")


class GadgetPerWindowCloseTest(unittest.TestCase):
    """Closing one window releases only that window's widgets and projection."""

    def test_close_releases_only_its_own_widgets(self) -> None:
        app = _app()
        proj = QtHostWindowProjection(app)
        intent_a = _intent(window_addr=0xA000, rport_addr=0x2000, gadgets=[_desc(kind_name=KIND_BUTTON, label="A")])
        intent_b = _intent(window_addr=0xB000, rport_addr=0x2100, gadgets=[_desc(kind_name=KIND_CHECKBOX, label="B")])
        proj.open_window(intent_a)
        proj.open_window(intent_b)
        host_a = proj.host_window(0xA000)
        host_b = proj.host_window(0xB000)
        box_b = proj.windows[0xB000].gadget_widgets[0]
        assert isinstance(box_b, QCheckBox)
        assert host_a is not None and host_b is not None
        self.assertTrue(host_a.isVisible())
        self.assertTrue(host_b.isVisible())

        proj.close_window(0xA000)
        app.processEvents()

        # Window A's projection association is removed, its host window closed,
        # and the projection no longer references its widget (the _ProjectedWindow
        # was popped, so its gadget_widgets list is gone with it).
        self.assertNotIn(0xA000, proj.windows)
        self.assertIsNone(proj.host_window(0xA000))
        self.assertFalse(host_a.isVisible())
        # Window B is untouched: still projected, host window alive and visible,
        # and its widget still valid with the right text.
        self.assertIn(0xB000, proj.windows)
        self.assertIs(proj.host_window(0xB000), host_b)
        self.assertTrue(host_b.isVisible())
        self.assertTrue(shiboken6.isValid(box_b))
        self.assertEqual(box_b.text(), "B")

    def test_double_close_is_idempotent(self) -> None:
        app = _app()
        proj = QtHostWindowProjection(app)
        proj.open_window(_intent(gadgets=[_desc(kind_name=KIND_BUTTON, label="A")]))
        proj.close_window(0x1000)
        proj.close_window(0x1000)  # second close: no exception, still empty
        app.processEvents()
        self.assertNotIn(0x1000, proj.windows)
        self.assertEqual(len(proj.windows), 0)


if __name__ == "__main__":
    unittest.main()
