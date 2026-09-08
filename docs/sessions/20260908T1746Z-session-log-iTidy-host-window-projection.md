---
title: "Session log — iTidy host window projection (first end-to-end host-rendering slice)"
status: log
depends_on:
  - "../apps/itidy/run-log.md"
  - "../apps/itidy/compatibility-notes.md"
  - "../architecture/platform-target.md"
  - "../architecture/hosted-application-mode.md"
  - "../platform/library-cards/intuition.library.md"
  - "../platform/library-cards/gadtools.library.md"
  - "../platform/library-cards/graphics.library.md"
  - "../host-gui/threading-and-desktop-boundaries.md"
  - "../host-gui/painting-styling-and-layout.md"
  - "../host-gui/testing-host-ui.md"
  - "../workflows/error-driven-porting.md"
  - "../workflows/branching-and-merging.md"
citations_used:
  - S1
  - S42
  - S43
  - S49
  - S58
  - S61
  - S64
---

# Session log — iTidy host window projection (2026-09-08)

Purpose: Durable record of the session that implemented the **first narrow
end-to-end host-rendering slice** for hosted application mode. Starting from a
baseline where the entire `host-ui-required` (visible-UI) frontier and the
stateful-runtime frontier were already cleared (the prior
`20260906T1845Z-…-host-ui-frontier-cleared.md` and
`20260908T0847Z-…-stateful-runtime-frontier-cleared.md` sessions) and the full
ordered per-RastPort op stream was already recorded, this session added a
projection boundary that turns the already-intercepted Intuition/GadTools window
intent into **real host top-level Qt windows** and **replays** the recorded RastPort
op stream onto a custom drawing surface. A real iTidy run under Xvfb now opens a
genuinely visible, correctly titled/positioned host window that is actually
painted. The compatibility layer stays Qt-free, the plain (non-GUI) probe still
never requires a display, and the honest `WaitPort`-on-empty-queue boundary stayed
intact throughout.

Needed for:
- Recalling *how* host rendering is wired: the Qt-free projection boundary, the
  PySide6 projection (host window + replay surface), and the three compat-layer
  hook points (`OpenWindowTagList` / `CloseWindow` / `GT_RefreshWindow`).
- Recalling the **display-free guarantee**: a `NullHostWindowProjection` is the
  default, so ordinary probes keep working with no X server and no Qt import.
- Recalling the *deliberate* approximations left in place (non-`DM_COPY` draw
  modes, the bevel frame, the pen palette) so they are not mistaken for defects.
- Knowing the next host-GUI increment (an interactive host event loop).

Notes:
- This is the first increment that produces *visible* host output. Everything
  before it recorded emulated state / host-side ops that a *future* renderer would
  replay; this session is that first renderer, scoped to one window's initial paint.

## Session summary

| Item | Value |
| --- | --- |
| Harness | DeepSeek Harness (dsh), Web GUI at 127.0.0.1:3080 |
| Sandbox / approval | workspace-write / ask |
| Main work date | 2026-09-08 (UTC+01:00) |
| Work span (from commit evidence) | baseline 13:25 → merge 16:40 local (≈3 h active across one gated increment) |
| Model | `Qwen3.8-27B-UD-Q6_K_M` (llama-cpp, OpenAI-compatible endpoint) |
| Git baseline → end | `development` @ aaa9711 → f20b59c (one feature branch `feat/host-window-projection`, created, gated, no-ff-merged; kept, not deleted) |
| Exact request/token counts, compactions, session id | in the raw session log on the agent host (not re-derived here) |

