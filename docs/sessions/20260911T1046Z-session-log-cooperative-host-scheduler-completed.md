---
title: "Session log — cooperative host scheduler completed: IntuiMessage target ABI corrected and merged"
status: log
depends_on:
  - "../architecture/cooperative-host-scheduler.md"
  - "../architecture/platform-target.md"
  - "../apps/itidy/compatibility-notes.md"
  - "20260910T1711Z-session-log-cooperative-host-scheduler-recovery-interrupted.md"
citations_used:
  - S27
  - S41
  - S42
---

# Session log — cooperative host scheduler completed (2026-09-11)

## Session prompts

Raw DSH session: `session-a739849d-386d-4b30-a58c-e29e4e0eaba4`
Log: `/home/runuser/.dsh/sessions/--workspace-amiga-ui--/session-a739849d-386d-4b30-a58c-e29e4e0eaba4/session.jsonl.zstd`

### Starting prompt (2026-09-11 10:46 UTC)

```text
You are working in the amiga-ui repository.

Continue from the existing branch `feat/cooperative-host-scheduler`. It is clean and contains the committed cooperative-scheduler implementation in commit `d2a0f79`. Do not reset it, recreate the work from `development`, or reopen settled ABI questions without new target-specific evidence.

Start by inspecting:

- AGENTS.md and the documentation map;
- docs/architecture/cooperative-host-scheduler.md;
- docs/architecture/hosted-application-mode.md;
- docs/architecture/platform-target.md;
- docs/workflows/error-driven-porting.md;
- docs/apps/itidy/compatibility-notes.md;
- the latest two summaries under docs/sessions;
- the complete diff from `development` to the current branch.

The latest two sessions ended when individual model responses entered repetitive reasoning loops and exhausted their output allowance. Codex subsequently restored the settled classic m68k structure offsets, removed unsafe diagnostics and detritus, corrected repo checks, documented the failures, and committed the recovered work. Treat the summaries as the authoritative handoff; use the raw DSH logs only if a specific unresolved detail requires them.

Objective: validate and complete the existing single-active-context cooperative host scheduler increment without broadening its architecture.

Begin with the simplest discriminating checks:

1. Run the focused scheduler, event-bridge, Qt activation, CLI and projection tests.
2. Run the existing real-iTidy interactive Exit-button smoke test with the restored ABI.
3. Determine whether the full intended event path now works:

   Qt Exit activation
   -> real IntuiMessage allocation
   -> Window.UserPort queue
   -> WaitPort wake
   -> GT_GetIMsg
   -> iTidy recognises IDCMP_GADGETUP and GID_CANCEL
   -> GT_ReplyIMsg
   -> CloseWindow
   -> host window closes
   -> target and host exit cleanly

If this path succeeds, remove only obsolete temporary diagnostic machinery, run the normal repository checks, and assess whether the increment is ready to merge into `development`.

If it still fails, identify the first demonstrated divergence using focused runtime evidence. Prefer tracing the produced and consumed IntuiMessage fields and the application's observed dispatch behavior. Do not begin broad disassembly or restructure the scheduler unless the current evidence specifically requires it.

Architectural constraints:

- Keep one active Amiga execution context on one host thread.
- Preserve the explicit wait request, registration and outcome model.
- Keep Qt's nested event loop as a replaceable backend mechanism, not the representation of the Amiga wait.
- Treat host notifications as hints and recheck the real Amiga-side readiness condition.
- Do not fabricate messages or make WaitPort succeed on an empty queue.
- Do not broaden this into a general multitasking scheduler.
- Preserve hosted application mode: the public Workbench screen remains invisible/notional and app-facing Amiga windows are host top-level windows.
- Do not introduce a cross-compiler for ABI investigation.
- Never use native host compiler structure layouts as evidence for classic m68k offsets or alignment.
- Use settled repo documentation, classic sources, focused memory evidence and, only when necessary, narrowly bounded target disassembly.
- Do not change ABI constants and their tests together merely to make an internal hypothesis self-consistent.
- Keep reasoning concise. If reasoning begins repeating without producing new evidence, stop and take one concrete diagnostic action.

Before merging, run the relevant focused tests, the real-iTidy interactive Exit smoke, pre-commit, and the normal repository checks. Account explicitly for any environment-dependent skipped or isolated GUI test.

If the cooperative scheduler increment is genuinely working and gated, merge `feat/cooperative-host-scheduler` into `development`. Do not advance to a new compatibility feature in the same session.

When finished, leave a concise summary of:

1. what was verified or corrected,
2. the observed real-iTidy event path,
3. checks run and their results,
4. remaining uncertainty,
5. whether the branch was merged,
6. the recommended next increment.
```

