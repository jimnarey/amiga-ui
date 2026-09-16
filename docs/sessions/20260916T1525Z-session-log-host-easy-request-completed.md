---
title: "Session log — host EasyRequestArgs completed: real blocking QMessageBox round trip, gates green, merged"
status: log
depends_on:
  - "../architecture/hosted-application-mode.md"
  - "../workflows/branching-and-merging.md"
  - "../host-gui/translation-obligations.md"
  - "20260915T0006Z-session-log-host-window-close-completed.md"
citations_used: []
---

# Session log — host EasyRequestArgs completed (2026-09-16)

`EasyRequestArgs` (intuition.library LVO 588) is now a genuinely *blocking* call
on `feat/host-easy-request`: it opens a real `QMessageBox` parented to the correct
host window, waits for the user's actual button choice, and returns the real
classic result code (nonzero for the positive gadget, `0` for the negative/cancel
gadget) back into the emulated call — not a fabricated default answer. The
end-to-end acceptance route is iTidy's LHA-not-found Continue/Cancel dialog, and
the test observes the app's *own* branch on the returned LONG rather than any
value the harness invented.

## Session prompts

Raw DSH session: `session-36bc522e-8a1a-4c0d-a846-78b78ae02bd6`
Log: `/home/runuser/.dsh/sessions/--workspace-amiga-ui--/session-36bc522e-8a1a-4c0d-a846-78b78ae02bd6/session.jsonl.zstd`

### Starting prompt (captured intent)

```text
Implement EasyRequestArgs (intuition.library LVO 588) on
feat/host-easy-request (off development) as a genuinely blocking call: it opens a
real QMessageBox parented to the correct host window, waits for the user's actual
button choice, and returns the real classic result code (nonzero for the positive
gadget, 0 for negative/cancel) back into the emulated call — not a fabricated
default answer.

Decode real emulated EasyStruct fields (title, body text, gadget/button
label(s), IDCMP/flags). The concrete end-to-end acceptance route is the
LHA-not-found Continue/Cancel dialog in
amiga_apps/itidy1classic/source/src/GUI/main_window.c (GID_APPLY handler, ~line
1417): two buttons "Continue"/"Cancel", body read from emulated memory, real host
click, real returned LONG.

Add focused tests: (a) EasyStruct field decoding, (b) a QMessageBox round trip
(button labels + returned code per button), (c) a real interactive smoke test
mirroring the existing exit/close/menu ones that triggers the actual
LHA-not-found path in a build without LHA available, observing the app's own
branch on the returned result rather than fabricating it.

Before merging: focused tests, the three existing interactive smoke tests still
passing, the new one, the full suite, and pre-commit. If genuinely gated, merge
into development per docs/workflows/branching-and-merging.md.

Leave a session summary under docs/sessions covering what was implemented, the
observed real dialog round trip, checks run + results, remaining uncertainty,
whether merged, and the next recommended increment (likely an ASL directory
picker, or AutoRequest/BuildEasyRequestArgs).

Boundaries: EasyRequestArgs alone (a single button pair first); do NOT implement
AutoRequest/BuildEasyRequestArgs/ASL file requester; follow the settled
QMessageBox rule (no custom QDialog unless a concrete case forces it); keep the
existing address/structure-based routing (no new generic "requester manager"); do
NOT touch the settled menu/scheduler/event-bridge ABI; if restating a concluded
answer, take the concrete action instead.
```

## The blocking question, settled first

The hard question was *how to observe the app's own branch* on the returned LONG,
since the app's `CONSOLE_STATUS`/`CONSOLE_WARNING` macros are `printf` only under
`ENABLE_CONSOLE` and are no-ops in the shipped binary — app stdout is therefore
**unreliable** as the branch observable (the earlier menu/close smoke tests never
relied on it for exactly this reason).

The settled answer: read the **live host-side registry's backup-checkbox checked
state** through the real `GT_GetGadgetAttrsA`/`GT_SetGadgetAttrsA` path. This is a
direct, reliable observation of the app's own branch:

- **Continue** (returned `1`, nonzero): the app's `GID_APPLY` handler runs
  `GT_SetGadgetAttrs(win_data->backup_check, win, NULL, GTCB_Checked, FALSE,
  TAG_DONE)` to uncheck the backup checkbox → the registry reads **FALSE**.
