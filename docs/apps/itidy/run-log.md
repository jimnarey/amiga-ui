---
title: "iTidy Run Log"
status: log
depends_on:
  - "compatibility-notes.md"
  - "../../workflows/error-driven-porting.md"
citations_used: []
---

# iTidy Run Log

Purpose: Append-only, dated record of what has actually been run against `iTidy` and observed, so a blocker that has already been diagnosed is not re-investigated from scratch.

Needed for:
- Confirming whether `compatibility-notes.md`'s prose is still current.
- Picking up work without re-deriving the current frontier from raw logs.

Notes:
- Treat this file as the durable history for `iTidy` runs. Pull forward the important facts from recent run artifacts instead of assuming those local files will still exist later. Each entry should preserve the first blocker, the useful evidence, any repo change that followed, and the next recommended step.

## Entries

### 2026-08-09 — Missing `icon.library` blocks startup past core-library setup

- Observed: repeated same-day probe runs converged on the same first app-level blocker: startup advanced past earlier launcher issues, then stopped because `icon.library` was missing during initial library setup.
- Change: none — recorded for triage.
- Next: implement `icon.library` (or the part of it `iTidy` needs first) per `../../runtime/writing-a-library-impl.md`, then rerun and add a new entry here.

### 2026-08-11 — Repo-owned `icon.library` seam advances startup to `graphics.library`

- Observed: a direct probe run now opens `icon.library` successfully and gets past the earlier missing-library failure. The next first blocker is `graphics.library`, which means the new `icon.library` override is being picked up by the in-process launcher.
- Change: added a minimal repo-owned `IconLibrary` implementation in `src/amiga_ui/vamos/icon_library.py`, registered it in `src/amiga_ui/vamos/extensions.py`, and tightened the launcher integration test so it asserts that `icon.library` opens at a non-zero address.
- Next: add the smallest honest `graphics.library` implementation needed for the next startup sequence, then rerun and record the next blocker rather than speculating ahead into wider drawing support.

### 2026-08-16 — Repo-owned stub libraries advance startup to dos.CreateDir with PROGDIR volume missing

- Observed: after implementing `icon.library`, `graphics.library`, `diskfont.library`, `workbench.library`, `gadtools.library`, and `asl.library` in a parallel fashion, the first non-library blocker was that `das.library` called `CreateDir(lock, 'PROGDIR:logs/')` which failed because the `PROGDIR:` volume name had no mapped path.
- Change: none — recorded for triage. The fix needs to either:
  1) define a `.cfg.path.auto_assigns` entry for `prog` in the launch config, or
  2) register a stub volume mapping programmatically via an extension hook before dos runs.
- Next: extend the repo's path manager extension point so it registers `PROGDIR:/sys/path/to/amiga_apps/<app>/binary/extracted` automatically when launching a probe run; rerun and record either the next missing library, structure issue, or GUI request.

### 2026-08-20 — PROGDIR volume registration fixed; GUI/window frontier reached

- Observed: `artifacts/runs/20260820T211914Z-probe-iTidy` still failed at `dos.CreateDir`/`Lock('PROGDIR:logs/')` because `PROGDIR:` was not registered when other `-V` volumes were present. After the launcher fix, `artifacts/runs/20260820T212739Z-probe-iTidy` resolves `PROGDIR:logs/` to `amiga_apps/itidy1classic/binary/extracted/logs/` and writes the app log successfully.
- Change: corrected the launcher's automatic `PROGDIR:` volume detection so other `-V` volume arguments do not suppress the `progdir:<app root>` volume. Added regression coverage for this case in `tests/test_vamos_launcher.py`.
- Next: continue from the new first blocker in the verified probe: `GetCurrentDirName` still returns the default failure value, `ENV:`/`ENVARC:` prefs paths are missing, `iffparse.library` reports `UNKNOWN(#8)`, and `intuition.library` reports `UNKNOWN(#100)`/`UNKNOWN(#85)` before the app exits with `Could not get visual info` and `Failed to open GUI window`.

### 2026-08-21 — Real IntuiMessage event bridge drives the app's `WaitPort -> GT_GetIMsg -> GT_ReplyIMsg` loop