### Additional human prompts

- "Did you add a summary of the session under docs/session?"
- "Please add a summary of this session under docs/sessions, conforming to the style and format of the existing summaries in that dir."

All other `user/message` events in the raw log are harness-injected (AGENTS.md /
skill-catalog / runtime-context reminders and one auto-generated compaction
checkpoint) — not direct human requests.

## Purpose

Resume from a checkpoint and complete the single-active-context cooperative host
scheduler increment. The branch `feat/cooperative-host-scheduler` already held the
committed scheduler implementation (`d2a0f79`), but the real-iTidy Exit path was
still failing: the posted `IntuiMessage` reached the app and `WaitPort` resumed
satisfied, yet the app did not run the `GID_CANCEL` handler and the second
`WaitPort` timed out. The objective was to validate and complete the increment
without broadening the architecture, identify the first demonstrated divergence
with focused runtime evidence, and merge only if genuinely working and gated.

## Root cause (target-specific IntuiMessage layout)

The first demonstrated divergence was in **event-field interpretation**, not host
delivery or wake-up. Tracing the produced and consumed fields (the starting
prompt's preferred diagnostic) showed the bridge and the target disagreed on the
`IntuiMessage` field offsets.

Narrowly bounded disassembly of the shipped iTidy binary's event handler
(`handle_itidy_window_events`, runtime address `0x2f7be`) shows the app reads:

- `im_Class` from `msg+0x14` — byte-verified `28 6b 00 14` at `0x2f7f4`;
- `im_IAddress` from `msg+0x1c` — byte-verified `20 6b 00 1c` at `0x2f7fe`;
- `GadgetID` from `gad+0x26` — byte-verified `36 28 00 26` at `0x2f802`.

These are **+0x04** from the classic `IntuiMessage` offsets the bridge was
posting (`Class@0x10`, `IAddress@0x18`). The explanation consistent with the
disassembly: the iTidy binary was built against NDK headers whose `struct Message`
is **0x14 bytes** (one ULONG wider than the classic 0x10-byte layout), which
shifts every `IntuiMessage` field after `im_Message` by +0x04. With the classic
layout posted, the app read `0x00` at `msg+0x14`/`msg+0x1c` and never matched
`IDCMP_GADGETUP` (0x40) [S27], so `GID_CANCEL` was never dispatched.

This is a **target-specific** finding, established by the shipped binary (the
authority per the repo's evidence order) plus runtime memory evidence — not by the
classic NDK and not by a native host compiler. The native-host `sizeof`/`offsetof`
experiments from the earlier interrupted sessions (recorded in the recovery log)
are exactly the evidence class the starting prompt forbids; this finding uses
bounded target disassembly instead. The classic layout (size `0x30`,
`Class@0x10`, `IAddress@0x18`) is not wrong for a classic 0x10-byte
`struct Message` target — it is simply not the layout this particular shipped
binary consumes.

## The fix

Shifted the post-`im_Message` `IntuiMessage` field offsets by +0x04 in
`src/amiga_ui/vamos/event_bridge.py` to the target layout:

- `IMSG_SIZE` `0x30` → `0x34`
- `IMSG_OFF_CLASS` `0x10` → `0x14`
- `IMSG_OFF_CODE` `0x14` → `0x18`
- `IMSG_OFF_QUALIFIER` `0x16` → `0x1a`
- `IMSG_OFF_IADDRESS` `0x18` → `0x1c`
- `IMSG_OFF_MOUSEX` `0x1c` → `0x20`
- `IMSG_OFF_MOUSEY` `0x1e` → `0x22`
- `IMSG_OFF_SECONDS` `0x20` → `0x24`
- `IMSG_OFF_MICROS` `0x24` → `0x28`
- `IMSG_OFF_IDCMPWINDOW` `0x28` → `0x2c`
- `IMSG_OFF_SPECIALLINK` `0x2c` → `0x30`

The `im_Message` prefix (`ReplyMsg@0x00`, `Node@0x04`) was intentionally left at
classic offsets: the handler's `GT_GetIMsg`/`GT_ReplyIMsg` [S42] own that region and
the app does not read it for dispatch.

Also:

- Updated the layout test in `tests/test_event_bridge.py`
  (`test_intuimessage_itidy_target_layout`) to assert the target offsets.
- Corrected the authoritative `docs/apps/itidy/compatibility-notes.md` — its
  "Unresolved Struct-Offset Questions" section had recorded
  `IntuiMessage.IAddress@0x18` as settled; it now records the +0x04 target layout
  and its evidence.
- Removed only the obsolete temporary diagnostics (the env-gated
  `AMIGA_UI_DIAG_IMSG` blocks in `event_bridge.py` and `gadtools_library.py`);
  `gadtools_library.py` is fully reverted.

The ABI change is justified by genuine new target-specific evidence (target
disassembly of the real binary + runtime memory), satisfying the starting prompt's
"do not reopen settled ABI without new target-specific evidence" and "do not change
ABI constants and their tests together merely to make an internal hypothesis
self-consistent" constraints — the disassembly is independent of the repo's
producer, and the before/after runtime evidence discriminates.

## Verification

Reported exactly:

- **Full non-GUI unit suite** (19 modules): **Ran 203 tests, OK** (exit 0).
- **Qt offscreen suite** (`test_host_qt_gadget_projection`,
  `test_host_qt_projection`, `test_qt_gadget_activation`): **Ran 47 tests, OK**.
- **Real-iTidy interactive Exit smoke**
  (`uv run python -m tests.run_interactive_exit_smoke_test`, Xvfb-backed,
  in-process): **PASS** — `projected iTidy Exit gadget -> real IntuiMessage ->
  WaitPort resume -> clean exit`. With the fix the app reads `class@0x14 = 0x40`
  (IDCMP_GADGETUP [S27]) and `iaddress@0x1c` (gadget pointer), matches
  `GID_CANCEL`, replies via `GT_ReplyIMsg` [S42], closes the window, and exits
  cleanly (`exit_code 0`). The same smoke failed before the fix with
  `WaitPort outcome TIMEOUT` [S41] and `exit_code 1`.
- **`pre-commit`** (ruff check, ruff format, pyright, check-yaml): all **Passed**.
  (The pre-commit cache dir was read-only in this environment, so it was run with
  `PRE_COMMIT_HOME` pointed at a writable path — an environment detail, not a repo
  change.)

## Pre-existing lint blockers (cleared to pass the merge gate)

`pre-commit` surfaced 26 ruff findings plus one format issue that pre-date this
change (in `scheduler.py`, `qt_scheduler_backend.py`, and three test modules). To
pass the merge gate they were cleared and committed **separately** from the ABI fix
so the ABI commit stays focused:

- typing modernization (`typing.Optional` → `X | None`,
  `typing.Callable` → `collections.abc.Callable`);
- import sorting;
- two unused smoke-test imports removed;
- the frozen-`MessagePortWait` immutability test now asserts
  `dataclasses.FrozenInstanceError` instead of a blind `Exception` (B017);
- one `ruff format` reflow in `scheduler.py`.

## Approximations / uncertainty

- The exact `GID_CANCEL` branch that clears `continue_running` was **inferred**,
  not fully byte-traced; the byte-verified reads are `im_Class@0x14`,
  `im_IAddress@0x1c`, `GadgetID@0x26`. The passing smoke confirms the full path
  end-to-end, but the specific branch that stores `continue_running=FALSE` was not
  disassembled to that store.
- The `im_Message` prefix (`ReplyMsg@0x00`, `Node@0x04`) was left at classic
  offsets because the handler's `GT_GetIMsg`/`GT_ReplyIMsg` [S42] own that region
  and the app does not read it for dispatch; this is validated by the working
  smoke but not independently disassembled.
- The layout is **target-specific**: the bridge now hardcodes the iTidy layout
  (a 0x14-byte `struct Message`). A target built against a classic 0x10-byte
  `struct Message` would need the classic offsets, so a second differently-compiled
  target would require per-target layout selection rather than reopening this ABI.

## Merge and state after session

The increment is working and gated, so `feat/cooperative-host-scheduler` was
**merged into `development`** (fast-forward; `development` now at `2f559c3`). Two
commits were added on the branch:

- `7c0275e` — "Fix IntuiMessage field offsets for the iTidy target" (the ABI fix +
  test + notes);
- `2f559c3` — "Satisfy the pre-commit lint gate" (the lint fixes).

Per the repo workflow, the feature branch was **not** deleted, and no new
compatibility feature was started in this session.

## Next increment (deliberately deferred)

From a fresh branch off the updated `development`, the natural next steps are:

1. Byte-verify the `GID_CANCEL` branch (the store that clears `continue_running`)
   and the `im_Message`-prefix assumption, converting the two remaining
   uncertainties into documented, disassembly-backed findings.
2. If a second target is introduced, make the `IntuiMessage` layout target-aware
   (classic 0x10-byte vs. 0x14-byte `struct Message`) rather than hardcoding the
   iTidy layout — generalizing the event bridge without reopening the now-settled
   iTidy ABI.
