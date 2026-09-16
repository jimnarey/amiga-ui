---
title: "gadtools.library"
status: draft
depends_on:
  - "../gui-stack.md"
  - "intuition.library.md"
citations_used:
  - "S1"
  - "S31"
  - "S42"
---

# gadtools.library

Purpose: Summarize standard gadget construction helpers used by many classic GUI apps.

Needed for:
- Understanding common widget patterns in target software.

## Summary

`gadtools.library` is the classic convenience layer for building standard Intuition gadgets and menus without hand-assembling every gadget structure. The autodocs index highlights the core surface clearly: `CreateGadgetA()`, `CreateMenusA()`, `GetVisualInfoA()`, `LayoutMenusA()`, `GT_GetIMsg()`, `GT_ReplyIMsg()`, and `GT_RefreshWindow()` are all first-class parts of the API [S42 item 1].

## What GadTools Adds

The NDK header defines a catalog of standard gadget kinds such as:

- `BUTTON_KIND`
- `CHECKBOX_KIND`
- `INTEGER_KIND`
- `LISTVIEW_KIND`
- `CYCLE_KIND`
- `SLIDER_KIND`
- `STRING_KIND`
- `TEXT_KIND` [S1 Include_H/libraries/gadtools.h L29-L48]

It also defines `struct NewGadget` as the generic specification block used to create many of these controls, including geometry, label, gadget ID, flags, `VisualInfo`, and caller `UserData` [S1 Include_H/libraries/gadtools.h L77-L89].

For menus, the same header defines `struct NewMenu` and the `NM_TITLE`, `NM_ITEM`, `NM_SUB`, and `NM_END` scheme used by `CreateMenus()` and `LayoutMenus()` [S1 Include_H/libraries/gadtools.h L111-L157].

## Event-Loop Semantics

GadTools does not replace the underlying Intuition message loop. It wraps it. That is why the API includes `GT_GetIMsg()` and `GT_ReplyIMsg()` rather than a wholly separate event model [S42 item 1].

The current `iTidy` code shows the exact pattern the compatibility layer must respect:

- wait on the window's port,
- fetch translated messages with `GT_GetIMsg()`,
- inspect class and gadget data,
- reply each message exactly once [S31 L1308-L1319]

## IDCMP Contract Still Matters

The header also publishes IDCMP masks associated with different gadget families, for example `BUTTONIDCMP`, `LISTVIEWIDCMP`, `CYCLEIDCMP`, `SLIDERIDCMP`, and `STRINGIDCMP` [S1 Include_H/libraries/gadtools.h L52-L74]. That is a useful reminder that a GadTools UI still depends on correct Intuition IDCMP handling underneath.

## Concrete Relevance In `iTidy`

`iTidy` is thoroughly GadTools-based. The source uses:

- `GetVisualInfo()`
- `CreateGadget()` across button, text, cycle, checkbox, listview, slider, integer, and string gadgets
- `CreateMenus()` and `LayoutMenus()`
- `GT_RefreshWindow()` after window opening [S31 L195-L227] [S31 L581-L914] [S31 L1014-L1107]

That makes GadTools one of the highest-priority GUI cards for the repo.

## Working Rule

For this project, `gadtools.library` support should first preserve:

1. standard gadget creation from `NewGadget`,
2. standard menu creation from `NewMenu`,
3. correct `VisualInfo` and public-screen integration,
4. the GadTools-flavored message loop on top of Intuition.

## Bevel Box And Window Refresh

`iTidy` draws its group-box frames (and a recessed folder-path box) with
`DrawBevelBox`, the varargs wrapper that calls `DrawBevelBoxA`, and triggers a
gadget redraw with `GT_RefreshWindow`. Both are implemented so the window's
visible chrome is recorded rather than dropped:

