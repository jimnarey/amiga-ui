---
title: "Session log — first static GadTools-to-Qt projection slice for hosted application mode"
status: log
depends_on:
  - "../apps/itidy/run-log.md"
  - "../apps/itidy/compatibility-notes.md"
  - "../architecture/platform-target.md"
  - "../architecture/hosted-application-mode.md"
  - "../architecture/translation-pipeline.md"
  - "../platform/library-cards/gadtools.library.md"
  - "../host-gui/widget-mapping.md"
  - "../host-gui/testing-host-ui.md"
  - "../host-gui/threading-and-desktop-boundaries.md"
  - "../workflows/error-driven-porting.md"
  - "../workflows/branching-and-merging.md"
  - "20260909T1917Z-session-log-iTidy-drawinfo-pen-semantics.md"
citations_used:
  - S1
  - S28
  - S31
  - S36
  - S42
---

# Session log — first static GadTools-to-Qt projection slice (2026-09-09/10)

## Session prompts

Raw DSH session: `session-ec2325a8-f8d7-43dd-83a4-686ddb4343dd`
Log: `/home/runuser/.dsh/sessions/--workspace-amiga-ui--/session-ec2325a8-f8d7-43dd-83a4-686ddb4343dd/session.jsonl.zstd`

### Starting prompt (2026-09-09 22:18 UTC)

````text
You are working in the amiga-ui repository.

There are intentional uncommitted documentation-hardening changes in the
working tree. They qualify several drawing-semantics conclusions, add a central
compatibility-risk register, record an NDK provenance warning, and document the
difference between scanner wiring and semantic implementation.

Start by inspecting the working tree and reviewing those documentation changes.
Do not discard or rewrite them. Run the documentation checks and
`git diff --check`. If they are coherent and valid, put them on a dedicated
documentation branch, commit them, and merge that branch into `development`.
Then create a fresh feature branch from the updated `development` for the
implementation work below. Do not combine the documentation-hardening commit
with the host-GUI implementation commit.

For the implementation increment, inspect AGENTS.md, README.md,
docs/workflows/dsh.md, docs/workflows/error-driven-porting.md,
docs/architecture/platform-target.md,
docs/architecture/hosted-application-mode.md,
docs/architecture/translation-pipeline.md,
docs/research/open-questions.md,
docs/host-gui/translation-obligations.md,
docs/host-gui/widget-mapping.md,
docs/host-gui/component-implementation-standard.md,
docs/host-gui/threading-and-desktop-boundaries.md,
docs/host-gui/testing-host-ui.md, and the latest relevant session summary under
docs/sessions. Earlier summaries and their original prompts are available there
if needed; do not read every session summary by default.

Inspect the current GadTools implementation, gadget memory/state model, host
projection boundary, Qt window implementation, event bridge, launcher, and the
iTidy main-window gadget creation source.

Run the current plain iTidy probe, GUI smoke test, host-projection smoke test,
and a bounded `amiga-ui run` launch to confirm the baseline. The expected
baseline is:

- one app-facing iTidy host window is visible;
- the public Workbench screen remains invisible/notional;
- the custom group boxes, folder path and labels are rendered;
- the former black title bars are gone;
- the GadTools controls themselves are absent;
- the target still reaches the honest WaitPort-on-empty-queue boundary.

Objective: implement the first coherent static GadTools-to-Qt projection slice
for hosted application mode.

The visible milestone is that the initial iTidy main window displays its
GadTools controls in their intended approximate positions over the existing
RastPort-rendered background. Focus only on the kinds exercised by the initial
main window:

- BUTTON_KIND
- TEXT_KIND
- CYCLE_KIND
- CHECKBOX_KIND

The expected initial list appears to contain thirteen real gadgets plus the
invisible GadTools context gadget. Confirm the actual count, kinds, geometry and
state from a fresh run and the source. Do not hard-code that count or identify
controls from iTidy-specific labels, IDs or window titles.

Keep this increment about accurate gadget state and static host projection.
Do not solve the interactive vamos/Qt scheduler or general event-loop
integration in this branch.

Implementation guidance:

- Preserve the hosted-application-mode design.
- Keep the public Workbench screen as an internal Amiga-side structure.
- Do not create a visible Workbench desktop, wallpaper, screen title bar or host
  container around application windows.
