"""Qt (offscreen) tests for the host window-manager **close request** path.

The route under test (``docs/architecture/cooperative-host-scheduler.md``
"Window Close Semantics")::

    host close request (QCloseEvent on the projected window)
      -> AmigaHostWindow.closeEvent  -- event.ignore(): never self-destroy
      -> QtHostWindowProjection._on_close_request(window_addr)
      -> IntuitionEventBridge.request_close_window(window_addr)
      -> real IDCMP_CLOSEWINDOW IntuiMessage on the window's real UserPort
      -> the app decides; only ITS CloseWindow destroys the host window

These are the widget/projection-level tests (no target binary): the close
request is refused by Qt and forwarded *by real window address*; a window that
never requested ``IDCMP_CLOSEWINDOW`` gets no message and must not vanish; the
second request is an idempotent no-op; the app-driven release path
(:meth:`QtHostWindowProjection.close_window`) remains the only place the widget
is destroyed while the session is live; and once the session has ended
(``mark_session_ended`` — ``--auto-close-after``'s forced shutdown, whose
``app.quit()`` synthesises a close per visible window) closes complete in Qt
without touching the bridge. The full real-iTidy route is covered by
``tests/run_interactive_close_smoke_test.py``.

Requires PySide6 and a headless display: run under Xvfb or with
``QT_QPA_PLATFORM=offscreen``.
"""

from __future__ import annotations

import os
import unittest
from typing import ClassVar

# Headless by default; a real display (or Xvfb) is also fine.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from amiga_ui.host.projection import OpenWindowIntent  # noqa: E402
from amiga_ui.host.qt_projection import AmigaHostWindow, QtHostWindowProjection  # noqa: E402
from amiga_ui.host.scheduler import WaitResource  # noqa: E402
from amiga_ui.vamos.event_bridge import (  # noqa: E402
    IDCMP_CLOSEWINDOW,
    IDCMP_GADGETUP,
    IMSG_OFF_CLASS,
    IMSG_OFF_IADDRESS,
    IMSG_OFF_IDCMPWINDOW,
    IMSG_OFF_REPLYMSG,
    IntuitionEventBridge,
)
from amiga_ui.vamos.exec_library import PeekPortManager  # noqa: E402
from tests.test_event_bridge import _FakeAlloc, _make_ctx  # noqa: E402

WINDOW_ADDR = 0x000A0000
RPORT_ADDR = 0x000B0000
_MAIN_IDCMP = IDCMP_CLOSEWINDOW | IDCMP_GADGETUP  # 0x240


def _intent(window_addr: int = WINDOW_ADDR, idcmp: int = _MAIN_IDCMP) -> OpenWindowIntent:
    return OpenWindowIntent(
        window_addr=window_addr,
        title="Test Window",
        left=20,
        top=20,
        width=320,
        height=120,
        rport_addr=RPORT_ADDR,
        idcmp=idcmp,
        has_menu_strip=False,
        gadgets=(),
    )


class _CloseRecordingBridge:
    """Records the address-based ``request_close_window`` calls it receives."""

    def __init__(self) -> None:
        self.close_requests: list[int] = []

    def request_close_window(self, window_addr: int) -> int:
        self.close_requests.append(window_addr)
        return 0x1234


class _RecordingScheduler:
    """Scheduler stand-in: records hints and *when* the port looked ready."""

    def __init__(self, port_mgr: PeekPortManager) -> None:
        self.port_mgr = port_mgr
        self.notified: list[tuple] = []
        self.port_had_message_at_notify: list[bool] = []

    def notify_resource_changed(self, resource, address: int) -> None:
        self.notified.append((resource, address))
        self.port_had_message_at_notify.append(self.port_mgr.has_msg(address))


