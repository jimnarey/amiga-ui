"""Qt (offscreen) tests for the projected menu strip: ``QMenuBar`` -> ``IDCMP_MENUPICK``.

These are the *widget-level* tests for the interactive menu route, the mirror of
``tests/test_qt_gadget_activation.py``:

- ``set_menu_strip`` builds a real, **non-native** ``QMenuBar`` inside the host
  window from the immutable ``MenuStripDescription`` — titles, entry order,
  separators, and nested sub-menus all come from what the app created;
- each selectable entry becomes a :class:`QtMenuAction` that records the real
  ``struct Window *``, the packed ``MenuNumber`` and the real ``MenuItem *``
  (identity keys, never dereferenced by the host);
- activating an action is routed (address-based, generically) to the event
  bridge's ``menu_pick``; the semantic path (``menu_pick`` -> real
  ``IntuiMessage`` with ``Code`` on the real ``UserPort`` -> notify) is covered
  in ``tests/test_event_bridge.py``, and the round trip back to the app's own
  item (``ItemAddress(strip, Code)``) in ``tests/test_menu_strip_path.py``;
- a window without a strip gets no menu bar, and detaching removes it.

Requires PySide6 and a (headless) display: run under Xvfb or
``QT_QPA_PLATFORM=offscreen``.
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import ClassVar

# Headless by default; a real display (or Xvfb) is also fine. Restored in
# ``tearDownModule`` so this module does not change what later test modules see.
_saved_qt_platform = os.environ.get("QT_QPA_PLATFORM")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def tearDownModule() -> None:
    """Undo the ``QT_QPA_PLATFORM`` this module set for its own Qt widgets."""

    if _saved_qt_platform is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = _saved_qt_platform


from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QMenu,
    QMenuBar,
    QVBoxLayout,
    QWidget,
)

from amiga_ui.host.projection import (  # noqa: E402
    MenuEntryDescription,
    MenuStripDescription,
    MenuTitleDescription,
    OpenWindowIntent,
)
from amiga_ui.host.qt_projection import (  # noqa: E402
    AmigaHostWindow,
    QtHostWindowProjection,
    QtMenuAction,
)
from amiga_ui.vamos.menu_state import pack_menu_number  # noqa: E402

WINDOW_ADDR = 0x000A0000
IDCMP_MENUPICK = 0x00000100


def _entry(item_addr: int, menu_index: int, item_index: int, label: str, item_data: int = 0) -> MenuEntryDescription:
    return MenuEntryDescription(
        item_addr=item_addr,
        code=pack_menu_number(menu_index, item_index),
        label=label,
        item_data=item_data,
    )


def _project_menu(entries: list[MenuEntryDescription], titles: tuple[str, ...] = ("Project",)) -> MenuStripDescription:
    menus = tuple(MenuTitleDescription(title, tuple(entries)) for title in titles)
    return MenuStripDescription(strip_addr=0x000C0000, menus=menus, entry_count=len(entries))


def _itidy_like_strip() -> MenuStripDescription:
    """The iTidy Project menu as the projection receives it (bars included)."""

    entries = [
        _entry(0x200, 0, 0, "New", 1001),
        _entry(0x226, 0, 1, "Open...", 1002),
        MenuEntryDescription(0x24C, pack_menu_number(0, 2), is_separator=True),
        _entry(0x272, 0, 3, "Save", 1003),
        _entry(0x298, 0, 4, "Save as...", 1004),
        MenuEntryDescription(0x2BE, pack_menu_number(0, 5), is_separator=True),
        _entry(0x2E4, 0, 6, "About...", 1006),
        MenuEntryDescription(0x30A, pack_menu_number(0, 7), is_separator=True),
        _entry(0x330, 0, 8, "Close", 1005),
    ]
    return _project_menu(entries)


def _intent(has_menu_strip: bool = False) -> OpenWindowIntent:
    return OpenWindowIntent(
        window_addr=WINDOW_ADDR,
        title="iTidy v3.0 - Icon Cleanup Tool",
        left=20,
        top=20,
        width=640,
        height=400,
        rport_addr=0x000B0000,
        idcmp=IDCMP_MENUPICK,
        has_menu_strip=has_menu_strip,
    )


class _FakeBridge:
    """Records the address-based ``menu_pick`` calls the projection routes to it."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def menu_pick(self, window_addr: int, code: int, **kwargs) -> None:
        self.calls.append((window_addr, code, kwargs))


