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

Depends on:
- `../gui-stack.md`
- `intuition.library.md`

Status: Draft.

Notes:
- Note how GadTools differs from lower-level Intuition gadget work.

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
