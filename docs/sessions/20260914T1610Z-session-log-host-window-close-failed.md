---
title: "Session log — host window-close increment failed (compaction stream-idle-timeout loop)"
status: log
depends_on:
  - "../architecture/cooperative-host-scheduler.md"
  - "../architecture/hosted-application-mode.md"
  - "../apps/itidy/compatibility-notes.md"
  - "20260911T1046Z-session-log-cooperative-host-scheduler-completed.md"
citations_used: []
---

# Session log — host window-close increment failed (2026-09-14)

> **Recovery note:** Claude (Sonnet 5) wrote this summary after the local-model
> session failed to reach its own requested handoff. Unlike the two 2026-09-10
> interruptions, this was not a runaway-reasoning failure: the session was
> restarted with `reasoning_effort` correctly defaulted to `low` for this
> model (a fix applied and verified earlier the same day), and it never
> entered a repetitive-reasoning pattern. Instead, every attempted context
> compaction on this session failed with the same infrastructure error
> (`pi-ai stream idle timeout after 300000ms`), driving the session into a
> compact-fail / retry loop for roughly two and a half hours until the user
> manually aborted it. Treat this as an incomplete-but-diagnosable record: the
> code the model produced was inspected directly (not summarized by the model
> itself), and the infrastructure fault that stalled the session has since
> been fixed outside this repository, in the DeepSeek Harness / llama.cpp
> deployment config, not in `amiga-ui`.

## Session prompts

Raw DSH session: `session-f5a86480-a59a-4776-accb-33dd7bd0024c`
Log: `/home/runuser/.dsh/sessions/--workspace-amiga-ui--/session-f5a86480-a59a-4776-accb-33dd7bd0024c/session.jsonl.zstd`

### Starting prompt (2026-09-14 16:10 UTC)

```text
You are working in the amiga-ui repository.

Start from the updated `development` branch (currently at commit `4430fe5`, which
already contains the merged cooperative host scheduler and the corrected
IntuiMessage ABI). Create a fresh branch for this blocker:

    git checkout development
    git checkout -b feat/host-window-close

Start by inspecting:

- AGENTS.md and the documentation map;
- docs/architecture/cooperative-host-scheduler.md, specifically the "Window
  Close Semantics" section;
- docs/architecture/hosted-application-mode.md;
- docs/apps/itidy/compatibility-notes.md and the latest entries in
  docs/apps/itidy/run-log.md;
- the most recent session summary under docs/sessions
  (20260911T1046Z-session-log-cooperative-host-scheduler-completed.md);
- src/amiga_ui/vamos/event_bridge.py, especially `schedule_close_window`
  (already implemented) and how `schedule_gadget_up` checks the window's
  requested IDCMP flags before scheduling;
- tests/test_event_bridge.py, the existing close-window bridge tests (these
  already pass — they prove the message-construction half of this path is
  correct; do not re-derive it);
- src/amiga_ui/host/qt_projection.py, specifically `AmigaHostWindow` and
  `QtHostWindowProjection.close_window` (the *app-driven* release path, called
  when the target calls `CloseWindow` — this is NOT currently reachable from a
  host window-manager close request);
- tests/run_interactive_exit_smoke_test.py, as the pattern to mirror for a new
  interactive close smoke test.

Objective: wire a real host window-manager close request (the OS close button /
QCloseEvent on a projected window) through the same validated mechanism the
Exit-gadget path already uses, instead of letting Qt destroy the widget
directly. Do not broaden this into general window-management or menu work.

[... six numbered implementation steps, architectural constraints, and a
pre-merge checklist, matching the format of prior session prompts in this log
— omitted here for length; the full text is in the raw DSH session log above.]
```

There were no additional human-authored prompts in this session; the user
observed and discussed the session's behavior in a separate conversation with
Claude while it ran, but did not send it further instructions.

## Work left in the working tree

The session produced a small, uncommitted implementation on
`feat/host-window-close` (branch created, but at the same commit as
`development` — `4430fe5` — nothing was ever committed):

