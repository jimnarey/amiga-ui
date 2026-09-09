---
title: "graphics.library"
status: draft
depends_on:
  - "../gui-stack.md"
citations_used:
  - "S1"
  - "S31"
  - "S43"
---

# graphics.library

Purpose: Record the limited `graphics.library` behavior relevant to non-hardware-targeted apps.

Needed for:
- Deciding what can be ignored and what still affects Workbench-class software.

## Summary

`graphics.library` is not the main compatibility battleground for this project, but it is not irrelevant either. The autodocs index shows that the library owns the standard raster drawing operations such as `Move`, `Draw`, `Text`, `RectFill`, `SetAPen`, `SetBPen`, and font-related helpers [S43 item 1]. Those are exactly the operations that Workbench-class utilities may still use for custom adornments even when they are otherwise built on Intuition and GadTools.

## The Part That Matters Here

The central data structure is `RastPort`, which holds the bitmap/layer target, pens, draw mode, current pen position, current font, and text metrics [S1 Include_H/graphics/rastport.h L53-L88]. The header also defines the core draw modes `JAM1`, `JAM2`, `COMPLEMENT`, and `INVERSVID` [S1 Include_H/graphics/rastport.h L90-L95].

For this repository, the highest-value subset is:

- pen selection,
- line and rectangle drawing,
- text drawing,
- current font and text metrics,
- draw-mode handling.

## Draw-Mode And RectFill Semantics

The `DrMd` field is a **RastPort draw mode**, not a blitter minterm. The
classic `RastPort` header defines four mode bits [S1
Include_H/graphics/rastport.h L90-L95]:

- `JAM1` = 0 — "jam 1 color into raster".
- `JAM2` = 1 — "jam 2 colors into raster".
- `COMPLEMENT` = 2 — complement destination bits selected by the operation.
- `INVERSVID` = 4 — inverse the source-video interpretation.

`RectFill` fills a rectangle with the **foreground pen**, taking the draw mode
into account [S1 Autodocs/graphics.doc RectFill]. Neither that statement nor the
short header comments proves the repo's current whole-operation reduction
`JAM1 -> APen`, `JAM2 -> BPen`. In the usual one-colour/two-colour model, source
bits select APen while JAM2 additionally maps clear source bits to BPen; solid
fills, line patterns, area patterns, write masks, and inverse video therefore
need operation-specific treatment. The exact classic behavior required here is
an active question in `docs/research/open-questions.md`.

`InitRastPort` leaves `Mask`/`FgPen`/`AOLPen`/`LinePtrn` at `-1` and sets
`DrawMode` to `JAM2`, with the standard screen font [S1
Autodocs/graphics.doc InitRastPort]; the repo's `RastPortState` mirrors those
standard values (`apen=0xFF`, `bpen=0`, `draw_mode=JAM2`, `outline_pen=0xFF`).

The host renderer currently approximates `COMPLEMENT` by XORing host RGB
channels through an operation-shaped coverage mask. That is deliberately not
Qt's Porter-Duff `CompositionMode_Xor`, but it is also not a faithful model of
indexed Amiga bitplanes, RastPort `Mask`, bitmap depth, or palette lookup.
`INVERSVID` is likewise represented by swapping host pen roles. These are
deterministic host approximations, not established pixel-exact Amiga semantics.

`Text` currently paints foreground glyphs only. It does **not** implement the
JAM2 background-cell write; it happens to look correct in the current iTidy
window because the application first clears the containing area. `PrintIText`
likewise paints its recorded FrontPen and does not interpret `IntuiText.DrawMode`.
The repo previously described that field as a separate, undefined value set,
but the local header and `PrintIText` AutoDoc do not establish that claim: they
say only that it is the text rendering mode and that `PrintIText` configures the
RastPort from the IntuiText values. Its relationship to the graphics JAM modes
therefore remains unresolved. A previously observed `0x8C` byte was not a valid
decoded mode; that observation alone does not define a separate value set.

## Why It Still Matters For GUI Utilities

Even a mostly standard GUI application may use raw raster drawing for:

- group boxes,
- progress bars,
- custom labels,
- text truncation,
- separator lines,
- or refreshed window decorations.

