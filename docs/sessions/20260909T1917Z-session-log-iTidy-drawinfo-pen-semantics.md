---
title: "Session log — iTidy DrawInfo ABI and classic pen / RastPort draw-mode semantics"
status: log
depends_on:
  - "../apps/itidy/run-log.md"
  - "../apps/itidy/compatibility-notes.md"
  - "../architecture/platform-target.md"
  - "../architecture/hosted-application-mode.md"
  - "../platform/library-cards/intuition.library.md"
  - "../platform/library-cards/graphics.library.md"
  - "../host-gui/painting-styling-and-layout.md"
  - "../host-gui/testing-host-ui.md"
  - "../workflows/error-driven-porting.md"
  - "../workflows/branching-and-merging.md"
citations_used:
  - S1
  - S2
---

# Session log — iTidy DrawInfo ABI and pen / RastPort draw-mode semantics (2026-09-09)

Purpose: Durable record of the session that fixed the screenshot-visible iTidy
GUI defect where **group-box title backgrounds and the folder-path area rendered
as black bars**. The root cause was a fabricated `DrawInfo` whose `dri_Pens`
pointed at the screen RastPort instead of a real pen-index array, so every
`dri_Pens[...]` read the app made landed in garbage (effectively pen 0 = black).
This session made the rendering primitives and semantic pens correct, and kept
it as one coherent rendering-correctness increment (no host input/event routing
or general GadTools gadget projection).

The fix has two halves:

1. **Correct classic `struct DrawInfo` ABI** (the primary fix).
   `GetScreenDrawInfo` now builds a genuine classic m68k `DRI_VERSION_2` block
   (30 bytes, the exact field offsets the 3.x binary reads) with a **separately
   allocated** `dri_Pens` UWORD array in emulated memory. The pen array holds
   the screen's semantic pen indices mapped to the host Workbench palette
   approximation, is owned by the DrawInfo, and is released (with the block) by
   `FreeScreenDrawInfo` — which touches neither the screen RastPort nor any
   window RastPort. Multiple allocations have independent lifetimes.

2. **Correct classic pen / RastPort draw-mode semantics** (the secondary fix).
   - The host surface background is now the classic Workbench window light grey
     (pen 15, `0xC0C0C0`), matching the notional public screen's
     `BACKGROUNDPEN`, so a `RectFill` with `dri_Pens[BACKGROUNDPEN]` clears to
     the same colour as the window surface (not a black bar).
   - The window RastPort is initialized to the screen's pens (FgPen =
     `TEXTPEN`/black, BgPen = `BACKGROUNDPEN`/light grey) and **JAM1**, so the
     group-box title clear (which does `SetAPen(dri_Pens[BACKGROUNDPEN])` +
     `RectFill` with no `SetDrMd`) uses the FgPen.
   - The renderer's draw-mode rule is now scoped to **vector/fill** ops
     (`Draw`/`AreaDraw`/`RectFill`): the *source* pen is selected by the draw
     mode (JAM1→FgPen, JAM2→BgPen, COMPLEMENT→FgPen XOR, INVERSVID→swap).
     `Text`/`PrintIText` are a **separate branch**: glyphs use the FgPen
     foreground and the JAM1/JAM2 treatment applies to the *background* behind
     the glyphs — the "JAM2 universally = draw using BPen" rule is explicitly
     NOT applied to text (the folder-path box sets `SetBPen(BACKGROUNDPEN)` +
     `SetDrMd(JAM2)` and then draws `Text` in the FgPen/black).

The honest `WaitPort`-on-empty-queue boundary stayed intact, per-window RastPort
isolation is preserved, the public screen stays notional/invisible, and a real
iTidy run under Xvfb opens one correctly titled/positioned host window whose
group-title clear and folder-path clear now read as the window background
(light grey) rather than black, with white shine / black shadow / black text /
yellow highlight titles all distinguishable from it.

Needed for:
- Recalling the **correct** `DrawInfo` layout (DRI_VERSION_2, 30 bytes) and why
  `dri_Pens` must be a real, separately allocated pen-index array (the target is
  NOT opaque about it: it dereferences `dri_Pens`, `dri_Font`, `dri_Depth`).
