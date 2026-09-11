"""Qt-free cooperative host scheduler core.

Implements the single-active-context cooperative wait design settled in
``docs/architecture/cooperative-host-scheduler.md``:

1. an immutable declarative wait request (:class:`MessagePortWait`);
2. a runtime-owned readiness evaluation against the real Amiga port queue
   (a ``readiness`` callable the caller supplies — the scheduler never owns
   emulated memory);
3. an explicit wait registration (:class:`WaitRegistration`) carrying a unique
   token, the immutable request, an explicit singleton execution identity, an
   active/completed/cancelled state, and the final outcome;
4. a replaceable host event-service backend (:class:`HostEventServiceBackend`);
5. a synchronous blocking facade for the current execution model
   (:meth:`CooperativeHostScheduler.run_wait`).

The parked Python call stack (inside ``WaitPort``) and any nested Qt loop are
*not* the scheduler's stored representation of the wait: the registration is.
A host notification (:meth:`CooperativeHostScheduler.notify_resource_changed`)
is only a *hint* — it may be stale, duplicated, coalesced or unrelated. The real
port queue is rechecked (through the ``readiness`` callable) before a satisfied
result is produced, and only a genuinely satisfied Amiga wait condition may
yield a normal ``WaitPort`` return.

This module is deliberately Qt-free: it owns no ``QEventLoop``, no ``QTimer`` and
no lock. The concrete event-service mechanics live in a replaceable backend
(the first one is ``amiga_ui.host.qt_scheduler_backend.QtEventLoopBackend``,
confined to the Qt side). Plain (non-GUI) probes install no scheduler, in which
case ``WaitPort`` keeps its existing honest headless boundary.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

# --- Wait outcomes -------------------------------------------------------------
class WaitOutcome(enum.Enum):
    """Terminal outcomes of a cooperative host wait.

    Only :attr:`SATISFIED` may produce a normal ``WaitPort`` return. Every other
    outcome must surface as an honest termination (never a fabricated
    ``IntuiMessage`` or a successful empty wait).
    """

    SATISFIED = "satisfied"  # the real Amiga wait condition became true
    SHUTDOWN = "shutdown"  # the host shell is shutting down
    TIMEOUT = "timeout"  # an automation / diagnostic timeout bound expired
    UNSUPPORTED = "unsupported"  # non-interactive / cannot service this wait


class WaitResource(enum.Enum):
    """Resource kinds a wait can be satisfied by (resource-specific hints).

    Notifications are resource-specific, not a context-free ``wake()``: a hint
    names the resource and the address it pertains to, so the scheduler can tell
    a relevant hint apart from one for some other resource or address.
    """

    MESSAGE_PORT = "message_port"


class SchedulerBusyError(RuntimeError):
    """Raised when a second independently active wait is attempted.

    The first implementation supports exactly one active Amiga execution context
    and one outstanding wait. A nested ``WaitPort`` (or any second concurrently
    active wait) is rejected explicitly rather than corrupting the current
    registration.
    """


# The single active Amiga execution context. There is exactly one for the first
# implementation; every wait registration carries this identity so a stale or
# second context is detectable (see :class:`WaitRegistration.execution_context`).
EXECUTION_CONTEXT_ID = "amiga-single-active-context"


# --- Immutable wait request ----------------------------------------------------
@dataclass(frozen=True)
class MessagePortWait:
    """Immutable declarative request: a message is available on ``port_addr``.

    This is the *declared* wait condition, not an evaluation of it. The runtime
    evaluates readiness against the real port queue separately; the request only
    names *what* is being waited on.
    """

    resource: WaitResource = WaitResource.MESSAGE_PORT
    port_addr: int = 0

    def __post_init__(self) -> None:
        if self.resource is not WaitResource.MESSAGE_PORT:
            raise ValueError(f"unsupported wait resource: {self.resource!r}")
        if self.port_addr <= 0:
            raise ValueError(f"MessagePortWait requires a valid port address, got {self.port_addr:#x}")


# --- Wait registration ---------------------------------------------------------
@dataclass
class WaitRegistration:
    """Runtime-owned registration of one outstanding cooperative wait.

    This is the scheduler's stored representation of a wait — *not* the parked
    call stack. It is created when an unsatisfied wait enters the backend and is
    cleared in every exit path (satisfied, shutdown, timeout, exception).
    """

    token: int
    request: MessagePortWait
    execution_context: str
    state: str = "pending"  # "pending" | "satisfied" | "cancelled"
    outcome: Optional[WaitOutcome] = None


# --- Replaceable host event-service backend ------------------------------------
class HostEventServiceBackend:
    """Replaceable host event-service backend.

    The core scheduler owns the wait representation and the readiness
    discipline; the backend knows how to block the single GUI-thread event
    service and how to wake it. The first (and only) backend in this increment
    is the Qt event-loop backend; a future headless-automation or diagnostic
    backend can be substituted without touching ``WaitPort``.
    """

    def service_until_ready(
        self,
        registration: WaitRegistration,
        readiness: Callable[[], bool],
        deadline: Optional[float],
    ) -> WaitOutcome:
        """Block the event service until ``readiness()`` is true or a terminal
        outcome is reached.

        The backend must recheck ``readiness`` after every wake and may return
        :attr:`WaitOutcome.SATISFIED` only when ``readiness()`` is genuinely
        true. ``deadline`` is an optional absolute monotonic time after which
        the wait must terminate honestly (it must not fabricate a message).
        """

        raise NotImplementedError

    def wake(self, registration: WaitRegistration) -> None:
        """Wake the blocked event service for one registration (a hint)."""

        raise NotImplementedError

    def cleanup(self, registration: WaitRegistration) -> None:
        """Release any per-wait backend state (called in every exit path)."""

        # The default is a no-op so minimal backends need not implement it.


# --- The scheduler -------------------------------------------------------------
class CooperativeHostScheduler:
    """Single-active-context cooperative host scheduler.

    One scheduler instance per in-process run. ``WaitPort`` (via the
    ``scheduler`` context attribute) calls :meth:`run_wait` when the requested
    port's queue is empty and an interactive scheduler is installed; the host
    event bridge calls :meth:`notify_resource_changed` after enqueuing a real
    ``IntuiMessage`` on the port.
    """

    def __init__(self, backend: HostEventServiceBackend) -> None:
        self._backend = backend
        self._active: Optional[WaitRegistration] = None
        self._token_seq = 0
        # The terminal outcome of the most recent wait (``None`` before any
        # wait, or when the run never reached a supported wait). The run command
        # reads this to distinguish application-driven completion, host
        # shutdown, automation timeout, and target-phase failure.
        self.last_outcome: Optional[WaitOutcome] = None
        # Optional automation/diagnostic bound for a wait, in seconds. When set,
        # a wait entered through :meth:`run_wait` without an explicit deadline
        # is bounded by ``monotonic() + wait_bound`` so automation can terminate
        # it honestly (a :attr:`WaitOutcome.TIMEOUT`, never a fabricated
        # message). ``None`` means "no bound" (interactive, no automation).
        self._wait_bound: Optional[float] = None

    def set_wait_bound(self, seconds: Optional[float]) -> None:
        """Set (or clear, with ``None``) the automation wait bound in seconds."""

        self._wait_bound = seconds

    # -- synchronous blocking facade ------------------------------------------
    def run_wait(
        self,
        request: MessagePortWait,
        readiness: Callable[[], bool],
        deadline: Optional[float] = None,
    ) -> WaitOutcome:
        """Wait until the real condition named by ``request`` is satisfied.

        - If ``readiness()`` is already true, return :attr:`WaitOutcome.SATISFIED`
          immediately without entering the backend.
        - Otherwise register the wait (unique token, singleton execution
          identity) and service host events through the backend.
        - A second independently active wait is rejected with
          :class:`SchedulerBusyError` (never corrupting the current
          registration).
        - Only a genuinely satisfied condition (rechecked after the backend
          returns) yields :attr:`WaitOutcome.SATISFIED`; a backend that reports
          satisfied while the condition is still false is downgraded to
          :attr:`WaitOutcome.UNSUPPORTED`.
        - The registration is cleared in every exit path (success, shutdown,
          timeout, exception).
        """

        if self._active is not None:
            raise SchedulerBusyError(
                "a second independently active wait is not supported by the "
                "single-active-context cooperative scheduler"
            )

        # Apply the automation bound when the caller did not pass an explicit
        # deadline (WaitPort never knows the bound; the run command sets it).
        if deadline is None and self._wait_bound is not None:
            deadline = time.monotonic() + self._wait_bound

        if readiness():
            # Already satisfied: no backend entry, no registration to store.
            self.last_outcome = WaitOutcome.SATISFIED
            return WaitOutcome.SATISFIED

        self._token_seq += 1
        registration = WaitRegistration(
            token=self._token_seq,
            request=request,
            execution_context=EXECUTION_CONTEXT_ID,
        )
        self._active = registration
        try:
            outcome = self._backend.service_until_ready(registration, readiness, deadline)
            # Defensive recheck: only a genuinely satisfied condition may be
            # reported as satisfied. The real backend already rechecks, but the
            # facade is the authority on "may WaitPort return normally".
            if outcome is WaitOutcome.SATISFIED and not readiness():
                outcome = WaitOutcome.UNSUPPORTED
            registration.state = "satisfied" if outcome is WaitOutcome.SATISFIED else "cancelled"
            registration.outcome = outcome
            self.last_outcome = outcome
            return outcome
        finally:
            # Clean up in every path (success, shutdown, timeout, exception).
            self._active = None
            self._backend.cleanup(registration)

    # -- resource-specific notifications (hints) ------------------------------
    def notify_resource_changed(self, resource: WaitResource, address: int) -> None:
        """Record a resource change as a *hint* for an outstanding wait.

        The hint is only meaningful when it matches the active wait's resource
        and address; otherwise it is dropped (a stale, duplicated, coalesced or
        unrelated hint). A matching hint wakes the backend, which then rechecks
        the real condition — the hint itself never produces a result.
        """

        active = self._active
        if active is None:
            return  # stale: no outstanding wait
        if active.execution_context != EXECUTION_CONTEXT_ID:
            return  # not our single execution context
        request = active.request
        if request.resource is not resource:
            return  # different resource: ignore
        if resource is WaitResource.MESSAGE_PORT and request.port_addr != address:
            return  # a notification for a different port: ignore
        self._backend.wake(active)

    # -- introspection (tests / the run command) ------------------------------
    @property
    def active(self) -> Optional[WaitRegistration]:
        """The currently outstanding registration (or ``None``)."""

        return self._active

    @property
    def backend(self) -> HostEventServiceBackend:
        return self._backend
