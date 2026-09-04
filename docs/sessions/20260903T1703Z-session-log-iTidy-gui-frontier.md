---
title: "Session log — iTidy GUI frontier: jump tables, real Window/UserPort, event-loop boundary, group-box geometry"
status: log
depends_on:
  - "../apps/itidy/run-log.md"
  - "../apps/itidy/compatibility-notes.md"
  - "../workflows/error-driven-porting.md"
  - "../runtime/vamos-overview.md"
citations_used:
  - S1
---

# Session log — iTidy GUI frontier (2026-09-03 → 2026-09-04)

Purpose: Durable record of one long DeepSeek Harness session that moved the `iTidy` probe from "Could not get visual info" to a fully initialized GUI (two windows, thirteen gadgets, menus, sane group boxes) stopping honestly at the event loop.

Needed for:
- Recalling how the in-process `vamos` launcher actually dispatches library calls, so the same ground is not re-derived.
- Picking up the remaining `iTidy` blockers (gadget struct tail, unimplemented `? CALL`s, event loop) without re-diagnosis.

Notes:
- Companion to `../apps/itidy/run-log.md`, which tracks run-level blockers; this file records the *session*: what was discovered about the runtime, what was changed, and what was deliberately left open.
- Session identifier: `session-36a21762-518d-4fad-bbfb-c17f6e1859ab`. The raw session log (JSONL, zstd) on the agent host is a superset of this file and can be used to recover exact commands, tool outputs, and the user's decisions.

## Session summary

| Item | Value |
| --- | --- |
| Harness | DeepSeek Harness (dsh), preset `amiga-ui-standard`, Web GUI at 127.0.0.1:3080 |
| Sandbox / approval | workspace-write / ask |
| Session created | 2026-09-03 17:03:06 UTC |
| Main work turn | 2026-09-03 17:10 → 2026-09-04 17:13 UTC (one continuous autonomous turn) |
| Wall-clock span | ~26 h (includes an idle overnight gap); ~7.6 h of active (sub-minute-gap) time |
| Model | `Qwen3.8-27B-UD-Q6_K_M` via llama-cpp (OpenAI-compatible endpoint), context window 163,840 |
| Reasoning | Model emits reasoning content (recorded as `reasoning-chunks` in the log); no separate reasoning budget configured in the preset |
| Model requests / steps | 399 requests, 395 steps |
| Tokens | ~459,000 output tokens generated; peak request context 94,891 tokens |
| Compactions | 7 during the main turn (09-03 18:43, 20:06, 21:23, 22:45; 09-04 13:59, 14:17, 16:02 UTC), 1 at the start of the follow-up turn |
| Git baseline → end | `development` @ 98447a1's parent chain → 79447b8 (four feature branches created, gated, merged; none deleted) |

Milestone achieved: the probe run's terminal state moved from a hard failure at `GetVisualInfo` ("Could not get visual info" → "Failed to open GUI window") to a **fully initialized GUI that reaches the main IDCMP event loop**, where it stops at the recorded emulator boundary (`WaitPort` on an empty queue).

## What changed in the repo (in order)

| Commit | Branch (kept) | Change |
| --- | --- | --- |
| 205e4c8, merged f6b9279 | `fix/intuition-screen-visual-info` (built on pre-existing WIP f292230 exposing `ctx.alloc`) | Bundled-first / repo-NDK-fallback FD `LibCreator` (`src/amiga_ui/vamos/fd_creator.py`); real `GetVisualInfoA`/`FreeVisualInfo`, `CreateContext`/`CreateGadgetA`/`FreeGadgets`, `CreateMenusA`/`LayoutMenusA`/`FreeMenus`, `GetScreenDrawInfo`/`FreeScreenDrawInfo`, real `OpenWindowTagList` Window struct + `SetMenuStrip` (+652 lines across `fd_creator.py`, `gadtools_library.py`, `intuition_library.py`, `launcher.py`) |
| 8eb8335, merged 446e451 | `fix/iTidy-window-userport` | Register real `UserPort`/`WindowPort` MsgPorts for opened windows via the exec impl's `port_mgr`; `CloseWindow` releases them; launcher exposes `vlib_mgr` to library impls |
| 41e297e, merged 98447a1 | `docs/event-loop-boundary` | Record the in-process event-loop boundary in the intuition/exec library cards |
| a326cb3, merged 79447b8 | `fix/iTidy-groupbox-geometry` | Shift embedded `Screen.RastPort` 0x58 → 0x54 and `BitMap` 0xBC → 0xB8 to match the app's pre-`RasInfo` ViewPort layout |