- `AmigaHostWindow.closeEvent`: a host close request is refused
  (`event.ignore()`) and forwarded, by the widget's real Amiga `struct
  Window *`, to the projection, exactly mirroring the existing gadget-click
  address-based pattern;
- `QtHostWindowProjection._on_close_request`: routes the forwarded address to
  the event bridge, returning whether the window is still projected (so a
  request racing the app's own release is told to let the close proceed);
- `IntuitionEventBridge.request_close_window`: the live counterpart of the
  existing `schedule_close_window`, with the same window-open and
  `IDCMP_CLOSEWINDOW`-requested checks used by `gadget_up`, plus a
  `_close_pending` dict making repeated host close requests idempotent
  (including the recycled-window-address edge case, cleaned up on both window
  close and message release);
- `tests/test_qt_window_close.py` (new, untracked): 10 Qt-offscreen tests
  covering deferral, idempotency, the filtered/no-`IDCMP_CLOSEWINDOW` case,
  the app-driven release path, the scheduler-hint timing, and the recycled
  address case.

This matches the architecture and constraints in
`docs/architecture/cooperative-host-scheduler.md` ("Window Close Semantics")
closely, and does **not** touch `QtHostWindowProjection.close_window`, the
IntuiMessage ABI, or the scheduler core.

**Not done:** no interactive close smoke test (mirroring
`tests/run_interactive_exit_smoke_test.py`) was written, and the branch was
never merged or even committed to.

## Verified progress and stopping point

Claude independently ran the checks the model's prompt required, rather than
trusting the model's own unproduced summary:

- `tests/test_qt_window_close.py`: **10/10 pass** in isolation.
- Full non-GUI suite (`unittest discover`): **265 tests, 2 failures.**
  - `test_xvfb.py::test_build_env_sets_display_and_default_qt_platform` — the
    pre-existing, already-documented test-order env-var pollution (see the
    2026-09-09 `run-log.md` entry); not a regression.
  - `test_cli.py::BoundedGuiLaunchTest::test_run_command_enters_and_exits_cleanly`
    — **a genuine regression**, confirmed by `git stash` / rerun against clean
    `development` (passes there, fails here with `returncode -11` / SIGSEGV
    and `stderr: "amiga-ui run: the interactive wait timed out (automation
    bound); no message was fabricated"`). Root cause not yet fixed: the new
    `closeEvent` deferral does not distinguish a genuine interactive
    window-manager close request from `--auto-close-after`'s forced/automated
    shutdown, so the automated close is deferred exactly like a real one, the
    wait times out, and teardown crashes.
  - `pre-commit` (pyright only run against the changed files): **22 errors**,
    all `reportOptionalMemberAccess`/`reportOptionalOperand` in the new test
    file — every one is `projection.host_window(...)` returning `X | None`
    and the test calling `.close()`/`.isVisible()` without narrowing it first.
    Mechanical; not a design problem.

No interactive smoke test, no commit, no merge.

## Harness/model performance

The session ran a single turn from 16:10:42 to 18:39:19 UTC (turn/end reason:
`{"kind": "aborted", "reason": {"kind": "user"}}` — the user's own
`docker compose` / UI stop action, recorded in the session log itself).

Reasoning was **not** the failure mode this time: `reasoning_effort` was
correctly defaulted to `low` for this model as of this session (the DSH
provider config fix landed and `deepseek-c` was restarted at 16:10:05 UTC,
immediately before this session's turn began), and nothing in the log shows
the repetitive-reasoning pattern that ended the two 2026-09-10 sessions.

Instead, the session was consumed by context compaction failing outright,
repeatedly:

| Compaction attempt | Start (UTC) | End (UTC) | Result |
|---|---|---|---|
| 1 | 17:17:21 | 17:22:21 | `pi-ai stream idle timeout after 300000ms` |
| 2 | 17:30:51 | 17:35:51 | same |
| 3 | 17:49:29 | 17:54:29 | same |
| 4 | 18:03:51 | 18:08:51 | same |
| 5 | 18:17:54 | 18:22:54 | same |
| 6 | 18:33:02 | 18:38:02 | same |

**All six compaction attempts failed**, every one taking almost exactly 5
minutes before the client-side idle watchdog gave up — strong evidence this
was a structural mismatch (compaction genuinely needing a little over 5
minutes on this model/hardware) rather than an occasional stall. Ordinary
turns interleaved between compaction attempts also hit the same timeout on
occasion (e.g. `llm/retry` at 16:58:17, 17:03:17, 17:27:21, 17:40:51). Because
compaction never succeeded, context pressure never relieved, so the next step
re-triggered compaction again — a loop with no way to make forward progress
on its own.

**Root cause and fix (applied by Claude, outside this repository):** DSH's
`llm-pi-ai` provider adapter defaults `streamIdleTimeoutMs` to 300,000ms
(5 minutes) per provider; this is too short for the `llama-cpp-moe-16gb` /
`llama-cpp-moe-32gb` providers given this model's prefill throughput. Fixed
in `/home/ai/server_containers/deepseek/config/settings.yaml`
(`streamIdleTimeoutMs: 1800000` added to both providers) and
`/home/ai/server_containers/deepseek/agent-preset-overrides/standard/agent.cordis.yml`
(Flash Next's compaction `maxTokens` lowered from 12,288 to 4,096, to reduce
worst-case compaction wall-clock time on top of the timeout fix). Both were
synced/deployed and `deepseek-c` was restarted; a fresh session should not
reproduce this failure. This is DSH/llama.cpp deployment configuration, not
part of the `amiga-ui` repository, so there is no corresponding code change
here.

## Recovery recommendation

The working-tree diff is small (163 lines across two files, plus one new
10-test file), closely follows the settled architecture doc, and is not
entangled with the ABI or scheduler internals. One real regression is
identified and narrowly scoped (the `closeEvent` deferral needs to let a
forced/automated host shutdown proceed rather than deferring it like a
genuine interactive close), plus a mechanical pyright fix in the new test
file. Recommend continuing this branch in a fresh session rather than
discarding it: inspect the diff above, fix the automated-shutdown
distinction (`run_command.py`'s `--auto-close-after` path likely needs a
"force close" call that bypasses `closeEvent`, or the handler needs to
recognize host-shutdown intent), add the null-checks pyright wants in
`tests/test_qt_window_close.py`, then write the still-missing interactive
close smoke test before running the normal merge gate.
