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
classic `RastPort` header defines exactly four modes [S1
Include_H/graphics/rastport.h L90-L95]:

- `JAM1` = 0 — use the foreground pen (`APen`/`FgPen`).
- `JAM2` = 1 — use the background pen (`BPen`/`BgPen`).
- `COMPLEMENT` = 2 — bitwise XOR with the existing pixel.
- `INVERSVID` = 4 — swap the foreground/background pen roles for the op.

`RectFill` fills a rectangle with the **foreground pen**, taking the draw mode
into account (so under `JAM2` it effectively uses the background pen, and under
`COMPLEMENT` it XORs the foreground pen) [S1 Autodocs/graphics.doc RectFill].
`InitRastPort` leaves `Mask`/`FgPen`/`AOLPen`/`LinePtrn` at `-1` and sets
`DrawMode` to `JAM2`, with the standard screen font [S1
Autodocs/graphics.doc InitRastPort]; the repo's `RastPortState` mirrors those
standard values (`apen=0xFF`, `bpen=0`, `draw_mode=JAM2`, `outline_pen=0xFF`).

The host renderer implements `COMPLEMENT` as a genuine per-pixel bitwise XOR
(not a blitter minterm and not a Qt composition mode — Qt's
`CompositionMode_Xor` is Porter-Duff non-overlap, which is a different
operation). `INVERSVID` swaps which pen the op uses. Undefined draw-mode bits
are ignored. This is recorded behavior, not an "approximation" of a minterm.

Note: `IntuiText.DrawMode` (the Intuition text field) is a *different* value set
from `RastPort.DrMd`; the local NDK does not define its bit values, so
`PrintIText` does not decode it. A previously recorded `0x8C` "DrawMode" byte on
an `IntuiText` was a mislabeled observation, not a real RastPort draw mode.

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
- **Frontier calls are recorded, not faked.** Color/BitMap/display-info/font
  entry points the app has not driven yet record their invocation in
  `GraphicsLibrary.call_log` and return honest defaults (e.g. `AllocBitMap`
  returns `0`, `GetVPModeID` returns `0`) rather than a fabricated success.
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
