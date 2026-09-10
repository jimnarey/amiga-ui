---
title: "Cooperative Host Scheduler"
status: draft
depends_on:
  - "hosted-application-mode.md"
  - "translation-pipeline.md"
  - "../host-gui/threading-and-desktop-boundaries.md"
  - "../platform/library-cards/exec.library.md"
citations_used:
  - "S27"
  - "S40"
  - "S41"
---

# Cooperative Host Scheduler

Purpose: Define how a synchronously executing Amiga application can block in
an intercepted OS call while the host Qt interface remains responsive and can
produce the event that satisfies the block.

Needed for:
- Delivering real host interactions through `IntuiMessage` and Exec ports.
- Preventing `WaitPort` from becoming a Qt-specific or polling implementation.
- Keeping the first interactive runtime extensible without prematurely building
  an Amiga multitasking scheduler.

Notes:
- This is a project architecture decision for the first interactive hosted-app
  runtime, not a claim that a single host thread reproduces Amiga scheduling.
- The initial implementation has one active Amiga execution context and one
  supported wait condition: a message becoming available on a `MsgPort`.

## Decision

Use a **single-active-context cooperative host scheduler**. The Amiga target,
repo-owned library implementations, emulated memory, message queues, host
projection, and Qt widgets continue to be serviced on the GUI thread.

When target execution reaches a supported blocking OS operation whose condition
is not yet true, the operation delegates to a Qt-free scheduler interface. The
interactive Qt backend services host events until the actual Amiga-side
condition becomes true. The library operation then rechecks the condition and
returns its normal Amiga result.

For the first implementation, the Python call stack may remain parked inside
`WaitPort` while the Qt backend runs a controlled nested event loop. That is an
implementation technique behind the scheduler boundary, not part of Exec's
public semantics and not a commitment to use nested loops forever.

This decision does **not** introduce multiple emulated tasks, CPU-context
switching, priorities, pre-emption, or a general Amiga scheduler.

## Why One Thread

Vamos and the repo-owned libraries directly share emulated memory, allocation
state, message-port queues, gadget registrations, RastPort streams, and window
projection mappings. Their current implementations do not provide a concurrency
contract. Keeping one owner thread means a host callback cannot race target code
while either side is allocating an `IntuiMessage`, closing a window, freeing a
gadget, or changing a port queue.

Qt also requires widgets to be created and mutated on their owning GUI thread.
A one-thread design therefore avoids both a new locking protocol for the
compatibility layer and pervasive cross-thread marshalling for the host GUI.
The event trace remains serial and reproducible:

```text
WaitPort enters
-> host scheduler services Qt
-> widget signal is translated
-> complete IntuiMessage is allocated and queued
-> wait condition becomes true
-> scheduler returns
-> WaitPort rechecks and returns without consuming
-> GT_GetIMsg removes the message
-> application handles it
-> GT_ReplyIMsg releases it
```

## Architectural Boundary

The compatibility libraries must not import Qt or construct a `QEventLoop`.
They should see a small host-scheduling interface installed on the run context.
Names below are illustrative; the semantic separation is required even if the
implementation chooses different Python names.

```python
@dataclass(frozen=True)
class MessagePortWait:
    port_addr: int


class HostCooperativeScheduler(Protocol):
    def register(self, request: MessagePortWait, execution_id: object) -> WaitRegistration: ...
    def block_current(self, registration: WaitRegistration) -> WaitOutcome: ...
    def unregister(self, registration: WaitRegistration) -> None: ...
    def notify_resource_changed(self, resource_kind: WaitResource, address: int) -> None: ...
```

The first request represents **wait for this message port to become non-empty**.
It is immutable data, not a closure over `ctx`, emulated memory, Qt objects, or
the current Python call stack. Readiness is evaluated by the compatibility/runtime
layer that owns the port model. A host notification only says the named resource
may have changed; only a rechecked port queue permits `WaitPort` to return
normally.

The initial scheduler has a single explicit execution identity. This may be a
singleton token, but it must not be hidden as an accidental global assumption.
Attempting to register a second independently active execution context should
fail explicitly. A later scheduler can replace the singleton with an emulated
task or saved CPU-context identity while retaining the request and registration
model.

`WaitOutcome` must distinguish at least:

- condition satisfied;
- host shutdown;
- automation or diagnostic timeout;
- unsupported/non-interactive environment.

Only `condition satisfied` is an ordinary Amiga wake. Shutdown and timeout are
host lifecycle outcomes and must not be converted into fabricated messages or a
successful empty `WaitPort`.

## Future-Compatible Internal Shape

Keep five responsibilities distinct even though the first implementation is
small:

