"""Tests for the host-side IntuiMessage event bridge (event loop driver).

Covers, in layers:
- the ``struct IntuiMessage`` (V36+) layout constants against NDK 3.2
  ``Include_H/intuition/intuition.h``;
- the classic ``WaitPort`` (peek) vs ``GetMsg`` (remove) split in
  ``RepoExecLibrary``;
- bridge scheduling/targeting/delivery/release against a fake 68k context;
- an in-process iTidy run where a scheduled close event is delivered to the
  app's real ``UserPort`` and consumed by its event loop through
  ``WaitPort -> GT_GetIMsg -> GT_ReplyIMsg``. The target *binary's* event
  loop consumes the message without a clean exit (it differs from the repo
  source and discards the message before its real event loop, which then
  ``WaitPort``s the now-empty queue and fails honestly); that is a documented
  target limitation, not a bridge defect, so the test asserts
  delivery/consumption, not a clean exit. There is also a regression test
  that without host events ``WaitPort`` still fails honestly on the empty
  queue.
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from amitools.vamos.error import UnsupportedFeatureError, VamosInternalError
from amitools.vamos.lib.lexec.PortManager import PortManager
from amitools.vamos.machine.mockmem import MockMemory
from amitools.vamos.machine.regs import REG_A0

from amiga_ui.config import PROJECT_ROOT
from amiga_ui.vamos.event_bridge import (
    IDCMP_CLOSEWINDOW,
    IDCMP_GADGETUP,
    IDCMP_MENUPICK,
    IDCMP_REFRESHWINDOW,
    IMSG_OFF_CLASS,
    IMSG_OFF_CODE,
    IMSG_OFF_IADDRESS,
    IMSG_OFF_IDCMPWINDOW,
    IMSG_OFF_MOUSEX,
    IMSG_OFF_MOUSEY,
    IMSG_OFF_QUALIFIER,
    IMSG_OFF_REPLYMSG,
    IMSG_OFF_SPECIALLINK,
    IMSG_SIZE,
    IntuitionEventBridge,
)
from amiga_ui.vamos.exec_library import PeekPortManager, RepoExecLibrary
from amiga_ui.vamos.launcher import run_vamos_in_process
from tests.test_vamos_launcher import _LauncherRuntimeFixture

_MAIN_WINDOW_IDCMP = 0x344  # CLOSEWINDOW|GADGETUP|REFRESHWINDOW|MENUPICK
_MAIN_WINDOW_TITLE = "iTidy v3.0 - Icon Cleanup Tool"


# --- fakes for the unit layer -------------------------------------------------
class _FakeBlock:
    def __init__(self, addr: int, size: int) -> None:
        self.addr = addr
        self.size = size


class _FakeAlloc:
    """Minimal MemoryAlloc stand-in: bump allocator over a MockMemory."""

    def __init__(self, mem: MockMemory, base: int = 0x080000) -> None:
        self.mem = mem
        self.next_addr = base
        self.freed: list[int] = []
        self.live: dict[int, _FakeBlock] = {}

    def alloc_memory(self, size: int, label: str | None = None) -> _FakeBlock:
        addr = self.next_addr
        self.next_addr += (size + 3) & ~3
        block = _FakeBlock(addr, size)
        self.live[addr] = block
        return block

    def free_memory(self, block: _FakeBlock) -> None:
        self.freed.append(block.addr)
        self.live.pop(block.addr, None)


class _FakeVLib:
    def __init__(self, impl) -> None:
        self.impl = impl


class _FakeVLibMgr:
    def __init__(self, exec_impl) -> None:
        self._exec = _FakeVLib(exec_impl)

    def get_vlib_by_name(self, name: str):
        return self._exec if name == "exec.library" else None


class _FakeCpu:
    def __init__(self, a0: int) -> None:
        self._a0 = a0

    def r_reg(self, reg: int) -> int:
        assert reg == REG_A0
        return self._a0


def _make_ctx(port_mgr: PortManager, mem: MockMemory, alloc: _FakeAlloc):
    exec_impl = SimpleNamespace(port_mgr=port_mgr)
    return SimpleNamespace(mem=mem, alloc=alloc, vlib_mgr=_FakeVLibMgr(exec_impl))


class IntuiMessageLayoutTest(unittest.TestCase):
    def test_intuimessage_v36_layout(self) -> None:
        # struct IntuiMessage (V36+), NDK 3.2 intuition.h:
        # Message(16) + Class@0x10 + Code@0x14 + Qualifier@0x16 + IAddress@0x18
        # + MouseX@0x1C + MouseY@0x1E + Seconds@0x20 + Micros@0x24
        # + IDCMPWindow@0x28 + SpecialLink@0x2C; size 0x30.
        self.assertEqual(IMSG_SIZE, 0x30)
        self.assertEqual(IMSG_OFF_CLASS, 0x10)
        self.assertEqual(IMSG_OFF_CODE, 0x14)
        self.assertEqual(IMSG_OFF_QUALIFIER, 0x16)
        self.assertEqual(IMSG_OFF_IADDRESS, 0x18)
        self.assertEqual(IMSG_OFF_MOUSEX, 0x1C)
        self.assertEqual(IMSG_OFF_MOUSEY, 0x1E)  # consecutive word, no overlap
        self.assertEqual(IMSG_OFF_IDCMPWINDOW, 0x28)
        self.assertEqual(IMSG_OFF_SPECIALLINK, 0x2C)
        self.assertEqual(IMSG_OFF_REPLYMSG, 0x00)

    def test_idcmp_flag_values_match_ndk(self) -> None:
        # NDK 3.2 intuition.h lines 863-873.
        self.assertEqual(IDCMP_REFRESHWINDOW, 0x00000004)
        self.assertEqual(IDCMP_GADGETUP, 0x00000040)
        self.assertEqual(IDCMP_MENUPICK, 0x00000100)
        self.assertEqual(IDCMP_CLOSEWINDOW, 0x00000200)


class WaitPortSemanticsTest(unittest.TestCase):
    """Classic WaitPort reports the first message WITHOUT removing it."""

    def _make_impl(self, port_addr: int = 0x06B330) -> RepoExecLibrary:
        impl = RepoExecLibrary()
        impl.port_mgr = PeekPortManager(None)
        impl.port_mgr.register_port(port_addr)
        return impl

    def test_waitport_empty_queue_raises(self) -> None:
        impl = self._make_impl()
        ctx = SimpleNamespace(cpu=_FakeCpu(0x06B330))
        with self.assertRaises(UnsupportedFeatureError):
            impl.WaitPort(ctx)

    def test_waitport_invalid_port_raises(self) -> None:
        impl = self._make_impl()
        ctx = SimpleNamespace(cpu=_FakeCpu(0xDEAD00))
        with self.assertRaises(VamosInternalError):
            impl.WaitPort(ctx)

    def test_waitport_peek_leaves_message_queued(self) -> None:
        impl = self._make_impl()
        port = 0x06B330
        impl.port_mgr.put_msg(port, 0x06C000)

        result = impl.WaitPort(SimpleNamespace(cpu=_FakeCpu(port)))

        self.assertEqual(result, 0x06C000)
        # The classic contract: GetMsg (GT_GetIMsg) still sees the message.
        self.assertTrue(impl.port_mgr.has_msg(port))
        self.assertEqual(impl.port_mgr.peek_msg(port), 0x06C000)
        self.assertEqual(impl.port_mgr.get_msg(port), 0x06C000)
        self.assertFalse(impl.port_mgr.has_msg(port))

    def test_peek_msg_empty_and_unknown_port(self) -> None:
        impl = self._make_impl()
        self.assertIsNone(impl.port_mgr.peek_msg(0x06B330))
        self.assertIsNone(impl.port_mgr.peek_msg(0x999999))


class EventBridgeUnitTest(unittest.TestCase):
    def _setup(self):
        mem = MockMemory(1024)  # 1 MiB: covers the fake alloc base 0x080000+
        alloc = _FakeAlloc(mem)
        port_mgr = PeekPortManager(alloc)
        backdrop_up, main_up, backdrop_wp, main_wp = (alloc.alloc_memory(0x14).addr for _ in range(4))
        port_mgr.register_port(backdrop_up)
        port_mgr.register_port(main_up)
        ctx = _make_ctx(port_mgr, mem, alloc)
        return SimpleNamespace(
            mem=mem,
            alloc=alloc,
            port_mgr=port_mgr,
            ctx=ctx,
            backdrop_up=backdrop_up,
            main_up=main_up,
            backdrop_wp=backdrop_wp,
            main_wp=main_wp,
        )

    def test_close_event_delivered_to_first_window_admitting_class(self) -> None:
        env = self._setup()
        bridge = IntuitionEventBridge()
        bridge.schedule_close_window()
        win_a, win_b = 0x060000, 0x062000

        # The 1x1 WFLG_BACKDROP utility window (no IDCMP flags) opens first:
        # real Intuition never generates a class a window did not request,
        # so the event must not be delivered there.
        bridge.on_window_opened(env.ctx, win_a, env.backdrop_up, env.backdrop_wp, 0, "")
        self.assertEqual(bridge.posted, [])
        self.assertEqual(len(bridge._pending), 1)

        bridge.on_window_opened(env.ctx, win_b, env.main_up, env.main_wp, _MAIN_WINDOW_IDCMP, _MAIN_WINDOW_TITLE)

        self.assertEqual(len(bridge.posted), 1)
        record = bridge.posted[0]
        self.assertEqual(record["window"], win_b)
        self.assertEqual(record["idcmp_class"], IDCMP_CLOSEWINDOW)
        self.assertEqual(len(bridge._pending), 0)
        # The message is on the window's REAL UserPort queue.
        self.assertTrue(env.port_mgr.has_msg(env.main_up))
        imsg = env.port_mgr.peek_msg(env.main_up)
        self.assertEqual(imsg, record["imsg"])
        # Real struct IntuiMessage content.
        self.assertEqual(env.mem.r32(imsg + IMSG_OFF_CLASS), IDCMP_CLOSEWINDOW)
        self.assertEqual(env.mem.r16(imsg + IMSG_OFF_CODE), 0)
        self.assertEqual(env.mem.r16(imsg + IMSG_OFF_QUALIFIER), 0)
        self.assertEqual(env.mem.r32(imsg + IMSG_OFF_IADDRESS), 0)
        self.assertEqual(env.mem.r32(imsg + IMSG_OFF_REPLYMSG), env.main_wp)
        self.assertEqual(env.mem.r32(imsg + IMSG_OFF_IDCMPWINDOW), win_b)
        self.assertEqual(env.mem.r32(imsg + IMSG_OFF_SPECIALLINK), 0)

    def test_title_targeting_only_matches_titled_window(self) -> None:
        env = self._setup()
        bridge = IntuitionEventBridge()
        bridge.schedule_close_window(window="iTidy")
        win_other, win_main = 0x060000, 0x062000

        bridge.on_window_opened(env.ctx, win_other, env.backdrop_up, env.backdrop_wp, _MAIN_WINDOW_IDCMP, "Other Tool")
        self.assertEqual(bridge.posted, [])

        bridge.on_window_opened(env.ctx, win_main, env.main_up, env.main_wp, _MAIN_WINDOW_IDCMP, _MAIN_WINDOW_TITLE)
        self.assertEqual(len(bridge.posted), 1)
        self.assertEqual(bridge.posted[0]["window"], win_main)

    def test_class_not_requested_by_any_window_stays_pending(self) -> None:
        env = self._setup()
        env.port_mgr.register_port(env.backdrop_up)
        bridge = IntuitionEventBridge()
        bridge.schedule_refresh_window()

        # Window admits GADGETUP but not REFRESHWINDOW: no delivery, event
        # remains pending for a later matching window.
        bridge.on_window_opened(env.ctx, 0x060000, env.backdrop_up, env.backdrop_wp, IDCMP_GADGETUP, "NoRefresh")
        self.assertEqual(bridge.posted, [])
        self.assertEqual(len(bridge._pending), 1)

        bridge.on_window_opened(env.ctx, 0x062000, env.main_up, env.main_wp, IDCMP_REFRESHWINDOW, "Refreshable")
        self.assertEqual(len(bridge.posted), 1)
        self.assertEqual(bridge.posted[0]["idcmp_class"], IDCMP_REFRESHWINDOW)

    def test_gadgetup_resolves_iaddress_to_registered_gadget(self) -> None:
        env = self._setup()
        bridge = IntuitionEventBridge()
        gadget_addr = env.alloc.alloc_memory(0x2C).addr
        bridge.register_gadget(gadget_addr, 7)
        bridge.schedule_gadget_up(gadget_id=7, mousex=12, mousey=34)

        bridge.on_window_opened(env.ctx, 0x062000, env.main_up, env.main_wp, IDCMP_GADGETUP, "Main")

        self.assertEqual(len(bridge.posted), 1)
        imsg = bridge.posted[0]["imsg"]
        self.assertEqual(env.mem.r32(imsg + IMSG_OFF_CLASS), IDCMP_GADGETUP)
        self.assertEqual(env.mem.r32(imsg + IMSG_OFF_IADDRESS), gadget_addr)
        self.assertEqual(env.mem.r16(imsg + IMSG_OFF_MOUSEX), 12)
        self.assertEqual(env.mem.r16(imsg + IMSG_OFF_MOUSEY), 34)

    def test_gadgetup_unknown_gid_is_skipped_not_posted(self) -> None:
        env = self._setup()
        bridge = IntuitionEventBridge()
        bridge.schedule_gadget_up(gadget_id=99)

        bridge.on_window_opened(env.ctx, 0x062000, env.main_up, env.main_wp, IDCMP_GADGETUP, "Main")

        self.assertEqual(bridge.posted, [])
        self.assertEqual(env.port_mgr.has_msg(env.main_up), False)
        self.assertEqual(len(bridge.skipped), 1)
        self.assertIn("99", bridge.skipped[0])

    def test_release_message_frees_bridge_allocated_block(self) -> None:
        env = self._setup()
        bridge = IntuitionEventBridge()
        bridge.schedule_close_window()
        bridge.on_window_opened(env.ctx, 0x062000, env.main_up, env.main_wp, _MAIN_WINDOW_IDCMP, _MAIN_WINDOW_TITLE)
        imsg = bridge.posted[0]["imsg"]
        self.assertIn(imsg, env.alloc.live)

        bridge.release_message(env.ctx, imsg)

        self.assertEqual(bridge.released, [imsg])
        self.assertNotIn(imsg, env.alloc.live)
        self.assertIn(imsg, env.alloc.freed)

    def test_release_message_ignores_foreign_address(self) -> None:
        env = self._setup()
        bridge = IntuitionEventBridge()
        # No exception, no free: the bridge does not own this block.
        bridge.release_message(env.ctx, 0x0FFFFF)
        self.assertEqual(bridge.released, [])
        self.assertEqual(env.alloc.freed, [])


class EventBridgeIntegrationTest(unittest.TestCase):
    """In-process iTidy: host close event drives the real event loop."""

    def _skip_if_no_binary(self) -> Path | None:
        app_dir = PROJECT_ROOT / "amiga_apps/itidy1classic/binary/extracted"
        app_binary = app_dir / "iTidy"
        if not app_binary.is_file():
            self.skipTest("iTidy binary is not present in the working tree")
            return None
        return app_dir

    def test_close_event_delivered_to_app_event_loop(self) -> None:
        """A host close event reaches the app's real UserPort and is consumed.

        Proves the sanctioned bridge path end-to-end: the test event becomes a
        real ``struct IntuiMessage`` (Class = IDCMP_CloseWindow) posted on the
        main window's real ``UserPort``; the app's ``WaitPort`` honestly finds
        it (classic peek) and its ``GT_GetIMsg -> GT_ReplyIMsg`` loop consumes
        and replies to the very same message.

        The target *binary's* event loop consumes the message without a clean
        exit (it differs from the repo source and drains the message before
        its real event loop, which then ``WaitPort``s the now-empty queue and
        fails honestly). That is a documented target limitation, not a bridge
        defect, so this test asserts delivery/consumption, not a clean exit.
        """
        app_dir = self._skip_if_no_binary()
        assert app_dir is not None
        bridge = IntuitionEventBridge()
        bridge.schedule_close_window()

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            runtime = _LauncherRuntimeFixture.create(temp_dir)
            vamos_log_path = temp_dir / "vamos.log"
            # A real file: vamos' dos FileManager wraps sys.stdout.buffer,
            # which StringIO does not have (same pattern as the CLI probe).
            with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as stdout_file:
                with contextlib.redirect_stdout(stdout_file), contextlib.redirect_stderr(io.StringIO()):
                    run_vamos_in_process(
                        args=runtime.build_itidy_args(app_dir=app_dir, vamos_log_path=vamos_log_path),
                        event_bridge=bridge,
                    )

            log_text = vamos_log_path.read_text(encoding="utf-8")

            # The host event was posted to the main window's real UserPort as a
            # real IntuiMessage carrying the CloseWindow class.
            self.assertEqual(len(bridge.posted), 1)
            self.assertEqual(bridge.posted[0]["idcmp_class"], IDCMP_CLOSEWINDOW)
            # The app's event loop consumed and replied to the very same
            # IntuiMessage (GT_GetIMsg removed it, GT_ReplyIMsg released it).
            self.assertEqual(bridge.released, [bridge.posted[0]["imsg"]])
            # WaitPort honestly found the message (classic peek) ...
            first_wait = "WaitPort: first queued message"
            self.assertIn(first_wait, log_text)
            # ... and the message WaitPort found is the bridge's own imsg,
            # cross-linking the host post to the app's real port.
            found_line = next(line for line in log_text.splitlines() if first_wait in line)
            self.assertIn(f"{bridge.posted[0]['imsg']:06x}", found_line)

    def test_no_host_events_keeps_honest_waitport_failure(self) -> None:
        """Regression: without scheduled events WaitPort must NOT succeed."""
        app_dir = self._skip_if_no_binary()
        assert app_dir is not None

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            runtime = _LauncherRuntimeFixture.create(temp_dir)
            vamos_log_path = temp_dir / "vamos.log"

            # A real file for stdout (vamos wraps sys.stdout.buffer); stderr
            # can stay a StringIO.
            with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as stdout_file:
                with contextlib.redirect_stdout(stdout_file), contextlib.redirect_stderr(io.StringIO()):
                    exit_code = run_vamos_in_process(
                        args=runtime.build_itidy_args(app_dir=app_dir, vamos_log_path=vamos_log_path)
                    )

            log_text = vamos_log_path.read_text(encoding="utf-8")
            # Honest failure: the queue really is empty; nothing is faked.
            self.assertIn("WaitPort on empty message queue", log_text)
            self.assertNotEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
