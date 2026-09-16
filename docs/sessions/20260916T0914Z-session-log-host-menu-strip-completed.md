---
title: "Session log — host menu-strip completed: real MenuNumber round trip through SetMenuStrip/ItemAddress, gates green, merged"
status: log
depends_on:
  - "../architecture/hosted-application-mode.md"
  - "../workflows/branching-and-merging.md"
  - "../host-gui/translation-obligations.md"
  - "../apps/itidy/menu-strip-menupick-abi.md"
  - "20260915T0057Z-session-log-host-menu-strip-failed.md"
citations_used: []
---

# Session log — host menu-strip completed (2026-09-16)

The increment that failed on 2026-09-15 (five hours, zero code, `max-tokens`
inside one turn) is now done on the same branch, `feat/host-menu-strip`. What
followed the failed session was not more reasoning about the same open
question: the question was settled from the shipped binary first, and the
implementation was written against the settled answer.

## Session prompt

Objective carried over from the failed session: implement `SetMenuStrip`,
`ClearMenuStrip`, `ItemAddress`, and real `IDCMP_MENUPICK` delivery for iTidy's
`Project → Close`, "mirroring the address-based, real-ABI pattern already used
for the gadget-click and window-close paths", with UI functions backed by "real
Qt-backed host state, not a value that merely lets the binary proceed"
(`docs/host-gui/translation-obligations.md`). Gate: focused unit tests, both
existing interactive smoke tests still passing, a new interactive menu smoke
test observing the real round trip without fabricating any part of it, the full
suite, `pre-commit`, then merge into `development`.

## The blocking question, settled first

The open question was whether the app converts `IntuiMessage.Code` into a
`MenuNumber` before calling `ItemAddress`, or hands it over unchanged. Getting
this wrong in either direction produces a green-looking test over an encoding
the target never uses, which is exactly what `translation-obligations.md`
forbids. It was answered at byte level from the released binary, and the answer
— **unchanged; `Code` *is* the packed `MenuNumber`** — plus the disassembly, the
LVO call sites, and the derived obligations are recorded in
`docs/apps/itidy/menu-strip-menupick-abi.md`. `docs/apps/itidy/compatibility-notes.md`
gained the settled summary and a correction of an earlier wrong note (the
`move.l $22(a2)` at `0x21c66` is the menu-command dispatch, not a `HUNK_CODE`
check).

## What was done

- **`src/amiga_ui/vamos/menu_state.py` (new, Qt-free).** The classic menu ABI in
  one place: `MENUNULL` / `NOMENU` / `NOITEM` / `NOSUB`, `Menu` / `MenuItem`
  field offsets (including the `GTMENUITEM_USERDATA` slot at `MenuItem + 0x22`),
  `MenuNumber` pack/decode with 1-based fields, `resolve_menu_item_address()`
  implementing the real `NextMenu` → `FirstItem`/`NextItem` → `SubItem` walk, the
  run-wide `MenuDescriptionRegistry`, and `describe_strip()`.
- **`gadtools_library.py`.** `CreateMenusA` walks the app's flat `NewMenu`
  template (`NM_TITLE`/`NM_ITEM`/`NM_SUB`/`NM_END`, `_NM_BARLABEL` included),
  allocates real `Menu`/`MenuItem` blocks, stores `nm_UserData` at `+0x22`, and
  records the host-safe description; `LayoutMenusA` fills geometry from the
  `VisualInfo`'s font metrics; `FreeMenus` releases.
- **`intuition_library.py`.** `SetMenuStrip` records `Window.MenuStrip`
  (`+0x1C`) and projects the strip through the host projection; `ClearMenuStrip`
  detaches it; `ItemAddress` delegates to `resolve_menu_item_address` and
  returns NULL rather than inventing a handle.
- **`event_bridge.py`.** `menu_pick(window_addr, code)` posts a genuine
  `struct IntuiMessage` with `Class = IDCMP_MENUPICK`, the packed `Code`, and
  `IAddress = 0` on the window's real `UserPort`.
- **`qt_projection.py`.** A real `QMenuBar` (explicitly non-native) above the
  window's drawing surface, built from the recorded strip: nested submenus,
  separators, and only selectable entries as `QtMenuAction`s carrying
  `amiga_window_addr` / `amiga_menu_code` / `amiga_item_addr`. Activation calls
  the bridge; nothing about the label participates in the translation.
- **Library cards updated** (`intuition.library.md` "Menu Strip And Menu Picks",
  `gadtools.library.md` "Menu Creation From `NewMenu`"), including a fix of a
  stale `GT_RefreshWindow` claim ("there is no host window yet").

## Two real defects the new tests caught