Milestone achieved: a real iTidy run under Xvfb, driven in-process through the
repo `vamos` launcher with a PySide6 projection installed, opens **one** real host
top-level window — titled **"iTidy v1.0 - Icon Cleanup Tool"** at exactly **625×215**
(the Amiga window's title and initial geometry) — and replays the **59-op** RastPort
stream (lines, rect fills, `Text`/`PrintIText`, the group-box bevel) onto its drawing
surface, producing **13,433** non-background pixels. The 1×1 backdrop utility window
is tracked but correctly **not** projected. The final plain probe
(`artifacts/runs/20260908T153627Z-probe-iTidy`) is **headless** (no `DISPLAY`, no
`QT_QPA_PLATFORM`), ends at the honest `WaitPort`-on-empty-queue boundary with **zero**
Qt references, and `tools/analyze_target_failure.py --latest` reports the **same**
baseline as before this session (only the prepared-runtime `ENV:/ENVARC:/RAM:/S:`
gaps remain) — i.e. no stateful/host-UI call was regressed and no display is newly
required.

## What changed in the repo (in order)

| Commit | Branch (kept) | Change |
| --- | --- | --- |
| adef637 | `feat/host-window-projection` | New Qt-free boundary `src/amiga_ui/host/projection.py` (`OpenWindowIntent` with an app-facing decision, the `HostWindowProjection` protocol, and `NullHostWindowProjection` as the no-GUI default). New PySide6 projection `src/amiga_ui/host/qt_projection.py` (`AmigaHostWindow` — a plain top-level `QWidget`, so menu-bar-free by construction; `RastPortReplaySurface` — replays the ordered op stream, treating `TextLength`/`Move`/pen-state as history not marks; `QtHostWindowProjection` — one host window per app-facing window, refresh replays the bound registry's op stream, close is idempotent; plus an explicit, replaceable `CLASSIC_PEN_PALETTE`). Compat-layer hooks (no Qt import): `intuition_library.py` `OpenWindowTagList` decodes the `WA_Title` C-string and calls `projection.open_window(OpenWindowIntent)` (new `_s16` signed-coordinate helper), `CloseWindow` calls `projection.close_window`; `gadtools_library.py` `GT_RefreshWindow` calls `projection.refresh_window`. `launcher.py` threads a `host_projection` param through `ProjectSetupLibManager` / `VamosSessionRunner` / `run_vamos_in_process`, defaults to `NullHostWindowProjection`, binds the run-wide `RastPortRegistry` to the projection, and exposes it as the `ctx.host_projection` extra attr. Tests: `tests/test_host_projection.py` (Qt-free boundary), `tests/test_host_qt_projection.py` (offscreen Qt window/replay/refresh/close driven by a synthetic `RastPortState`), `tests/run_host_projection_smoke_test.py` (narrow Xvfb-backed iTidy smoke). |

## Blocker narrative (what actually happened)

### 1. The frontier at session start

The two prior sessions had already made every Amiga-side obligation *meaningful*:
the app's full drawing is recorded as one ordered, per-RastPort op stream, and the
app's two windows are fully understood. From the baseline probe the relevant facts
were:

- **Window 1 (backdrop)** `win=0x06AB44`, geometry `(319,199,1,1)`, `title=NULL`,
  `idcmp=0` — a 1×1 utility window. **Not** app-facing; must stay internal.
- **Window 2 (main)** `win=0x06B344`, geometry `(50,30,625,215)`, a real title
  pointer, `idcmp=836` — the visible app window. **App-facing**; must be projected.
- Both share one RastPort (`rp=0x06a8a8`) with **59 ops**: paint ops
  `Draw`(24) / `RectFill`(4) / `PrintIText`(3) / `Text`(1) / `DrawBevelBox`(1);
  state/history `SetAPen`(12) / `Move`(7) / `SetFont`(1) / `SetDrMd`(1) /
  `SetBPen`(1); measurement `TextLength`(4). Draw modes present: `DM_COPY` (0x8C)
  and `DM_NOT` (0x01).
- `GT_RefreshWindow` already fired for the main window (`win=0x06B344`) — the
  natural repaint boundary.

So the remaining gap was purely the *host side*: nothing yet turned that intent
and that op stream into a visible, painted host window. The task was scoped to that
one slice — **not** the complete iTidy interface (no menus/requesters/pref parsing,
no general IFF parser, no interactive event loop this increment).

### 2. The Qt-free projection boundary

The first decision was to put a **Qt-free boundary** between the compatibility
layer and Qt so that the low-level Amiga libraries never import Qt.
`src/amiga_ui/host/projection.py` defines:

- `OpenWindowIntent` — a dataclass carrying the already-interpreted window
  (window addr, decoded title, signed `left`/`top`, unsigned `width`/`height`,
  RastPort addr, `idcmp`, `has_menu_strip`), with an `is_app_facing` property
  (`bool(title) or idcmp != 0 or has_menu_strip`).
- `HostWindowProjection` — a `Protocol` with `open_window` / `refresh_window` /
  `close_window` / `bind_registry`.
- `NullHostWindowProjection` — the no-GUI default that records
  `opened`/`refreshed`/`closed`, refreshes only for known windows, and closes
  idempotently, importing **no** Qt.

This is what makes "ordinary non-GUI probes remain supported and don't unexpectedly
require a display" hold by construction: the default projection is inert and
Qt-free.

### 3. The PySide6 projection (window + replay surface)

`src/amiga_ui/host/qt_projection.py` is the concrete, Qt-only projection:

- `AmigaHostWindow` is a **plain top-level `QWidget`** (deliberately *not*
  `QMainWindow`), so it carries **no menu bar by construction** — the
  "no menu bar unless a menu strip is attached" rule holds without any extra
  guard. It sets the title, resizes to the Amiga window's `width`/`height`,
  moves to `left`/`top` when given, and holds one `RastPortReplaySurface` child in
  a zero-margin `QVBoxLayout`.
- `RastPortReplaySurface` implements `paintEvent` by filling a background then
  replaying `state.ops` in order: `Draw`/`AreaDraw` → line in `apen`; `RectFill` →
  filled rect in `bpen`; `Text`/`PrintIText` → `drawText` at the recorded position
  in the front/`apen` (only for non-empty text); `DrawBevelBox` → light/dark edges
  derived from the background (recessed swaps). `TextLength`/`Move`/`AreaMove` and
  all the `Set*`/`InitRastPort` state ops produce **no** visible mark.
- `QtHostWindowProjection` stores the window-address → host-window association,
  creates/shows an `AmigaHostWindow` **only** when `intent.is_app_facing`, replays
  `bind_registry(...).state(rport_addr)` on `refresh_window`, and closes
  idempotently.

Threading: every widget is created and mutated on the GUI thread. The in-process
vamos run executes on the main (GUI) thread, so no `QThread`/worker architecture is
introduced, consistent with `threading-and-desktop-boundaries.md`.

### 4. The three compat-layer hook points

The compatibility layer expresses intent through the boundary **without importing
Qt** (it imports only the pure-data `OpenWindowIntent`):

- `IntuitionLibrary.OpenWindowTagList` — after the window block is built, it decodes
  the `WA_Title` pointer to a NUL-bounded C-string (reusing the existing
  `_read_cstr`), converts `left`/`top` to signed 16-bit (new `_s16`), and calls
  `projection.open_window(OpenWindowIntent(...))` (guarded for `None`).
- `IntuitionLibrary.CloseWindow` — after freeing the window + ports, calls
  `projection.close_window(window)` (idempotent).
- `GadToolsLibrary.GT_RefreshWindow` — keeps the existing `refresh_requests.append`
  (still asserted by `tests/test_gadtools_bevel.py`) **and** adds
  `projection.refresh_window(win)` — the first repaint boundary. No polling timer is
  used; replay is driven by the app's own refresh call.

### 5. The launcher wiring + the display-free guarantee

`launcher.py` threads an optional `host_projection` through
`ProjectSetupLibManager` → `VamosSessionRunner` → `run_vamos_in_process`. When
omitted, a `NullHostWindowProjection` is installed (so `ctx.host_projection` always
exists and plain probes are display-free). The run-wide `RastPortRegistry` is bound
to the projection (`bind_registry`) so refresh can resolve the op stream, and the
projection is exposed as the `ctx.host_projection` extra attr. The launcher itself
stays Qt-free: it imports only `NullHostWindowProjection` (from the Qt-free
`projection` module); the PySide6 module is imported only by the GUI path (tests / a
future host shell).

## Key technical findings

### The projection boundary keeps Qt out of the compat layer

The single most important structural decision. The Amiga libraries
(`intuition_library.py`, `gadtools_library.py`) import only the **pure-data**
`OpenWindowIntent` from `amiga_ui.host.projection` — a module that imports no Qt —
so importing the compat layer and the launcher pulls **no** PySide6 (verified:
`'PySide6' in sys.modules` is `False` after importing them). This is what lets the
plain probe stay headless and keeps Qt imports out of the low-level libraries, as
the task required.

### A plain top-level `QWidget` is menu-bar-free by construction

Using `QWidget` (not `QMainWindow`) means there is no `menuBar()` at all, so the
hosted-application-mode rule "attach a host menu bar only when the Amiga window has
a menu strip" is satisfied for this increment (no menu strips are attached) without
any conditional. A `has_menu_strip` property is carried on the intent for the future.

### The app-facing decision lives in the projection, not the widget

`OpenWindowIntent.is_app_facing` (title/IDCMP/menu-strip) is computed from
already-interpreted values in the Qt-free boundary, so the Amiga-memory
interpretation stays in the compat layer and the Qt widget is a dumb surface. This
is what correctly keeps the 1×1 backdrop window internal while projecting the main
window — the smoke test asserts exactly one projected, titled window.

### `GT_RefreshWindow` is the repaint boundary (no polling timer)

Replay is triggered by the app's own `GT_RefreshWindow` call (which it issues after
drawing), not by a `QTimer`. This matches the "no background timers/polling loops"
rule and means the paint is driven by the app's real redraw semantics.

### Non-`DM_COPY` draw modes are a documented approximation

iTidy's gadget ops use `DM_NOT` (0x01) as well as `DM_COPY` (0x8C). This increment
renders every op as `DM_COPY` (source-over); the XOR/NOT semantics are not
implemented. This is recorded as a known approximation, not a defect, so it is not
mistaken for a bug in a later session.

## Latent defects and follow-ups (not fixed this session)

- **No interactive host event loop.** The window is drawn but host mouse/keyboard
  events are not routed to gadgets; the app still ends at the honest
  `WaitPort`-on-empty-queue boundary. This is the next increment (route host input
  into real IntuiMessages via the existing `IntuitionEventBridge`).
- **Non-`DM_COPY` draw modes** (e.g. `DM_NOT`) render as `DM_COPY`.
- **Bevel frame and pen palette are approximations.** `DrawBevelBox` edges are
  derived by lightening/darkening the background, and `CLASSIC_PEN_PALETTE` is an
  explicit 16-entry classic-style table — neither claims pixel-exact Workbench
  fidelity (that would need the real DrawInfo/screen colour state, which the notional
  public screen does not render).
- **`Text` draws in the recorded `apen`** (the op stream carries the pen);
  `PrintIText` uses the IntuiText front pen. Font is a fixed Monospace stand-in, not
  the opened disk font's metrics.
- **No menu strip / requester / pref parsing** this increment (explicitly out of
  scope).

## Techniques that worked

- **One branch for one coherent increment, gated, then merged.**
  `feat/host-window-projection` off updated `development`, gated (full suite, GUI
  smoke, ruff, pyright, plain probe, Xvfb smoke), then no-ff-merged into
  `development`; the branch is kept, not deleted.
- **A Qt-free boundary + a Qt-only projection.** The boundary module imports no Qt,
  so the compat layer and launcher stay display-free; the PySide6 module is imported
  only by the GUI path. Verified by asserting PySide6 is not in `sys.modules` after
  importing the compat layer / launcher.
- **Two layers of tests at the right altitude.** Qt-free unit tests for the
  boundary (run headless, no display), offscreen-Qt unit tests for the
  window/replay/refresh/close driven by a **synthetic** `RastPortState` (so most
  tests don't need iTidy or Xvfb), and **one** narrow Xvfb-backed smoke test that
  runs real iTidy end-to-end. A single small pixel assertion (non-background
  pixel count) proves the paint path actually draws, per `testing-host-ui.md`.
- **Pin the offscreen platform only for `QApplication` construction.** The Qt unit
  test sets `QT_QPA_PLATFORM=offscreen` for the moment of construction and restores
  the ambient value immediately, so it does not leak `offscreen` into `test_xvfb`
  (whose `build_env` must default to `xcb`).
- **Reuse the existing integration fixture.** The Xvfb smoke reuses
  `_LauncherRuntimeFixture` + `build_itidy_args` from `tests/test_vamos_launcher.py`
  and the `start_xvfb`/`build_env` helpers, so it shares the exact in-process run
  path the other integration tests use.
- **Assert the honest boundary, not a clean exit.** The iTidy *binary* ends at the
  `WaitPort`-on-empty-queue boundary (a documented target limitation), so the smoke
  test asserts the host window was created/titled/sized/painted **and** that the
  app did *not* exit cleanly — it does not bless a fake success.
- **Git discipline per `../workflows/branching-and-merging.md`:** the full suite
  (165 OK) + `tests/run_gui_smoke_test.py` (Xvfb) + `ruff check`/`format` +
  `pyright` (0 errors) + the plain `amiga-ui probe` (headless, honest boundary, zero
  Qt) + `tools/analyze_target_failure.py --latest` (baseline unchanged) + the new
  `tests/run_host_projection_smoke_test.py` (Xvfb iTidy) before the merge.

## Session-log recovery note

The full raw session log (zstd-compressed JSONL: all user/assistant messages,
reasoning, tool calls, tool results, compaction events) is stored on the agent host
under the harness sessions directory for this session id and is a strict superset of
this file; use it to recover exact commands, outputs, the exact session-creation
time, and the request/token counts (which this markdown does not re-derive). This
markdown is the distilled, repo-durable version.
