"""Tests for the repo ``timer.device`` ``GetSysTime``.

Covers, without depending on the iTidy binary, the ``timer.device`` call the
target drives 17x during startup to read the system time:

- ``GetSysTime(dest)`` (A0 = ``struct timeval *``) writes ``tv_secs`` @ 0x00 and
  ``tv_micro`` @ 0x04 in m68k **big-endian** byte order;
- the time base is the classic **Amiga epoch** (``1978-01-01 00:00:00 UTC``), not
  the Unix ``1970`` epoch — cross-checked against the Unix value for the same
  instant;
- the clock source is a narrow replaceable callable (``self.clock``), so exact
  seconds/microseconds are asserted without depending on the host wall clock;
- a scanner regression guard: the method must be a valid ``.fd`` trap
  (``ctx`` first, exact arg count) so vamos wires it instead of silently dropping
  it as an ``UNKNOWN`` trap.

The ``struct timeval`` layout matches the classic m68k NDK (``<devices/timer.h>``
[struct TimeVal]): ``tv_secs`` (ULONG) @ 0x00, ``tv_micro`` (ULONG) @ 0x04.
"""

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from amiga_ui.vamos.timer_device import AMIGA_EPOCH, RepoTimerDevice


class _FakeMem:
    """A minimal big-endian 68k memory model (unwritten bytes are 0)."""

    def __init__(self) -> None:
        self._bytes: dict[int, int] = {}

    def r8(self, addr: int) -> int:
        return self._bytes.get(addr, 0) & 0xFF

    def w8(self, addr: int, value: int) -> None:
        self._bytes[addr] = value & 0xFF

    def r32(self, addr: int) -> int:
        return (self.r8(addr) << 24) | (self.r8(addr + 1) << 16) | (self.r8(addr + 2) << 8) | self.r8(addr + 3)

    def w32(self, addr: int, value: int) -> None:
        value &= 0xFFFFFFFF
        self.w8(addr, (value >> 24) & 0xFF)
        self.w8(addr + 1, (value >> 16) & 0xFF)
        self.w8(addr + 2, (value >> 8) & 0xFF)
        self.w8(addr + 3, value & 0xFF)


class _FakeCpu:
    """A minimal CPU whose A0 register returns a fixed ``dest`` address."""

    def __init__(self, dest: int) -> None:
        self._dest = dest

    def r_reg(self, reg: int) -> int:
        # Only REG_A0 is consulted by GetSysTime; return the dest for it.
        return self._dest


def _ctx(dest: int, mem: _FakeMem | None) -> SimpleNamespace:
    return SimpleNamespace(cpu=_FakeCpu(dest), mem=mem)