The current `iTidy` tree does exactly that. Its GUI helper code uses `SetAPen()`, `Move()`, `Draw()`, `RectFill()`, `Text()`, and `PrintIText()` for custom group boxes and progress/status displays [S31 L1795-L1860] [S31 L1812-L1813].

## Repo Implementation Status

`src/amiga_ui/vamos/graphics_library.py` (`GraphicsLibrary`, registered in
`extensions.py`) now owns a real dispatch surface and a host-side drawing model:

- **Dispatch is wired.** Every method takes `ctx` first and its remaining
  parameters match the pinned `graphics.library` `.fd` entry exactly (name and
  count), so the `LibImplScanner` installs them as valid traps. Before this fix
  the drawing methods lacked `ctx` and were scanner errors, so vamos dropped the
  app's `SetAPen`/`Move`/`Draw`/`RectFill`/`SetBPen`/`SetDrMd` calls as
  `UNKNOWN` traps and the drawing was silently lost.
- **RastPort drawing is recorded, not no-op'ed.** `SetFont`, `SetAPen`,
  `SetBPen`, `SetDrMd`, `SetABPenDrMd`, `SetMaxPen`, `SetOutlinePen`, `Move`,
  `AreaMove`, `Draw`, `AreaDraw`, `RectFill`, and `InitRastPort` update a
  host-side `RastPortState` (see `src/amiga_ui/vamos/rastport_state.py`) keyed
  by the emulated RastPort pointer: the pen/draw-mode/font state the app
  configured plus the ordered sequence of drawing operations. There is no host
  window yet, so this record — not a fake success — is what makes the calls
  meaningful; a later renderer can replay the ops. The launcher installs one
  run-wide `RastPortRegistry` on every library context (`ctx.rastports`), so
  `graphics.library` (`Text`) and `intuition.library` (`PrintIText`) draw into
  the *same* per-RastPort op log in chronological order — the state a future
  host renderer needs to replay a window.
- **Some scanner-valid frontier calls remain semantically incomplete.**
  Color/ViewPort/display-info/BitMap/RastPort-attribute/pen/font entry points
  that the app has not driven record their invocation in
  `GraphicsLibrary.call_log`. A documented failure such as `AllocBitMap`
  returning NULL is an honest failure, but logging and returning `None` from an
  operation that should mutate state is not a semantic implementation. Treat
  these methods as `recorded-but-unimplemented`; because their traps are wired,
  they may not reappear in the defaulted-call analyser when future target code
  begins to depend on them.
- **Text: `TextLength` (measure) and `Text` (draw) are implemented.**
  `TextLength` (bias 54) now measures the pixel width of the requested characters from the
  RastPort's font — it reads `RastPort.TxWidth` [S1 Include_H/graphics/rastport.h] at the
  pre-`RasInfo` offset the target was compiled against and returns `count * TxWidth` for the
  fixed-pitch Topaz screen font, then records the measurement on the host-side RastPort model
  [S31 L644-L646, the app's label-width layout] [S43 item 8]. `Text` (bias 60) is its draw
  counterpart [S43 item 1]: it records a text-draw op at the current pen position (string
  pointer, decoded content, pen, font) and advances the pen by `count * TxWidth`, per the
  classic contract [S31 L1813-L1860, the folder-path label draw]. The Intuition pair
  `IntuiTextLength`/`PrintIText` is now implemented in `intuition.library` (see the
  intuition card, Text Drawing). The GadTools `DrawBevelBoxA`/`GT_RefreshWindow` pair is
  implemented in `gadtools.library` (see the GadTools card, Bevel Box And Window Refresh),
  so `iTidy`'s visible text and bevel drawing are recorded in the shared RastPort op log.

Coverage: `tests/test_graphics_library.py` (model, dispatch, and a scanner
regression guard asserting zero scanner errors and that the six drawing
functions are wired) — no target binary required.

## Working Rule

For this project, `graphics.library` work should initially prioritize:

1. `RastPort` state that affects ordinary window drawing,
2. basic text and primitive drawing calls,
3. compatibility with Intuition-owned window rendering contexts,
4. correctness for small helper drawings before breadth elsewhere.