- Continue projecting each app-facing Amiga Window as an independent host
  top-level window.
- Preserve the existing custom RastPort replay surface and corrected DrawInfo
  ABI.
- Project gadgets as positioned child widgets over the drawing surface, or use
  another small composition that preserves Amiga window coordinates and the
  existing custom drawing.
- Keep Qt imports out of the low-level Amiga library implementations.
- Extend the Qt-free projection boundary using immutable, host-safe gadget
  descriptions or semantic intents.
- Keep 68k structure and tag-list interpretation in the compatibility/adapter
  layer. QWidget code must not dereference emulated memory after the target
  phase.
- Associate gadgets with their Window through the real
  CreateContext/CreateGadgetA/gadget-chain/Window.FirstGadget relationship.
- Exclude the invisible CreateContext/GContext gadget from host projection.
- Ensure each projected window receives only its own gadgets.
- Make projection and close/release behavior idempotent.

Decode and retain the relevant CreateGadgetA state, including at least:

- gadget address and GadgetID;
- gadget kind;
- geometry;
- label text;
- checkbox checked state;
- cycle label array and active index;
- TEXT_KIND displayed text and border flag where exercised;
- enabled or disabled state where present on the observed path.

Do not retain raw string or label-array pointers as the only host
representation. Decode immutable host-safe values while emulated memory is
valid.

Use appropriate Qt Widgets for the four kinds, likely:

- QPushButton for BUTTON_KIND;
- QLabel for TEXT_KIND;
- QComboBox for CYCLE_KIND;
- QCheckBox for CHECKBOX_KIND.

Treat that mapping as a starting point to validate against the repo’s host-GUI
guidance, not as permission to bypass Amiga-side gadget state.

If GT_SetGadgetAttrs is exercised during initial setup, implement meaningful
updates for the supported attributes and propagate visible state through the
projection boundary. Do not add an empty success implementation.

Interaction boundary:

- Static, correctly populated widgets are the milestone.
- Do not make WaitPort succeed on an empty queue.
- Do not fabricate an IntuiMessage to make a button appear operational.
- Do not claim that controls are interactive merely because Qt supplies hover,
  focus or pressed visuals.
- Avoid connecting activation signals to application-changing behavior in this
  increment unless they can be delivered through the real event route while
  the target is genuinely waiting.
- Preserve the intended future route:

  Qt widget event
  -> IntuiMessage
  -> Window.UserPort
  -> WaitPort
  -> GT_GetIMsg
  -> GT_ReplyIMsg

- Characterize any scheduler or lifecycle obstacle exposed by projection, but
  leave live Qt-event-to-IntuiMessage integration for a fresh branch.

Drawing-semantics guardrail:

The corrected documentation now records that the current draw-mode model is
provisional. Do not treat existing renderer tests as proof that classic JAM2
universally selects BPen.

In particular:

- the whole-operation `JAM1 -> APen`, `JAM2 -> BPen` reduction is not settled;
- JAM2 Text background cells are not currently rendered;
- RGB-channel XOR is only a host approximation of planar COMPLEMENT;
- the relationship between IntuiText.DrawMode and RastPort draw modes remains
  unresolved;
- initial JAM1 for a window-owned RastPort is an iTidy-informed compatibility
  choice, not yet a proven universal OpenWindow contract.

Do not expand the gadget branch into a general raster/minterm implementation.
If gadget projection exposes a visible dependency on one of these uncertainties,
stop and document the exact discriminating evidence needed. Otherwise preserve
the current working rendering and continue with the gadget milestone.

Evidence and provenance guardrail:

- Keep the default target classic m68k Workbench/AmigaOS 3.0-3.1.
- Do not infer OS4/PPC/ReAction/MorphOS behavior.
- Files under `assets/docs/ndk/NDK3.2/` identify themselves as later
  AmigaOS 4.1/V47 material. Use them only as field-by-field corroboration, not
  blanket classic authority.
- The available iTidy source is guidance and is not guaranteed to be the exact
  source of the shipped binary.
- Prefer fresh runtime evidence and the shipped binary when source and binary
  disagree.
- Do not treat a scanner-valid trap or disappearance from the defaulted-call
  report as proof of semantic implementation.
- Keep scanner-valid calls that merely log or omit required effects classified
  as recorded-but-unimplemented.

