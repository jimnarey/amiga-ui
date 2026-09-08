---
title: "iTidy Compatibility Notes"
status: draft
depends_on:
  - "runbook.md"
  - "../../runtime/vamos-gaps.md"
  - "run-log.md"
  - "../../runtime/workbench-integration-boundaries.md"
  - "../../host-gui/README.md"
  - "../../workflows/external-helpers-and-shellouts.md"
citations_used:
  - "S11"
  - "S12"
  - "S29"
  - "S30"
  - "S31"
  - "S32"
  - "S33"
  - "S34"
  - "S35"
---

# iTidy Compatibility Notes

Purpose: Track the current support state of `iTidy` under the project runtime.

Needed for:
- Preventing repeated investigation of the same failures.

## Current Status

Trust `run-log.md` over any status claim in the sections below. The log is the append-only, dated record of what has actually been run and observed; the sections below are forward-looking triage guidance written before most of that evidence existed, and can go stale as the log advances. Read the log's most recent entry first, then use the rest of this file to interpret it.

The latest direct CLI probe draws the full window chrome — the group-box bevels (`DrawBevelBoxA`), the group-box titles (`PrintIText`), the folder-path box (`Text`), the busy-pointer toggles (`SetWindowPointerA`), and the window/icon font (`OpenDiskFont`) — and **no `host-ui-required` (visible-UI) call remains**. The stateful-runtime frontier is also now **fully cleared**: `timer.device` `GetSysTime` (coherent 1978-epoch system clock), `dos.library` `GetCurrentDirName` (derived from the process cwd lock), and `iffparse.library` `FreeIFF` (honest `AllocIFF`/`FreeIFF` handle lifecycle) are all implemented, gated, and merged (see `run-log.md`, 2026-09-08). The app now ends at the honest `WaitPort`-on-empty-queue `UnsupportedFeatureError` boundary, and the only remaining analyzer items are missing prepared-runtime paths (`ENV:`/`ENVARC:` prefs, `RAM:CRITICAL_FAILURE.log`, `S:User-Startup`). Treat that prepared-runtime/prefs boundary as the next workstream, not the stateful frontier.

## Compatibility Frontier

The purpose of the sections below is to define the expected compatibility frontier clearly enough that new runs can be classified quickly instead of re-arguing the target every time.

## Likely Earliest Wins

These are the behaviors most likely to become usable first:

- binary loading under `vamos` with explicit volumes, assigns, and command path
- basic `.info` discovery in a small test drawer
- non-recursive icon layout over real icon files
- visible progress to main-window creation

Those are the most realistic early wins because the app's core scope is Workbench metadata rather than direct graphics hardware or undocumented devices [S11 L150-L153] [S12 L5-L8].

## Behaviors That Clearly Need Workbench-Class Support

The following areas should be treated as blocked until the runtime can supply genuine Workbench semantics:

- launch via `WBStartup` rather than only CLI argv [S30 L623-L687]
- reading program-icon tooltypes at startup [S30 L277-L380]
- correct current-directory behavior during Workbench launch [S30 L330-L335]
- stable use of Workbench/public-screen UI resources, menus, and requesters [S31 L174-L227] [S31 L470-L518]

If an investigation is still at plain Shell launch, failures in these areas are expected rather than surprising. See `../../runtime/workbench-integration-boundaries.md` for which of these are first-wave versus later-phase, and `../../host-gui/README.md` for how the UI-facing items should be implemented on the host side.

## Behaviors That Are Probably Optional Or Second-Phase

These features matter, but they should not be allowed to block the very first runnable milestone:

- default-tool validation using PATH parsed from startup scripts [S12 L244-L250] [S34 L1275-L1310]
- LhA backup and restore [S12 L256-L299] [S32 L93-L119] [S32 L201-L249]
- higher-fidelity icon handling that depends on icon-library v44 features [S12 L207-L209] [S34 L803-L825]
- scan-time exclusions such as left-out icons and disk icons [S35 L366-L395]

They are important compatibility targets, but they sit behind "the app launches and can inspect a small test folder" in the delivery order. See `../../workflows/external-helpers-and-shellouts.md` for how to triage the `LhA` dependency specifically.

