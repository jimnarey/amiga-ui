"""Repo-owned ``timer.device`` override: a coherent system clock for ``GetSysTime``.

vamos' built-in ``TimerDevice`` (``amitools/vamos/lib/TimerDevice.py``) only
implements ``ReadEClock`` — and incorrectly, by "abusing" the ``DateStampStruct``
layout — and has no ``GetSysTime`` at all. The target app calls ``GetSysTime``
(17x during startup) to read the system time, so it currently hits the default
(no-op) vector and reads a zeroed ``timeval``.

This subclass provides a coherent, wall-clock system time on the classic
**Amiga epoch**. The AmigaOS ``timer.device`` time base is ``1978-01-01
00:00:00 UTC`` (not the Unix ``1970-01-01`` epoch): the in-tree ``amitools``
convention encodes exactly this — ``AmiTime`` documents "2922 is the number of
days between Jan-1 1970 and Jan-1 1978. Note that Amiga uses an epoch of Jan-1
1978 whereas Unix uses an epoch of Jan-1 1970", and ``DosLibrary.DateStamp``
turns ``time.time()`` (Unix seconds) into the 1978-based ``ds_Days``/``ds_Minute``/
``ds_Tick``. ``GetSysTime`` is the ``struct timeval`` sibling of that same clock,
so it is expressed as whole seconds + microseconds since ``1978-01-01``.

``GetSysTime(Dest)`` (A0 = ``struct timeval *``) fills::

    struct timeval {
        ULONG tv_secs;   /* @ 0x00: seconds since 1978-01-01 00:00:00 UTC */
        ULONG tv_micro;  /* @ 0x04: microseconds (0..999999)              */
    };

in m68k big-endian byte order (the vamos ``Mem.w32`` accessor is big-endian).

The clock source is a narrow, replaceable callable (``self.clock``) so focused
tests can assert exact ``tv_secs``/``tv_micro`` values without depending on the
host wall clock.
"""

from __future__ import annotations

from datetime import UTC, datetime

from amitools.vamos.machine.regs import REG_A0

from .base_library import BaseLibrary

# The AmigaOS ``timer.device`` epoch: 1978-01-01 00:00:00 UTC. This is 2922 days
# after the Unix epoch and matches the in-tree ``amitools`` convention (see the
# module docstring and ``amitools/vamos/lib/dos/AmiTime.py``).
AMIGA_EPOCH = datetime(1978, 1, 1, tzinfo=UTC)

# struct timeval field offsets (classic m68k NDK, <devices/timer.h>).
_TV_OFF_SECS = 0x00
_TV_OFF_MICRO = 0x04


def _utc_now() -> datetime:
    """Return the host wall clock as a timezone-aware UTC ``datetime``."""

    return datetime.now(UTC)


class RepoTimerDevice(BaseLibrary):
    """``timer.device`` with a coherent, testable ``GetSysTime``.

    All other timer functions are inherited unchanged; only ``GetSysTime`` is
    added (the upstream device has none).
    """

    def __init__(self) -> None:
        # Narrow, replaceable clock source: a zero-arg callable returning a
        # timezone-aware ``datetime``. Tests override this to pin the exact
        # seconds/microseconds they want to observe.
        self.clock = _utc_now

    def GetSysTime(self, ctx):
        """Fill the caller's ``struct timeval`` with the current system time.

        ``Dest`` (A0) is a ``struct timeval *``; the result is written there, so
        D0 carries no status. Without 68k memory there is nowhere to write, so the
        call is a no-op (the caller keeps its zeroed struct) rather than raising.
        """

        dest = ctx.cpu.r_reg(REG_A0)
        mem = getattr(ctx, "mem", None)
        if mem is None:
            return 0

        now = self.clock()
        delta = now - AMIGA_EPOCH
        tv_secs = int(delta.total_seconds())
        if tv_secs < 0:
            # The AutoDoc: "The system time starts off at zero at power on."
            # A pre-epoch clock is clamped to zero rather than a negative ULONG.
            tv_secs = 0
        tv_secs &= 0xFFFFFFFF
        tv_micro = now.microsecond & 0xFFFFFFFF

        mem.w32(dest + _TV_OFF_SECS, tv_secs)
        mem.w32(dest + _TV_OFF_MICRO, tv_micro)
        return 0