1. **Wait request:** immutable, declarative data describing the Amiga resource
   and condition, such as `MessagePortWait(port_addr)`.
2. **Readiness evaluation:** runtime-owned inspection of the real Amiga-side
   state. It must not depend on Qt or on a wake notification being accurate.
3. **Registration:** a scheduler-owned record associating one request with an
   explicit execution identity and lifecycle token.
4. **Host event service:** a replaceable backend that allows external events to
   occur while the execution context is blocked.
5. **Resumption:** the mechanism that continues the registered execution only
   after readiness or produces an explicit non-Amiga outcome.

The first synchronous API may offer a convenience operation equivalent to
`wait_until(request)`, but it must be implemented as a façade over explicit
registration, blocking, readiness checks, and unregister cleanup. It must not
make a parked Python call stack the scheduler's stored representation of a wait.

Likewise, the first implementation may store only one registration, but the
registration should still carry:

- a unique token or generation;
- the immutable request;
- the singleton execution identity;
- its active/completed/cancelled state;
- and its final `WaitOutcome`, if any.

This prevents stale Qt callbacks from satisfying a later wait and gives cleanup
one unambiguous object to invalidate. Registration must be removed in a `finally`
path after success, shutdown, timeout, or exception.

Notifications are resource-specific. Message delivery should call the semantic
equivalent of:

```python
scheduler.notify_resource_changed(WaitResource.MESSAGE_PORT, port_addr)
```

Do not expose a context-free `wake()` as the normal producer API. A later
scheduler may have waits for several ports, signal masks, or timers; naming the
changed resource allows it to find the relevant registrations without changing
event producers. Notifications remain hints and may be coalesced, duplicated,
or stale, so they never replace readiness evaluation.

The scheduler core owns registrations and outcomes, but it does not own
`QApplication`, widgets, projected windows, or the complete GUI-command
lifecycle. The Qt backend services host events for the scheduler. Keeping that
direction of dependency allows a future outer event loop or resumable CPU runner
to replace `block_current` without changing wait requests, readiness logic, or
host-to-Amiga event translation.

## `WaitPort` Contract

The classic path remains `WaitPort` followed by message removal through
`GetMsg` or `GT_GetIMsg` [S40 §FUNCTION ¶1-5] [S41 §FUNCTION ¶1-5]. The scheduler
does not consume the message.

The implementation sequence is:

1. Validate and inspect the requested port.
2. If a message is already queued, return according to the normal `WaitPort`
   contract without entering the host scheduler.
3. If no interactive scheduler is installed, retain the existing honest
   headless boundary; do not report success.
4. Otherwise construct an immutable port-non-empty request, register it against
   the singleton execution identity, and enter the scheduler's synchronous
   blocking façade.
5. After every backend wake, recheck the real queue. A spurious wake continues
   waiting.
6. On a satisfied outcome, return the queued head without removing it.
7. Unregister in every exit path and propagate host shutdown, timeout,
   unsupported nesting, and internal errors as explicit non-Amiga outcomes.

This preserves ordinary headless probes: installing the Qt scheduler is an
explicit property of the graphical `run` path, not a change to default Exec
behavior.

## Qt Backend

The first Qt backend may use a nested `QEventLoop` while the target call stack
is stopped inside the scheduler's synchronous blocking façade. This keeps paint,
input, timer, and window-system events flowing on the GUI thread. The nested loop
belongs only to this backend; it is not the registration store, readiness model,
or scheduler lifecycle.

The backend must:

- allow only one supported active wait unless nesting is deliberately modelled;
- keep the active registration and termination outcome explicit;
- respond only to relevant resource-change notifications while tolerating
  spurious or stale ones;
- recheck rather than trusting the wake notification;
- distinguish test timeout from an Amiga event;
- terminate cleanly on host shutdown or projection teardown;
- disconnect temporary signals and clear active-wait state on every exit path;
- avoid `QApplication.processEvents()` polling loops and background polling
  timers.

Qt callbacks may translate host input and update projection bookkeeping, but
must not independently resume or recursively execute arbitrary target code.
Resumption occurs only when control returns through the scheduler to the blocked
library call.

## Host Input Translation

An event becomes eligible to wake the target only after it has been translated
into complete Amiga-side state. For a GadTools activation:

1. The projected widget carries the owning Amiga window and gadget addresses.
2. The signal is converted into an `IDCMP_GADGETUP` intent.
3. The event bridge verifies that the window requested that IDCMP class.
4. It allocates and fills a real `struct IntuiMessage`.
5. `IAddress` identifies the real emulated gadget, carrying its real
   `GadgetID`.
6. The message is enqueued on that window's real `UserPort`.
7. The scheduler receives a resource-specific notification naming that
   `UserPort` as possibly changed.

