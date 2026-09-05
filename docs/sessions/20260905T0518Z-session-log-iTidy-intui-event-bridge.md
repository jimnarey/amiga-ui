---
title: "Session log — iTidy IntuiMessage event bridge: real UserPort delivery, WaitPort peek, honest boundary"
status: log
depends_on:
  - "../apps/itidy/run-log.md"
  - "../apps/itidy/compatibility-notes.md"
  - "../architecture/translation-pipeline.md"
  - "../runtime/vamos-overview.md"
  - "../workflows/branching-and-merging.md"
citations_used:
  - S1
  - S31
  - S40
  - S41
  - S42
---

# Session log — iTidy IntuiMessage event bridge (2026-09-05)

Purpose: Durable record of the session that implemented the host→`IntuiMessage` event bridge, moving the `iTidy` probe from "stops honestly at `WaitPort` on an empty queue" to "a **real** `IntuiMessage` is delivered to the app's **real** `UserPort` and consumed through `WaitPort → GT_GetIMsg → GT_ReplyIMsg`", while keeping the empty-queue `WaitPort` failure honest (never faked).

Needed for:
- Recalling how the in-process `vamos` event loop is actually driven from the host, so the same ground is not re-derived.
- Picking up the remaining `iTidy` blockers (the five frontier `? CALL`s, graphics RastPort, text metrics) without re-diagnosis.
- Remembering the durable finding that the **compiled binary differs from the checked-in repo source** in its event handling.

Notes:
- Continues `20260903T1703Z-session-log-iTidy-gui-frontier.md`, which ended at the frontier (unimplemented `GT_RefreshWindow`, `IntuiTextLength`, `PrintIText`, `DrawBevelBoxA`, `SetWindowPointerA`) plus the event-loop boundary. Companion to `../apps/itidy/run-log.md` (run-level blockers); this file records the *session*.
- The session started from a prompt pointing at that frontier, with the **GUI/event-loop bridge** as the emphasized focus. The event loop was taken first because it is the gate that decides whether any of the drawing APIs are ever exercised by a live interaction.

## Session summary

| Item | Value |
| --- | --- |
| Harness | DeepSeek Harness (dsh), Web GUI at 127.0.0.1:3080 |
| Sandbox / approval | workspace-write / ask |
| Main work date | 2026-09-05 (UTC) |
| Work span (from repo/run evidence) | probe runs 00:13 & 00:42 UTC → event-bridge commit 05:18 UTC → merge 05:19 UTC (≈5 h, includes an idle overnight gap) |
| Model | `Qwen3.8-27B-UD-Q6_K_M` (llama-cpp, OpenAI-compatible endpoint) |
| Git baseline → end | `development` @ 566920a → fcedc6c (one feature branch, `feat/intui-message-bridge`, created, gated, merged; kept, not deleted) |
| Exact request/token counts, compactions, session id | in the raw session log on the agent host (not re-derived here) |

Milestone achieved: the probe's terminal state moved from "reaches the event loop and stops at the recorded `WaitPort`-on-empty-queue boundary" to "a host-scheduled close event becomes a **real** `struct IntuiMessage` (Class = `IDCMP_CloseWindow`), is posted on the main window's **real** `UserPort`, is found by a genuine `WaitPort` (classic peek), and is consumed and replied to by the app via `GT_GetIMsg → GT_ReplyIMsg`." The empty-queue `WaitPort` failure is preserved as honest behavior, per the design rule recorded in `../architecture/translation-pipeline.md`.

## What changed in the repo (in order)

| Commit | Branch (kept) | Change |
| --- | --- | --- |
| 726c178, merged fcedc6c | `feat/intui-message-bridge` | The bridge itself: `src/amiga_ui/vamos/event_bridge.py` (new, host source of real `IntuiMessage`s); `src/amiga_ui/vamos/exec_library.py` (new, `RepoExecLibrary` with classic **peek** `WaitPort`); `GT_GetIMsg`/`GT_ReplyIMsg` in `gadtools_library.py`; `on_window_opened` hook in `intuition_library.py`; `event_bridge` plumbing in `launcher.py`; `tests/test_event_bridge.py` (new, 15 tests); docs (`intuition.library.md` card, `run-log.md` entry) |

## Blocker narrative (what actually happened)

### 1. The frontier, and why the event loop went first

The prior log closed on five unimplemented `? CALL`s (`GT_RefreshWindow`, `IntuiTextLength`, `PrintIText`, `DrawBevelBoxA`, `SetWindowPointerA`) plus the event-loop boundary. The event loop was implemented first because it is the gate: none of the drawing/text APIs matter for a *live* interaction until an IDCMP message can actually reach the app and be consumed.