- **Cancel** (returned `0`): the app `break`s *before* any `GT_SetGadgetAttrs` →
  the registry stays **TRUE** (the state the test set by clicking the checkbox).

So the branch is observed through the app's *own write* to the registry (Continue)
or its *own non-write* (Cancel) — no stdout, no fabricated value.

## What was done

- **`src/amiga_ui/vamos/intuition_library.py`.** `EasyRequestArgs(ctx, window,
  easyStruct, idcmpPtr, args)` (LVO 588), the Qt-free seam. It decodes the app's
  own `struct EasyStruct` from emulated memory (`es_Title` `+0x08`, `es_TextFormat`
  `+0x0C`, `es_GadgetFormat` `+0x10` — the NDK `STRPTR` fields), splits the
  pipe-separated button list, calls the host projection's blocking dialog, and maps
  the clicked index to the classic result code (`_easy_request_code`: single → `1`,
  last/cancel → `0`, otherwise 1-based position). Raises
  `UnsupportedFeatureError` when there is no host projection (honest headless
  boundary — a plain probe stops earlier at `WaitPort`, so this is a defensive
  guard, and failing beats fabricating a default the app would branch on).
  `idcmpPtr` is `NULL` for the target, so IDCMP-termination is out of scope.
- **`src/amiga_ui/host/qt_projection.py`.** `show_easy_request(window_addr, title,
  body, buttons) -> int`: a real, parented `QMessageBox` (parented to the app's own
  host window; `ValueError` if the window is not projected, rather than an
  unparented top-level). The last button is `RejectRole` (Escape maps to it, as
  classic), the first `YesRole`, a single button `AcceptRole`. `.exec()` blocks the
  GUI thread until the user actually clicks, and the method returns the 0-based
  index of the clicked button. Also: the projected `CHECKBOX` became a
  `QtGadgetCheckbox` (mirroring `QtGadgetButton`) that records the real Amiga
  window/gadget addresses, and a real toggle now routes to the event bridge's
  `gadget_up`.
- **`src/amiga_ui/vamos/event_bridge.py`.** In `gadget_up`, a `CHECKBOX` activation
  toggles the gadget's live registry checked state *before* the `IDCMP_GADGETUP` is
  posted (classic Intuition toggles the clicked gadget's `Value`, then reports the
  `GADGETUP`). This is the only interactive-checkbox path; buttons and every other
  kind are unaffected, so the settled button/menu/close flows are untouched.
- **`src/amiga_ui/vamos/gadtools_library.py`.** `GT_GetGadgetAttrsA` (LVO 174) and
  `GT_SetGadgetAttrsA` (LVO 42) — the **`A` variants the binary actually calls**
  (the app's variadic `GT_GetGadgetAttrs`/`GT_SetGadgetAttrs` taglib stubs expand to
  them; the repo convention is the `A` suffix, as with `CreateGadgetA`). Get reads
  the live checked state to the `GTCB_Checked` out-param; Set re-records the
  description from the tag. Both return the tags processed (`1`) or `0`.
- **`docs/platform/library-cards/intuition.library.md`** gained a "Requesters
  (EasyRequestArgs)" section; **`gadtools.library.md`** gained a "Checkbox Gadget
  State (`GTCB_Checked`)" section.
- **Tests.** `tests/test_easy_request_args.py` (Qt-free: EasyStruct decode +
  result-code mapping + the full seam via a fake projection, no-projection →
  `UnsupportedFeatureError`), `tests/test_qt_easy_request_dialog.py` (offscreen
  `QMessageBox` round trip: labels, per-button returned code, parenting, missing
  window → `ValueError`), and `tests/run_interactive_lha_smoke_test.py`
  (`--branch continue|cancel`): a real Xvfb-backed interactive test that enables
  the backup checkbox, presses Start, finds the real LHA `QMessageBox`, clicks the
  chosen button, and reads the live registry to observe the app's own branch.
- **`tests/test_host_qt_gadget_projection.py`.** `test_checkbox_is_qcheckbox` →
  `test_checkbox_is_gadget_checkbox`, mirroring the existing
  `test_button_is_push_button` (the interactive subclass is the documented class).

## Real defects the new interactive test caught