- Recalling the **classic semantic pen → host palette** mapping (the documented
  Workbench approximation) and why the host surface background is pen 15 light
  grey (so the `BACKGROUNDPEN` clear matches the window surface).
- Recalling the **corrected** draw-mode semantics: fill/line source pen is
  mode-selected, while text foreground is always the FgPen (JAM1/JAM2 govern the
  background behind the glyphs, not the glyphs). The window RastPort starts in
  JAM1 with the screen's pens.
- Knowing the next increment (host input/event routing or general GadTools
  gadget projection) is deliberately deferred to a fresh branch.

## Evidence (local NDK / AutoDocs / app source / recorded ops)

### DrawInfo ABI
- NDK `Include_H/intuition/screens.h`: `struct DrawInfo` is `DRI_VERSION_2` on
  AmigaOS 3.x with `dri_Version`(UWORD)@0x00, `dri_NumPens`(UWORD)@0x02,
  `dri_Pens`(UWORD*)@0x04, `dri_Font`(TextFont*)@0x08, `dri_Depth`(UWORD)@0x0C,
  `dri_Resolution.{X,Y}`(UWORD)@0x0E/0x10, `dri_Flags`(ULONG)@0x12,
  `dri_CheckMark`(Image*)@0x16, `dri_AmigaKey`(Image*)@0x1A — 30 bytes total.
  The OS4 `DRI_VERSION_3` superset appends `dri_Screen` + reserved words the
  3.x binary does not read.
- Classic semantic pen indices (NDK `intuition/screens.h`): DETAILPEN=0,
  BLOCKPEN=1, TEXTPEN=2, SHINEPEN=3, SHADOWPEN=4, FILLPEN=5, FILLTEXTPEN=6,
  BACKGROUNDPEN=7, HIGHLIGHTTEXTPEN=8, BARDETAILPEN=9, BARBLOCKPEN=10,
  BARTRIMPEN=11, NUMDRIPENS=13.
- App source (`amiga_apps/itidy1classic/source/src/GUI/gui_groupbox.c`
  `DrawGroupBoxWithLabel`): the group box reads `dri_Pens[SHINEPEN]`/
  `dri_Pens[SHADOWPEN]` for the bevel, `dri_Pens[TEXTPEN]`/
  `dri_Pens[BACKGROUNDPEN]` for the title IntuiText, and
  `dri_Pens[HIGHLIGHTTEXTPEN]` for the title front pen — i.e. the target
  dereferences `dri_Pens` (it is not opaque).

### Draw-mode semantics
- NDK `Include_H/graphics/rastport.h`: `JAM1=0`, `JAM2=1`, `COMPLEMENT=2`,
  `INVERSVID=4`; `BYTE DrawMode; /* drawing mode for fill, lines, and text */`.
- AutoDoc `RectFill`: "fill the rectangular region with the FgPen color, taking
  into account the drawing mode." AutoDoc `ClearEOL`: "setting the color of the
  swath to zero, or, if the DrawMode is JAM2, to the BgPen." AutoDoc
  `InitRastPort`: sets DrawMode to JAM2.
- The **window** RastPort's initial draw mode is **JAM1** (not InitRastPort's
  JAM2), evidenced by the app: the group box calls `SetAPen`+`Draw`/`RectFill`
  expecting the FgPen without a prior `SetDrMd`, while `draw_folder_path_box`
  (`main_window.c`) *explicitly* `SetBPen(BACKGROUNDPEN)`+`SetDrMd(JAM2)` before
  its `RectFill` — it would not set JAM2 if the default were already JAM2.
  App source confirms the explicit JAM1/JAM2 switches across
  `main_window.c`/`tool_cache_window.c`/`restore_window.c`/
  `main_progress_window.c`.
- Resolution: for **fill/line** ops the source pen is mode-selected
  (JAM1→FgPen, JAM2→BgPen); for **text** the glyphs use the FgPen foreground and
  JAM1/JAM2 govern the background behind the glyphs. This is the distinction the
  "JAM2 = BPen" audit required.