class _QtTestCase(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        existing = QApplication.instance()
        cls.app = existing if isinstance(existing, QApplication) else QApplication([])


def _live_bridge(idcmp: int = _MAIN_IDCMP, window_addr: int = WINDOW_ADDR):
    """A real bridge with a live fake ctx and one opened window (+ scheduler)."""

    from amitools.vamos.machine.mockmem import MockMemory

    mem = MockMemory(4096)
    alloc = _FakeAlloc(mem)
    port_mgr = PeekPortManager(alloc)
    user_port = alloc.alloc_memory(0x14).addr
    window_port = alloc.alloc_memory(0x14).addr
    port_mgr.register_port(user_port)
    ctx = _make_ctx(port_mgr, mem, alloc)
    scheduler = _RecordingScheduler(port_mgr)
    ctx.scheduler = scheduler
    bridge = IntuitionEventBridge()
    bridge.on_window_opened(ctx, window_addr, user_port, window_port, idcmp, "Test Window")
    return bridge, ctx, port_mgr, scheduler, user_port, window_port


def _projected_window(projection: QtHostWindowProjection, window_addr: int = WINDOW_ADDR) -> AmigaHostWindow:
    """Narrow ``host_window(...)``: the projection must have projected this window."""

    window = projection.host_window(window_addr)
    assert window is not None, f"window {window_addr:06x} was never projected"
    return window


class CloseRequestDeferralTest(_QtTestCase):
    """A host close request never destroys the widget; it becomes an Amiga event."""

    def test_close_request_is_refused_and_forwarded_by_address(self) -> None:
        bridge = _CloseRecordingBridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())
        window = _projected_window(projection)
        self.assertTrue(window.isVisible())

        closed = window.close()  # the host asking this window to close

        self.assertFalse(closed, "a host close request must not close the widget")
        self.assertTrue(window.isVisible(), "the window must stay open, not vanish")
        # Address-based: the projection forwarded the window's real address.
        self.assertEqual(bridge.close_requests, [WINDOW_ADDR])
        self.assertIn(WINDOW_ADDR, projection.windows)

    def test_second_close_request_stays_deferred(self) -> None:
        bridge = _CloseRecordingBridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())
        window = _projected_window(projection)

        self.assertFalse(window.close())
        self.assertFalse(window.close())

        self.assertTrue(window.isVisible())
        self.assertEqual(bridge.close_requests, [WINDOW_ADDR, WINDOW_ADDR])

    def test_widget_without_event_source_keeps_plain_qt_behaviour(self) -> None:
        projection = QtHostWindowProjection(self.app, event_source=None)
        projection.open_window(_intent())
        window = _projected_window(projection)
        # Display-only projection: no Amiga window to notify, so the pre-existing
        # plain-Qt close behaviour is preserved (this is what the non-interactive
        # projection smoke tests rely on).
        self.assertTrue(window.close())
        self.assertFalse(window.isVisible())

    def test_app_driven_release_still_destroys_the_widget(self) -> None:
        bridge = _CloseRecordingBridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())
        window = _projected_window(projection)

        projection.close_window(WINDOW_ADDR)  # the app called CloseWindow

        self.assertFalse(window.isVisible(), "the app-driven release must destroy the widget")
        self.assertNotIn(WINDOW_ADDR, projection.windows)
        # The release must not masquerade as a close *request*.
        self.assertEqual(bridge.close_requests, [])


class CloseRequestBridgeTest(_QtTestCase):
    """The projected close request becomes one real IDCMP_CLOSEWINDOW message."""

    def test_two_requests_post_exactly_one_real_intuimessage(self) -> None:
        bridge, ctx, port_mgr, _sched, user_port, window_port = _live_bridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())
        window = _projected_window(projection)

        window.close()
        window.close()  # double-click / a request while the first is pending

        self.assertEqual(len(bridge.posted), 1, f"expected one message, got {bridge.posted}")
        record = bridge.posted[0]
        self.assertEqual(record["idcmp_class"], IDCMP_CLOSEWINDOW)
        self.assertEqual(record["window"], WINDOW_ADDR)
        self.assertEqual(record["port"], user_port)
        self.assertTrue(port_mgr.has_msg(user_port))
        imsg = port_mgr.peek_msg(user_port)
        assert imsg is not None, "the real message must be queued on the real UserPort"
        self.assertEqual(imsg, record["imsg"])
        # The settled iTidy IntuiMessage layout (offsets unchanged this session).
        self.assertEqual(ctx.mem.r32(imsg + IMSG_OFF_CLASS), IDCMP_CLOSEWINDOW)
        self.assertEqual(ctx.mem.r32(imsg + IMSG_OFF_IADDRESS), 0)
        self.assertEqual(ctx.mem.r32(imsg + IMSG_OFF_IDCMPWINDOW), WINDOW_ADDR)
        self.assertEqual(ctx.mem.r32(imsg + IMSG_OFF_REPLYMSG), window_port)
        # The widget is still open: only the app may close it.
        self.assertTrue(window.isVisible())
        # The duplicate is an honest, recorded no-op — not a second message.
        self.assertEqual(len(bridge.skipped), 1)
        self.assertIn("already pending", bridge.skipped[0])

    def test_scheduler_hint_is_a_port_hint_issued_after_the_queueing(self) -> None:
        bridge, _ctx, _port_mgr, scheduler, user_port, _window_port = _live_bridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())

        _projected_window(projection).close()

        self.assertEqual(scheduler.notified, [(WaitResource.MESSAGE_PORT, user_port)])
        # The hint is only meaningful once the message is really queued.
        self.assertEqual(scheduler.port_had_message_at_notify, [True])

    def test_window_that_did_not_request_closewindow_gets_no_message(self) -> None:
        bridge, _ctx, port_mgr, scheduler, user_port, _window_port = _live_bridge(
            idcmp=IDCMP_GADGETUP
        )
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent(idcmp=IDCMP_GADGETUP))
        window = _projected_window(projection)

        closed = window.close()

        self.assertFalse(closed)
        self.assertTrue(window.isVisible(), "a filtered request must not close the window either")
        self.assertEqual(bridge.posted, [])
        self.assertFalse(port_mgr.has_msg(user_port))
        self.assertEqual(scheduler.notified, [], "no message, so no wake hint")
        self.assertEqual(len(bridge.skipped), 1)
        self.assertIn("did not request IDCMP_CLOSEWINDOW", bridge.skipped[0])

    def test_request_after_the_app_closed_the_window_is_a_noop(self) -> None:
        bridge, _ctx, port_mgr, scheduler, user_port, _window_port = _live_bridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())

        projection.close_window(WINDOW_ADDR)  # the app's own CloseWindow
        bridge.on_window_closed(WINDOW_ADDR)  # (idempotent second release)
        imsg_count = len(bridge.posted)

        self.assertIsNone(bridge.request_close_window(WINDOW_ADDR))
        self.assertEqual(bridge.posted.__len__(), imsg_count)
        self.assertFalse(port_mgr.has_msg(user_port))
        self.assertEqual(scheduler.notified, [])
        self.assertIn("not open", bridge.skipped[-1])

    def test_answered_close_request_can_be_followed_by_a_fresh_one(self) -> None:
        bridge, ctx, port_mgr, _scheduler, user_port, _window_port = _live_bridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())
        window = _projected_window(projection)

        window.close()
        first = bridge.posted[0]["imsg"]
        # The app consumed and replied to the message but kept its window open:
        # a *later* request is a fresh event, not a duplicate.
        port_mgr.get_msg(user_port)
        bridge.release_message(ctx, first)

        window.close()

        self.assertEqual(len(bridge.posted), 2)
        self.assertEqual({r["idcmp_class"] for r in bridge.posted}, {IDCMP_CLOSEWINDOW})

    def test_reopened_window_at_a_recycled_address_starts_clean(self) -> None:
        bridge, _ctx, port_mgr, _scheduler, user_port, window_port = _live_bridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())
        window = _projected_window(projection)

        window.close()
        # The app closed this window; a *new* window later reuses the address.
        bridge.on_window_closed(WINDOW_ADDR)
        projection.close_window(WINDOW_ADDR)
        bridge.on_window_opened(_ctx, WINDOW_ADDR, user_port, window_port, _MAIN_IDCMP, "Test Window")

        self.assertEqual(bridge.request_close_window(WINDOW_ADDR) is not None, True)
        self.assertEqual(len(bridge.posted), 2)