Intuition communicates application input primarily through IDCMP messages
[S27 §Communicating with Intuition ¶1-4] [S27 §The IDCMP ¶1-3]. A Qt signal is
therefore only the producer-side trigger; it is not itself the event consumed by
the Amiga application.

Checkboxes, cycles, strings, sliders, and similar gadgets may require their
Amiga-side state to be updated before the message is enqueued. That behavior
must be implemented per gadget kind rather than inferred from the generic
scheduler.

## Window Close Semantics

A host window-manager close request must not immediately destroy the projection
when the Amiga window requested `IDCMP_CLOSEWINDOW`.

The host window should defer the close, enqueue a real close-window message, and
wake the scheduler. The application remains responsible for handling the event
and calling `CloseWindow`; that call then releases the Amiga state and closes the
host projection. An explicit forced host shutdown remains possible, but it is a
host lifecycle outcome rather than a fabricated application acknowledgement.

Repeated close requests, late signals, and a projection already being released
must be idempotent.

## First End-To-End Milestone

Use the projected iTidy Exit button as the first proof:

1. Launch iTidy through the graphical command.
2. Let the target enter `WaitPort` with an empty real `UserPort`.
3. Keep the host window responsive through the cooperative scheduler.
4. Activate the projected Exit gadget.
5. Deliver a real `IDCMP_GADGETUP` message with the real gadget address and ID.
6. Let `WaitPort -> GT_GetIMsg -> application dispatch -> GT_ReplyIMsg` run.
7. Observe the application call `CloseWindow` and release the projection.
8. Exit the target and host lifecycle cleanly.

The gadget must be identified through projection state, not by matching the
label "Exit" in production code. Tests may locate it by accessible properties
when initiating the interaction, but the delivered identity must still be the
recorded Amiga gadget identity.

Host-window close translation is the next case if it fits the same mechanism
without broadening the increment.

## Testing Obligations

Test the scheduler without Qt first:

- an already-satisfied condition does not enter the backend;
- an unsatisfied condition enters it and resumes only after becoming true;
- a spurious wake does not produce success;
- a notification for a different port does not satisfy the active registration;
- a stale registration token cannot wake a later wait;
- the scheduler never removes a port message;
- shutdown and timeout are distinguishable from satisfaction;
- unsupported nested waits fail explicitly;
- cleanup runs after success, cancellation, and exceptions.

Then test the Qt backend and full route:

- the GUI remains paintable and responsive while the target is in `WaitPort`;
- clicking a generic projected gadget enqueues the correct complete message;
- the target consumes and replies to that message through the existing APIs;
- clicking iTidy's projected Exit gadget causes application-driven close;
- a host close request becomes `IDCMP_CLOSEWINDOW` rather than immediate
  destruction;
- a headless probe retains the honest empty-queue boundary and imports no Qt;
- automation timeout terminates the host wait without masquerading as an Amiga
  event.

Tests should assert the port queue and message lifecycle, not merely that a Qt
signal fired or a window disappeared.

## Evolution Path

The scheduler interface is deliberately broader than its first backend. Later
immutable host-cooperative requests may cover an Exec signal mask, timer
completion, requester response, or another host-produced result. Add one only
when a real target reaches it. A future resumable runtime should replace the
synchronous `block_current` technique while preserving requests, registrations,
resource notifications, readiness evaluation, and outcomes.

The following pressure would require reassessing the single-context design:

- two Amiga tasks must make progress independently;
- one emulated task must wake another while the first is blocked;
- asynchronous device completion requires saved runnable contexts;
- target code must remain responsive during long execution outside intercepted
  blocking calls;
- correct behavior depends on task priorities, pre-emption, or Forbid/Permit.

At that point the project may need resumable 68k CPU contexts, ready/waiting task
queues, general signal delivery, and integration below the current library-call
override layer. That is a general Amiga scheduler and a separate architectural
decision. The host wait conditions, event translation, lifecycle outcomes, and
tests from this design should remain useful inputs, but they do not make that
larger scheduler automatic.

## Non-Goals

The first cooperative host scheduler does not implement:

- multiple runnable Amiga tasks;
- CPU context switching or instruction-budget pre-emption;
- general `Wait()` masks;
- timer or device scheduling;
- subprocess scheduling;
- worker-thread execution of vamos;
- arbitrary re-entrant target callbacks from Qt;
- polling that makes an empty `WaitPort` appear successful.

## Working Rule

Treat a blocking Amiga API as a declared wait condition. Let the host service
events while that condition is false, translate host outcomes into complete
Amiga-side state, and resume only after rechecking that the real condition is
true. Generalise the condition vocabulary only under concrete target pressure;
do not generalise prematurely into Amiga task scheduling.