class QtMenuStripTestBase(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        existing = QApplication.instance()
        cls.app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)

    def _projection(self, bridge=None) -> QtHostWindowProjection:
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())
        self.addCleanup(projection.close_window, WINDOW_ADDR)
        return projection

    def _bar(self, projection: QtHostWindowProjection) -> QMenuBar:
        window = projection.host_window(WINDOW_ADDR)
        self.assertIsInstance(window, AmigaHostWindow)
        assert window is not None
        self.assertIsInstance(window.menu_bar, QMenuBar)
        return window.menu_bar

    @staticmethod
    def _title_menu(bar: QMenuBar, index: int = 0) -> QMenu:
        menu = bar.actions()[index].menu()
        assert isinstance(menu, QMenu)
        return menu

    @staticmethod
    def _submenu(action) -> QMenu:
        menu = action.menu()
        assert isinstance(menu, QMenu)
        return menu


class MenuBarProjectionTests(QtMenuStripTestBase):
    def test_window_without_strip_has_no_menu_bar(self) -> None:
        projection = self._projection(_FakeBridge())
        window = projection.host_window(WINDOW_ADDR)
        assert window is not None
        self.assertIsNone(window.menu_bar, "no strip attached: no host menu bar")

    def test_set_menu_strip_builds_a_non_native_bar(self) -> None:
        projection = self._projection(_FakeBridge())
        projection.set_menu_strip(WINDOW_ADDR, _itidy_like_strip())
        bar = self._bar(projection)
        self.assertFalse(bar.isNativeMenuBar(), "the strip belongs to the window, never the host app menu")
        self.assertEqual([action.text() for action in bar.actions()], ["Project"])

    def test_bar_is_a_child_of_the_window_above_its_content(self) -> None:
        projection = self._projection(_FakeBridge())
        projection.set_menu_strip(WINDOW_ADDR, _itidy_like_strip())
        window = projection.host_window(WINDOW_ADDR)
        assert window is not None
        layout = window.layout()
        self.assertIsInstance(layout, QVBoxLayout)
        assert layout is not None
        bar_item, content_item = layout.itemAt(0), layout.itemAt(1)
        assert bar_item is not None and content_item is not None
        self.assertIsInstance(bar_item.widget(), QMenuBar, "the bar sits above the window content")
        self.assertIsInstance(content_item.widget(), QWidget)

    def test_entries_keep_order_labels_and_separators(self) -> None:
        projection = self._projection(_FakeBridge())
        projection.set_menu_strip(WINDOW_ADDR, _itidy_like_strip())
        menu = self._title_menu(self._bar(projection))
        actions = menu.actions()
        self.assertEqual(len(actions), 9, "one widget action per chain slot")
        self.assertEqual(
            [action.isSeparator() for action in actions],
            [False, False, True, False, False, True, False, True, False],
        )
        self.assertEqual(
            [action.text() for action in actions if not action.isSeparator()],
            ["New", "Open...", "Save", "Save as...", "About...", "Close"],
        )

    def test_actions_record_the_real_addresses_and_packed_code(self) -> None:
        strip = _itidy_like_strip()
        projection = self._projection(_FakeBridge())
        projection.set_menu_strip(WINDOW_ADDR, strip)
        menu = self._title_menu(self._bar(projection))
        by_label = {a.text(): a for a in menu.actions() if isinstance(a, QtMenuAction)}
        for entry in strip.menus[0].items:
            if not entry.is_selectable:
                continue
            with self.subTest(label=entry.label):
                action = by_label[entry.label]
                self.assertEqual(action.amiga_window_addr, WINDOW_ADDR)
                self.assertEqual(action.amiga_menu_code, entry.code)
                self.assertEqual(action.amiga_item_addr, entry.item_addr)

    def test_separators_are_not_triggerable_actions(self) -> None:
        projection = self._projection(_FakeBridge())
        projection.set_menu_strip(WINDOW_ADDR, _itidy_like_strip())
        menu = self._title_menu(self._bar(projection))
        self.assertEqual(len([a for a in menu.actions() if isinstance(a, QtMenuAction)]), 6)
        self.assertTrue(all(a.isSeparator() for a in menu.actions() if not isinstance(a, QtMenuAction)))

    def test_setting_the_intent_flag(self) -> None:
        projection = self._projection(_FakeBridge())
        projected = projection.windows[WINDOW_ADDR]
        self.assertFalse(projected.intent.has_menu_strip)
        projection.set_menu_strip(WINDOW_ADDR, _itidy_like_strip())
        self.assertTrue(projected.intent.has_menu_strip)
        projection.clear_menu_strip(WINDOW_ADDR)
        self.assertFalse(projected.intent.has_menu_strip)

    def test_ampersand_in_a_label_is_not_a_mnemonic(self) -> None:
        projection = self._projection(_FakeBridge())
        projection.set_menu_strip(WINDOW_ADDR, _project_menu([_entry(0x200, 0, 0, "Save & Close")]))
        menu = self._title_menu(self._bar(projection))
        self.assertEqual(menu.actions()[0].text(), "Save && Close", "a classic label's & renders literally")


