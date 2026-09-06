---
title: "Session log — iTidy graphics `TextLength`: real label-width measurement from the RastPort font"
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

## What changed

Branch `feat/graphics-textlength` (from `development`), one blocker:

- `src/amiga_ui/vamos/graphics_library.py` — added `TextLength(ctx, rp, string,
  count)`. It reads `RastPort.TxWidth` from 68k memory at `RastPort+0x3C` (the
  classic pre-`RasInfo` offset the target was compiled against, matching
  `intuition_library._RP_OFF_TXWIDTH` where the Topaz width is written) and returns
  `count * TxWidth` for the fixed-pitch font. A read that is not a plausible
  fixed-pitch width (band `1..32`) falls back to the Topaz baseline (`6`), so an
  unpopulated or mis-offset RastPort degrades to the correct width instead of a
  garbage pointer. Each measurement is recorded on the host-side `RastPortState`.
- `src/amiga_ui/vamos/rastport_state.py` — added `record_text_length(string,
  count, length)` so the ordered RastPort op log captures what was measured and the
  width the library reported (inspectable by a future renderer/probe).
- `tests/test_graphics_library.py` — a `GraphicsLibraryTextLengthTest` class (7
  cases: uses the RastPort font width, uses a different width, unpopulated
  fallback, implausible-width fallback, zero-count, no-`mem` context, and
  measurement recording) plus a scanner guard that `TextLength` is a wired `.fd`
  trap.
- Docs: `docs/apps/itidy/run-log.md` (new entry),
  `docs/apps/itidy/compatibility-notes.md` (RastPort-offset bullet now notes
  `TextLength` consumes `TxWidth@+0x3C` and has the bounded fallback),
  `docs/platform/library-cards/graphics.library.md` (text-metrics status updated).
- Regenerated `assets/generated/api-index.md`/`.json`: `TextLength` is now `valid`
  and graphics.library shows `38 / 176` implemented. (The checked-in index was
  stale from before the RastPort drawing-state fix.)

## Why `TextLength` first

The post-RastPort-drawing probe (`artifacts/runs/20260905T232639Z-probe-iTidy`)
draws all three group boxes, then the first unimplemented call is `TextLength`
(bias 54), logged four times as `? CALL ... -> d0=0 (default)`: counts 6/3/9 for
`"Order:"`/`"By:"`/`"Position:"` and 4 for `"Max:"` — the label-width
measurements in `main_window.c` L644-L646 and the `Max:` progress label [S31
L644-L646]. It is the smallest and most foundational frontier API: a pure
measurement (no host window needed), its return value feeds real gadget layout, and
the Intuition `IntuiTextLength` conceptually builds on it. Implementing it with a
genuine width computation (not `return 0`) satisfies "no empty success stubs."

## Verification (what was actually run)

- `uv run python -m unittest tests.test_graphics_library -v` — 26 tests OK (18
  pre-existing + 8 new).
- `uv run python -m unittest discover -s tests -t .` — 71 tests OK.
- `uv run amiga-ui probe amiga_apps/itidy1classic/binary/extracted/iTidy` —
  `artifacts/runs/20260906T000103Z-probe-iTidy`: the four `TextLength` traps are
  now hooked (no longer `? CALL ... -> d0=0`); the app still ends at the honest
  `WaitPort`-on-empty-queue `UnsupportedFeatureError` (no regression).
- `uv run python tools/analyze_target_failure.py --latest` — `TextLength` no longer
  listed among defaulted calls; remaining graphics frontier is `Text` (bias 60).
- `uv run pre-commit run --files <changed files>` — ruff check, ruff format,
  pyright all pass.
- `uv run python tests/run_gui_smoke_test.py` — Qt window created under Xvfb (host
  smoke gate, unaffected but green).

## Uncertain / open

- **RastPort `TxWidth@+0x3C` offset still unconfirmed against the binary.** The
  value is read from where `intuition_library` writes it, and the app demonstrably
  reads `TxHeight` from the same `+0x3A` convention and gets usable values, so the
  result is correct for the repo's font either way (the bounded fallback also
  returns `6`). But if the true offset differs, `TextLength` would still return the
  correct Topaz width via the fallback — the offset question is now lower-risk for
  `TextLength` specifically, yet still the real ABI risk for the broader RastPort
  model. See `docs/apps/itidy/compatibility-notes.md`.
- **Fixed-pitch assumption.** `TextLength` returns `count * TxWidth`, which is exact
  for the monospace Topaz disk font the repo installs. A proportional font would
  need per-character width summation from the font's glyph data; that is deferred
  (no proportional font is in the target's default path) and documented.

## Next recommended blocker

`graphics.library` `Text` (bias 60) — the actual text **draw** call
(`Text(rp, "Max:", 4)` at PC `0279ce`). It should record a text-draw op on the
RastPort model (string pointer, count, pen, current pen position) rather than a
no-op, mirroring how the drawing calls record state. Start from a fresh branch off
the updated `development`. After that, the Intuition text pair (`IntuiTextLength`
bias 330 / `PrintIText` bias 216) and the GadTools `DrawBevelBoxA` /
`GT_RefreshWindow` pair remain the drawing frontier.
