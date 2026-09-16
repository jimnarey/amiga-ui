---
title: "iTidy Menu Strip And IDCMP_MENUPICK ABI"
status: reference
depends_on:
  - "compatibility-notes.md"
  - "../../host-gui/translation-obligations.md"
  - "../../architecture/platform-target.md"
citations_used:
  - "S1"
  - "S15"
  - "S26"
  - "S27"
  - "S29"
  - "S31"
---

# iTidy Menu Strip And IDCMP_MENUPICK ABI

Purpose: Record the menu-pick ABI that the released `iTidy` binary itself fixes, so the compat layer stops re-litigating it.

Needed for:
- `SetMenuStrip` / `ClearMenuStrip` / `ItemAddress` / `IDCMP_MENUPICK` implementation and diagnosis.

## Settled answer

**The target passes `IntuiMessage.Code` to `ItemAddress()` unchanged.** It performs no
`MENUNUM()` / `ITEMNUM()` / `SUBNUM()` unpacking before the call: the packed selector word is
zero-extended and handed over as the `MenuNumber`, exactly as classic Intuition documents
(`Item = ItemAddress(MenuStrip, MenuNumber)`) [S26 §Menus ¶1-4] [S31 L296-L304]. The unpacked
value the app actually acts on is **not** decoded from the selector at all — it comes from
`GTMENUITEM_USERDATA()`, i.e. the `APTR` GadTools parked after the `MenuItem` block
[S31 L307]. The selector's only other job is the `NextSelect` continuation of the walk.

That means consistency is required between **the `Code` we deliver** and **our own
`ItemAddress()` resolution**, not against any decoding inside the app.

## Evidence (shipped binary, byte level)

Artifact: `amiga_apps/itidy1classic/binary/extracted/iTidy` (released package binary [S15]),
335,008 bytes, MD5 `2bc845299228c9b2620b5dc1a61dbaff`, HUNK CODE segment starting at file
offset `0x34`. **Runtime address = file offset − 0x34**, so reproduce with
`tools/disassemble_m68k.py <binary> --offset <addr+0x34> --size N --address <addr>`. Built by
`vc +aos68k`, which aligns struct members to their natural alignment [S29 L1-L40].

### Event-class dispatch (`0x240ce`)

```text
000240d0  26 29 00 14        move.l $14(a1), d3        ; IntuiMessage.Class   (@0x14)
000240d6  3f 69 00 18 00 2c  move.w $18(a1), $2c(a7)   ; Code (UWORD @0x18) -> stack slot
000240de  2f 69 00 1c 00 30  move.l $1c(a1), $30(a7)   ; IAddress (LONG @0x1C) -> stack slot
000240ec  4e ae ff b2        jsr -$4e(a6)              ; exec ReplyMsg(msg)
000240f0  20 03              move.l d3, d0
000240f2  59 80              subq.l #$4, d0            ; 0x04 REFRESHWINDOW
000240f6  90 bc 00 00 00 3c  sub.l   #$3c, d0          ; 0x40  IDCMP_GADGETUP
00024100  90 bc 00 00 00 c0  sub.l   #$c0, d0          ; 0x100 IDCMP_MENUPICK -> $24a28
0002410a  90 bc 00 00 01 00  sub.l   #$100, d0         ; fallthrough = 0x200 CLOSEWINDOW
```

### The `IDCMP_MENUPICK` arm (`0x24a28`) — the settled question

```text
00024a28  2f 2f 08 b8        move.l $8b8(a7), -(a7)    ; arg2 = win_data
00024a2c  70 00              moveq #$0, d0
00024a2e  30 2f 00 30        move.w $30(a7), d0        ; == the Code slot ($2c before the push)
00024a32  20 40              movea.l d0, a0            ; zero-extend the UWORD
00024a34  2f 08              move.l a0, -(a7)          ; arg1 = raw MenuNumber
00024a36  61 00 d1 fc        bsr.w $21c34              ; handle_main_window_menu_selection
```

