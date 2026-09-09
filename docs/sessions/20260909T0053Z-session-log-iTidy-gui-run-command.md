---
title: "Session log — iTidy GUI run command, per-window RastPort, and draw-mode correction"
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
---

# Session log — iTidy GUI run command (2026-09-09)

Purpose: Durable record of the session that turned the previously-tested host
window projection into a **supported, user-invokable GUI launch path** and
corrected two drawing/window-ownership assumptions. Building on the prior
`20260908T1746Z-…-host-window-projection.md` increment (which added the Qt-free
projection boundary, the PySide6 projection, and the first visible, painted iTidy
window under Xvfb), this session added:

1. **`amiga-ui run <binary>`** — a documented, user-facing GUI launch command that
   reuses the probe's target resolution and prepared runtime, installs the *real*
   Qt projection (not the null projection), and keeps the host shell open after the
   target run ends so the projected window can be inspected.
2. **Per-window RastPort ownership** — each opened app-facing Amiga window now gets
   its **own** valid `RastPort` (a distinct allocation, not the public screen's
   embedded RPort), so two windows' drawing can never be replayed into the wrong
   host window, and `CloseWindow` releases only the closing window's allocation.
3. **Renderer draw-mode correction** — `RectFill` now fills with the **FgPen**
   (mode-aware) and the classic `RastPort` draw modes are implemented with their
   documented meanings (`JAM1`/`JAM2`/`COMPLEMENT`/`INVERSVID`), with
   `COMPLEMENT` as a genuine bitwise XOR rather than a mislabeled approximation.

The plain `probe` command remains headless/null-projected and Qt-free, the honest
`WaitPort`-on-empty-queue boundary stayed intact throughout, and a real iTidy run
under Xvfb still opens one correctly titled/positioned host window that is actually
painted (13,433 non-background pixels).

Needed for:
- Recalling *how* the GUI launch path is wired: the `run` subcommand, the
  `run_command.py` lifecycle (target run phase vs host-shell exit), and the
  no-display failure path.
- Recalling the **per-window RastPort** decision (allocation in
  `OpenWindow`/`OpenWindowTagList`, release in `CloseWindow`, up-front registry
  registration) so it is not regressed back to a shared screen RPort.
- Recalling the **corrected** RastPort draw-mode semantics and the `COMPLEMENT`
  bitwise-XOR implementation (and why Qt's `CompositionMode_Xor` could not be
  used), so the earlier "DM_COPY approximation" framing is not mistaken for the
  current behavior.
- Knowing the next host-GUI increment (an interactive host event loop that routes
  host input into real IntuiMessages).

Notes:
- This increment makes the visible host window *user-reachable* without a test
  harness: a developer runs one documented command on a graphical desktop and sees
  iTidy's projected window. Static inspection is an acceptable milestone; gadget
  interaction is still the next increment.

## Session summary

| Item | Value |
| --- | --- |
| Harness | DeepSeek Harness (dsh), Web GUI at 127.0.0.1:3080 |
| Sandbox / approval | workspace-write / ask |
| Main work date | 2026-09-09 (UTC) |
| Model | `Qwen3.8-27B-UD-Q6_K_M` (llama-cpp, OpenAI-compatible endpoint) |
| Git baseline → end | `development` @ `beb9fea` → feature branch `feat/gui-run-command` (created from `development`, gated, merged; kept, not deleted) |
| Exact request/token counts, compactions, session id | in the raw session log on the agent host (not re-derived here) |

Milestone achieved: `uv run amiga-ui run
amiga_apps/itidy1classic/binary/extracted/iTidy` on a graphical desktop (verified
under Xvfb) opens **one** real host top-level window — titled **"iTidy v1.0 - Icon
Cleanup Tool"** at exactly **625×215** — and replays the main window's **55-op**
RastPort stream onto its drawing surface, producing **13,433** non-background
pixels (identical to the prior baseline). The 1×1 backdrop utility window is still
tracked but correctly **not** projected. After the target run reaches its honest
`WaitPort`-on-empty-queue boundary the host shell stays open (with
`--auto-close-after` it exits on the timer); both the offscreen and Xvfb bounded
launch checks exit 0. The plain `probe` remains headless (no `DISPLAY`, no
`QT_QPA_PLATFORM`), ends at the same `WaitPort` boundary with **zero** Qt imports,
and `tools/analyze_target_failure.py --latest` reports the **same** baseline
missing-path list as before this session.