Testing requirements:

- Add Qt-free tests for decoding and recording each supported gadget kind.
- Test cycle-label decoding and the active index independently of iTidy.
- Test checkbox state, button/text labels, geometry and GadgetID retention.
- Test that the context gadget is never projected.
- Test window-to-gadget association and isolation across two windows.
- Add Qt tests proving that the four kinds create the intended widget classes
  with the expected geometry, text and initial state.
- Test that host widgets overlay the drawing surface without removing the
  existing group-box rendering.
- Test update/refresh behavior where supported.
- Test that closing one window releases only its own widgets and projection.
- Add one Xvfb-backed real-iTidy assertion that the main projected window
  contains the expected supported widget types with meaningful labels and
  geometry.
- Prefer widget and property assertions over fragile pixel-perfect screenshots.
- Retain one small paint assertion proving the RastPort background remains
  visible.
- Preserve ordinary headless probes and prove they neither import nor require
  Qt.

Important constraints:

- Do not implement menus, requesters, every GadTools kind, or complete visual
  fidelity in this increment.
- Do not build the host controls through iTidy-specific Qt code.
- Do not add fake handles, fabricated interactions or empty success stubs.
- Do not reopen unrelated RastPort or Screen offset investigations.
- Keep compatibility changes in the repository, not in `.venv`.
- Use one feature branch created from the updated `development`.
- Commit and merge only after the coherent increment is gated.

Run the relevant focused tests, complete unit suite, ruff, pyright, GUI smoke
test, host-projection smoke test, plain iTidy probe/analyser path, and a bounded
real `amiga-ui run` launch.

Report aggregate test results exactly. If a test fails under an inherited
environment but passes separately, report both facts and do not call the
aggregate suite fully green.

When finished, add a session summary under docs/sessions following the existing
format. Include the starting prompt and every additional human prompt from the
raw DSH log in the prompt section.

Leave a concise final summary of:

1. how the documentation-hardening changes were landed,
2. which GadTools kinds and state are now projected,
3. what the real iTidy window visibly contains,
4. what was verified,
5. what remains approximate, uncertain or non-interactive,
6. the next recommended increment, especially live
   Qt-event-to-IntuiMessage integration.
````

No additional human prompts were sent in this session. The only other `user/message`
events in the raw log are harness-injected (AGENTS.md / skill-catalog /
runtime-context reminders, two auto-generated compaction checkpoints, and
background-job completion notices) — not direct human requests — so there is
nothing further to record here.

## Purpose

Two-part increment. First, land the already-prepared documentation-hardening
changes on a dedicated branch and merge them into `development`. Second,
implement the first coherent **static** GadTools-to-Qt projection slice for
hosted application mode, whose visible milestone is that the initial iTidy main
window displays its GadTools controls (BUTTON / TEXT / CYCLE / CHECKBOX kinds)
in their intended approximate positions over the existing RastPort-rendered
background — without touching the interactive event loop.

## Documentation-hardening landing (discrepancy noted)

The starting prompt described the documentation-hardening changes as
*intentional uncommitted* changes in the working tree. On inspection they were
**already committed** on `development` as `3daafda` ("Small docs corrections"),
and the working tree was clean for docs. The committed content matches all four
described aspects (qualified drawing-semantics conclusions, a central
compatibility-risk register, an NDK provenance warning, and the
scanner-wiring vs. semantic-implementation distinction); `git diff --check` was
clean and `tools/docs_triage.py` passed. No history rewrite was performed: the
invariant the prompt cares about — *the documentation-hardening commit is not
combined with the host-GUI implementation commit* — already held, because the
docs commit predates the feature branch. The feature branch
`feat/gadtools-qt-projection` was created from the updated `development`
(including `3daafda`). This discrepancy (uncommitted in the prompt vs.
already-committed in the tree) is reported rather than "fixed" by rewriting
history.

## Evidence (NDK / app source / recorded ops)

### GadTools tag base (the one real bug found)

