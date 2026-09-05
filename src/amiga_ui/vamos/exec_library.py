"""Repo-owned ``exec.library`` override: classic ``WaitPort`` semantics.

vamos' built-in ``WaitPort`` (``amitools/vamos/lib/ExecLibrary.py``) removes
the first message from the port queue and returns it — i.e. it implements
``GetMsg`` semantics. Classic AmigaOS ``WaitPort`` is different: it waits
until the port has *at least one* message, then returns the address of the
first queued message **leaving it in the queue**, so the caller's subsequent
``GetMsg()`` removes it.

The target app relies on exactly that split (``handle_itidy_window_events``
in ``amiga_apps/itidy1classic/source/src/GUI/main_window.c``)::

    WaitPort(win->UserPort);
    while ((msg = GT_GetIMsg(win->UserPort))) {   /* GT_GetIMsg == GetMsg */
        ...
        GT_ReplyIMsg(msg);
    }

With pop-semantics ``WaitPort`` the message the app expects to drain in the
``GT_GetIMsg`` loop would already be consumed by ``WaitPort`` itself and the
loop would see an empty queue. This subclass restores the classic contract:
``WaitPort`` peeks; only ``GetMsg`` removes.

Honest behaviour is preserved: an unregistered port is still a hard
``VamosInternalError`` and a registered-but-empty queue still raises
``UnsupportedFeatureError`` — ``WaitPort`` never "succeeds" with nothing
queued. See ``docs/platform/library-cards/intuition.library.md`` for the
event-loop design this supports.
"""

from __future__ import annotations

from amitools.vamos.error import UnsupportedFeatureError, VamosInternalError
from amitools.vamos.lib.ExecLibrary import ExecLibrary
from amitools.vamos.lib.lexec.PortManager import PortManager
from amitools.vamos.log import log_exec
from amitools.vamos.machine.regs import REG_A0


class PeekPortManager(PortManager):
    """PortManager with a non-destructive queue peek for ``WaitPort``."""

    def peek_msg(self, port_addr):
        """Return the first queued message without removing it, or ``None``."""
        port = self.ports.get(port_addr)
        if port is None or port.queue is None:
            return None
        return port.queue[0] if port.queue else None


class RepoExecLibrary(ExecLibrary):
    """``ExecLibrary`` with classic (leave-in-queue) ``WaitPort`` semantics.

    All other exec functions are inherited unchanged; only ``WaitPort`` and
    the port manager it uses are replaced.
    """

    def setup_lib(self, ctx, base_addr):
        super().setup_lib(ctx, base_addr)
        # Replace the just-created port manager with the peek-capable
        # subclass. Nothing is registered on it at setup time (ports are
        # created later, at OpenWindow/CreateMsgPort time), so the swap is
        # safe, and every consumer reads ``impl.port_mgr`` at call time.
        self.port_mgr = PeekPortManager(ctx.alloc)

    def WaitPort(self, ctx):
        port_addr = ctx.cpu.r_reg(REG_A0)
        log_exec.info("WaitPort: port=%06x", port_addr)
        if not self.port_mgr.has_port(port_addr):
            raise VamosInternalError(f"WaitPort: on invalid Port ({port_addr:06x}) called!")
        if not self.port_mgr.has_msg(port_addr):
            raise UnsupportedFeatureError(f"WaitPort on empty message queue called: Port ({port_addr:06x})")
        # Classic contract: report the first queued message WITHOUT removing
        # it — GetMsg (the app's GT_GetIMsg) is what removes it.
        msg_addr = self.port_mgr.peek_msg(port_addr)
        log_exec.info("WaitPort: first queued message %06x (left in queue)", msg_addr)
        return msg_addr
