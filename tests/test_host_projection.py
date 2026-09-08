"""Tests for the Qt-independent host window-projection boundary.

Covers the semantic intent type (:class:`OpenWindowIntent`) and the no-GUI
default (:class:`NullHostWindowProjection`) without any Qt dependency, so these
run in a plain headless environment (no display, no PySide6 import).
"""

import unittest
from dataclasses import replace

from amiga_ui.host.projection import (
    NullHostWindowProjection,
    OpenWindowIntent,
)


def _intent(**overrides: int | str | bool) -> OpenWindowIntent:
    base = OpenWindowIntent(
        window_addr=0x1000,
        title="iTidy",
        left=50,
        top=30,
        width=625,
        height=215,
        rport_addr=0x2000,
    )
    return replace(base, **overrides)


class OpenWindowIntentTest(unittest.TestCase):
    def test_app_facing_when_titled(self) -> None:
        self.assertTrue(_intent(title="iTidy", idcmp=0).is_app_facing)

    def test_app_facing_when_idcmp_set(self) -> None:
        self.assertTrue(_intent(title="", idcmp=0x344).is_app_facing)

    def test_app_facing_when_menu_strip_attached(self) -> None:
        self.assertTrue(_intent(title="", idcmp=0, has_menu_strip=True).is_app_facing)

    def test_helper_backdrop_window_is_not_app_facing(self) -> None:
        # The iTidy 1x1 backdrop window: no title, no IDCMP, no menu strip.
        intent = _intent(title="", idcmp=0, width=1, height=1)
        self.assertFalse(intent.is_app_facing)


class NullHostWindowProjectionTest(unittest.TestCase):
    def test_open_records_intent(self) -> None:
        projection = NullHostWindowProjection()
        intent = _intent()
        projection.open_window(intent)
        self.assertEqual(projection.opened, [intent])

    def test_refresh_only_for_opened_window(self) -> None:
        projection = NullHostWindowProjection()
        projection.open_window(_intent(window_addr=0x1000))
        projection.refresh_window(0x1000)  # known -> recorded
        projection.refresh_window(0x9999)  # unknown -> ignored
        self.assertEqual(projection.refreshed, [0x1000])

    def test_close_is_idempotent(self) -> None:
        projection = NullHostWindowProjection()
        projection.open_window(_intent(window_addr=0x1000))
        projection.close_window(0x1000)
        projection.close_window(0x1000)  # second close is a no-op
        self.assertEqual(projection.closed, [0x1000])
        # A refresh after close is ignored (window no longer known).
        projection.refresh_window(0x1000)
        self.assertEqual(projection.refreshed, [])

    def test_bind_registry_stores(self) -> None:
        projection = NullHostWindowProjection()
        sentinel = object()
        projection.bind_registry(sentinel)
        self.assertIs(projection._registry, sentinel)


if __name__ == "__main__":
    unittest.main()
