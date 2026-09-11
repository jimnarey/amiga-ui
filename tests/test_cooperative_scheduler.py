"""Qt-free unit tests for the cooperative host scheduler core.

These exercise the single-active-context cooperative wait design from
``docs/architecture/cooperative-host-scheduler.md`` using a synchronous
:class:`FakeBackend` (no Qt, no threads): the scheduler's wait representation,
readiness discipline, resource-specific notification hints, nested-wait
rejection, defensive recheck, wait-bound application, and cleanup in every
exit path. The Qt event-loop backend (``qt_scheduler_backend``) is tested
separately (it needs a QApplication); here the backend is a scripted stand-in.
"""

from __future__ import annotations

import time
import unittest

from amiga_ui.host.scheduler import (
    EXECUTION_CONTEXT_ID,
    HostEventServiceBackend,
    MessagePortWait,
    SchedulerBusyError,
    WaitOutcome,
    WaitRegistration,
    WaitResource,
    CooperativeHostScheduler,
)

PORT = 0x00A1B2C0
OTHER_PORT = 0x00D00000


class FakeBackend(HostEventServiceBackend):
    """Synchronous scripted backend: services host events, rechecks readiness.

    ``events`` are callables run in order while "blocking" (each simulates one
    host event, e.g. a projected gadget activation that enqueues a real message
    and/or satisfies the condition). After each event the backend rechecks
    ``readiness``; when it is true the wait is satisfied. If no event satisfies
    the condition, the backend returns ``terminal`` (or ``UNSUPPORTED`` when
    ``terminal`` is ``None``) — the honest non-interactive / terminal outcome.
    """

    def __init__(self, events=(), terminal=None):
        self.events = list(events)
        self.terminal = terminal
        self.service_calls: list[dict] = []
        self.wake_calls: list[WaitRegistration | None] = []
        self.cleanup_calls: list[WaitRegistration] = []

    def service_until_ready(self, registration, readiness, deadline) -> WaitOutcome:
        self.service_calls.append({"registration": registration, "deadline": deadline})
        if readiness():
            return WaitOutcome.SATISFIED
        for event in self.events:
            event()
            if readiness():
                return WaitOutcome.SATISFIED
        return self.terminal if self.terminal is not None else WaitOutcome.UNSUPPORTED

    def wake(self, registration) -> None:
        self.wake_calls.append(registration)

    def cleanup(self, registration) -> None:
        self.cleanup_calls.append(registration)


class MessagePortWaitRequestTest(unittest.TestCase):
    def test_request_names_port_and_resource(self) -> None:
        request = MessagePortWait(port_addr=PORT)
        self.assertIs(request.resource, WaitResource.MESSAGE_PORT)
        self.assertEqual(request.port_addr, PORT)

    def test_request_rejects_invalid_port(self) -> None:
        with self.assertRaises(ValueError):
            MessagePortWait(port_addr=0)

    def test_request_is_immutable(self) -> None:
        request = MessagePortWait(port_addr=PORT)
        with self.assertRaises(Exception):
            request.port_addr = OTHER_PORT  # type: ignore[misc]


class RunWaitTest(unittest.TestCase):
    def test_immediate_satisfaction_does_not_enter_backend(self) -> None:
        backend = FakeBackend()
        scheduler = CooperativeHostScheduler(backend)
        outcome = scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: True)
        self.assertIs(outcome, WaitOutcome.SATISFIED)
        self.assertEqual(backend.service_calls, [])  # no backend entry
        self.assertIsNone(scheduler.active)
        self.assertIs(scheduler.last_outcome, WaitOutcome.SATISFIED)

    def test_satisfaction_via_host_event_creates_registration(self) -> None:
        ready = {"v": False}
        backend = FakeBackend(events=[lambda: ready.__setitem__("v", True)])
        scheduler = CooperativeHostScheduler(backend)
        outcome = scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: ready["v"])
        self.assertIs(outcome, WaitOutcome.SATISFIED)
        self.assertEqual(len(backend.service_calls), 1)
        reg = backend.service_calls[0]["registration"]
        self.assertEqual(reg.request.port_addr, PORT)
        self.assertIs(reg.request.resource, WaitResource.MESSAGE_PORT)
        self.assertEqual(reg.execution_context, EXECUTION_CONTEXT_ID)
        self.assertEqual(reg.state, "satisfied")
        self.assertIs(reg.outcome, WaitOutcome.SATISFIED)
        self.assertIsInstance(reg.token, int)
        # Cleaned up in the exit path; no outstanding wait afterwards.
        self.assertEqual(backend.cleanup_calls, [reg])
        self.assertIsNone(scheduler.active)
        self.assertIs(scheduler.last_outcome, WaitOutcome.SATISFIED)

    def test_unique_tokens_across_waits(self) -> None:
        ready = {"v": False}
        backend = FakeBackend(events=[lambda: ready.__setitem__("v", True)])
        scheduler = CooperativeHostScheduler(backend)
        scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: ready["v"])
        ready["v"] = False
        backend.events = [lambda: ready.__setitem__("v", True)]
        scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: ready["v"])
        tokens = [c["registration"].token for c in backend.service_calls]
        self.assertEqual(tokens, sorted(tokens))
        self.assertEqual(len(set(tokens)), len(tokens))  # unique

    def test_timeout_outcome(self) -> None:
        backend = FakeBackend(terminal=WaitOutcome.TIMEOUT)
        scheduler = CooperativeHostScheduler(backend)
        outcome = scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: False)
        self.assertIs(outcome, WaitOutcome.TIMEOUT)
        self.assertIs(scheduler.last_outcome, WaitOutcome.TIMEOUT)
        self.assertIsNone(scheduler.active)
        self.assertEqual(len(backend.cleanup_calls), 1)

    def test_shutdown_outcome(self) -> None:
        backend = FakeBackend(terminal=WaitOutcome.SHUTDOWN)
        scheduler = CooperativeHostScheduler(backend)
        outcome = scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: False)
        self.assertIs(outcome, WaitOutcome.SHUTDOWN)
        self.assertIsNone(scheduler.active)
        self.assertEqual(len(backend.cleanup_calls), 1)

    def test_unsupported_outcome_when_nothing_satisfies(self) -> None:
        backend = FakeBackend()  # no events, no terminal
        scheduler = CooperativeHostScheduler(backend)
        outcome = scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: False)
        self.assertIs(outcome, WaitOutcome.UNSUPPORTED)
        self.assertIsNone(scheduler.active)
        self.assertEqual(len(backend.cleanup_calls), 1)

    def test_defensive_recheck_downgrades_stale_satisfaction(self) -> None:
        # The backend reports SATISFIED but the real condition is still false:
        # the facade must not let that become a normal WaitPort return.
        class LyingBackend(HostEventServiceBackend):
            def service_until_ready(self, registration, readiness, deadline):
                return WaitOutcome.SATISFIED

            def wake(self, registration):
                pass

            def cleanup(self, registration):
                pass

        scheduler = CooperativeHostScheduler(LyingBackend())
        outcome = scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: False)
        self.assertIs(outcome, WaitOutcome.UNSUPPORTED)

    def test_wait_bound_applies_to_implicit_deadline(self) -> None:
        backend = FakeBackend(terminal=WaitOutcome.TIMEOUT)
        scheduler = CooperativeHostScheduler(backend)
        scheduler.set_wait_bound(30.0)
        scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: False)
        deadline = backend.service_calls[0]["deadline"]
        now = time.monotonic()
        self.assertIsNotNone(deadline)
        self.assertGreaterEqual(deadline - now, 29.0)
        self.assertLessEqual(deadline - now, 30.001)

    def test_no_wait_bound_means_no_deadline(self) -> None:
        backend = FakeBackend(terminal=WaitOutcome.TIMEOUT)
        scheduler = CooperativeHostScheduler(backend)
        scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: False)
        self.assertIsNone(backend.service_calls[0]["deadline"])


