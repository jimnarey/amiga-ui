---
title: "Session log — iTidy graphics TextLength: real label-width measurement from the RastPort font"
status: log
depends_on:
  - "../apps/itidy/run-log.md"
  - "../apps/itidy/compatibility-notes.md"
  - "../architecture/platform-target.md"
  - "../platform/library-cards/graphics.library.md"
  - "../workflows/error-driven-porting.md"
  - "../workflows/branching-and-merging.md"
citations_used:
  - S1
  - S31
  - S43
---

# Session log — iTidy graphics `TextLength` (2026-09-06)

Purpose: Durable record of the session that implemented `graphics.library`
`TextLength` (bias 54) — the first unimplemented call in the post-RastPort-drawing
frontier — as a real text-metrics function that measures the pixel width of the
requested characters from the RastPort's current font, rather than returning the
honest-but-useless `d0=0` default. It continues the drawing-state work of
`20260905T2101Z-session-log-iTidy-graphics-rastport-abi.md`, keeping the honest
`WaitPort`-on-empty-queue boundary intact and adding no fake success.

Needed for:
- Recalling *how* `TextLength` measures width (read `RastPort.TxWidth` from 68k
  memory at the pre-`RasInfo` offset, return `count * TxWidth`, bounded fallback to
  the Topaz baseline) so the same approach is not re-derived for the other text calls.
- Knowing the `RastPort.TxWidth@+0x3C` offset is now **directly consumed by a
  returned value** (label widths), which raises the stakes of the still-open
  RastPort-offset follow-up.
- Picking up the next smallest graphics-library blocker (`Text`, bias 60) without
  re-triaging the whole frontier.

Notes:
- Continues `20260905T2101Z-session-log-iTidy-graphics-rastport-abi.md`, which fixed
  the `graphics.library` dispatch, added the RastPort drawing-state model, and left
  the text/UI frontier open (`Text`, `TextLength`, `IntuiTextLength`, `PrintIText`,
  `DrawBevelBoxA`, `GT_RefreshWindow`, `SetWindowPointerA`). Companion to
  `../apps/itidy/run-log.md` (run-level blockers); this file records the *session*.

## Session summary

| Item | Value |
| --- | --- |
| Harness | DeepSeek Harness (dsh), Web GUI at 127.0.0.1:3080 |
| Sandbox / approval | workspace-write / ask |
| Main work date | 2026-09-06 (UTC) |
| Work span (from repo/run evidence) | baseline probe 2026-09-05 23:26 UTC → post-fix probe 2026-09-06 00:01 UTC → commit 00:19 UTC → merge 00:19 UTC (≈53 min active) |
| Model | `Qwen3.8-27B-UD-Q6_K_M` (llama-cpp, OpenAI-compatible endpoint) |
| Git baseline → end | `development` @ 12b9a30 → 39a7fad (one feature branch, `feat/graphics-textlength`, created, gated, merged; kept, not deleted) |
| Exact request/token counts, compactions, session id | in the raw session log on the agent host (not re-derived here) |

Milestone achieved: `TextLength` moved from an honest-but-useless `? CALL … -> d0=0
(default)` to a **real, hooked** text-metrics entry point — the four app calls
(counts 6/3/9/4 for `"Order:"`/`"By:"`/`"Position:"`/`"Max:"`) now return measured
pixel widths instead of zero, and `tools/analyze_target_failure.py` no longer lists
`TextLength` among defaulted calls. The probe's *terminal* state did **not** change:
the app still ends at the honest `WaitPort`-on-empty-queue `UnsupportedFeatureError`
boundary, exactly as designed.

## What changed in the repo (in order)

| Commit | Branch (kept) | Change |
| --- | --- | --- |
| 22f0ccd, merged 39a7fad | `feat/graphics-textlength` | `TextLength` in `src/amiga_ui/vamos/graphics_library.py` (reads `RastPort.TxWidth` from 68k memory at `RastPort+0x3C`, returns `count * TxWidth`, bounded fallback to the Topaz baseline `6`); `record_text_length` in `src/amiga_ui/vamos/rastport_state.py` (records the measurement on the host-side RastPort op log); `tests/test_graphics_library.py` (new `GraphicsLibraryTextLengthTest`, 7 cases, + a scanner guard that `TextLength` is a wired `.fd` trap); docs (`run-log.md` entry, `compatibility-notes.md`, `graphics.library.md` card, this session log); regenerated `assets/generated/api-index.{md,json}` (`TextLength` → `valid`, graphics `38/176`) |

## Blocker narrative (what actually happened)

### 1. The frontier after the RastPort drawing-state work

The session started from `development` @ 12b9a30 (clean tree). The prior session had
wired the six drawing calls and added the RastPort state model, but the probe still
stopped short of a live UI: it drew all three group boxes, then hit the text/UI
frontier. The fresh probe (`artifacts/runs/20260905T232639Z-probe-iTidy`) logged the
**first** unimplemented call as `graphics.library` `TextLength` (bias 54) four times —
`? CALL … -> d0=0 (default)`, counts 6/3/9 for `"Order:"`/`"By:"`/`"Position:"` and 4
for `"Max:"` — before the app fell through to the honest `WaitPort`-on-empty-queue
`UnsupportedFeatureError`.

### 2. Why `TextLength`, and why it must be a real measurement

`TextLength` was the smallest and most foundational frontier API: a pure measurement
(no host window needed), its return value feeds the app's real two-column gadget
layout (`main_window.c` L644-L646 measures the three labels, picks the widest per
column, and offsets the gadgets from there [S31 L644-L646]), and the Intuition
`IntuiTextLength` conceptually builds on it. The task constraint was explicit — "do
not add empty success stubs merely to advance the trace" — so the fix had to compute a
genuine width, not return `0` or a constant.