class MenuPickActivationTests(QtMenuStripTestBase):
    def test_activating_an_action_routes_to_bridge_menu_pick(self) -> None:
        strip = _itidy_like_strip()
        bridge = _FakeBridge()
        projection = self._projection(bridge)
        projection.set_menu_strip(WINDOW_ADDR, strip)
        menu = self._title_menu(self._bar(projection))
        close = next(a for a in menu.actions() if isinstance(a, QtMenuAction) and a.text() == "Close")

        close.trigger()  # a real Qt activation (emits ``triggered``)

        self.assertEqual(len(bridge.calls), 1)
        window_addr, code, kwargs = bridge.calls[0]
        self.assertEqual(window_addr, WINDOW_ADDR)
        self.assertEqual(code, pack_menu_number(0, 8), "the packed MenuNumber, not a label")
        self.assertEqual(kwargs, {})

    def test_every_action_carries_its_own_code(self) -> None:
        strip = _itidy_like_strip()
        bridge = _FakeBridge()
        projection = self._projection(bridge)
        projection.set_menu_strip(WINDOW_ADDR, strip)
        menu = self._title_menu(self._bar(projection))
        actions = [a for a in menu.actions() if isinstance(a, QtMenuAction)]
        for action in actions:
            action.trigger()
        self.assertEqual(
            [call[1] for call in bridge.calls],
            [entry.code for entry in strip.menus[0].items if entry.is_selectable],
        )
        self.assertTrue(all(call[0] == WINDOW_ADDR for call in bridge.calls))

    def test_without_event_source_the_bar_is_display_only(self) -> None:
        projection = self._projection(None)
        projection.set_menu_strip(WINDOW_ADDR, _itidy_like_strip())
        menu = self._title_menu(self._bar(projection))
        next(a for a in menu.actions() if isinstance(a, QtMenuAction)).trigger()  # must not raise

    def test_pick_after_close_is_not_routed(self) -> None:
        bridge = _FakeBridge()
        projection = self._projection(bridge)
        projection.set_menu_strip(WINDOW_ADDR, _itidy_like_strip())
        self.assertTrue(any(isinstance(a, QtMenuAction) for a in self._title_menu(self._bar(projection)).actions()))
        projection.close_window(WINDOW_ADDR)
        self.assertEqual(bridge.calls, [], "the bar dies with the window: nothing is left to route a pick")