### 2. The bridge: real message, real port, classic `WaitPort`

The core of the work was making the sanctioned path execute with **real** semantics:

- **`struct IntuiMessage`** blocks are allocated in 68k memory and filled field-by-field exactly as NDK 3.2 `intuition.h` declares them (0x30 bytes) [S1 Include_H/intuition/intuition.h]. A host-scheduled event (close/refresh/gadgetup) is posted onto the window's **real** `UserPort` — the genuine queue-backed MsgPort that `OpenWindowTagList` now registers. Delivery is filtered by the window's `IDCMPFlags` (real Intuition never generates a class a window did not request, so the 1×1 `WFLG_BACKDROP` utility window `iTidy` opens first is naturally excluded).
- **`WaitPort` was the subtle part.** vamos' built-in `WaitPort` has `GetMsg` (pop) semantics — it *removes* the first message. Classic AmigaOS `WaitPort` is a **peek**: it returns the first queued message **without removing it**; only `GetMsg` removes [S41 §FUNCTION] [S40 §FUNCTION]. `RepoExecLibrary` overrides it to the classic contract (via a `PeekPortManager.peek_msg`). Empty queue still raises `UnsupportedFeatureError`; invalid port still raises `VamosInternalError`. It never invents a message.
- **`GT_GetIMsg`** (GadTools) is the classic `GetMsg` on the `UserPort` [S42 item GT_GetIMsg]; **`GT_ReplyIMsg`** releases the bridge-allocated block [S42 item GT_ReplyIMsg].

The end-to-end path is proven by an in-process `iTidy` test: a scheduled close event is posted to the real `UserPort`, the app's `WaitPort` honestly peeks it, `GT_GetIMsg` pops it, `GT_ReplyIMsg` replies — and the test cross-links the bridge's posted `imsg` address to the one `WaitPort` logged as found.

### 3. The close event did not exit — root cause: binary ≠ source, plus a pre-loop drain

