---
title: "Session log — cooperative host scheduler implementation interrupted by runaway response"
status: log
depends_on:
  - "../architecture/cooperative-host-scheduler.md"
  - "../architecture/hosted-application-mode.md"
  - "../apps/itidy/compatibility-notes.md"
  - "20260909T2218Z-session-log-iTidy-gadtools-qt-projection.md"
citations_used: []
---

# Session log — cooperative host scheduler implementation interrupted (2026-09-10)

> **Recovery note:** Codex produced this summary after the local-model session
> failed during compaction-era operation and did not produce its requested
> handoff. Compaction itself ran twice successfully. The terminal failure was a
> single runaway model response which repeated speculative reasoning until it
> reached the 32,768-token generation limit (`turn/end: max-tokens`). Treat this
> as an incomplete recovery record, not a claim that the feature was finished.

## Session prompts

Raw DSH session: `session-7ab723bb-c626-4d80-9249-400b285fec1f`

Log: `/home/runuser/.dsh/sessions/--workspace-amiga-ui--/session-7ab723bb-c626-4d80-9249-400b285fec1f/session.jsonl.zstd`

### Starting prompt (2026-09-10 11:32 UTC)

The starting prompt instructed the model to work from `development`, inspect
the scheduler, hosted-application, translation, GUI-threading and latest-session
documentation, and implement the architecture already settled in
`docs/architecture/cooperative-host-scheduler.md`.

Its required milestone was the complete path:

```text
Qt gadget activation
-> semantic gadget event
-> real IntuiMessage allocation
-> real Window.UserPort queue
-> WaitPort resumes
-> GT_GetIMsg removes the message
-> iTidy dispatches the real GadgetID
-> GT_ReplyIMsg releases the message
-> iTidy calls CloseWindow
-> the host projection closes
-> target and host lifecycle exit cleanly
```

The prompt required a single active Amiga execution context on the GUI thread,
an immutable wait request, explicit registration and outcomes, a Qt-free core,
a replaceable Qt event-service backend, resource-specific wake hints, readiness
checks against the real port, and honest timeout/shutdown/headless behavior. It
explicitly prohibited worker-thread vamos execution, polling, fabricated
messages, a general Amiga scheduler, and reopening documented structure-offset
questions without directly relevant discriminating evidence. It also required
focused scheduler, bridge, Qt and real-iTidy tests plus normal project gates and
a final session summary.

There were no additional human-authored prompts in this session.

## Work left in the working tree

The session created a substantial uncommitted implementation on
`feat/cooperative-host-scheduler`:

- a Qt-free scheduler core with message-port requests, registrations, unique
  tokens, explicit outcomes and a single-active-context guard;
- a Qt backend using a controlled nested `QEventLoop` and one-shot timeout;
- `WaitPort` integration which preserves immediate queue-peek behavior and the
  honest unsupported boundary when no interactive scheduler is installed;
- scheduler plumbing through the graphical run path and vamos library contexts;
- generic address-based Qt button activation routed through the event bridge;
- message-port notification after real queue insertion;
- stale gadget/window guards and lifecycle cleanup;
- focused scheduler, event-bridge and Qt tests; and
- an Xvfb-backed real-iTidy Exit-button smoke test.

None of this work was committed or merged.

## Verified progress and stopping point

The focused implementation had progressed far enough for the Qt shell to remain
responsive while iTidy was parked in `WaitPort`. The unresolved integration run
then crashed while the Qt activation callback attempted to construct or enqueue
an `IntuiMessage` in emulated memory.

The final response repeatedly proposed and withdrew explanations involving
allocation and memory writes during the nested event loop. It established no
reliable root cause before exhausting its output limit. Those final speculative
claims must not be treated as architecture evidence.

## Harness/model performance

DSH performed two full compactions and multiple tool-result prunes. The final
request contained about 113,500 cached prompt tokens; the model then generated
the full 32,768-token response allowance. llama.cpp reported 146,604 resident
tokens inside its 163,840-token Q6 context and no truncation. The failure was
therefore a runaway generation which compaction could not interrupt, rather
than rejection of an oversized prompt.

The model produced substantial coherent code before the failure, but its final
debugging phase showed severe repetition, failure to notice that no new evidence
was being obtained, and increasing confidence in mutually inconsistent causes.

## Recovery recommendation recorded at the time

Preserve the branch and inspect the existing diff rather than restarting. Use a
fresh session to reproduce the crash narrowly and distinguish allocation,
memory-write, invalid-address, lifecycle and re-entrancy hypotheses using
concrete instrumentation or a backtrace. Do not carry the exhausted session's
speculative conclusion forward.