### Recorded ops (real iTidy run)
A real in-process run (offscreen) records, for the main window RastPort:
- Group box: `SetAPen(1)`+`Draw` (white shine), `SetAPen(0)`+`Draw` (black
  shadow), `SetAPen(15)`+`RectFill` under JAM1 (light-grey title clear),
  `PrintIText` front=5 (yellow title).
- Folder path: `SetAPen(0)`, `SetBPen(15)`, `SetDrMd(JAM2)`, `SetAPen(15)`+
  `RectFill` (light-grey clear, BgPen under JAM2), `SetAPen(0)`+`Text` (black
  text, FgPen under JAM2).
The cleared regions are light grey (the window background), not black.

## Verification

- Narrow (projection) tests: `TextAndClearSemanticsTest` (5 new) — `SetAPen`
  (BACKGROUNDPEN)+`RectFill` clears to the background under JAM1 (group box) and
  under JAM2 (folder path); `Text` under JAM2 uses the FgPen (not the BgPen); a
  same-state guard proving a JAM2 `RectFill` uses the BgPen while a JAM2 `Text`
  uses the FgPen; and a **pixel-semantic** assertion that *every* pixel in the
  group-title clear region equals the window background (not a "count
  non-background" check). `DrawModeSemanticsTest` (5) unchanged. All projection
  tests pass (25).
- Narrow (DrawInfo) tests: `IntuitionGetScreenDrawInfoTest` (7) — layout matches
  the classic DRI_VERSION_2 offsets; `dri_Pens` is a live separate allocation;
  the semantic pen indices dereference to the intended host palette colours;
  multiple DrawInfos have independent lifetimes; `FreeScreenDrawInfo` releases
  the block *and* the owned pen array; it does not touch the screen/window
  RastPorts; null is a safe no-op. The window-RastPort tests now expect the
  screen's pens + JAM1. All intuition tests pass (33).
- Full unit suite: 201 tests, all green except the one xvfb env-sensitive test
  that fails only when the shell exports `QT_QPA_PLATFORM=offscreen` (passes
  standalone and is unrelated to this change).
- Lint/type: `ruff check` clean, `ruff format` clean, `pyright` 0 errors.
- GUI smoke: `tests/run_gui_smoke_test.py` passes (xcb window created, visible,
  correct geometry).
- Probe: `amiga-ui probe iTidy --direct --timeout 8` ends at the documented
  `app_failed`/WaitPort-on-empty-queue boundary (honest).
- Bounded real run: `amiga-ui run iTidy` under Xvfb opens one projected window
  (`iTidy v1.0 - Icon Cleanup Tool`, 625x215), reaches the WaitPort boundary,
  and the host shell exits cleanly.
- Visible result (rendered offscreen and pixel-analyzed): window background is
  light grey (192,192,192, dominant); the group-title clear and folder-path
  clear regions contain **zero black pixels** (the black bars are gone); white
  shine lines, black shadow lines, black text, and yellow highlight titles are
  all present and distinguishable from the background.

## Approximations / uncertainty

- The semantic-pen→host-palette mapping is a **documented approximation** of the
  classic Workbench palette (the notional public screen has no real colour
  state). The specific indices (0=black, 1=white, 5=yellow, 15=light grey) match
  the repo's `CLASSIC_PEN_PALETTE`; the host surface background is set to pen 15
  so the `BACKGROUNDPEN` clear reads as the window surface.
- Text is rendered with the host monospace font (anti-aliased), not the exact
  classic Topaz/8x8 diskfont glyph metrics; glyph *positions* come from the
  recorded ops but glyph *shapes* are the host approximation.
- `dri_CheckMark`/`dri_AmigaKey` are set to NULL (the target does not read them
  for these windows); the screen font/BitMap referenced by `dri_Font`/
  `dri_Depth` are not freed by `FreeScreenDrawInfo` (they belong to the screen).
- The window RastPort byte layout is the separately-tracked follow-up from the
  prior increment (not re-litigated here).

## Next increment (deliberately deferred)

The next host-GUI increment — an interactive host event loop that routes host
input into real IntuiMessages, or general GadTools gadget projection — should
start from a **fresh branch** off the updated `development`, per the repo
branching workflow. This increment stays strictly within rendering correctness.