The decode initially produced empty cycle label arrays. Dumping the real
cycle-gadget taglist from a live run showed tags `0x8008000e` / `0x8008000f`
for `GTCY_Labels` / `GTCY_Active`. The NDK header defines
`GT_TagBase = TAG_USER + 0x80000` [S1] and `utility/tagitem.h` defines
`TAG_USER = 1UL << 31 = 0x80000000`, so the base is **0x80080000** — not the
`0x88000` (which assumed `TAG_USER = 0x8000`) the compat layer used. The tag
*offsets* (`+4` checked, `+11` text, `+14` cycle labels, `+15` active, `+51`
recessed, `+52` visual info, `+57` border) already matched the header; only the
base was wrong. Correcting it made the cycle label arrays, the checkbox flag,
and the bevel-box `GTBB_Recessed`/`GT_VisualInfo` tags decode. The bevel box
now reads `recessed=True` for the group boxes (a correctness improvement; the
pixel count is unchanged because recessed only swaps the light/dark edges).

The NDK `gadtools.h`/`tagitem.h` used here are the 4.1-era/V47 cache (per the
repo provenance warning [S1]); they are used only as field-by-field
corroboration, and the **shipped binary's emitted tag values are the authority**
that the base is 0x80080000.

### Gadget set (from a fresh run + source, not hard-coded)

The initial main window's real gadget list is thirteen projectable gadgets plus
one invisible context gadget [S31]:

- 7 × BUTTON_KIND → `QPushButton` (incl. "Browse...", "Advanced...", "Start", "Exit")
- 3 × CYCLE_KIND → `QComboBox` (+ a right-aligned caption `QLabel` each, per the classic `PLACETEXT_LEFT`)
- 2 × CHECKBOX_KIND → `QCheckBox`
- 1 × TEXT_KIND → `QLabel` (the "Folder:" caption; its `GTTX_Text` is empty so the label is shown)

The projection code never hard-codes this count or any iTidy label/ID/title; it
switches on the generic `GadgetDescription.kind_name` and projects whatever
projectable gadgets the window's real `FirstGadget` chain yields.

### Recorded decode (real iTidy run, offscreen)

The main window (`iTidy v1.0 - Icon Cleanup Tool`, 625×215) projected
**buttons=7, combos=3, checkboxes=2, labels=4**, each at its NewGadget
geometry, with the RastPort-replayed background still visible
(55 ops, 130755 non-background surface pixels). The app still ends at the
honest `WaitPort on empty message queue` boundary (`Port 06b508`).

## Verification

Reported exactly, as required:

