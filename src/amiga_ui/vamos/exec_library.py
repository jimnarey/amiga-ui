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

from ..host.scheduler import MessagePortWait, WaitOutcome, WaitResource


class WaitTimeoutError(UnsupportedFeatureError):
    """``WaitPort`` terminated by an automation / diagnostic timeout bound.

    Distinct from the honest headless boundary: the wait *was* interactive, but
    its time bound expired before the real condition became true. It must never
    become a fabricated ``IntuiMessage`` or a successful empty wait.
    """


class WaitShutdownError(UnsupportedFeatureError):
    """``WaitPort`` terminated because the host shell is shutting down.

    A distinct lifecycle outcome from a timeout and from a satisfied wait; it
    never fabricates a message or reports a successful empty wait.
    """


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

        # Classic contract: if the port already holds a message, report the
        # first queued message WITHOUT removing it (GetMsg / GT_GetIMsg is what
        # removes it). Preserve this immediate behaviour without touching the
        # host scheduler.
        msg_addr = self.port_mgr.peek_msg(port_addr)
        if msg_addr is not None:
            log_exec.info("WaitPort: first queued message %06x (left in queue)", msg_addr)
            return msg_addr

        # The queue is empty. Without an interactive scheduler, preserve the
        # existing honest headless boundary: ``WaitPort`` never "succeeds" with
        # nothing queued.
        scheduler = getattr(ctx, "scheduler", None)
        if scheduler is None:
            log_exec.error("WaitPort on empty message queue called: Port (%06x)", port_addr)
            raise UnsupportedFeatureError(f"WaitPort on empty message queue called: Port ({port_addr:06x})")

        # Interactive scheduler installed: register the port wait and service
        # host events through the backend. The readiness predicate rechecks the
        # *real* port queue (a non-destructive peek), so only a genuinely
        # satisfied condition may produce a normal return.
        log_exec.info("WaitPort: queue empty; entering cooperative host scheduler for Port %06x", port_addr)

        def readiness() -> bool:
            return self.port_mgr.has_msg(port_addr)

        outcome = scheduler.run_wait(MessagePortWait(WaitResource.MESSAGE_PORT, port_addr), readiness)
        log_exec.info("WaitPort: cooperative wait finished with outcome %s", outcome.value)

        if outcome is not WaitOutcome.SATISFIED:
            # A shutdown / timeout / unsupported outcome is an honest
            # termination — never a fabricated message or a successful empty
            # wait. Each surfaces as a distinct, documented error.
            if outcome is WaitOutcome.TIMEOUT:
                raise WaitTimeoutError(f"WaitPort on empty message queue timed out: Port ({port_addr:06x})")
            if outcome is WaitOutcome.SHUTDOWN:
                raise WaitShutdownError(
                    f"WaitPort on empty message queue interrupted by host shutdown: Port ({port_addr:06x})"
                )
            raise UnsupportedFeatureError(f"WaitPort on empty message queue not supported here: Port ({port_addr:06x})")

        # SATISFIED: recheck the real requested port (a notification may have
        # been stale) and report the first queued message without removing it.
        msg_addr = self.port_mgr.peek_msg(port_addr)
        if msg_addr is None:
            # The condition was not genuinely satisfied; fail honestly rather
            # than report a successful empty wait.
            raise UnsupportedFeatureError(f"WaitPort satisfied but port still empty: Port ({port_addr:06x})")
        log_exec.info("WaitPort: first queued message %06x (left in queue)", msg_addr)
        return msg_addr