- `DrawBevelBoxA(rport, left, top, width, height, taglist)` reads the
  `GT_VisualInfo` (`GT_TagBase+52`) and `GTBB_Recessed` (`GT_TagBase+51`) tags
  from the app's tag list and records a `DrawBevelBox` op — explicit position,
  size, recessed flag, and VisualInfo — on the host-side RastPort op log. It
  draws at the explicit bounds and does not move the RastPort origin. The op
  shares the launcher's run-wide `RastPortRegistry` (`ctx.rastports`) with
  `graphics.library` `Text` and `intuition.library` `PrintIText`, so a window's
  bevel frame, text, and titles are one chronological stream.
- `GT_RefreshWindow(win, req)` records the refresh request (window address) for
  probes and, when a host projection is installed, asks it to replay that
  window's recorded RastPort op stream onto its drawing surface.

The bevel-box tags the app passes are the two above plus `TAG_END`; the optional
`VB_Pen`/`VB_Bevel` attributes are ignored (the app does not set them).

## Menu Creation From `NewMenu`

`CreateMenusA`, `LayoutMenusA`, and `FreeMenus` are implemented
(`src/amiga_ui/vamos/gadtools_library.py`) as real producers rather than stubs:

- `CreateMenusA` walks the app's flat `NewMenu` template (`NM_TITLE`, `NM_ITEM`,
  `NM_SUB`, `NM_END`, with `_NM_BARLABEL` handled), allocates real `Menu` and
  `MenuItem` blocks in target memory with the classic field layout, stores each
  item's `nm_UserData` in the `GTMENUITEM_USERDATA` slot (`MenuItem + 0x22`),
  chains the blocks, and records a host-safe `MenuStripDescription` for the
  strip so `intuition.library` `SetMenuStrip` can project it.
- Every created item gets `mi_NextSelect = MENUNULL` (`$FFFF`). The released
  binary advances its selection walk with the zero-extended WORD at
  `MenuItem + 0x20` and stops only on `$FFFF`, so a zeroed field turns
  `while (menu_number != MENUNULL)` into an endless `ItemAddress` loop.
  Separators are real items and therefore consume a chain slot.
- `LayoutMenusA` fills `LeftEdge`/`TopEdge`/`Width`/`Height` for each menu, item,
  and sub-item chain from the supplied `VisualInfo`'s font metrics, and
  `FreeMenus` releases the blocks it allocated.

The selector encoding (`MENUNULL`, `NOMENU`/`NOITEM`/`NOSUB`, 1-based fields) and
the binary evidence behind these obligations are recorded in
`docs/apps/itidy/menu-strip-menupick-abi.md`.

## Checkbox Gadget State (`GTCB_Checked`)

`GT_GetGadgetAttrsA(gad, win, req, taglist)` (LVO 174) and
`GT_SetGadgetAttrsA(gad, win, req, taglist)` (LVO 42) are implemented
(`src/amiga_ui/vamos/gadtools_library.py`). These are the `A` variants the app's
variadic `GT_GetGadgetAttrs`/`GT_SetGadgetAttrs` taglib stubs expand to — the
names the released binary actually calls (not the non-`A` forms). They round-trip
a CHECKBOX gadget's live checked state through the host-side `GadgetDescription`
registry (the non-classic gadget layout has no emulated `Gadget.Value` field, so
the registry is the genuine store):

- `GT_GetGadgetAttrsA` reads the `GTCB_Checked` out-param address from the tag
  list and writes the gadget's current checked state to it. This is what iTidy's
  `GID_BACKUP` handler uses after a backup-checkbox click to learn the new state.
- `GT_SetGadgetAttrsA` reads the `GTCB_Checked` value (the new checked state) from
  the tag list and re-records the description in place. This is what iTidy's
  LHA-not-found *Continue* branch uses to uncheck the backup checkbox after the
  user chooses to continue without backups.

The checked state itself is toggled by the host event bridge on each projected
checkbox click (`event_bridge.py` `gadget_up`), mirroring classic Intuition's
"toggle the clicked gadget's `Value`, then report the `GADGETUP`". Both return the
number of tags processed (`1`), or `0` when the gadget is unknown or the tag is
absent.
