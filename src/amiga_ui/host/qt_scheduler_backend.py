"""Qt event-service backend for the cooperative host scheduler.

Confines the ``QEventLoop`` / ``QTimer`` event-service mechanics to the Qt
side. The Qt-free core scheduler (``amiga_ui.host.scheduler``) owns the wait
representation and the readiness discipline; this backend is what actually
blocks the single GUI-thread event service in a controlled nested
``QEventLoop`` while one real Amiga wait condition is outstanding.

The nested loop is what keeps Qt responsive: every host event (a projected
gadget activation, a paint, a resize, a window-manager close request) is
dispatched normally while the target's Python call stack is parked in
``WaitPort``. A host notification wakes the loop; the loop then rechecks the
*real* Amiga condition (through the readiness callable) before a satisfied
result is produced. A one-shot timer bounds the wait so automation can
terminate it honestly — it terminates the wait, it does not repeatedly poll
state and it never fabricates a message.

Qt-only module: imported by the GUI ``run`` path and the interactive tests,
never by the low-level Amiga library implementations.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from PySide6.QtCore import QEventLoop, QTimer

from .scheduler import HostEventServiceBackend, WaitOutcome, WaitRegistration


class QtEventLoopBackend(HostEventServiceBackend):
    """First host event-service backend: a controlled nested Qt event loop."""

    def __init__(self, app) -> None:
        # The owning QApplication (for object parenting / lifecycle only — the
        # backend does not own the event loop, it parks the target's call stack
        # in a nested one). ``None`` is tolerated for tests that construct the
        # backend without a live app.
        self._app = app
        self._loop: Optional[QEventLoop] = None
        self._timeout_timer: Optional[QTimer] = None
        self._shutdown_requested = False
        self._timeout_fired = False

    # -- backend interface --------------------------------------------------
    def service_until_ready(
        self,
        registration: WaitRegistration,
        readiness: Callable[[], bool],
        deadline: Optional[float],
    ) -> WaitOutcome:
        """Park the target's call stack in a nested Qt loop until ``readiness``.

        Returns :attr:`WaitOutcome.SATISFIED` only when ``readiness()`` is
        genuinely true (rechecked after every wake), :attr:`WaitOutcome.TIMEOUT`
        when the one-shot deadline expires, or :attr:`WaitOutcome.SHUTDOWN` when
        the host requests shutdown.
        """

        loop = QEventLoop()
        self._loop = loop
        self._shutdown_requested = False
        self._timeout_fired = False

        # A one-shot timer bounds the wait (honest automation timeout). It is a
        # single firing, not a polling timer: it terminates the wait; it does
        # not repeatedly check state.
        if deadline is not None:
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000.0))
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(self._on_timeout)
            timer.start(remaining_ms)
            self._timeout_timer = timer
        try:
            while True:
                if readiness():
                    return WaitOutcome.SATISFIED
                if self._timeout_fired:
                    return WaitOutcome.TIMEOUT
                if self._shutdown_requested:
                    return WaitOutcome.SHUTDOWN
                # Block until a host event wakes the loop (a resource-change
                # hint, the timeout, or a shutdown). Qt keeps dispatching events
                # here, so the interface stays responsive while the target is
                # parked in WaitPort.
                loop.exec()
        finally:
            self._stop_timeout_timer()
            self._loop = None

    def wake(self, registration: Optional[WaitRegistration]) -> None:
        """Wake the blocked nested loop so it can recheck the real condition.

        ``registration`` is not used to decide anything (the loop is the single
        active one); it is accepted for interface uniformity.
        """

        loop = self._loop
        if loop is not None and loop.isRunning():
            loop.quit()

    def cleanup(self, registration: WaitRegistration) -> None:
        """Release per-wait backend state (called in every exit path)."""

        self._stop_timeout_timer()
        self._loop = None

    # -- host-driven controls (called on the GUI thread) ---------------------
    def request_shutdown(self) -> None:
        """Terminate the outstanding wait as a host shutdown.

        Distinct from a timeout and from a satisfied wait; it never fabricates a
        message. Called by the host shell's quit path.
        """

        self._shutdown_requested = True
        self.wake(None)

    # -- internals -----------------------------------------------------------
    def _stop_timeout_timer(self) -> None:
        if self._timeout_timer is not None:
            self._timeout_timer.stop()
            self._timeout_timer = None

    def _on_timeout(self) -> None:
        self._timeout_fired = True
        self.wake(None)
