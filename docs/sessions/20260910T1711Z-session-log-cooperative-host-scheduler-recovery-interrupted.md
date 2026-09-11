---
title: "Session log — cooperative host scheduler recovery interrupted by runaway response"
status: log
depends_on:
  - "../architecture/cooperative-host-scheduler.md"
  - "../architecture/platform-target.md"
  - "../apps/itidy/compatibility-notes.md"
  - "20260910T1132Z-session-log-cooperative-host-scheduler-interrupted.md"
citations_used: []
---

# Session log — cooperative host scheduler recovery interrupted (2026-09-10/11)

> **Recovery note:** Codex produced this summary because the local model again
> failed before producing a handoff. As in the preceding session, DSH compaction
> ran successfully (four full compactions plus tool-result pruning), but the
> final model response entered a repetitive reasoning loop and exhausted the
> 32,768-token generation allowance (`turn/end: max-tokens`). This summary also
> identifies and corrects an ABI regression introduced during that loop.

## Session prompts

Raw DSH session: `session-730dc1ed-7398-4af1-a08b-af456faabfb0`

Log: `/home/runuser/.dsh/sessions/--workspace-amiga-ui--/session-730dc1ed-7398-4af1-a08b-af456faabfb0/session.jsonl.zstd`

### Starting prompt (2026-09-10 17:11 UTC)

```text
You are recovering interrupted work in the amiga-ui repository.

The current branch is `feat/cooperative-host-scheduler`. It contains substantial uncommitted work from the previous DSH session. Preserve that work: do not reset the branch, discard changes, or start the implementation again from scratch.

Inspect:

- the current git status and complete diff;
- docs/architecture/cooperative-host-scheduler.md;
- the new scheduler and Qt scheduler backend;
- the changes to the host run path, event bridge, Exec/Intuition/GadTools libraries and launcher;
- the new and modified focused tests;
- the most recent DSH session log, which is available if historical context is useful.

The previous session ended because one model response reached its 32,768-token output limit. It did not finish or provide a reliable conclusion. Near the end it was investigating a segmentation fault when a Qt gadget activation attempted to enqueue an IntuiMessage while the target was parked in WaitPort and a nested Qt event loop was running. Its repeated speculation that all emulated-memory writes are unsafe in the nested loop is not an established fact.

Objective: recover, evaluate and complete the existing cooperative-host-scheduler increment without losing sound work.

First establish the actual state:

1. Summarise what the existing diff implements.
2. Run the smallest relevant non-interactive unit tests.
3. Reproduce the interactive Exit-button failure with the narrowest available smoke test.
4. Locate the exact crashing operation using concrete evidence such as instrumentation, a minimal reproduction, faulthandler or a debugger/backtrace where practical.
5. Distinguish among allocation safety, memory-write safety, re-entrant emulation, invalid/stale addresses and incorrect lifecycle/order assumptions. Do not select a cause merely because it seems plausible.

Then make the smallest architectural correction needed to complete the documented single-active-context cooperative scheduler.

Important constraints:

- Keep one Amiga execution context on one host thread.
- Preserve the explicit wait request/registration/outcome model described in the architecture document.
- Qt nested-loop state must remain a replaceable backend mechanism, not the stored representation of the Amiga wait.
- Host notifications are hints; readiness must be checked against the real Amiga-side condition.
- Do not fabricate messages or allow WaitPort to return successfully on an empty queue.
- Do not move emulated-memory allocation or mutation merely to avoid a crash unless its lifetime, ownership and validity are understood.
- Do not broaden this increment into a general multi-task scheduler.
- Preserve useful existing tests and add a focused regression test for the demonstrated fault.
- Keep reasoning concise. If an investigation starts cycling without new evidence, stop, record the uncertainty and choose a concrete diagnostic action.

Before committing, run the relevant focused tests, the interactive Exit-button smoke path and the normal repository checks. Commit and merge into `development` only if the coherent increment is genuinely working and gated.

When finished, leave a concise summary of what was retained or corrected, the demonstrated cause, verification, uncertainty and the next increment.
```

There were no additional human-authored prompts in this session.

## Practical progress

The session recovered past the earlier segmentation fault. Its later real-iTidy
run showed this sequence:

1. iTidy entered an empty `WaitPort` through the cooperative scheduler.
2. The projected Exit button was clicked.
3. A real message was queued and the wait completed as `satisfied`.
4. `WaitPort` returned the first queued message without consuming it.
5. iTidy consumed and replied to the message through `GT_GetIMsg` and
   `GT_ReplyIMsg`; the bridge released its allocation.
6. iTidy did not execute the expected `GID_CANCEL` handler and entered a second
   `WaitPort`, which reached the honest automation timeout.

This is meaningful progress: the scheduler and real message lifecycle reached
the application event loop. The remaining failure occurred during event-field
interpretation, not during host delivery or wake-up.

## ABI regression introduced by the session

While diagnosing the missing `GID_CANCEL`, the model compiled copied Amiga
structures with native host GCC. It replaced pointer fields with four-byte
integers but retained the host compiler's alignment rules, then incorrectly
treated the resulting `sizeof`/`offsetof` values as classic m68k ABI evidence.

It consequently changed settled layouts:

- `IntuiMessage`: size `0x30` to `0x38`, `Class@0x10` to `0x18`, and
  `IAddress@0x18` to `0x20`;
- `Gadget`: size `0x2C` to `0x30` and `GadgetID@0x26` to `0x28`; and
- `NewGadget.UserData`: `0x1A` to `0x1C`.

It also changed tests to assert the same incorrect assumptions and added
temporary file-writing diagnostics. Because producer, diagnostic and tests all
used the new offsets, the resulting message appeared self-consistent even though
the target read the established locations. This provides a direct explanation
for iTidy consuming the event without recognising `IDCMP_GADGETUP`/`GID_CANCEL`.

Codex subsequently restored the settled layouts selectively, retained the
useful scheduler/event changes, removed the temporary diagnostics, and added
explicit workflow warnings against native-host ABI inference.

## Harness/model performance

The session was industrious but poorly bounded: 247 model/tool steps, repeated
attempts to parse/disassemble the HUNK, several incorrect native compiler
experiments, and finally a long loop restating the same contradiction. Four DSH
compactions completed, so compaction was operating. The final request used about
97,800 prompt tokens and the response then consumed exactly 32,768 output tokens.

This is a model-control weakness as well as a prompting issue. The model failed
to consult a settled project decision before reopening it, confused field width
with target ABI alignment, altered tests to match its hypothesis, and did not
stop when its reasoning ceased producing evidence. A smaller model may make
this more likely, but the category is not unique to small models; explicit
evidence hierarchy, bounded diagnostics, regression tests, and a lower response
ceiling are still required.

## State after Codex recovery

The feature remains uncommitted and unfinished on
`feat/cooperative-host-scheduler`. The scheduler/event-route work is preserved.
The next model run should first execute focused tests and the interactive Exit
smoke with the restored ABI. It should not resume broad disassembly unless that
simple discriminating run still fails.