Verification (the full gate run before the merge):
`uv run python -m unittest discover -s tests -p "test_*.py"` → **189 OK**;
`uv run ruff check src/ tests/` → all checks passed; `uv run pyright src/ tests/`
→ **0 errors**; `uv run python tests/run_gui_smoke_test.py` → **exit 0** (Xvfb
minimal window); `uv run python -m tests.run_host_projection_smoke_test.py` →
**PASS** (one projected titled window "iTidy v1.0 - Icon Cleanup Tool" 625×215,
**55 ops**, **13,433** non-background pixels, and the target did **not** exit
cleanly); the plain `uv run amiga-ui probe …/iTidy` is headless at the honest
`WaitPort` boundary (port `06b4e8`) with **zero** Qt imports and the failure
analyser reports the **same** baseline missing-path list; the bounded direct
`run` launch (offscreen and under Xvfb, `--auto-close-after 2`) reports the
`WaitPort` boundary, the projected window, "host shell active" then "host shell
exited", and **exit 0**; and the no-display path fails cleanly with **exit 2**
rather than aborting.

## What changed in the repo (in order)

| File | Change |
| --- | --- |
| `src/amiga_ui/vamos/rastport_state.py` | Added the classic RastPort draw-mode constants `JAM1=0`, `JAM2=1`, `COMPLEMENT=2`, `INVERSVID=4`; the default draw mode is now `JAM2` (documented `InitRastPort` value). `RastPortState` standard values are `apen=0xFF`, `bpen=0`, `draw_mode=JAM2`, `maxpen=0`, `outline_pen=0xFF`; `init()` resets to those standard values. Added `RastPortRegistry.remove(rp)` so a window can unregister its RPort on close. |
| `src/amiga_ui/vamos/intuition_library.py` | `OpenWindowTagList` now allocates a **window-owned RastPort** (a 0x50-byte block, label "Intuition.WindowRPort"), initializes it to the documented standard values, explicitly copies the font pointer + `TxHeight`/`TxWidth` from the public screen RPort, stores the pointer at `Window.RPort` (offset 0x32), and registers it up-front in the run-wide `ctx.rastports` registry keyed by address. `CloseWindow` unregisters and frees that window's RPort block (and the window) without touching any other window's state. `GetScreenDrawInfo` still returns the public screen RPort (a different target). |
| `src/amiga_ui/host/qt_projection.py` | `RastPortReplaySurface` now builds an offscreen `QImage` raster by replaying the op stream and blits it in `paintEvent` (rebuilt when the stream grows or the size changes, so a late paint always shows the full recorded stream). `RectFill` fills with the **mode-aware pen** (FgPen under `JAM1`/`COMPLEMENT`, BgPen under `JAM2`). `Draw`/`AreaDraw`/`Text` select the pen by draw mode (`INVERSVID` swaps the pens; `COMPLEMENT` XORs). `COMPLEMENT` is implemented as a genuine per-pixel bitwise XOR via a white-on-black coverage mask + channel XOR into the raster — **not** a Qt composition mode (Qt's `CompositionMode_Xor` is Porter-Duff non-overlap, a different operation). `PrintIText` stays on the IntuiText front pen (`IntuiText.DrawMode` is a separate value set, not decoded). The stale "DM_COPY approximation" docstring was removed. |
| `src/amiga_ui/host/run_command.py` | **New, Qt-only** module (imported lazily by the CLI `run` command so `probe` stays Qt-free). `run_gui_launch(vamos_args, timeout, auto_close_after, projection)` reuses an existing `QApplication` if present (else constructs one, failing clearly with exit 2 when no usable display is available — a pre-flight `_no_display_reason()` check, because on this PySide6 build a failed `QApplication` **aborts** the process, exit 134, rather than raising). It runs the in-process vamos target phase (bounded by a `SIGALRM` timeout, real `NamedTemporaryFile` stdout/stderr), reports whether the target hit the documented `WaitPort`-on-empty-queue boundary vs exited cleanly vs failed elsewhere, and — if at least one app-facing window was projected — keeps the host shell (`app.exec()`) alive until the last window closes or `auto_close_after` seconds elapse, then releases every projected window. Return codes: 0 clean shell cycle, 1 no app-facing window, 2 no display. |
| `src/amiga_ui/cli.py` | Added the `run` subcommand (positional `binary`, `--timeout`, `--auto-close-after`, `func=_run_cmd`). `_run_cmd` reuses the probe's `resolve_probe_target` + `_probe_preflight_errors` + `_prepare_probe_runtime` + `_build_probe_args` (no divergent second preparation) and calls `run_gui_launch` with `projection=None` (so the real Qt projection is installed). The `gui_smoke` import was made lazy so the module-level CLI import stays Qt-free. |
| `tests/test_cli.py` | **New.** Parsing of `run` (defaults/overrides, existing subcommands still parse); the Qt boundary (importing the CLI and a plain `probe` do **not** import PySide6, in fresh interpreters); that `run_gui_launch` installs a real `QtHostWindowProjection` when none is injected; that the CLI `run` command reuses the probe's prepared vamos args and passes `projection=None`; that an ordinary (non-GUI) run installs `NullHostWindowProjection`; the no-display clean-fail (exit 2, fresh interpreter so the Qt SIGABRT cannot kill the runner); and a bounded end-to-end GUI launch (fresh interpreter, offscreen Qt, `--auto-close-after`) that proves the shell enters and exits cleanly with no manual interaction. |
| `tests/test_intuition_library.py` | Added `IntuitionWindowRPortTest` with a `_FakeAlloc` (alloc/free/cstr) + `_FakeVLib`/`_FakeVLibMgr`: the window RPort is **not** the screen RPort; it carries the standard values and inherits font/text metrics; its state is registered in the shared registry; two windows have **isolated** op streams; `CloseWindow` releases only the closing window's RPort (and window) and leaves the other's state intact; and close notifies the projection. The stale `0x8C` "DrawMode (JAM2)" `IntuiText` byte write was corrected to an honest 0 with a comment (IntuiText.DrawMode is a different value set the local NDK does not define). |
| `tests/test_graphics_library.py` | Added `test_draw_mode_constants_are_classic_rastport_modes` and `test_registry_remove_returns_and_drops_the_state`; `test_set_dr_md_accepts_classic_mode_bits` (NDK: "mode — 0-255"). Stale assertions updated to the documented standard values (init → apen 0xFF / bpen 0 / DrMd JAM2 / outline 0xFF); arbitrary `0xC0`/`0x8C` bytes replaced with the meaningful constants. |
| `tests/test_host_qt_projection.py` | Added `DrawModeSemanticsTest`: `RectFill` default mode uses BgPen, `JAM1` uses FgPen, `INVERSVID` swaps pen roles, `COMPLEMENT` is a **genuine** XOR (red then blue → magenta overlap, unchanged red elsewhere), and `Draw` respects the draw-mode pen. |
| `AGENTS.md` | "Runtime And GUI": `probe` is the headless/null-projected path; added the `run` GUI-launch command (reuses the prepared runtime, real Qt projection, exit 2 with no display). |
| `README.md` | Added `run` to the subcommand list + examples (including an Xvfb `--auto-close-after` form) and a "Run (GUI Launch)" section describing the lifecycle and the `probe` vs `run` distinction. |
| `docs/architecture/hosted-application-mode.md` | Window Projection: each app-facing window owns its **own** RastPort (allocated, standard-initialized, font/metrics copied, stored at `Window.RPort`). Implementation Consequences: window RPort lifecycle (alloc/register on open, unregister/free on close; the public screen keeps its own embedded RPort for screen-level drawing + `GetScreenDrawInfo`). New "Launching From The Command Line" section for `amiga-ui run`. |
| `docs/platform/library-cards/graphics.library.md` | New "Draw-Mode And RectFill Semantics" section: `DrMd` is a RastPort draw mode (not a blitter minterm); the four modes with their values; `RectFill` fills with FgPen mode-aware (NDK); `InitRastPort` standard values; `COMPLEMENT` is a genuine bitwise XOR (not a Qt composition mode); `IntuiText.DrawMode` is a different, not-decoded value set; the `0x8C` byte was a mislabeled observation. |

## Blocker narrative (what actually happened)

### 1. The starting point

The prior session had proven the projection works under a test harness (Xvfb
smoke), but the visible window was not **user-reachable**: there was no documented
command a developer could run on a desktop to see it. Two correctness assumptions
also needed fixing before that command could be trusted:

- **Shared drawing state.** Every window drew through the public screen's embedded
  RastPort, so two windows' op streams shared one target — a latent risk that one
  window's drawing could be replayed into the other's host window.
- **Mislabeled draw modes.** The renderer treated non-`DM_COPY` modes as an
  approximation (everything rendered source-over) and a recorded `0x8C` "DrawMode"
  was presented as if it were a real RastPort mode. In fact the classic `RastPort`
  draw modes are `JAM1`/`JAM2`/`COMPLEMENT`/`INVERSVID` [S1
  Include_H/graphics/rastport.h L90-L95], `RectFill` uses the FgPen mode-aware [S1
  Autodocs/graphics.doc RectFill], and `IntuiText.DrawMode` is a separate value set
  the local NDK does not define.

### 2. The `run` command reuses the probe's preparation

The requirement was explicit: **do not copy the probe runtime preparation into a
divergent second implementation** — extract or reuse the smallest shared helper.
`_run_cmd` therefore calls the *same* `resolve_probe_target`,
`_probe_preflight_errors`, `_prepare_probe_runtime`, and `_build_probe_args` the
`probe` command uses, builds the identical `-V`/`-a`/`--cwd` vamos argument list
into a temp runtime dir + a real `NamedTemporaryFile` wasms log, and hands it to
`run_gui_launch` with `projection=None`. The only difference between `probe` and
`run` is which projection is installed: `probe` runs the launcher's default
`NullHostWindowProjection`; `run` installs `QtHostWindowProjection`. That single
difference is asserted directly in `tests/test_cli.py`.

### 3. The `run` lifecycle: target run phase vs host-shell exit

The command distinguishes two events that must not be conflated:

- **The target run phase** ends when the in-process vamos run returns. For the
  current target that is the honest `WaitPort`-on-empty-queue boundary (the app's
  main loop blocks on an empty `UserPort`). The command detects the marker in the
  wasms log and reports it, versus "exited cleanly" vs "ended with code N".
- **The host shell** only starts *after* the run phase, and only if at least one
  app-facing window was projected (otherwise it fails clearly with exit 1 and never
  enters `app.exec()`). It stays open for inspection until the last projected window
  is closed (Qt's default quit-on-last-window-closed) or `auto_close_after` seconds
  elapse (a `QTimer.singleShot` for automation), then releases every window.

The run phase is bounded by a `SIGALRM` `setitimer` timeout (cleared before the
event loop), so a hung target cannot hang the command.

### 4. The no-display failure path must not abort the process

The requirement "fail clearly when no usable display is available" turned out to be
subtle: on this PySide6/Qt build, constructing `QApplication` when the xcb platform
has no display **aborts the whole process** (SIGABRT, exit 134) via C++ `qFatal` —
it does **not** raise a Python `RuntimeError`. So the "fail clearly" guarantee can
only be met by detecting the condition *before* the `QApplication` constructor runs.
`_no_display_reason()` is deliberately conservative: it reports "no display" only
when the requested platform is not self-contained (offscreen/minimal/etc.) and
neither `DISPLAY` nor `WAYLAND_DISPLAY` is set; any uncertainty defers to Qt (with
the `RuntimeError` catch kept as a fallback for builds that do raise). The result is
a clean exit 2 with a clear message instead of an abort.

### 5. Per-window RastPort ownership

`OpenWindowTagList` now allocates a distinct 0x50-byte window RPort block,
initializes it to the documented standard values (Mask/FgPen/AOLPen/LinePtrn = -1,
DrawMode = JAM2 [S1 Autodocs/graphics.doc InitRastPort]), **explicitly** copies the
font pointer and `TxHeight`/`TxWidth` from the public screen RPort (preserving the
classic inheritance behavior through explicit initialization rather than shared
mutable state), stores the pointer at `Window.RPort`, and registers it up-front in
the run-wide `ctx.rastports` registry keyed by address. Because every RastPort is a
distinct registered address, per-window op-stream isolation is structural: drawing
into a window's RPort can only ever land in that window's stream. `CloseWindow`
unregisters and frees exactly that window's RPort (and the window). The public
screen keeps its own embedded RPort for screen-level drawing and for
`GetScreenDrawInfo`, which is a different target from any window's RPort.

The observable effect on the iTidy run: the main window's stream is now **55 ops**
(the 3 `TextLength` measurement ops and 1 `SetFont` that previously sat on the
shared screen RPort moved to the screen RPort's own stream). The rendered pixel
count is unchanged (13,433) because those relocated ops produce no visible marks.

### 6. Draw-mode correction + the `COMPLEMENT` XOR

The renderer now implements the documented RastPort draw modes:

- `JAM1` (0) → foreground pen; `JAM2` (1) → background pen.
- `INVERSVID` (4) → swap the foreground/background pen roles for the op.
- `COMPLEMENT` (2) → bitwise XOR with the existing pixel.

`RectFill` fills with the FgPen, taking the draw mode into account [S1
Autodocs/graphics.doc RectFill]. `COMPLEMENT` is the subtle one: Qt has no
bitwise-XOR `QPainter` composition mode — `CompositionMode_Xor` is Porter-Duff
non-overlap (red-over-blue → black, not magenta), verified empirically. So
`COMPLEMENT` is implemented as a genuine per-pixel bitwise XOR: draw the op into a
white-on-black coverage mask, then for each covered pixel XOR the mask's
channel-1 bit into the raster's RGB channels. This makes `COMPLEMENT` real XOR, not
an approximation, and the stale "DM_COPY approximation" docstring was removed.
`PrintIText` deliberately does **not** decode `IntuiText.DrawMode` (a different
value set the local NDK does not define) — recorded as a deferral, not a guess.

## Key technical findings

### The Qt-free boundary holds for `run` too
`cli.py` imports the CLI surface with **no** module-level Qt import; `gui_smoke`
and `run_command` are imported lazily inside their handlers. Verified in fresh
interpreters: importing `amiga_ui.cli` and running a plain `probe` leave
`'PySide6' in sys.modules` `False`. The low-level Amiga libraries and the launcher
remain Qt-free; only the `run` path pulls PySide6.

### A failed `QApplication` aborts, so "no display" is a pre-flight check
On this PySide6 6.11.1 / Qt 6 build, a `QApplication` on xcb with no display dies
via C++ `qFatal` (SIGABRT, exit 134) rather than raising. The clean exit-2
behavior therefore requires a conservative pre-flight check
(`_no_display_reason()`) that only short-circuits when a display is *certainly*
absent, deferring every uncertain case to Qt.

### Per-window RPort isolation is structural, not behavioral
Because the run-wide registry is keyed by RastPort **address** and each window's
RPort is a distinct allocation registered up-front, two windows' op streams cannot
mix. This is proven directly by
`IntuitionWindowRPortTest.test_two_windows_have_isolated_op_streams` and
`test_close_window_releases_only_its_own_rport`.

### `COMPLEMENT` is genuine XOR, implemented around Qt's composition modes
Qt's `CompositionMode_Xor` is Porter-Duff non-overlap, not bitwise XOR (verified:
red then blue → black overlap, not magenta). The bitwise XOR is implemented with a
coverage mask + per-pixel channel XOR into an offscreen `QImage` raster, which is
what makes the red-then-blue → magenta unit test pass.

### The `0x8C` "DrawMode" was a mislabeled observation
The previously recorded `0x8C` byte on an `IntuiText` was presented as a RastPort
draw mode. It is neither a RastPort mode (the set is JAM1/JAM2/COMPLEMENT/INVERSVID)
nor a defined `IntuiText.DrawMode` value (the local NDK does not define that field's
bits). The test now writes an honest 0 with a comment, and the graphics card records
the correction.

## Latent defects and follow-ups (not fixed this session)

- **No interactive host event loop.** The window is drawn and inspectable, but host
  mouse/keyboard events are not routed to gadgets; the app still ends at the honest
  `WaitPort`-on-empty-queue boundary. This is the next increment (route host input
  into real IntuiMessages via the existing `IntuitionEventBridge`).
- **`IntuiText.DrawMode` is not decoded.** The local NDK does not define its bit
  values, so `PrintIText` uses the IntuiText front pen and does not apply a draw
  mode. Recorded as a deferral, to be revisited with a source that defines the bits.
- **Bevel frame and pen palette remain approximations.** `DrawBevelBox` edges are
  derived by lightening/darkening the background and `CLASSIC_PEN_PALETTE` is an
  explicit 16-entry classic-style table — neither claims pixel-exact Workbench
  fidelity (that would need the real DrawInfo/screen colour state, which the
  notional public screen does not render).
- **Undefined draw-mode bits are ignored.** Only the four documented RastPort modes
  are interpreted; any other bits in `DrMd` are dropped (honest, per the NDK's
  four-mode definition).
- **Host font is a fixed Monospace stand-in**, not the opened disk font's metrics.

## Techniques that worked

- **Reuse, don't re-implement, the probe preparation.** The `run` command calls the
  same `_build_probe_args`/`_prepare_probe_runtime` the probe uses; the only
  difference is the installed projection. The test asserts the arg list is the
  prepared probe shape and that `projection=None` is passed (so the *real* Qt
  projection is created, not a test double).
- **Detect "no display" before `QApplication`.** Because Qt aborts (exit 134)
  instead of raising, the clean exit-2 path is a conservative pre-flight check, with
  a `RuntimeError` catch kept as a fallback. The test runs it in a fresh interpreter
  so a potential abort cannot kill the test runner.
- **A raster that rebuilds when the stream grows.** The op stream can grow after the
  last `GT_RefreshWindow` (the app keeps drawing), so `paintEvent` rebuilds the
  offscreen raster when the op count or size changed — preserving the old
  paint-time-replay guarantee that a paint always shows the full recorded stream.
- **Two layers of tests at the right altitude.** Qt-free CLI/boundary tests (fresh
  interpreters for the Qt-boundary and no-display checks), offscreen-Qt unit tests
  for the window/replay/draw-mode semantics driven by synthetic `RastPortState`s,
  and the existing narrow Xvfb-backed iTidy smoke (unchanged, still passing) — so
  most tests need neither iTidy nor Xvfb.
- **Assert the honest boundary, not a clean exit.** The bounded launch test asserts
  the `WaitPort`-on-empty-queue marker, the titled projected window, "host shell
  active" **and** "host shell exited", and RC 0 — proving the shell enters and exits
  cleanly with no manual interaction, without blessing a fake target success.
- **Git discipline per `../workflows/branching-and-merging.md`:** one feature branch
  (`feat/gui-run-command`) from `development`, gated (full suite, both smokes, ruff,
  pyright, plain probe + analyzer, bounded direct launch) before the merge; branch
  kept, not deleted.

## Session-log recovery note

The full raw session log (zstd-compressed JSONL: all user/assistant messages,
reasoning, tool calls, tool results, compaction events) is stored on the agent host
under the harness sessions directory for this session id and is a strict superset of
this file; use it to recover exact commands, outputs, the exact session-creation
time, and the request/token counts (which this markdown does not re-derive). This
markdown is the distilled, repo-durable version.