The `-(a7)` push shifts the frame, so `$30(a7)` after it *is* the `Code` slot written at
`0x240d6`. No `andi`/`lsl`/`rol` appears between the message and the call: **raw `Code`
through**. The handler at `0x21c34` reads that argument back with `movea.l $20(a7),a4` and
compares it directly against `$ffff` (`MENUNULL`).

### The selection walk (`0x21c34` … `0x21ce2`)

```text
00021c34  48 e7 38 3a        movem.l d2-d4/a2-a4/a6, -(a7)
00021c38  28 6f 00 20        movea.l $20(a7), a4       ; a4 = MenuNumber (raw Code)
00021c3c  26 6f 00 24        movea.l $24(a7), a3       ; a3 = win_data
00021c40  74 01              moveq #$1, d2             ; continue_running = TRUE
00021c42  b9 fc 00 00 ff ff  cmpa.l #$ffff, a4         ; MENUNULL?
00021c48  67 00 00 9c        beq.w $21ce6              ; ... return immediately
00021c4c  76 02              moveq #$2, d3
00021c4e  20 79 00 00 03 5c  movea.l $35c.l, a0        ; loop head; a0 = main_menu_strip (global)
00021c54  2c 79 00 00 01 60  movea.l $160.l, a6        ; a6 = IntuitionBase
00021c5a  20 0c              move.l a4, d0             ; d0 = MenuNumber, unchanged
00021c5c  4e ae ff 70        jsr -$90(a6)              ; ItemAddress(strip, MenuNumber)
00021c60  24 40              movea.l d0, a2            ; a2 = struct MenuItem *
00021c62  4a 80              tst.l d0
00021c64  67 6e              beq.b $21cd4              ; NULL item -> continue walking
00021c66  22 2a 00 22        move.l $22(a2), d1        ; GTMENUITEM_USERDATA (LONG @+0x22)
00021c6c  90 bc 00 00 03 e9  sub.l #$3e9, d0           ; 1001 MENU_PROJECT_NEW
      ...  six subq/beq arms ... 1002 OPEN, 1003 SAVE, 1004 SAVE_AS,
00021cb2  74 00              moveq #$0, d2             ; 1005 CLOSE -> continue_running = FALSE
      ... 1006 ABOUT; else $21cf0 "Unknown menu item ID: %ld\n"
00021cd4  78 00              moveq #$0, d4
00021cd6  38 2a 00 20        move.w $20(a2), d4        ; menu_number = item->NextSelect (WORD)
00021cda  28 44              movea.l d4, a4
00021cdc  b9 fc 00 00 ff ff  cmpa.l #$ffff, a4         ; while (menu_number != MENUNULL)
00021ce2  66 00 ff 6a        bne.w $21c4e
00021ce6  30 02              move.w d2, d0             ; return continue_running
```

This is the compiled form of `handle_main_window_menu_selection()` [S31 L296-L345]: the
`while (menu_number != MENUNULL)` loop, `ItemAddress(main_menu_strip, menu_number)`,
`GTMENUITEM_USERDATA()`, the `MENU_PROJECT_*` switch, and
`menu_number = menu_item->NextSelect;` closing the loop body. The app asks for
`IDCMP_MENUPICK` on the main window [S31 L1065] and `SetMenuStrip`s the strip after the
window opens [S31 L1101].

## What the binary pins

| Fact | Binary evidence | Compat-layer consequence |
| --- | --- | --- |
| `_LVOItemAddress = -144` (`-$90`), `A0` = strip, `D0` = packed `MenuNumber`, result `D0` | `jsr -$90(a6)` off `$160.l` at `0x21c5c` (also `0x34fcc`) | `intuition.library` `ItemAddress` must run the real walk, not invent an address |
| `_LVOSetMenuStrip = -264` (`-$108`), `A0` = window, `A1` = strip | `0x236a0`, `0x37a74` | attach projects a host menu bar and records `Window.MenuStrip` |
| `_LVOClearMenuStrip = -54` (`-$36`) | `0x23e72`, `0x380cc` | detach removes the host bar; strip state must be popped with the window |
| `GTMENUITEM_USERDATA` is a LONG at `MenuItem + 0x22` | `move.l $22(a2),d1` at `0x21c66` | GadTools-created items must store `nm_UserData` there (`MENUITEM_OFF_USERDATA`), matching the classic macro `*((APTR *)((struct MenuItem *)mi + 1))` |
| `mi_NextSelect` is a WORD at `MenuItem + 0x20`, **zero-extended**, compared with `$FFFF` | `move.w $20(a2),d4` / `cmpa.l #$ffff,a4` at `0x21cd4`/`0x21cdc` | every created item must carry `MENUNULL` in `mi_NextSelect`; a zero never terminates the walk |
| Selector is opaque to the app | `0x24a2c-0x24a36`, `0x21c5a` | our delivered `Code` only has to agree with our `ItemAddress` |

