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

Depends on:
- `../gui-stack.md`

Status: Draft.

Notes:
- Emphasize indirect relevance, not demo or direct-chip programming.

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

## Why It Still Matters For GUI Utilities

Even a mostly standard GUI application may use raw raster drawing for:

- group boxes,
- progress bars,
- custom labels,
- text truncation,
- separator lines,
- or refreshed window decorations.

The current `iTidy` tree does exactly that. Its GUI helper code uses `SetAPen()`, `Move()`, `Draw()`, `RectFill()`, `Text()`, and `PrintIText()` for custom group boxes and progress/status displays [S31 L1795-L1860] [S31 L1812-L1813].

## What It Does Not Mean

Supporting the project-relevant slice of `graphics.library` does not mean reproducing full chipset-era graphics behavior, sprite systems, or demo-scene style hardware tricks. The target class is still Workbench utilities. The value here is the conventional raster API that those utilities use inside normal windows, not direct hardware emulation.

## Working Rule

For this project, `graphics.library` work should initially prioritize:

1. `RastPort` state that affects ordinary window drawing,
2. basic text and primitive drawing calls,
3. compatibility with Intuition-owned window rendering contexts,
4. correctness for small helper drawings before breadth elsewhere.