1. **Endless selection walk.** The first interactive menu smoke run hung after
   delivery: `ItemAddress` was called **11,710,749** times. The app's walk is
   `while (menu_number != MENUNULL) { item = ItemAddress(strip, menu_number);
   …; menu_number = item->NextSelect; }` and reads `NextSelect` as a
   **zero-extended WORD**; our freshly created items left `mi_NextSelect` at 0,
   so the loop never terminated. Fixed by writing `NEXTSELECT_NULL` (`$FFFF`) in
   `_create_menu_item`, with two regression tests
   (`test_every_created_item_terminates_its_selection_chain`,
   `test_picked_item_terminates_the_apps_selection_walk`). After the fix the same
   run ends with `Closing iTidy main window... → cleanup complete → shutdown
   complete`, exit 0, IMsg released.
2. **A stale expectation in an existing smoke test.**
   `tests/run_host_projection_smoke_test.py` asserted the projected window must
   be "menu-bar-free" — written when no menu strip could be projected. iTidy does
   call `SetMenuStrip`, so the bar is now correct behavior. The assertion was
   inverted into a positive one that also refuses a fabricated bar: exactly one
   non-native `QMenuBar`, and every entry a `QtMenuAction` whose window address
   matches, whose `amiga_item_addr` is non-zero, and whose code decodes. Live:
   `menu bar titles: ['Project']; Amiga-backed entries: 6`.

Also fixed at the root: `tests/test_xvfb.test_build_env_sets_display_and_default_qt_platform`
was order-dependent — Qt test modules export `QT_QPA_PLATFORM=offscreen` and the
test asserting the *default* inherited it, so `unittest discover` failed while the
module alone passed. That test now clears and restores the variable itself, and the
new `tests/test_qt_menu_strip.py` restores it in `tearDownModule` instead of
leaking it. Full discovery passes with no exported `QT_QPA_PLATFORM`.

## Checks run and results

| Check | Result |
| --- | --- |
| `unittest discover` (full, clean env) | 330 tests, OK |
| `tests.test_menu_state` / `test_menu_strip_path` / `test_qt_menu_strip` / `test_event_bridge` | 17 / 19 / 19 / 28, OK |
| `tests.run_interactive_menu_smoke_test` (new) | PASS — host entry → real `IDCMP_MENUPICK` → `WaitPort` resume → app's own `ItemAddress` walk + `CloseWindow` → host window closed → clean exit |
| `tests.run_interactive_close_smoke_test`, `run_interactive_exit_smoke_test` | PASS |
| `tests.run_gadget_projection_smoke_test`, `run_host_projection_smoke_test` | PASS (the latter with the new menu-bar assertion) |
| `uv run python tests/run_gui_smoke_test.py` | PASS |
| `amiga-ui probe … --direct --timeout 5` | `app_failed`, byte-for-byte the pre-change baseline (same stdout cut-off at `iTidy main window ope…`, same log tail) — the documented honest `WaitPort`-on-empty-queue boundary in null-projection mode, not a regression |
| `ruff check src/ tests/`, `ruff format --check` | clean |
| `pyright src/amiga_ui/ tests/…` | 0 errors |
| `pre-commit` on the staged tree | ruff check / ruff format / pyright passed; check-yaml skipped (no YAML in the change) |
| `uv run python tools/check_yaml.py`, docs-metadata unit tests | OK |

Live values from the menu smoke run, for future comparisons: window `0x6b3b0`,
port `0x6B500`, picked item `0x6b364`, `Code = 0xF921` (`menu=1, item=9, sub=NOSUB`
— separators are real items and consume chain slots), IMsg `0x6B600`.

## Merge

`feat/host-menu-strip` is merged into `development` with a `--no-ff` merge; the
branch is retained (repo rule: do not delete branches after merge). No commit was
made on `main` or directly on `development`.

## Known gaps (recorded, not papered over)

- `_NM_BARLABEL` entries become real separators that consume selector slots, but
  their `_nm_SubItem` label text is not decoded — the host shows a plain
  separator. Labels containing `&` are projected with a doubled `&` because only
  the accelerator-escaping rule was implemented.
- A sub-menu parent is projected as a submenu container and is therefore not
  itself pickable; the classic case where a parent item is *also* selectable is
  not representable in Qt's widget model.
- Multi-select chaining through `mi_NextSelect` is not implemented: every created
  item terminates its chain, which is what the released binary's walk needs and
  matches how iTidy builds its strip.
- `probe --direct` still ends at the honest empty-queue `WaitPort` boundary; the
  menu path is exercised by the Xvfb-backed interactive smoke tests, not by the
  null projection.

## Next increment (deliberately deferred)

Requesters (`SetRFrontWindow` / `Request` family) and the third-level menu chains
plus `mi_MutualExclude` semantics, each from a fresh branch off the updated
`development`.