## Blocker narrative (what actually happened)

### 1. `GetVisualInfo` was never reached — the jump table was fake

The app printed "Could not get visual info" and no `gadtools.library` `? CALL` was logged, so the missing-function hypothesis was wrong: the call was not reaching the library at all. The root cause was in `vamos`'s library creation: its `LibCreator` reads function-definition tables from the **amitools bundled FD directory**, which has **no `gadtools_lib.fd`**. When the FD is missing, vamos generates a *fake* FD (standard calls only), so the real `GetVisualInfoA` entry (index 20, bias 126, LVO −126) did not exist in the jump table. Several other libraries (diskfont, workbench, gadtools, asl) were silently affected the same way.

Fix: a repo-owned `LibCreator` that is **bundled-first with a fallback to the repo's NDK 3.2 FD directory** (`assets/docs/ndk/NDK3.2/`) before generating a fake FD. Re-pointing the whole FD directory was deliberately rejected because the bundled and repo-NDK FDs differ even for libraries that already worked.

### 2. The GadTools/Intuition GUI path, one real function at a time

Once dispatch was fixed, each probe run surfaced the next missing function, implemented from NDK headers + app source + AutoDocs:

- `GetVisualInfoA`: returns NULL only for a NULL screen; otherwise a private, screen-derived block the app treats as opaque (passed to `NewGadget.ng_VisualInfo`, consumed by GadTools).
- `CreateContext` + `CreateGadgetA` + `FreeGadgets`: real gadget-list behaviour — `CreateContext(&glist)` allocates an invisible context gadget as the list head; `CreateGadget` copies geometry/kind/id from `NewGadget`, builds a minimal `IntuiText` label, and chains via `NextGadget`.
- `GetScreenDrawInfo`/`FreeScreenDrawInfo`: real screen-derived `DrawInfo` (RastPort pointer), not a bare stub.
- `CreateMenusA`/`LayoutMenusA`/`FreeMenus`: real `Menu`/`MenuItem` structures from the app's `NewMenu` template.
- Real `Window` from `OpenWindowTagList`: the previous fake `0x20000` handle crashed `CalcGadgetGroupBoxRect` (`InvalidMemoryAccessError: R(2): 6c7568`) because the app reads `win->RPort` (0x32) and `win->WScreen` (0x2E) from it.

### 3. The event loop: real UserPort, then an honest boundary

The app's main loop waits on `win->UserPort`. With the port NULL it hit `VamosInternalError: WaitPort on invalid Port (000000)`. Registering a real queue-backed MsgPort (via the exec impl's `port_mgr`, reached as `vlib_mgr.get_vlib_by_name("exec.library").impl.port_mgr`) changed the failure to the true boundary: `UnsupportedFeatureError: WaitPort on empty message queue`. The in-process emulator cannot block on a port, and there is **no host-side input source** that would ever enqueue IDCMP messages — so the event loop is out of reach without a genuine input-to-IDCMP bridge.

User decision (asked in-session): **record as an honest limitation**, do not fabricate IDCMP events. Documented in the intuition/exec library cards.

### 4. Group-box Y geometry: the app was compiled against a pre-`RasInfo` NDK