Macro values used for the encoding — `NOMENU $001F`, `NOITEM $003F`, `NOSUB $001F`,
`MENUNULL $FFFF`, `MENUNUM(n) = n & 0x1F`, `ITEMNUM(n) = (n >> 5) & 0x3F`,
`SUBNUM(n) = (n >> 11) & 0x1F`, with **1-based** field values [S1 Include_I/intuition/intuition.i
L1429-L1447] — are recorded in the in-tree include, which is the **4.1-era `intuition.i 47.6
(21.3.2021)`** cache, not the classic 3.x NDK (see the caveat in `compatibility-notes.md`).
They are treated as corroboration only; the binding constraint is the binary behaviour above
plus the app's own use of `MENUNULL` [S31 L300-L304].

## Obligations recorded from this

- `CreateMenusA` writes `NEXTSELECT_NULL` (`MENUNULL`) into every item block it builds
  (`menu_state.NEXTSELECT_NULL`, used by `src/amiga_ui/vamos/gadtools_library.py`). With a
  zeroed `mi_NextSelect` the target's walk never terminates: an observed run spun
  11.7 M `ItemAddress` calls instead of returning to `WaitPort`.
- `ItemAddress` resolves through `menu_state.resolve_menu_item_address`: `Menu.NextMenu` for
  the menu, `FirstItem`/`NextItem` for the item, `SubItem` + `NextItem` for the third level,
  NULL for `MENUNULL`/`NOMENU`/`NOITEM` or an exhausted chain. A miss records the strip as
  unprojected rather than producing a fake handle.
- The IntuiMessage bridge posts `IDCMP_MENUPICK` with the item's packed `Code` and
  `IAddress = 0` on the window's real `UserPort`; the app drives
  `WaitPort -> GT_GetIMsg -> GT_ReplyIMsg` itself [S27 §The IDCMP ¶1-3].
- A `NM_BARLABEL` separator is a real `MenuItem` and **consumes a chain slot**, so slot
  counts (not label counts) number the items. `iTidy`'s Project menu has 9 slots and `Close`
  is slot 9, i.e. `Code = 0xF921` (menu 1, item 9, `NOSUB`) — observed live.
- A sub-menu parent is opened, not picked: it gets no `IDCMP_MENUPICK` of its own.

## Verification

`tests/run_interactive_menu_smoke_test.py` runs the whole round trip without fabricating any
part of it: host `QAction` trigger → bridge `menu_pick` → real `IntuiMessage` on the real
`UserPort` → target `WaitPort`/`GT_GetIMsg` → target `ItemAddress` walk → `MENU_PROJECT_CLOSE`
→ target `CloseWindow` → host window closed, IMsg released, exit 0. Unit coverage:
`tests/test_menu_state.py`, `tests/test_menu_strip_path.py` (including the two
`NextSelect`-terminator regressions), `tests/test_qt_menu_strip.py`, `tests/test_event_bridge.py`.

## Not settled here

- Whether `_NM_BARLABEL` bar labels and the GadTools `/`-and-`\1` styling markup are honoured
  (the projection only doubles `&` for Qt mnemonics).
- Third-level (`SUBNUM`) chains: encoded and resolved, but `iTidy` uses two levels only.
- Multi-select `NextSelect` chaining beyond the app's own loop (the field is never written to
  anything but `MENUNULL` by the compat layer).
