---
title: "diskfont.library"
status: draft
depends_on:
  - "../../architecture/platform-target.md"
citations_used:
  - "S1"
  - "S70"
---

# diskfont.library

Purpose: Summarize disk-font (font-file) open/close operations and the `TextAttr`/`TextFont` model.

Needed for:
- `iTidy` loads a window/icon font with `OpenDiskFont()` and applies it via `SetFont()`.

## Summary

`diskfont.library` is the font-file API: it finds a font on disk from a `TextAttr` description, loads it, and returns a pointer usable in subsequent `SetFont()` and `CloseFont()` calls [S70 item OpenDiskFont]. The NDK `TextAttr` node matches the text attributes in a `RastPort` and is the single argument to `OpenDiskFont()` [S1 graphics/text.h L63-L69].

## TextAttr Layout

The `TextAttr` structure the app fills in before calling `OpenDiskFont()` [S1 graphics/text.h L63-L69]:

- `ta_Name` (STRPTR) @ 0x00 — name of the font (pointer to the font-name string);
- `ta_YSize` (UWORD) @ 0x04 — height of the font;
- `ta_Style` (UBYTE) @ 0x06 — intrinsic font style;
- `ta_Flags` (UBYTE) @ 0x07 — font preferences and flags (e.g. the `DESIGNED` bit) [S70 item OpenDiskFont].

## OpenDiskFont

`OpenDiskFont(textAttr)` takes the `TextAttr*` in `a0` and returns the font pointer in `d0` [S70 item OpenDiskFont]. The autodoc notes the call must be matched with a corresponding `CloseFont()` for effective font-memory management, and that `d0` is zero if the desired font cannot be found [S70 item OpenDiskFont]. As of V36 the library will construct (scale) a font when the requested size has no designed font and the `DESIGNED` bit is clear [S70 item OpenDiskFont].

## Emulation Posture

The emulated environment has no disk font files, so the repo implementation does not claim to load a real font file. Instead `OpenDiskFont()` reads the requested `TextAttr` (name, size), returns a repo-allocated `TextFont` stand-in carrying the requested name — the same pattern the screen's default font uses — and records the request so a future renderer can see which font the app asked for. This gives the app a real handle for its `SetFont()` call (meaningful emulated state) rather than a fake success or a silent no-op; when there is no 68k memory to read the `TextAttr` from, it returns zero and the app falls back to the screen font, which it handles gracefully.