The first integration test asserted a *clean exit* and failed. The investigation (the session's main effort) resolved it:

- The posted message is byte-perfect at reply time (Class=`0x200`, correct Window/ReplyMsg) and lands on the correct port; the app retrieves and replies to it. So the **bridge is correct**.
- The app then `WaitPort`s the **now-empty** queue and fails honestly. It does not stop on the close.
- **Decisive differential experiment:** scheduling a `REFRESHWINDOW` event instead, the app consumed it but made **no** refresh-handling calls (`GT_BeginRefresh`/`DrawBevelBoxA` appear only at setup, *before* `WaitPort` #1). So the loop between the two `WaitPort`s is a `while ((msg = GT_GetIMsg(...))) { GT_ReplyIMsg(msg); }` **drain that discards the message without switching on `Class`** — confirmed by instrumenting `GT_GetIMsg` with a stderr counter: exactly two calls (`msg`, then `NULL`).
- **The compiled binary differs from the repo source.** The binary performs a double `WaitPort(0x06b330)` immediately after the 2nd `SetWindowPointerA` (from `safe_set_window_pointer(FALSE)` in `open_itidy_main_window` [S31]), but the checked-in source has no `WaitPort` there. The repo source is **not** authoritative for the binary's behavior.

Conclusion: the app consumes the delivered event in a pre-loop drain (a target-binary behavior, not a bridge defect), then hits the honest empty-queue boundary. The integration test was rewritten to assert **delivery + consumption** (the bridge's guaranteed contract), not a clean exit.

## Key technical findings

### `struct IntuiMessage` layout (NDK 3.2, verified)

`0x30` bytes: `ReplyMsg@0x00`, `Node@0x04`, `Class@0x10`, `Code@0x14`, `Qualifier@0x16`, `IAddress@0x18`, `MouseX@0x1C`, **`MouseY@0x1E`** (consecutive words, *no* overlap — an earlier `0x1D` "overlap" theory was wrong), `Seconds@0x20`, `Micros@0x24`, `IDCMPWindow@0x28`, `SpecialLink@0x2C` [S1 Include_H/intuition/intuition.h]. IDCMP flags: `REFRESHWINDOW 0x4`, `GADGETUP 0x40`, `MENUPICK 0x100`, `CLOSEWINDOW 0x200`; the main window requests `0x344`.

### The `WaitPort`/`GetMsg` split is load-bearing

The app's event loop is `WaitPort(); while ((msg = GT_GetIMsg(...)))`. With pop-semantics `WaitPort` the message the loop expects would already be consumed by `WaitPort` itself and the loop would see an empty queue. Restoring the peek is what makes the classic loop work at all [S41 §FUNCTION] [S40 §FUNCTION].

### Binary ≠ repo source (the durable finding)

Do **not** trust `amiga_apps/itidy1classic/source` for the running binary's exact behavior. The binary was built `vbcc +aos68k -c99 -cpu=68000 -O2 -size -DENABLE_CONSOLE` against the Workbench 3.2 SDK (banner "compiled: Jan 12 2026"); `-O2` register allocation defeats raw instruction-pattern search in the binary, so the **vamos timeline + differential event experiments** are the reliable evidence, not opcode matching.

### vamos logging: what does and does not appear

`vamos.log` records explicit log lines + `? CALL` stub warnings. **Implemented** library calls log only when their logger is at the enabled level; the probe uses `-l dos:info,exec:info`, so `gadtools` calls (`GT_GetIMsg`/`GT_ReplyIMsg`) do **not** appear even though they run. The `? CALL` lines are for *unimplemented* functions only. Don't read the absence of `GT_GetIMsg` in the log as "not called."

### The honest boundary is a feature, not a bug

`WaitPort` on an empty queue raising `UnsupportedFeatureError` is the intended signal that the app has reached a genuine interactive boundary. The compatibility fix belongs on the **producer** side (host/test input → Amiga-shaped IDCMP traffic), never by making an empty wait succeed. This is now recorded in `../architecture/translation-pipeline.md` and the `intuition.library` card.

## Latent defects and follow-ups (not fixed this session)

- **The five frontier `? CALL`s** the session was pointed at — `GT_RefreshWindow` (PC `025876`), `IntuiTextLength` (bias 330), `PrintIText` (bias 216), `DrawBevelBoxA` (PC `0277b2`), `SetWindowPointerA` (bias 570; PC `030740`/`030764`) — remain unimplemented. `SetWindowPointerA` is version-gated in the source (`prefsWorkbench.workbenchVersion >= 39`; stdout shows "SysBase version 40 - OK").
- **`graphics.library` RastPort** (`fix/graphics-rastport`): `Move`/`Draw`/`RectFill`/`SetAPen`/`SetBPen`/`SetDrMd` lack the `ctx` argument (so they are dropped → `UNKNOWN`) and there is no host software framebuffer.
- **Gadget struct tail mismatch** (carried from the prior session, established): the repo's `struct Gadget` is 8 bytes too small — `Text` at `0x1A` (NDK `0x1C`), `GadgetID` at `0x24` (NDK `0x28`), `UserData` at `0x28` (NDK `0x2C`), size `0x2C` (real `0x30`) [S1 Include_H/intuition/intuition.h].
- **`GadgetID` offset for `GADGETUP` resolution** is still unresolved (the repo and NDK disagree on which offset the gadget id is read at); pin it down before integration-testing `GADGETUP` events.
- The target binary's **pre-loop drain** means a delivered close event is not guaranteed to produce a clean process exit; that is a target limitation, documented, not a bridge defect.

## Techniques that worked

- **Differential event experiment** to separate hypotheses: post a `REFRESHWINDOW` (which, if the app were in its real loop and reading `Class`, would trigger visible `GT_BeginRefresh`/`DrawBevelBoxA` calls) versus a `CLOSEWINDOW`. The absence of refresh-handling calls after `WaitPort` #1 pinned the "pre-loop drain" hypothesis.
- **Instrumenting `GT_GetIMsg` with a stderr counter that counts *all* calls (including the `NULL`-terminating one):** exactly two calls (`msg` then `NULL`) = a `while ((msg = GetMsg(...)))` loop, not a one-shot. Add → probe → verify → **remove before commit** (all probes were removed; the committed diffs contain only real behavior).
- **Capturing app stdout via a real file** (`tempfile.NamedTemporaryFile("w+")`): the dos `FileManager` wraps `sys.stdout.buffer`, which `StringIO` lacks.
- **Copying the `vamos -L` log immediately** after a run: the file vanishes on cleanup/rotation.
- Git discipline per `../workflows/branching-and-merging.md`: one branch per blocker off updated `development`, narrow tests (`tests.test_event_bridge` + `tests.test_vamos_launcher`, 20 OK) + `amiga-ui check` + `tests/run_gui_smoke_test.py` (Xvfb) + pre-commit (`PRE_COMMIT_HOME` pointed at a writable dir) before the merge; branch kept.

## Session-log recovery note

The full raw session log (zstd-compressed JSONL: all user/assistant messages, reasoning, tool calls, tool results, compaction events) is stored on the agent host under the harness sessions directory for this session id and is a strict superset of this file; use it to recover exact commands, outputs, and the exact session-creation time and request/token counts (which this markdown does not re-derive). This markdown is the distilled, repo-durable version.
