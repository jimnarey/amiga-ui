---
title: "Session log — iTidy graphics ABI: dispatch fix, RastPort state model, IntuiText layout, offset reconciliation"
status: log
depends_on:
  - "../apps/itidy/run-log.md"
  - "../apps/itidy/compatibility-notes.md"
  - "../architecture/platform-target.md"
  - "../platform/library-cards/graphics.library.md"
  - "../workflows/branching-and-merging.md"
citations_used:
  - S1
  - S26
  - S28
  - S31
  - S43
---

# Session log — iTidy graphics drawing ABI (2026-09-05)

Purpose: Durable record of the session that stabilised the classic Intuition/GadTools **drawing ABI** and drawing-state foundations that `iTidy` and other classic Workbench-era apps need: fixed the repo-owned `graphics.library` dispatch so the six drawing calls are actually invoked, added a minimal host-side RastPort state model, corrected `struct IntuiText`, and reconciled the gadget/RastPort/Screen struct offsets against the classic target — while keeping the honest `WaitPort`-on-empty-queue boundary intact and not faking any success.

Needed for:
- Recalling *why* the six drawing calls were silently dropped (missing `ctx`) and how the scanner classifies methods, so the same trap is not re-derived.
- Picking up the still-unconfirmed RastPort/Screen field offsets without re-diagnosis — those are the real remaining ABI risk.
- Remembering the correction to the prior session's "Gadget tail mismatch" follow-up (the repo layout was already correct) and the discovery that the repo's cached `NDK3.2` is mislabeled (it is the AmigaOS 4.1 NDK).

Notes:
- Continues `20260905T0518Z-session-log-iTidy-intui-event-bridge.md`, which ended at the honest `WaitPort`-on-empty-queue boundary with the drawing frontier open. Companion to `../apps/itidy/run-log.md` (run-level blockers) and `../apps/itidy/compatibility-notes.md` (target-specific triage); this file records the *session*.
- The default runtime target is classic m68k Workbench/AmigaOS 3.0–3.1 (see `../architecture/platform-target.md`). No host GUI window was in scope this session; drawing is recorded to a host-side state model, not rendered.

## Session summary

| Item | Value |
| --- | --- |
| Harness | DeepSeek Harness (dsh), Web GUI at 127.0.0.1:3080 |
| Sandbox / approval | workspace-write / ask |
| Main work date | 2026-09-05 (UTC) |
| Work span (from repo/run evidence) | probe run `20260905T205911Z` → commit `e5e7398` 21:01 UTC (exact start and token counts not re-derived here) |
| Model | `Qwen3.8-27B-UD-Q6_K_M` |
| Git baseline → end | `development` @ a51ce6a → e5e7398 (one feature branch, `fix/graphics-rastport-abi`, created from `development`, gated, fast-forward merged; kept, not deleted) |
| Exact request/token counts, compactions, session id | in the raw session log on the agent host (not re-derived here) |

Milestone achieved: the `iTidy` probe's six drawing calls (`SetAPen`/`SetBPen`/`SetDrMd`/`Move`/`Draw`/`RectFill`) plus `SetFont` now **hook and record real state** instead of being dropped as `UNKNOWN` traps, and the app's group-box drawing path executes end-to-end up to the unchanged, honest `WaitPort`-on-empty-queue boundary. The scanner for `graphics.library` went from several *error* methods to **37 valid / 0 error / 0 invalid**.

## What changed in the repo (in order)

| Commit | Branch (kept) | Change |
| --- | --- | --- |
| e5e7398 (merged into `development`) | `fix/graphics-rastport-abi` | `src/amiga_ui/vamos/graphics_library.py` (rewritten: every method `ctx`-first with the exact `.fd` arg count; drawing methods update the RastPort state, frontier methods record to `call_log`); `src/amiga_ui/vamos/rastport_state.py` (new: `RastPortState`/`RastPortRegistry`); `src/amiga_ui/vamos/gadtools_library.py` (`struct IntuiText` corrected to the classic 3.x `iT_*` layout, both write sites); `tests/test_graphics_library.py` (new, 18 tests); docs (`graphics.library.md` card, `itidy/compatibility-notes.md` offset follow-up) |

## Blocker narrative (what actually happened)

### 1. The six drawing calls were silently dropped — root cause: missing `ctx`

The app's `SetAPen`/`SetBPen`/`SetDrMd`/`Move`/`Draw`/`RectFill` (and `SetFont`) appeared in the probe log as `UNKNOWN(#56/#39/#40/#50/#57/#58)` at WARNING. The cause: the repo's `GraphicsLibrary` methods were declared **without** the leading `ctx` parameter. vamos' method matcher only installs a trap when **name + `ctx`-first + exact `.fd` arg count all match**; a mismatching method is a scanner *error* and is dropped, so the app's call fell through to the `UNKNOWN` hole and the drawing was lost. The fix was to declare every method `ctx`-first with the exact arg count of its pinned `graphics.library` `.fd` entry (see "Key technical findings" for the four methods that also had the wrong count).