class SubMenuProjectionTests(QtMenuStripTestBase):
    def _strip_with_subs(self) -> MenuStripDescription:
        parent = MenuEntryDescription(
            item_addr=0x200,
            code=pack_menu_number(0, 0),
            label="Tidy",
            sub_items=(
                MenuEntryDescription(0x226, pack_menu_number(0, 0, 0), label="Clean HTML"),
                MenuEntryDescription(0x24C, pack_menu_number(0, 0, 1), label="Check Links"),
            ),
        )
        return _project_menu([parent, _entry(0x272, 0, 1, "Quit")])

    def test_parent_entry_becomes_a_nested_menu(self) -> None:
        projection = self._projection(_FakeBridge())
        projection.set_menu_strip(WINDOW_ADDR, self._strip_with_subs())
        menu = self._title_menu(self._bar(projection))
        parent = menu.actions()[0]
        self.assertIsInstance(self._submenu(parent), QMenu)
        self.assertEqual([a.text() for a in self._submenu(parent).actions()], ["Clean HTML", "Check Links"])

    def test_sub_items_are_picked_by_their_own_codes(self) -> None:
        strip = self._strip_with_subs()
        bridge = _FakeBridge()
        projection = self._projection(bridge)
        projection.set_menu_strip(WINDOW_ADDR, strip)
        sub_menu = self._submenu(self._title_menu(self._bar(projection)).actions()[0])
        subs = {a.text(): a for a in sub_menu.actions() if isinstance(a, QtMenuAction)}
        for sub in strip.menus[0].items[0].sub_items:
            with self.subTest(label=sub.label):
                self.assertEqual(subs[sub.label].amiga_menu_code, sub.code)
                subs[sub.label].trigger()
        self.assertEqual([call[1] for call in bridge.calls], [sub.code for sub in strip.menus[0].items[0].sub_items])

    def test_parent_is_not_itself_a_pick(self) -> None:
        bridge = _FakeBridge()
        projection = self._projection(bridge)
        projection.set_menu_strip(WINDOW_ADDR, self._strip_with_subs())
        menu = self._title_menu(self._bar(projection))
        self.assertFalse(any(isinstance(a, QtMenuAction) for a in menu.actions()[:1]), "Intuition opens the sub-menu")


class MenuStripDetachmentTests(QtMenuStripTestBase):
    def test_clear_menu_strip_removes_the_bar(self) -> None:
        projection = self._projection(_FakeBridge())
        projection.set_menu_strip(WINDOW_ADDR, _itidy_like_strip())
        projection.clear_menu_strip(WINDOW_ADDR)
        window = projection.host_window(WINDOW_ADDR)
        assert window is not None
        self.assertIsNone(window.menu_bar)
        self.assertEqual([w for w in window.findChildren(QMenuBar)], [])

    def test_clear_is_idempotent_and_safe_without_a_strip(self) -> None:
        projection = self._projection(_FakeBridge())
        projection.clear_menu_strip(WINDOW_ADDR)
        projection.set_menu_strip(WINDOW_ADDR, _itidy_like_strip())
        projection.clear_menu_strip(WINDOW_ADDR)
        projection.clear_menu_strip(WINDOW_ADDR)
        window = projection.host_window(WINDOW_ADDR)
        assert window is not None
        self.assertIsNone(window.menu_bar)

    def test_re_attaching_replaces_the_bar(self) -> None:
        projection = self._projection(_FakeBridge())
        projection.set_menu_strip(WINDOW_ADDR, _itidy_like_strip())
        first = self._bar(projection)
        projection.set_menu_strip(WINDOW_ADDR, _project_menu([_entry(0x300, 0, 0, "Only")], titles=("Tools",)))
        window = projection.host_window(WINDOW_ADDR)
        assert window is not None
        bars = window.findChildren(QMenuBar)
        self.assertEqual(len(bars), 1, "one bar per window, the new strip replaces the old")
        self.assertIsNot(window.menu_bar, first)
        self.assertEqual([a.text() for a in window.menu_bar.actions()], ["Tools"])

    def test_unknown_window_records_nothing(self) -> None:
        projection = self._projection(_FakeBridge())
        projection.set_menu_strip(0x000F0000, _itidy_like_strip())
        projection.clear_menu_strip(0x000F0000)  # must not raise


if __name__ == "__main__":
    unittest.main()