## Source-Release Drift To Keep In Mind

The user-facing docs identify the application as version 1.0, but the current source comments describe a GUI migration and refer to a GUI version 2.0.0 [S12 L382-L386] [S30 L1-L9]. Treat this as a standing caution:

- the released binary and published manual define the baseline behavior we are trying to reproduce;
- the source tree is excellent for understanding dependencies and likely failure modes;
- but a source-only feature should not be marked as "required for compatibility" until a real run or release artifact confirms it.

## Likely Failure Buckets

When `iTidy` fails under the project runtime, the most probable first buckets are:

- missing or inaccurate Workbench launch semantics
- incomplete `dos.library` path and lock behavior
- incomplete `icon.library` load/save/default-tool behavior
- missing `graphics.library` startup support
- missing Intuition or requester behavior
- missing command execution support for `LhA`

This ordering comes directly from the published feature set and the current source structure, which bundles GUI, icon, scan, default-tool, and backup subsystems into one executable [S11 L15-L26] [S29 L38-L116].

## Unresolved Struct-Offset Questions (binary confirmation pending)

The classic `struct Gadget` tail fields (`GadgetID`, `UserData`, `SpecialInfo`) and
the event `IAddress` are settled: the repo offsets (`GadgetID@0x26`, `UserData@0x28`,
`SpecialInfo@0x22`, `IntuiMessage.IAddress@0x18`) match both the classic m68k NDK and
the header cached in the repo, and the `IAddress` value is exercised end-to-end by the
working event bridge (`WaitPort -> GT_GetIMsg -> GT_ReplyIMsg`). `struct NewGadget`
matches the classic layout. There are **two distinct `IntuiText` layouts** in the
repo: `gadtools_library.py` builds repo-allocated GadgetText in the 3.x `iT_*` layout
(separate, currently inert — nothing dereferences it), while `intuition.library`
`IntuiTextLength`/`PrintIText` read the **app's** IntuiText in the old pre-2.0 field
layout the target builds (settled below).

- **`struct IntuiText` ABI — settled from the running target.** The target's
  `vc +aos68k` compiler **aligns** members to their natural alignment (it does not
  pack), so the app's IntuiText field offsets are: `FrontPen@0x00`, `BackPen@0x01`,
  `DrawMode@0x02`, (pad)@0x03, `LeftEdge@0x04`, `TopEdge@0x06`, (pad)@0x08,
  `ITextFont@0x08`, **`IText@0x0C`** (string pointer), `NextText@0x10`, size `0x14`.
  This was confirmed empirically: the three group-box titles (`"Folder"`,
  `"Tidy options"`, `"Tools"`) decode correctly **only** from the pointer at `0x0C`;
  the packed offset `0x0B` yields a short pointer and garbage, and the other fields
  (`LeftEdge`/`TopEdge` = 0 at `0x04`/`0x06`, `ITextFont` = NULL at `0x08`,
  `NextText` = NULL at `0x10`) corroborate the aligned layout. `intuition_library.py`
  reads the string pointer and front pen from these offsets.

The following remain **unconfirmed against the binary** and should be settled by
disassembling `iTidy`'s event handler and RastPort reads (the HUNK CODE segment is the
ground truth; see `docs/architecture/platform-target.md` evidence order) before they are
treated as settled:

- **RastPort font-field offsets — the binary does not read them directly (disassembled,
  2026-09-06).** `intuition_library.py` writes `RpFont`/`TxHeight`/`TxWidth` at
  `RastPort+0x34`/`+0x3A`/`+0x3C`; the classic 3.x `RastPort` (with the `RasInfo` field)
  places them at `+0x22`/`+0x2E`/`+0x30`. The HUNK CODE segment was disassembled cleanly
  (VBCC 0.9; real code from file `0x3E` / disasm addr `0x0A`; 106,265 instructions, zero
  skipdata artifacts, so field displacements are reliable) and searched exhaustively for a
  direct RastPort font-field load:
  - **No** `move.b $3c(aX)` (repo `TxWidth`) from any `a0`–`a6` base, and **no**
    `move.b $2e(aX)`/`$2f(aX)` (classic `TxHeight`/`TxBaseline`) anywhere.
  - The two `move.b $3a(aX)` (repo `TxHeight`-offset) hits (`0x31c26`, `0x31e2a`) read a
    byte from a **function-argument struct** whose `+4` is a dereferenced pointer — a
    `RastPort`'s `+4` (`Rp_OrigY`) is a word, so that base is not a RastPort.
  - All five `move.b $30(aX)` (classic `TxWidth`-offset) hits load a byte from a
    **library-returned pointer** and compare it to `1`/`2` — an enum/state field, not a
    font metric (a width is multiplied, never compared to 1/2).
  - The `RpFont`-offset `move.l` hits are not RastPort reads either: `move.l $22(a2)` at
    `0x21c66` subtracts `HUNK_CODE` (`0x3e9`) — a HUNK-type check — and the `move.l
    $34(aX)` hits push struct fields for an internal call whose base is not a RastPort.
  - The `lea.l $54(aX)` (RastPort-in-`Screen`) sites either pass the RastPort pointer to a
    graphics-library call or read a word from a non-Screen struct; none lead to a
    `TxWidth` byte read. All 360 `mulu.w`/`muls.w` in the binary are unrelated to a
    byte-read from a RastPort base (there is no `font_width * N` computation).

  **Conclusion — this binary cannot settle the offset.** The shipped binary does **not**
  directly access `RastPort.TxWidth` or `RastPort.TxHeight`: it passes the RastPort
  pointer to graphics-library calls (`TextLength` and friends) and never loads the
  font-metric fields itself, so no HUNK CODE displacement pins the field offset. The
  `lea.l $54(aX)` sites do confirm RastPort-within-`Screen` at `+0x54`, matching the repo.
  The `+0x34`/`+0x3A`/`+0x3C` offsets are therefore a **compat-layer model choice**, not a
  binary constraint: `graphics.library` `TextLength`/`Text` read `TxWidth` from `+0x3C` and
  the repo writes the Topaz width (`6`) there, so the layer is self-consistent, and the
  binary's text metrics come from the library call, not a direct field load. No production
  offset change is warranted from this evidence, and a runtime sentinel diagnostic is not
  applicable because there is no binary-produced value that depends on a direct `TxWidth`
  read to observe. (The source's `calculate_font_dimensions` does read these fields
  directly, but the shipped binary predates it — the source's `"SCREEN CHROME"` debug
  string is absent from the binary — so the source is guidance, not the ground truth here.)
- **`struct Screen` field offsets.** `intuition_library.py` uses `Flags@0x14`,
  `Title@0x18`, `BarHeight@0x20`, `WBorTop@0x25`, `Font@0x2C`, embedded `ViewPort@0x30`,
  `RastPort@0x54`, `BitMap@0xB8`. These differ from the classic 3.x `Screen` layout the
  project otherwise targets; confirm `WBorTop`, `Font`, `BitMap`, and especially
  `RastPort`-within-`Screen` against the binary. `RastPort`-within-`Screen` at `+0x54` is
  now **binary-confirmed**: the CODE segment's `lea.l $54(aX)` sites compute
  `&screen->RastPort` and hand the result to graphics-library calls, so the app itself
  places the RastPort at `Screen+0x54`. The other offsets above remain to be confirmed.
- **`GadgetID` offset.** High confidence in `0x26` (three sources agree), but a prior
  session log claimed `0x28`/size `0x30`. A definitive disassembly of the
  `switch (gad->GadgetID)` ladder in the binary would close this out.

Note on references: the repo's cached `assets/docs/ndk/NDK3.2/` is actually the
**AmigaOS 4.1** NDK (`$VER: intuition.h 47.7 (26.12.2021)`, © Hyperion), not the classic
3.x NDK that citation `S1` points at. Its `struct Gadget` coincidentally matches the
classic layout, but its `struct IntuiText` is the old pre-2.0 shape, so it must not be
used as the reference for the default m68k 3.0-3.1 target.