### 2. The RastPort state model: record, don't no-op

The drawing methods were no-op success returns (forbidden by the repo rule that an implemented API must update emulated state or record a useful host-side operation). A host-side `RastPortState` (keyed by the emulated RastPort pointer) now records the pen/draw-mode/font state the app configured plus an ordered op log. `SetMaxPen`/`SetOutlinePen`/`SetFont` return the **previous** value (the classic contract [S43]); the drawing methods append ops that carry the state in effect when they ran. There is no host window yet, so this record — not a fake success — is what makes the calls meaningful; a later renderer can replay the ops. Frontier entry points the app has not driven (color/BitMap/display-info/font) record into `call_log` and return honest defaults (`AllocBitMap` → 0, `GetVPModeID` → 0) rather than a fabricated success.

### 3. `struct IntuiText` matched no NDK

The repo's `IntuiText` layout (used to build `Gadget.GadgetText` in `CreateGadgetA` and the menu path) matched no known NDK. It was corrected to the classic AmigaOS 3.x `iT_*` layout: `iT_Face@0x00`, `iT_FaceRelative@0x02`, `iT_Left@0x04`, `iT_Top@0x06`, `iT_Width@0x08`, `iT_Height@0x0A`, `iT_ForePen@0x0C`, `iT_BackPen@0x0D`, `iT_DrawMode@0x0E`, `iT_Proportion@0x0F`, `iT_Quality@0x10`, `iT_Text@0x14`, `iT_FaceFont@0x18`, `iT_PenMap[8]@0x1C`, size `0x24`. This is low-risk: nothing in the implemented path dereferences IntuiText fields yet — the app hands `GadgetText` to the (frontier) text-metrics/`PrintIText` functions.

### 4. Offset reconciliation, and the correction to the prior session

The task was to verify `struct Gadget`, `NewGadget`, `IntuiText`, `RastPort`, and event `IAddress` offsets against the classic target, "especially the gadget tail fields". Findings:

- **`struct Gadget` and `NewGadget` were already correct.** The repo layout is `GadgetID@0x26`, `UserData@0x28`, `SpecialInfo@0x22`, size `0x2C`; `NewGadget` is `ng_GadgetID@0x10`, `ng_UserData@0x1A`, size `0x1E`. Both match the classic m68k 3.x NDK [S1]. **This corrects the prior session log's "Gadget struct tail mismatch" follow-up** (`20260905T0518Z` line 104), which claimed the repo was "8 bytes too small" with `GadgetID@0x28`/size `0x30` — that claim is not supported by the repo code, the classic NDK, or the in-repo header, and is treated as a misreading. No change was made to the gadget layout.
- **`IntuiMessage.IAddress@0x18`** is exercised end-to-end by the working event bridge and is unchanged.
- **`RastPort` and `struct Screen` field offsets remain unconfirmed against the binary** (see "Latent defects and follow-ups").

### 5. Binary ground-truth extraction was inconclusive

A subagent was dispatched to disassemble `iTidy`'s relocated CODE segment and extract the actual field offsets the app reads (GadgetID, RastPort `RpFont`/`TxHeight`/`TxWidth`, `Screen` fields, `IAddress`). It ran long and was interrupted before returning a final report; its partial output is treated as **inconclusive**. The RastPort/Screen offsets are therefore documented as an open follow-up rather than settled. The durable methodological caution stands: the app *working* (drawing group boxes, passing the visual-info gate) is **not** proof of offset correctness, because zeroed memory yields plausible values.

## Key technical findings

### vamos FD-driven method matching (confirmed)

A library method is hooked **only** if its name, a leading `ctx` parameter, and the exact `.fd` arg count all match the pinned library's function-definition table. The `LibImplScanner` classifies each method:

- **valid** — hooked; logged at INFO (which the probe's `vamos.log` does *not* capture).
- **error** — bad signature (missing `ctx` or wrong arg count) → dropped; the app's call shows as `UNKNOWN(#idx)` at WARNING.
- **missing** — in the `.fd` but not implemented → `? CALL: Name(args) -> d0=0 (default)` at WARNING.

Non-`.fd` methods are silently not wired (no error). "0 `UNKNOWN` lines for `graphics.library`" is therefore the observable success signal; the hooked calls themselves are invisible in the probe log. Four methods also had the **wrong arg count** (fixed per the `.fd` dump): `GetDisplayInfoData` 3→5, `AllocBitMap` 4→5, `ObtainBestPenA` `*args`→5, `ObtainPen` 2→6.

### The repo's cached `NDK3.2` is the AmigaOS 4.1 NDK (mislabeled)

`assets/docs/ndk/NDK3.2/` is the **AmigaOS 4.1** NDK (`$VER: intuition.h 47.7 (26.12.2021)`, © 2019–2022 Hyperion), not the classic 3.x NDK that citation `S1` points at. Its `struct Gadget` *coincidentally* matches the classic layout, but its `struct IntuiText` is the **old pre-2.0 shape** (`FrontPen@0x00` … size `0x14`, no `iT_*` fields). Per `../architecture/platform-target.md` evidence order, it must not drive default m68k 3.0–3.1 struct choices; the discrepancy is now recorded in `../apps/itidy/compatibility-notes.md`.

### The honest `WaitPort` boundary is preserved

`WaitPort` on an empty queue still raises `UnsupportedFeatureError` (`exec_library.py` line 72). The probe ends exactly there (`Port (06b3c8)`), identical boundary to the prior session — no regression, and the fix was not papered over by making an empty wait succeed.

### Text metrics remain the honest graphics frontier

`Text` (bias 60) and `TextLength` (bias 54) are not implemented and log as honest `? CALL … -> d0=0 (default)`. `IntuiTextLength`/`PrintIText`/`DrawBevelBoxA`/`GT_RefreshWindow`/`SetWindowPointerA` (carried from the prior session) remain frontier and are out of scope here.

## Latent defects and follow-ups (not fixed this session)

- **`RastPort` field offsets (unconfirmed).** `intuition_library.py` writes `RpFont`/`TxHeight`/`TxWidth` at `RastPort+0x34`/`+0x3A`/`+0x3C` (i.e. `Screen+0x88`/`+0x8E`/`+0x90`, with `RastPort` embedded at `Screen+0x54`). The classic AmigaOS 3.x `RastPort` (with the 3.0 `RasInfo` field) places them at `+0x22`/`+0x2E`/`+0x30`. The app reads usable values, but that is not proof. Confirm the binary's actual offsets; if they differ, update `intuition_library.py`.
- **`struct Screen` field offsets (unconfirmed).** `intuition_library.py` uses `Flags@0x14` (WORD; classic is ULONG@0x18), `Title@0x18`, `WBorTop@0x25`, `Font@0x2C`, embedded `ViewPort@0x30`, `RastPort@0x54`, `BitMap@0xB8`. These differ from the classic 3.x `Screen` layout and are unconfirmed against the binary.
- **`GadgetID` offset** — high confidence in `0x26` (three sources agree), but a definitive disassembly of the `switch(gad->GadgetID)` ladder would close it out for good.
- **Binary offset disassembly** — the subagent extraction was inconclusive; the follow-up (disassemble `iTidy`'s RastPort reads / event handler from the relocated CODE segment) is still open.
- **Text-metrics frontier** — `Text`/`TextLength`/`IntuiTextLength`/`PrintIText` remain unimplemented (`d0=0`).

## Techniques that worked

- **Scanner diagnostic as the arbiter of dispatch.** Running `LibImplScanner().scan("graphics.library", impl, read_lib_fd("graphics.library"), True)` before/after the fix turned the "is it hooked?" question into a count (37 valid / 0 error) instead of log-archaeology. The paired signal — *absence* of `UNKNOWN` `graphics.library` lines in the probe log — confirmed the app's six calls now land.
- **pyright narrowing via a `self.fail()` guard.** `RastPortRegistry.state()` returns `RastPortState | None`; this pyright version did not narrow on `self.assertIsNotNone(...)`, so the test helper returns the narrowed type via `if st is None: self.fail(...)` (the `NoReturn` guard narrows reliably).
- **`PRE_COMMIT_HOME` pointed at a writable dir.** The default `~/.cache/pre-commit` store is read-only under the `workspace-write` sandbox (`attempt to write a readonly database`); setting `PRE_COMMIT_HOME` to a workspace path let `pre-commit` run its hooks (ruff check / ruff format / pyright).
- **Repo-vs-NDK cross-check to catch the IntuiText mismatch.** Comparing the repo constants against the classic 3.x NDK [S1] (and the in-repo OS4 header) surfaced that the IntuiText layout matched neither, and that the "NDK3.2" cache is mislabeled.
- **Git discipline per `../workflows/branching-and-merging.md`:** one branch per blocker off updated `development`, narrow tests (`tests.test_graphics_library`, 18) + the full suite (63 OK) + direct `amiga-ui probe … --direct` (no regression, honest `WaitPort` boundary) + pre-commit before the fast-forward merge; branch kept, not deleted. `artifacts/` (probe outputs + relocated-code analysis binaries) deliberately left untracked.

## Session-log recovery note

The full raw session log (zstd-compressed JSONL: all user/assistant messages, reasoning, tool calls, tool results, compaction events) is stored on the agent host under the harness sessions directory for this session id and is a strict superset of this file; use it to recover exact commands, outputs, the exact session-creation time, and the request/token counts (which this markdown does not re-derive). This markdown is the distilled, repo-durable version.
