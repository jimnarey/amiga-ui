"""Repo-owned ``dos.library`` override: a real ``GetCurrentDirName``.

vamos' built-in ``DosLibrary`` (``amitools/vamos/lib/DosLibrary.py``) implements
most of the dos surface — including the process current-directory state
(``get_current_dir`` → ``pr_CurrentDir`` → a ``Lock``) — but has no
``GetCurrentDirName``. The target app calls it (2x, right after its ``ENV:`` prefs
lookups fail) to learn the directory it was launched from, so the call hits the
default no-op vector, D0 stays zero, and the app prints "Error getting current
directory".

This subclass inherits the whole upstream ``DosLibrary`` unchanged and adds
``GetCurrentDirName(buf, len)`` (D1=buf, D2=len, D0=success), per the classic
contract (AutoDoc [GetCurrentDirName]):

- the name is derived from the **active process's current-directory lock** — the
  Amiga-visible ``lock.ami_path`` — never a host filesystem path;
- the buffer length is respected including the NUL terminator;
- if the buffer is too small, the name is truncated to fit and failure is
  returned (``IoErr == ERROR_LINE_TOO_LONG``);
- if there is no current directory (no CLI / no cwd lock), a null string is
  written and failure is returned (``IoErr == ERROR_OBJECT_WRONG_TYPE``).

The AutoDoc notes this is the CLI-directory name; in the vamos runtime the
process cwd lock is the authoritative "current directory that the process is
using" (the same source ``NameFromLock``/``Lock``/``MatchFirst`` resolve from), so
it is what the launched process actually agrees with.
"""

from __future__ import annotations

from amitools.vamos.lib.dos.Error import ERROR_LINE_TOO_LONG, ERROR_OBJECT_WRONG_TYPE
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.log import log_dos
from amitools.vamos.machine.regs import REG_D1, REG_D2


class RepoDosLibrary(DosLibrary):
    """``dos.library`` with a real ``GetCurrentDirName``.

    Everything else is inherited unchanged from the upstream ``DosLibrary``; only
    ``GetCurrentDirName`` (and the two narrow helpers it uses) are added.
    """

    def GetCurrentDirName(self, ctx):
        """Extract the current directory name into ``buf`` (D1) of size ``len`` (D2)."""

        buf = ctx.cpu.r_reg(REG_D1)
        buf_len = ctx.cpu.r_reg(REG_D2)
        mem = getattr(ctx, "mem", None)
        if mem is None:
            # No 68k memory to write into: honest failure, no crash. The real
            # runtime always has memory, so this is a defensive edge only.
            return self.DOSFALSE

        name = self._current_dir_name(ctx)
        if name is None:
            # No current directory (no CLI / no cwd lock): per the AutoDoc, put a
            # null string in the buffer and report failure with
            # IoErr == ERROR_OBJECT_WRONG_TYPE.
            if buf_len > 0:
                mem.w8(buf, 0)
            self.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
            return self.DOSFALSE

        if buf_len <= 0:
            self.setioerr(ctx, ERROR_LINE_TOO_LONG)
            return self.DOSFALSE

        if len(name) + 1 > buf_len:
            # Buffer too small: truncate the name to fit (buf_len-1 chars + NUL)
            # and report failure, per the AutoDoc.
            mem.w_cstr(buf, name[: buf_len - 1])
            self.setioerr(ctx, ERROR_LINE_TOO_LONG)
            return self.DOSFALSE

        mem.w_cstr(buf, name)
        log_dos.info("GetCurrentDirName: buf=%06x len=%d -> '%s'", buf, buf_len, name)
        return self.DOSTRUE

    def _current_dir_name(self, ctx):
        """Return the Amiga-visible name of the process cwd lock, or ``None``.

        Resolves through the inherited upstream ``get_current_dir`` (which maps
        ``pr_CurrentDir`` to a ``Lock``) so the result is the same lock the rest of
        the dos surface uses — never a host path.
        """

        if getattr(ctx, "process", None) is None:
            return None
        lock = self.get_current_dir(ctx)
        return lock.ami_path if lock is not None else None
