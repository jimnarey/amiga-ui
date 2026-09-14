---
title: "Session log — host window-close recovery interrupted (compaction token-cap truncation)"
status: log
depends_on:
  - "../architecture/cooperative-host-scheduler.md"
  - "20260914T1610Z-session-log-host-window-close-failed.md"
citations_used: []
---

# Session log — host window-close recovery interrupted (2026-09-14)

> **Recovery note:** Claude (Sonnet 5) wrote this summary after the local-model
> session was manually stopped by the user, again without reaching its own
> requested handoff. As with the previous attempt on this branch, the failure
> was infrastructure, not the model's own reasoning or code: this time a
> *different* compaction fault than before (a token-cap truncation, not the
> stream-idle-timeout from the prior session), caused by an overcorrection
> Claude applied after that prior session. The code the model produced in
> this session was inspected directly and independently verified (tests run,
> a `git stash`-style before/after check was not needed since the prior
> regression's own fix was reverified against clean `development` in place)
> — it is a genuine, working fix for the regression the previous session log
> identified.

## Session prompts

Raw DSH session: `session-85b70124-048f-402a-88ce-391f2e0914bc`
Log: `/home/runuser/.dsh/sessions/--workspace-amiga-ui--/session-85b70124-048f-402a-88ce-391f2e0914bc/session.jsonl.zstd`

### Starting prompt (2026-09-14 19:42 UTC)

The prompt resumed `feat/host-window-close` at commit `f0663a5` and asked the
model to: fix the `--auto-close-after` SIGSEGV regression identified in the
prior session's summary (`AmigaHostWindow.closeEvent` deferring a forced host
shutdown exactly like a genuine interactive close request), clear the 22
pyright null-narrowing errors in `tests/test_qt_window_close.py`, write the
still-missing interactive close smoke test, then run the full gate and merge.
See `20260914T1610Z-session-log-host-window-close-failed.md` for the complete
prompt text and the regression's original diagnosis.

There were no additional human-authored prompts in this session.

## Work left in the working tree

Uncommitted changes on `feat/host-window-close` (still at `f0663a5`; nothing
new was committed):

- `QtHostWindowProjection.mark_session_ended()` (new): records that the
  Amiga session behind a projection has ended.
- `run_command.py` now calls it as soon as the target returns from the run,
  before `_report_outcome`.
- `QtHostWindowProjection._on_close_request` now also returns `False` (let Qt
  complete the close) once the session has ended, alongside the existing
  "window no longer projected" case — distinguishing a forced/automated host
  shutdown (including the synthesised `QCloseEvent`s `QApplication.quit()`
  delivers to every visible top-level window) from a genuine interactive
  close request, which is exactly the gap the prior session's regression
  came from.
- `tests/test_qt_window_close.py` gained further tests (file grew from 287 to
  ~387 lines) covering the new session-ended behavior.

**Not done:** the interactive close smoke test (mirroring
`tests/run_interactive_exit_smoke_test.py`) still was not written. Nothing
was committed or merged.

## Verified progress and stopping point

Claude independently re-verified the fix rather than trusting the model's
own unproduced summary:

- `tests/test_cli.py::BoundedGuiLaunchTest::test_run_command_enters_and_exits_cleanly`
  — **the previously-identified SIGSEGV regression is genuinely fixed.**
  Passes cleanly now (it was the one test confirmed broken by this branch's
  diff in the prior session log).
- Full non-GUI suite: **268 tests, 1 failure** — only the pre-existing,
  already-documented `test_xvfb.py` test-order env-var pollution (see the
  2026-09-09 `run-log.md` entry and the prior two session logs); not a
  regression. Test count grew from 265 to 268 (3 new tests, consistent with
  the `test_qt_window_close.py` growth).
- `pre-commit` on the changed files: **pyright now passes** (the 22
  `reportOptionalMemberAccess`/`reportOptionalOperand` errors from the prior
  session are cleared) and `ruff check` passes. `ruff format` reports exactly
  **one** line in `tests/test_qt_window_close.py` that would be reformatted
  (a call that fits on one line but is currently wrapped) — trivial,
  mechanical, not yet applied.

So: the regression fix is real and verified, the diff is clean by every gate
except one cosmetic formatting line, and the only remaining functional gap
from the original prompt is the interactive close smoke test.

## Harness/model performance

The session ran a single turn from 19:42:08 to 21:29:43 UTC — over an hour
and a half producing the fix above, then stalled on compaction again for the
final ~25 minutes before the user stopped it.

This was **not** a repeat of the prior session's stream-idle-timeout failure
— that fix (`streamIdleTimeoutMs: 1800000`) held; the first compaction
attempt below ran a full 15 minutes without tripping the client watchdog.
Instead, it hit a *different* compaction fault, one Claude introduced as a
side effect of the previous session's fix:

| Time (UTC) | Event |
|---|---|
| 21:05:10 → 21:20:22 | `compaction/start` → `compaction/end`, error: `"summarization truncated at the token cap (incomplete checkpoint)"` |
| 21:24:19 → 21:29:43 | `compaction/start` → `compaction/end`, error: `"Request was aborted"` (the user's stop action, not a second independent failure) |

**Root cause:** the prior session's summary lowered Flash Next's compaction
`maxTokens` from 12,288 to 4,096 to bound wall-clock time, without any
evidence that 4,096 was enough to actually complete a checkpoint — every
prior attempt had died to the timeout before generation meant anything, so
this value had never been tested for completion, only for speed. It wasn't
enough: `dsh-compaction-basic` treats a `max-tokens` finish as an
unconditional failure (`finishError()` in
`dsh-compaction-basic/lib/index.js`), with no retry-with-a-larger-budget and
no chunking of an oversized shadowed region — confirmed by reading the
plugin source directly, not inferred. `compactionRetries` (set to 2) retries
the whole call with the *same* budget, so a truncation failure is expected to
repeat identically rather than self-correct.

**Fix (applied by Claude, outside this repository, per the user's explicit
instruction to test with more headroom given two failed attempts):**
`maxTokens` raised back to 12,288 for both `llama-cpp-moe-16gb` and
`llama-cpp-moe-32gb` Flash Next policies in
`/home/ai/server_containers/deepseek/agent-preset-overrides/standard/agent.cordis.yml`,
with the full history and reasoning recorded in that file's comment.
`deepseek-c` was restarted. This is a guess with more headroom, not a
measurement — see the "Tuning note" below for how to stop guessing once a
compaction actually succeeds. No corresponding code change was needed or
made in `amiga-ui`.

**Tuning note for future sessions:** a *successful* compaction appends a
`compaction/summary` session event carrying real `usage` and
`shadowedTokenCount` fields (`commitCompactionBody()` in the same plugin
file) — nothing about a successful compaction has ever been logged by this
deployment yet, since every attempt so far has failed. Once one succeeds,
that event is the evidence to right-size `maxTokens` precisely instead of
guessing again.

## Recovery recommendation

The regression fix is done and verified; what's left is small and low-risk:

1. Run `ruff format` to fix the one flagged line in
   `tests/test_qt_window_close.py`.
2. Write the interactive close smoke test (mirroring
   `tests/run_interactive_exit_smoke_test.py`), per the original prompt's
   still-unmet step.
3. Run the full gate (focused tests, full suite, Qt offscreen suite, both
   interactive smoke tests, pre-commit) and merge
   `feat/host-window-close` into `development` per
   `docs/workflows/branching-and-merging.md`.

The user intends to commit the current working tree as another progress
commit before starting the next session, matching the pattern of the prior
`f0663a5` commit.