class NotificationTest(unittest.TestCase):
    def _wait_with_event(self, event, *, ready=lambda: False):
        backend = FakeBackend(events=[event], terminal=WaitOutcome.TIMEOUT)
        scheduler = CooperativeHostScheduler(backend)
        outcome = scheduler.run_wait(MessagePortWait(port_addr=PORT), ready)
        return scheduler, backend, outcome

    def test_matching_port_hint_wakes(self) -> None:
        ready = {"v": False}
        holder: dict = {}

        def event():
            # A matching hint for the active wait's port, then the condition is
            # genuinely satisfied (as a real posted message would do).
            holder["scheduler"].notify_resource_changed(WaitResource.MESSAGE_PORT, PORT)
            ready["v"] = True

        backend = FakeBackend(events=[event], terminal=WaitOutcome.TIMEOUT)
        scheduler = CooperativeHostScheduler(backend)
        holder["scheduler"] = scheduler
        outcome = scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: ready["v"])
        self.assertIs(outcome, WaitOutcome.SATISFIED)
        self.assertEqual(len(backend.wake_calls), 1)
        assert backend.wake_calls[0] is not None
        self.assertIs(backend.wake_calls[0].request.port_addr, PORT)

    def test_different_port_hint_is_ignored(self) -> None:
        ready = {"v": False}
        holder: dict = {}

        def event():
            holder["scheduler"].notify_resource_changed(WaitResource.MESSAGE_PORT, OTHER_PORT)
            ready["v"] = True

        backend = FakeBackend(events=[event], terminal=WaitOutcome.TIMEOUT)
        scheduler = CooperativeHostScheduler(backend)
        holder["scheduler"] = scheduler
        outcome = scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: ready["v"])
        self.assertIs(outcome, WaitOutcome.SATISFIED)
        self.assertEqual(backend.wake_calls, [])  # a different port: no wake

    def test_stale_notification_with_no_active_wait_is_noop(self) -> None:
        backend = FakeBackend()
        scheduler = CooperativeHostScheduler(backend)
        # No outstanding wait: a resource-change hint is dropped.
        scheduler.notify_resource_changed(WaitResource.MESSAGE_PORT, PORT)
        self.assertEqual(backend.wake_calls, [])


class NestedWaitTest(unittest.TestCase):
    def test_second_independently_active_wait_is_rejected(self) -> None:
        backend = FakeBackend()
        scheduler = CooperativeHostScheduler(backend)
        nested_raised = {"v": False}

        def outer_event():
            # While the outer wait is active, a nested WaitPort (a second
            # independently active wait) must be rejected explicitly.
            try:
                scheduler.run_wait(MessagePortWait(port_addr=OTHER_PORT), lambda: False)
            except SchedulerBusyError:
                nested_raised["v"] = True

        backend.events = [outer_event]
        backend.terminal = WaitOutcome.TIMEOUT
        outcome = scheduler.run_wait(MessagePortWait(port_addr=PORT), lambda: False)
        self.assertIs(outcome, WaitOutcome.TIMEOUT)
        self.assertTrue(nested_raised["v"])
        # The outer registration survived the rejected nested attempt.
        self.assertIsNone(scheduler.active)


if __name__ == "__main__":
    unittest.main()