Gadget `TopEdge`/`Height` were fixed garbage (e.g. 43618/43598) while X values were correct. The app computes `font_height = screen->RastPort.TxHeight` and `topborder = screen->WBorTop + TxHeight + 1`, so the suspicion was `TxHeight`. Every NDK 3.2 offset was verified correct (ViewPort 0x28, RastPort at Screen+0x58, `TxHeight` at RastPort+0x3A = Screen+0x92), and probes proved the screen held `TxHeight=8` at both `OpenWindowTagList` and `CreateGadgetA` time.

The decisive diagnosis:

1. **Pattern-stamping** the screen region left the NewGadget `H` completely unchanged — the value did not track screen memory at all (fixed garbage).
2. **RAM scan** for the big-endian value the app evidently read (`font_height = 43598 − 6 = 43592 = 0xAA48`) found a hit at **screen+0x8E** — the low word of `RastPort.Font` in the 3.2 layout, i.e. the `TxHeight` offset in a layout where RastPort starts at **Screen+0x54**.

So `iTidy` was compiled against the **pre-`RasInfo` `struct ViewPort` (0x24 bytes)** rather than the NDK 3.2 one (0x28, with the `struct RasInfo *RasInfo` tail) [S1 Include_H/graphics/view.h]. Its `Screen.RastPort` sits at 0x54, `TxHeight` at 0x8E. Fix: `_OFF_RASTPORT` 0x58 → 0x54 and `_OFF_BITMAP` 0xBC → 0xB8 in `intuition_library.py`; `Window.RPort` and `DrawInfo.RastPort` derive from the constant and followed automatically. After the fix all 13 gadgets have sane geometry (Browse button T=34 H=14; `DrawBevelBoxA` at (95, 34, 395×14); group boxes (15,66)–(610,132) and (15,140)–(610,167)).

## Key technical findings

### How vamos dispatches library calls

- Every jump-table entry is `jmp <trap>`; vamos performs **no clib setup**. A library call is handled iff it lands on a jump-table entry.
- Jump-table entry for FD index *i* is at `lib_base − (i+1)·6` (the classic LVO displacement formula).
- The FD table drives the jump table. **Missing FD → fake FD (standard calls only) → non-standard entries silently absent** — the app's call simply never traps, with no error at all. This is the failure mode to suspect whenever a call that *should* log a `? CALL` does not appear in `vamos.log`.
- Logging: missing functions log `? CALL ... (default)` when `log_missing` is set (on in the probe); implemented functions log only when `log_valid` is set.
- The repo's in-process launcher extends upstream via `BaseLibrary`/`LibImpl` subclasses: impl method name must match the FD name exactly, and a non-`None` return value becomes D0. `ctx.mem` is the machine68k `Memory` object (`r8/r16/r32`, `w8/w16/w32`, `r_block`, `get_ram_size_bytes`); `ctx.alloc` (added by the launcher WIP) is the vamos allocator; `ctx.vlib_mgr` (added this session) reaches other libraries' impls.

### Calling conventions in the `iTidy` binary

- The app uses **clib stubs compiled into the binary**: `jsr (aX)` (4EAE, ~1752×) with aX holding the full jump-table entry address, and `jsr.l <abs>` (~3179×) to its own low-address stubs. **Zero** `jsr d16,a6` (1D70) — no inline LVO form at all.
- File offset ≠ runtime address: multiple segments with different bases, plus vamos relocations applied at load (only address operands change), so on-disk byte patterns must be matched against the relocated in-memory code.
- Register/PC capture inside a trap is unreliable (the trap mechanism clobbers stack/registers before the Python impl runs); instrumenting the trap *dispatch* to log every call was the reliable observability tool.
- A hand-rolled m68k opcode decoder was written and debugged for this session (wrong `jsr d16,A6` encoding at one point: it is `1D 70`, not `1D 90`); it was temporary and removed.

### Intuition ↔ GadTools interaction