1. **A `QComboBox` (cycle gadget) has no `text()`.** The first probe that located
   the backup checkbox by iterating `gadget_widgets` and calling `widget.text()`
   crashed on the cycle gadget every attempt (the exception was swallowed by Qt's
   timer callback, so the probe silently retried 400× and gave up). Fixed by
   matching on the concrete `QtGadgetCheckbox`/`QtGadgetButton` types (the same
   `findChildren`/`isinstance` convention the exit smoke test uses) instead of a
   generic `text()` scan.
2. **The main window is the *second* projected window.** iTidy projects a helper
   window first, then the main window that carries the 16 gadgets. Keying the test
   on "the first projected window" targeted the wrong one; the test now probes for
   the window that actually carries the backup checkbox.
3. **The sequence completes before the window is closed.** The observable (the
   registry checkbox state) is captured in one state-machine step, but the app
   exits after the close request is posted — before a further tick would mark
   `done`. The close is now a separate loop from the "sequence complete" flag, so
   the test reports the observed branch even though the app tears down immediately.

## The observed real dialog round trip

From a live `--branch continue` run (values for future comparison): main window
`0x6b3b0`, backup checkbox `0x6ae78`, Start/Apply button `0x6b058`. The dialog
appeared as a `QMessageBox` titled `LHA Not Found`, parented to the main window
(`parentWidget()` is the main window, not the bare `QApplication`), with the app's
own body text and the two buttons `Continue` / `Cancel`. Clicking the branch
button unblocked the app's `exec()`, the app branched on the returned LONG, and —
read through the live registry — **Continue** left the backup checkbox **unchecked**
(the app's own `GT_SetGadgetAttrsA` ran) while **Cancel** left it **checked** (the
app broke before any write). Both runs ended `exit_code=0` with
`last_outcome=WaitOutcome.SATISFIED`.

## Checks run and results

| Check | Result |
| --- | --- |
| `tests.test_easy_request_args` (Qt-free) | 9 tests, OK |
| `tests.test_qt_easy_request_dialog` (offscreen) | 4 tests, OK |
| `tests.test_vamos_launcher` | 5 tests, OK |
| `tests.run_interactive_lha_smoke_test --branch cancel` | PASS — checkbox stays checked (app's Cancel branch), clean exit |
| `tests.run_interactive_lha_smoke_test --branch continue` | PASS — app unchecks the checkbox (its own `GT_SetGadgetAttrsA`), clean exit |
| `tests.run_interactive_close_smoke_test` / `run_interactive_exit_smoke_test` / `run_interactive_menu_smoke_test` | PASS (unchanged) |
| `uv run python tests/run_gui_smoke_test.py` | PASS |
| `unittest discover` (full, clean env) | 343 tests, OK |
| `pre-commit` on the staged tree (ruff check / ruff format / pyright) | passed; check-yaml skipped (no YAML in the change) |

The full-suite count rose from 330 (the menu-strip session baseline) to 343 with the
new focused tests and the checkbox-class test rename.

## Merge

`feat/host-easy-request` is merged into `development` with a `--no-ff` merge; the
branch is retained (repo rule: do not delete branches after merge). No commit was
made on `main` or directly on `development`.

## Known gaps (recorded, not papered over)

- `idcmpPtr` is `NULL` for the accepted target, so the IDCMP-termination path of
  `EasyRequestArgs` (where a queued IDCMP event dismisses the requester) is not
  implemented; the dialog is dismissed by a button only. A target that passes a
  non-NULL `idcmpPtr` would need that path.
- `AutoRequest`, `EasyRequest`, and `BuildEasyRequest` are not implemented (the
  task scoped this increment to `EasyRequestArgs` with a single button pair).
- The actual LhA execution (running the archiver via `Execute`) is still second-
  phase; this increment handles the *not-found* dialog and the app's branch on the
  user's choice, not the backup itself.
- The `QMessageBox` button-role mapping assumes the last button is the cancel; a
  multi-button requester with a non-last cancel would need the role mapping
  revisited (the accepted target is a two-button Continue/Cancel, so this is not a
  live gap).

## Next increment (deliberately deferred)

An ASL file/directory requester (the likely next iTidy path, e.g. the folder
picker) or `AutoRequest`/`BuildEasyRequestArgs`, each from a fresh branch off the
updated `development`.