class HostForcedShutdownTest(_QtTestCase):
    """The forced-host-shutdown case: closes once the Amiga session has ended.

    ``--auto-close-after`` bounds the interactive wait and then asks the shell
    to exit via ``app.quit()`` — which the widgets layer answers with a
    *synthesised* ``QCloseEvent`` per visible top-level window. That is not a
    genuine interactive close request: the target has already returned, its
    emulated context is gone, and deferring the request would both post into a
    dead allocator and wedge the quit forever (an ignored close keeps Qt from
    leaving the loop). ``mark_session_ended()`` is the documented host-lifecycle
    switch ("Window Close Semantics": an explicit forced host shutdown remains
    possible); these tests pin down both sides of it.
    """

    def test_live_session_close_request_still_defers(self) -> None:
        # Sanity for the switch's *absence*: before the session ends, the
        # deferral is intact (this is the interactive close path, not a
        # forced shutdown).
        bridge = _CloseRecordingBridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())
        window = _projected_window(projection)

        self.assertFalse(window.close())

        self.assertTrue(window.isVisible())
        self.assertEqual(bridge.close_requests, [WINDOW_ADDR])

    def test_close_after_session_end_completes_in_qt_without_the_bridge(self) -> None:
        bridge = _CloseRecordingBridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())
        window = _projected_window(projection)

        # The target returned: run_command marks the session ended, and the
        # forced shutdown (app.quit()'s synthesised close, or a plain close
        # click now) must destroy the window rather than defer it.
        projection.mark_session_ended()
        self.assertTrue(window.close())

        self.assertFalse(window.isVisible())
        # Nothing was fabricated: no close-window request reached the bridge.
        self.assertEqual(bridge.close_requests, [])
        # The projection record stays the release path's to pop, exactly as
        # before: host teardown goes through close_window (idempotent here).
        projection.close_window(WINDOW_ADDR)
        self.assertEqual(projection.windows, {})

    def test_session_end_still_lets_the_app_release_path_close(self) -> None:
        bridge, _ctx, port_mgr, _scheduler, user_port, _window_port = _live_bridge()
        projection = QtHostWindowProjection(self.app, event_source=bridge)
        projection.open_window(_intent())
        window = _projected_window(projection)

        projection.mark_session_ended()
        projection.close_window(WINDOW_ADDR)

        self.assertIsNone(projection.host_window(WINDOW_ADDR))
        self.assertFalse(window.isVisible())
        # close_window remains the only destruction path; no message appears.
        self.assertEqual(bridge.posted, [])
        self.assertFalse(port_mgr.has_msg(user_port))


if __name__ == "__main__":
    unittest.main()