- Observed: a scheduled host close event now becomes a real `struct IntuiMessage` posted on the main window's real `UserPort` (`0x06b330`), and the app's event loop consumes and replies to it through the sanctioned path. The full intended path `test event -> IntuiMessage -> Window.UserPort -> WaitPort -> GT_GetIMsg -> GT_ReplyIMsg` executes end-to-end with a real message on a real port. The app then `WaitPort`s the now-empty queue and fails honestly; it does **not** exit cleanly.
- Evidence:
  - NDK 3.2 `Include_H/intuition/intuition.h`: `struct IntuiMessage` (V36+) is `0x30` bytes — `ReplyMsg@0x00`, `Node@0x04`, `Class@0x10`, `Code@0x14`, `Qualifier@0x16`, `IAddress@0x18`, `MouseX@0x1C`, `MouseY@0x1E` (consecutive words, no overlap), `Seconds@0x20`, `Micros@0x24`, `IDCMPWindow@0x28`, `SpecialLink@0x2C`. IDCMP flags: `REFRESHWINDOW 0x4`, `GADGETUP 0x40`, `MENUPICK 0x100`, `CLOSEWINDOW 0x200`. The main window requests IDCMP `0x344`.
  - FD biases: `GT_GetIMsg` 72 `(a0)`, `GT_ReplyIMsg` 78 `(a1)`, `WaitPort` 384.
  - App build (`Makefile`): `vbcc +aos68k -c99 -cpu=68000 -O2 -size -DENABLE_CONSOLE`, Workbench 3.2 SDK; binary banner reads "compiled: Jan 12 2026".
  - Vamos timeline (close-event run, `-l dos:info,exec:info`): last setup call is the 2nd `SetWindowPointerA` (PC `030764`); then `WaitPort(06b330)` #1 reports the first queued message `06b358` (classic peek, left in queue); the app calls `GT_GetIMsg` twice (`06b358` then `NULL`) and `GT_ReplyIMsg` (implemented calls do not log at the enabled level — confirmed with a temporary stderr hook); then `WaitPort(06b330)` #2 finds the empty queue and raises `UnsupportedFeatureError` -> `rc=1`.
  - **Binary != repo source.** The compiled binary performs a double `WaitPort(0x06b330)` immediately after the 2nd `SetWindowPointerA` (from `safe_set_window_pointer(FALSE)` in `open_itidy_main_window`), but the checked-in source has no `WaitPort` there (just `CONSOLE_STATUS` + `return TRUE`). A `REFRESHWINDOW` probe confirmed the loop between the two `WaitPort`s is a `while ((msg = GT_GetIMsg(...))) { GT_ReplyIMsg(msg); }` **drain that discards the message without switching on `Class`** (no `GT_BeginRefresh`/`DrawBevelBoxA` refresh-handling calls appear after `WaitPort` #1, and those are the only such calls in the log). So the delivered event is consumed by the drain, not by the real event loop.
- Change: added `src/amiga_ui/vamos/event_bridge.py` (real `IntuiMessage` production + real-`UserPort` delivery + release), `PeekPortManager`/classic-peek `WaitPort` in `src/amiga_ui/vamos/exec_library.py` (empty queue -> honest `UnsupportedFeatureError`, never a fabricated message), `GT_GetIMsg`/`GT_ReplyIMsg` in `src/amiga_ui/vamos/gadtools_library.py`, the `on_window_opened` hook in `intuition_library.py`, and `event_bridge` plumbing in `launcher.py`. Added `tests/test_event_bridge.py` (layout vs NDK, `WaitPort` peek semantics, bridge scheduling/targeting/delivery/release, and an in-process delivery test). Updated `docs/platform/library-cards/intuition.library.md` to record the sanctioned real-`IntuiMessage`-on-real-`UserPort` design and the honest empty-queue `WaitPort` rule.
- Next: the remaining work is target-side, not bridge-side. (1) `graphics.library` RastPort drawing (`fix/graphics-rastport`): `Move`/`Draw`/`RectFill`/`SetAPen`/`SetBPen`/`SetDrMd` lack `ctx` and are dropped, and there is no host framebuffer. (2) Intuition text metrics (`IntuiTextLength` bias 330, `PrintIText` bias 216). (3) GadTools `DrawBevelBoxA` (observed PC `0277b2`), `GT_RefreshWindow` (observed PC `025876`), `GT_BeginRefresh`/`GT_EndRefresh`, `GT_LayoutGadgetsA` — then integration-test refresh/gadgetup events (resolve the `GadgetID` offset first: repo `0x26` vs NDK `0x22`). (4) `SetWindowPointerA` (bias 570; observed twice, PC `030740`/`030764`).

### 2026-09-06 — `graphics.library` `TextLength` measures label widths from the RastPort font

- Observed: after the RastPort drawing-state work (see the 2026-09-05 graphics session log), the probe draws all three group boxes and then hits the text/UI frontier. The **first** unimplemented call in `artifacts/runs/20260905T232639Z-probe-iTidy` was `graphics.library` `TextLength` (bias 54), logged four times as `? CALL ... -> d0=0 (default)` (counts 6/3/9 for `"Order:"`/`"By:"`/`"Position:"`, then 4 for `"Max:"` — the label-width measurements in `main_window.c` L644-L646 and the `Max:` progress label).
- Change: implemented `TextLength` in `src/amiga_ui/vamos/graphics_library.py`. It reads `RastPort.TxWidth` from 68k memory at the pre-`RasInfo` offset the target was compiled against (`RastPort+0x3C`, where `intuition_library` writes the Topaz width) and returns `count * TxWidth` for the fixed-pitch font, with a sanity-bounded fallback to the Topaz baseline (`6`) so an unpopulated/mis-offset RastPort degrades to the correct width instead of a garbage pointer. Each measurement is recorded on the host-side `RastPortState` (`record_text_length`) so a future renderer/probe can see what was measured and how wide it was told the text was. It is a real measurement, not a fake zero.
- Evidence: `tools/analyze_target_failure.py --latest` on `artifacts/runs/20260906T000103Z-probe-iTidy` no longer lists `TextLength` among defaulted calls; the four `TextLength` traps are now hooked (they no longer log at WARNING). The app still ends at the honest `WaitPort`-on-empty-queue `UnsupportedFeatureError` boundary (no regression). `tests/test_graphics_library.py` gained a `TextLength` class (7 cases: RastPort font width, a different width, unpopulated fallback, implausible-width fallback, zero-count, no-`mem` context, and measurement recording) plus a scanner guard that `TextLength` is a wired `.fd` trap; the full suite is green and `pre-commit` (ruff + pyright) passes.
- Next: the next smallest graphics-library blocker is `Text` (bias 60), the actual text **draw** call (`Text(rp, "Max:", 4)` at PC `0279ce`), which should record a text-draw op on the RastPort model (string, position, pen) rather than a no-op. After that, the Intuition text pair (`IntuiTextLength` bias 330 / `PrintIText` bias 216) and the GadTools `DrawBevelBoxA`/`GT_RefreshWindow` pair remain the drawing frontier. The RastPort `TxWidth@+0x3C` offset is now directly consumed by a returned value, so settling it against the binary (open follow-up) has higher stakes than before.

### 2026-09-06 — `graphics.library` `Text` records a text-draw op and advances the pen

- Observed: with `TextLength` implemented, the probe draws all three group boxes and then hits the remaining text/UI frontier. The **first** unimplemented graphics-library call in `artifacts/runs/20260906T175909Z-probe-iTidy` is `graphics.library` `Text` (bias 60), logged once as `? CALL Text(rp=0006a868, string=00065140, count=04) -> d0=0 (default)` at PC `0279ce` — the folder-path label draw in `main_window.c` L1860 (drawn at the pen position left by the preceding `Move`, with the truncation decision coming from `TextLength`).
- Change: implemented `Text` in `src/amiga_ui/vamos/graphics_library.py`. It is the draw counterpart of `TextLength`: it measures the drawn width as `count * RastPort.TxWidth` (same font-width read and Topaz fallback), best-effort decodes the string content from 68k memory so the op record carries *what* was drawn, records a `Text` op on the host-side `RastPortState` (draw position, string pointer, decoded content, count, width, pen) via `record_text`, and advances the pen by the drawn width per the classic contract. There is no host window yet, so this record — not a silent no-op — is what makes the call meaningful.
- Evidence: `tools/analyze_target_failure.py --latest` no longer lists `graphics.library Text` among defaulted calls; the trap is now hooked (it no longer logs at WARNING). The app still ends at the honest `WaitPort`-on-empty-queue `UnsupportedFeatureError` boundary (no regression). `tests/test_graphics_library.py` gained a `GraphicsLibraryTextTest` (6 cases: records at pen position, advances the pen, uses the RastPort font width for the advance, decodes the drawn string, zero-count does not move the pen, no-`mem` context still records) and a scanner guard that `Text` is a wired `.fd` trap; the `_FakeMem` helper is now byte-backed so both byte (text content) and word (`TxWidth`) reads work. The full suite is green and `pre-commit` (ruff + pyright) passes.
- Next: the Intuition text pair (`IntuiTextLength` bias 330 / `PrintIText` bias 216) is the natural next increment — it draws the group-box titles (the app's most visible text) — but the source builds its `IntuiText` with the **old pre-2.0 field names** (`FrontPen`/`BackPen`/`LeftEdge`/`TopEdge`/`ITextFont`/`NextText` in `main_gui.c` and `gui_groupbox.c`), which conflicts with the repo's 3.x `iT_*` layout in `gadtools_library.py`. That IntuiText byte layout must be settled against the binary before the pair can read the string pointer/font correctly. The GadTools `DrawBevelBoxA`/`GT_RefreshWindow` pair and `intuition.library` `SetWindowPointerA` also remain frontier.