class GetSysTimeTest(unittest.TestCase):
    """``GetSysTime`` fills the caller's ``timeval`` on the Amiga 1978 epoch."""

    DEST = 0x000650B8  # the app's timeval address (probe log)

    def _lib_with(self, now: datetime) -> RepoTimerDevice:
        lib = RepoTimerDevice()
        lib.clock = lambda: now
        return lib

    def test_epoch_instant_is_zero(self) -> None:
        # Exactly at the Amiga epoch -> tv_secs = tv_micro = 0.
        lib = self._lib_with(datetime(1978, 1, 1, 0, 0, 0, 0, tzinfo=UTC))
        mem = _FakeMem()
        lib.GetSysTime(_ctx(self.DEST, mem))

        self.assertEqual(mem.r32(self.DEST + 0x00), 0)
        self.assertEqual(mem.r32(self.DEST + 0x04), 0)

    def test_one_second_and_half_micro(self) -> None:
        lib = self._lib_with(datetime(1978, 1, 1, 0, 0, 1, 500000, tzinfo=UTC))
        mem = _FakeMem()
        lib.GetSysTime(_ctx(self.DEST, mem))

        self.assertEqual(mem.r32(self.DEST + 0x00), 1)
        self.assertEqual(mem.r32(self.DEST + 0x04), 500000)

    def test_seconds_are_amiga_epoch_not_unix(self) -> None:
        now = datetime(2026, 9, 8, 12, 34, 56, 789012, tzinfo=UTC)
        lib = self._lib_with(now)
        mem = _FakeMem()
        lib.GetSysTime(_ctx(self.DEST, mem))

        expected_amiga_secs = int((now - AMIGA_EPOCH).total_seconds())
        expected_unix_secs = int((now - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds())
        self.assertEqual(mem.r32(self.DEST + 0x00), expected_amiga_secs)
        self.assertEqual(mem.r32(self.DEST + 0x04), 789012)
        # The Amiga value is exactly 2922 days (Unix 1970 -> Amiga 1978) behind
        # the Unix value — proof the 1978 epoch, not the 1970 epoch, is used.
        self.assertEqual(expected_unix_secs - expected_amiga_secs, 2922 * 86400)

    def test_bytes_are_big_endian(self) -> None:
        # A value whose 32-bit form is not palindromic pins the byte order.
        now = datetime(1979, 1, 1, 0, 0, 0, 0, tzinfo=UTC)  # 365 days -> 31536000 s
        lib = self._lib_with(now)
        mem = _FakeMem()
        lib.GetSysTime(_ctx(self.DEST, mem))

        expected = 31536000
        raw = bytes([mem.r8(self.DEST + i) for i in range(4)])
        self.assertEqual(raw, expected.to_bytes(4, "big"))

    def test_micro_range_is_valid(self) -> None:
        lib = self._lib_with(datetime(2026, 9, 8, 12, 34, 56, 999999, tzinfo=UTC))
        mem = _FakeMem()
        lib.GetSysTime(_ctx(self.DEST, mem))

        self.assertLessEqual(mem.r32(self.DEST + 0x04), 999999)

    def test_no_mem_is_a_safe_noop(self) -> None:
        # No 68k memory -> nowhere to write -> no-op (returns 0, no raise).
        lib = self._lib_with(datetime(2026, 9, 8, 12, 34, 56, 0, tzinfo=UTC))

        self.assertEqual(lib.GetSysTime(_ctx(self.DEST, None)), 0)

    def test_default_clock_is_utc_now(self) -> None:
        # A fresh device (no override) uses the host wall clock and still writes
        # plausible, in-range values on the 1978 epoch.
        lib = RepoTimerDevice()
        mem = _FakeMem()
        lib.GetSysTime(_ctx(self.DEST, mem))

        secs = mem.r32(self.DEST + 0x00)
        micros = mem.r32(self.DEST + 0x04)
        # 2026 wall clock is ~48 years after 1978 -> a large but < 2^32 second count.
        self.assertGreater(secs, 40 * 365 * 86400)
        self.assertLess(secs, 0xFFFFFFFF)
        self.assertLessEqual(micros, 999999)


class TimerScannerTest(unittest.TestCase):
    """Regression guard: GetSysTime must be a valid .fd trap."""

    def _scan(self):
        from amitools.fd import read_lib_fd
        from amitools.vamos.libcore.impl import LibImplScanner

        # timer.device is in the default amitools FD set (timer_lib.fd).
        impl = RepoTimerDevice()
        fd = read_lib_fd("timer.device")
        return LibImplScanner().scan("timer.device", impl, fd, True)

    def test_no_scanner_errors(self) -> None:
        scan = self._scan()
        self.assertEqual(scan.get_num_error_funcs(), 0, scan.get_error_func_names())
        self.assertEqual(scan.get_num_invalid_funcs(), 0, scan.get_invalid_func_names())
        self.assertGreater(scan.get_num_valid_funcs(), 0)

    def test_get_sys_time_is_a_wired_trap(self) -> None:
        scan = self._scan()
        self.assertIn("GetSysTime", set(scan.get_valid_func_names()))


if __name__ == "__main__":
    unittest.main()