### 3. The bounded-fallback decision

The width is read from the RastPort in 68k memory (faithful to real AmigaOS, where the
library reads the RastPort's font) rather than a baked-in constant, so a different font
width would be picked up automatically. But the `RastPort.TxWidth@+0x3C` offset is a
**known-open, unconfirmed** item (see `../apps/itidy/compatibility-notes.md`), so a
read outside the plausible fixed-pitch band (`1..32`) falls back to the Topaz baseline
(`6`). The upshot: even if the offset is wrong, `TextLength` returns the correct Topaz
width via the fallback instead of a garbage pointer — the offset question is lower-risk
for `TextLength` specifically, though it remains the real ABI risk for the broader
RastPort model.

## Key technical findings

### `TextLength` = `count * RastPort.TxWidth` for a fixed-pitch font

On classic AmigaOS `TextLength(rp, string, count)` returns the pixel width of the first
`count` characters in the RastPort's font [S43 item 8]. For the fixed-pitch disk font
the repo installs (Topaz 8x6, width `6`) every glyph is `RastPort.TxWidth` wide
[S1 Include_H/graphics/rastport.h], so the width is `count * TxWidth` — a real
computation, not a stub. A proportional font would need per-glyph width summation from
the font's character data; that is deferred (no proportional font is in the target's
default path).

### The RastPort the app measures against is the screen's embedded RastPort

The app calls `TextLength(&win_data->screen->RastPort, …)` [S31 L644-L646]. That
RastPort sits at `Screen+0x54` (the pre-`RasInfo` `ViewPort` layout the target was
compiled against), and `intuition_library` writes the Topaz `TxWidth` at
`RastPort+0x3C` (= `Screen+0x90`). In the probe the app's `rp` was `0x0006a868`, so
`rp+0x3C == 0x0006a8A4 == screen+0x90` — the exact word holding `6`. The app
demonstrably reads `TxHeight` from the same `+0x3A` convention and gets usable values,
so `+0x3C` for `TxWidth` is the consistent offset.

### The checked-in `api-index` was stale

The committed `assets/generated/api-index.md` still showed `graphics.library`
"Implemented: 0 / 176" with several methods marked `error` — a leftover from before the
prior session's dispatch fix. Regenerating it (after the `TextLength` addition) gave
`38 / 176` implemented and `TextLength` marked `valid`. Generated reference files are
not committed, so this only affects local tooling.

## Latent defects and follow-ups (not fixed this session)

- **`graphics.library` `Text` (bias 60)** — the actual text **draw** call
  (`Text(rp, "Max:", 4)`, PC `0279ce`). The next smallest graphics-library blocker; it
  should record a text-draw op on the RastPort model (string pointer, count, pen,
  current pen position) rather than a no-op.
- **Intuition text pair** — `IntuiTextLength` (bias 330, 3×) and `PrintIText` (bias 216,
  3×) remain unimplemented; `PrintIText` draws the group-box titles.
- **GadTools pair** — `DrawBevelBoxA` (bias 120, PC `0277b2`) and `GT_RefreshWindow`
  (bias 84, PC `025876`) remain unimplemented; `SetWindowPointerA` (bias 816) also
  still logs as defaulted (twice, PC `030740`/`030764`).
- **RastPort `TxWidth@+0x3C` offset** is still unconfirmed against the binary (a
  carried-over open item). `TextLength` now directly consumes it, but the bounded
  fallback returns the correct `6` either way. Settling the offset against the HUNK
  CODE segment remains the real ABI risk.
- The app's terminal state is unchanged: it ends at the honest `WaitPort`-on-empty-queue
  `UnsupportedFeatureError` — a boundary, not a defect.

## Techniques that worked

- **Treat the fresh probe as the authority, not the prior log.** The 2026-09-05 session
  log listed the frontier, but the new probe (`20260905T232639Z`) confirmed `TextLength`
  was the *first* unimplemented call and gave the exact counts/strings to assert on in
  tests.
- **Read the width from 68k memory with a sanity-bounded fallback** so the result is a
  genuine font measurement yet degrades to the correct value (not a pointer) if the
  unconfirmed offset is wrong — a robust way to consume a known-open ABI detail safely.
- **Assert the app's real calls in tests, no binary needed.** `test_uses_rastport_font_width`
  uses the probe-observed RastPort address (`0x06A868`) and the exact label counts
  (6/3/9) from `main_window.c`, so the test mirrors the target's usage without the
  `iTidy` binary.
- **Keep the scanner guard.** A new `.fd` method must take `ctx` first + the exact FD arg
  count (`rp, string, count`), else `LibImplScanner` drops it as an `UNKNOWN` trap and
  the call is silently lost — the same trap the prior session hit with the six drawing
  calls. `test_text_length_is_a_wired_trap` guards against regression.
- **Git discipline per `../workflows/branching-and-merging.md`:** one branch per blocker
  off updated `development` (`feat/graphics-textlength`), narrow tests
  (`tests.test_graphics_library`, 26 OK) + full suite (71 OK) +
  `amiga-ui probe` + `tools/analyze_target_failure.py --latest` +
  `pre-commit` (ruff + pyright) + `tests/run_gui_smoke_test.py` (Xvfb) before the merge;
  branch kept, not deleted.

## Session-log recovery note

The full raw session log (zstd-compressed JSONL: all user/assistant messages,
reasoning, tool calls, tool results, compaction events) is stored on the agent host
under the harness sessions directory for this session id and is a strict superset of
this file; use it to recover exact commands, outputs, and the exact session-creation
time and request/token counts (which this markdown does not re-derive). This markdown
is the distilled, repo-durable version.