- The app's gadget geometry is sourced from the **Intuition-owned `Screen` struct** during GadTools calls: `font_height = screen->RastPort.TxHeight`, `topborder = screen->WBorTop + RastPort.TxHeight + 1` (main_window.c), `ng_Height = font_height + 6`, `current_y = topborder + 25`. GadTools correctness therefore depends on the Intuition `Screen` layout matching the ABI the app was compiled against.
- `win_data->screen` comes from `LockPubScreen(NULL)`; `visual_info` from `GetVisualInfo(screen, TAG_END)`.
- `CalcGadgetGroupBoxRect` walks the gadget chain from the window (reading `win->RPort`/`win->WScreen`) and takes the union of gadget edges — which is why a fake window handle crashed it and why gadget geometry errors surface as group-box errors.

### Memory-addressing lesson (the durable one)

- A **struct-layout ABI mismatch** (app compiled against an older NDK) shifts every embedded-field offset silently; nothing crashes, values are just wrong.
- Effective diagnosis sequence: (a) prove the app's value is *fixed* garbage (pattern-stamp the suspected memory, watch the dependent value not move); (b) derive the exact value the app read from the app's own arithmetic (H − 6); (c) **scan RAM for the big-endian encoding of that value** and see which address hits — here screen+0x8E, pinning RastPort at 0x54.
- Arithmetic slips cost a scan round: 43598 is 0xAA4E, so `font_height` = 43592 = **0xAA48** (an earlier pass searched for the wrong needle, 0xA9D0).
- `machine68k` `Memory.r_block(addr, len)` returns raw bytes for bulk scans; `get_ram_size_bytes()` bounds the scan.

### Event-loop boundary (settled, recorded)

- `WaitPort` on an empty queue raises `UnsupportedFeatureError`; both it and `VamosInternalError` hard-fail the run. Reaching the event loop with a real, registered UserPort is the milestone ceiling for in-process runs until a host input source feeds IDCMP messages.

## Latent defects and follow-ups (deliberately not fixed this session)

- **Gadget struct tail mismatch** in the repo GadTools impl: `Text` at 0x1A vs NDK 0x1C, `GadgetID` should be 0x28, `UserData` 0x2C, struct size 0x2C vs the real 0x30 [S1 Include_H/intuition/intuition.h]. Does not corrupt geometry (TopEdge/Height at 0x06/0x0A are correct) but will bite `GadgetText`-style consumers.
- **Unimplemented `? CALL`s** at the frontier (logged as `(default)` in `vamos.log`): `GT_RefreshWindow`, `IntuiTextLength`, `PrintIText`, `DrawBevelBoxA`, `SetWindowPointerA`.
- **Event loop**: needs a real host-side input source enqueuing IDCMP messages onto the window port; fabrication was ruled out by the user.

## Techniques that worked

- `grep "? CALL" artifacts/runs/<latest>/vamos.log` to list the frontier after every probe run; `artifacts/runs/<latest>/stderr.txt` for host-side errors.
- Temporary `[DBG-*]` stderr probes in impl methods: add → probe → verify → **remove before commit** (all probes from this session were removed; the committed diffs contain only real behaviour).
- Reading the app's C source (`amiga_apps/itidy1classic/source`) to know exactly what the app reads from each structure, instead of guessing from the binary.
- NDK 3.2 headers under `assets/docs/ndk/NDK3.2/Include_H/` for every struct offset, cross-checked against the app's observed arithmetic.
- Git discipline per `../workflows/branching-and-merging.md`: one branch per blocker off updated `development`, tests (`tests.test_vamos_launcher`, 5 tests) + pre-commit (`PRE_COMMIT_HOME` must point at a writable dir) before each merge, branches kept after merge.

## Session-log recovery note

The full raw session log (zstd-compressed JSONL: all user/assistant messages, reasoning, tool calls, tool results, compaction events) is stored on the agent host under the harness sessions directory for this session id and is a strict superset of this file; use it to recover exact commands or outputs. This markdown is the distilled, repo-durable version.