- **Full unit suite**: `uv run python -m unittest discover tests` → **Ran 227
  tests, OK** (exit 0). That is 201 pre-existing + 26 new (10 Qt-free decode in
  `tests/test_gadget_decode.py`, 16 Qt projection in
  `tests/test_host_qt_gadget_projection.py`). No test failed in the aggregate.
  - *Environment note (both facts, per the prompt's rule)*: the aggregate run
    prints one stray line, `amiga-ui run: target run ended with code 1000 (not
    the documented WaitPort boundary)`, after the `OK` summary. This is
    **pre-existing** — it also appears on the unmodified base (verified by
    stashing the feature and re-running: base = 201 tests, same line) — and it
    comes from an in-process launcher test that runs the real app with inherited
    stdout, not from a failing test. The suite result is `OK`/exit 0 either way.
- **New focused decode tests**: 10/10 pass (each kind; cycle labels + active
  index with arbitrary non-iTidy labels; checkbox state incl. absent-tag default;
  labels; geometry; GadgetID; context-gadget exclusion; two-window isolation;
  `FreeGadgets` release).
- **New Qt projection tests**: 16/16 pass (widget class per kind; geometry;
  text/initial state; overlay without removing the group-box bevel op; refresh
  does not move/retext widgets; per-window close releases only its own widgets
  and association; double-close idempotent).
- **ruff check**: `All checks passed!`
- **ruff format --check**: `198 files already formatted` (after formatting; see
  the pre-existing `run_command.py` note below).
- **pyright** (src|tests|tools): **0 errors, 0 warnings**.
- **GUI smoke** (`tests/run_gui_smoke_test.py`): PASS (xcb/Xvfb window created,
  visible).
- **Host-projection smoke** (`-m tests.run_host_projection_smoke_test`): PASS
  (real iTidy window created/titled/sized/painted).
- **Xvfb gadget-projection smoke** (`-m tests.run_gadget_projection_smoke_test`,
  new): PASS — the real main window contains all four supported widget types
  with meaningful labels/geometry and the RastPort background remains visible.
- **Plain iTidy probe** (`amiga-ui probe …/iTidy`): status `app_failed` at the
  documented `WaitPort on empty message queue` boundary (honest, expected);
  analyser (`tools/analyze_target_failure.py --latest`) runs clean (the missing
  `ENV:`/`RAM:` prefs paths are pre-existing runtime-prep gaps, unrelated to
  gadgets).
- **Bounded real run** (`amiga-ui-xvfb -- amiga-ui run … --auto-close-after 8`):
  reached the WaitPort boundary, projected `06b3b8: 'iTidy v1.0 - Icon Cleanup
  Tool' 625x215`, host shell entered and exited cleanly (exit 0).
- **Headless Qt-freedom**: a fresh interpreter importing the probe/launcher/
  compat stack (including `gadtools_library`, `intuition_library`,
  `host.projection`) reports `PYSIDE False` and does not import
  `amiga_ui.host.qt_projection`; the repo's `test_cli.py` Qt-boundary tests
  (probe does not import Qt; plain run installs `NullHostWindowProjection`)
  pass.

### Pre-existing `run_command.py` format drift

`src/amiga_ui/host/run_command.py` was **already** failing `ruff format --check`
on `development` before this feature (verified by stashing the feature and
re-checking). To make the format gate pass it was reformatted (cosmetic only: a
`frozenset` literal and a string literal collapsed to fit the line length). This
was committed **separately** from the feature commit so the implementation commit
stays focused and the unrelated fix is isolated.

## Approximations / uncertainty

- **Enabled state**: the observed path projects every gadget as *enabled*. The
  app's `GA_Disabled` tag lives in the Intuition gadget-class tag space
  (`GA_Dummy`-based, `0x3800E`), not the GadTools tag space, and its GadTools
  interpretation is not established by classic evidence; the app passes `FALSE`
  (enabled), which matches the default. This is recorded as a compat note, not
  claimed as a decode.
- **`PLACETEXT` geometry**: the label placement (button label inside, checkbox
  label to the right, cycle label to the left as a separate caption, text
  inside) follows the classic `PLACETEXT_*` semantics as an approximation; exact
  caption offsets (e.g. the 6px cycle-caption gap) are host-side estimates, not
  decoded from the target.
- **Cycle caption width**: derived from host font metrics
  (`fontMetrics.horizontalAdvance` + a small pad), so the caption width depends
  on the host font, not the classic diskfont metrics.
- **Static, not interactive**: the widgets are populated correctly but are not
  wired to the app. `WaitPort` is not made to succeed on an empty queue and no
  `IntuiMessage` is fabricated; hover/focus/pressed visuals are a Qt artifact,
  not evidence of interactivity. `GT_SetGadgetAttrs` is **not** exercised during
  initial main-window setup (it is only called by the later LISTVIEW feature in
  `helpers/listview_columns_api.c`), so it is deliberately left unimplemented
  here rather than given an empty success stub; the registry's in-place
  `record()` already supports a future meaningful update.
- **Non-projected kinds**: kinds outside BUTTON/TEXT/CYCLE/CHECKBOX (and the
  context gadget) are decoded to a `kind_name` and recorded, but intentionally
  not turned into widgets in this increment.
- **shiboken deletion semantics** (test design note): under PySide6, a
  top-level `AmigaHostWindow` whose only Python reference is a throwaway
  projection is C++-deleted by GC (taking its children with it), and
  `deleteLater()` does not free a widget while a live Python reference exists.
  The Qt tests therefore keep a Python reference to the host window and assert
  close via the projection association + `isVisible()`, not via
  `shiboken6.isValid()` on a retained reference.

## Next increment (deliberately deferred)

The next host-GUI increment — **live Qt-event-to-IntuiMessage integration** —
should start from a **fresh branch** off the updated `development`, per the repo
branching workflow. The route to preserve and then wire is:

  Qt widget event -> IntuiMessage -> Window.UserPort -> WaitPort -> GT_GetIMsg -> GT_ReplyIMsg

This requires solving the interactive vamos/Qt scheduler and lifecycle (a Qt
widget event must be delivered to the app *while the target is genuinely
waiting* in `WaitPort`, without faking a successful `WaitPort` on an empty
queue). This increment stays strictly within accurate static gadget state and
host projection, and does not connect activation signals to
application-changing behavior.
