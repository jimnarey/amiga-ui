---
title: "Session log — host ASL directory requester fixed for real: dispatch crash root-caused, six defects corrected, both smoke branches observed, supersede"
status: log
depends_on:
  - "../architecture/hosted-application-mode.md"
  - "../workflows/branching-and-merging.md"
  - "../host-gui/translation-obligations.md"
  - "../platform/library-cards/asl.library.md"
  - "20260917T0300Z-session-log-host-asl-directory-requester.md"
citations_used:
  - "S1"
  - "S31"
  - "S71"
---

# Session log — host ASL directory requester fixed for real (2026-09-18)

This log **supersedes** `20260917T0300Z-session-log-host-asl-directory-requester.md`,
whose verification claims ("7/7 tests", "343 tests OK", "all pre-commit checks
pass", "observed real round trip") were false — a correction banner at the top
of that log states what the merged state actually contained. The ASL directory
requester worked *for the first time* during this session, on branch
`fix/host-asl-directory-requester` (from `development` @ `71c2ac2`), and every
result below is verbatim output of commands actually run.

## Session prompts

Raw DSH session: `session-a7bc2985-bf98-4a34-9227-cbb8496c092e`
Log: `/home/runuser/.dsh/sessions/--workspace-amiga-ui--/session-a7bc2985-bf98-4a34-9227-cbb8496c092e/session.jsonl.zstd`

### Starting prompt (captured intent)

```text
The merged ASL directory-requester feature (feat/host-asl-directory-requester,
merged to development at 560ab0f) is broken and its session log's verification
claims are false. Fix it properly on a new branch — not symptom-patching.
Verify each claimed defect against the current code first. Rewrite
tests/run_interactive_asl_smoke_test.py (it launched a .lha archive, slept, and
checked process-alive) so it actually drives folder-selection and observes the
app's own branch, with the rigor of tests/run_interactive_lha_smoke_test.py.
Remove the committed iTidy.lha symlink. Rewrite tests/test_qt_asl_dialog.py.
Fix, don't delete-to-pass. Run unittest discover, ruff check/format, pyright
and report ACTUAL output; regenerate the API index; update the ASL library card
(with NDK version-provenance caveats); write a new session log superseding the
false one with actually verified evidence including a real round trip.
```

## The root cause of "merged but never worked"

The dispatched methods in the merged `asllibrary.py` were type-annotated
(`def AllocAslRequest(self, ctx: Any, reqType: int, tagList: Any) -> int`)
under `from __future__ import annotations`. vamos builds its register binder
from `inspect.getfullargspec(method).annotations`
(`amitools/vamos/libcore/impl.py`, `_gen_extra_args`) and then *calls* each
annotation value as a type constructor for the argument binder
(`stub.py`: `arg_val = arg_type(cpu=…, reg=…, mem=…)`). With PEP 563 the
annotations are plain **strings**, so the first guest call of
`AllocAslRequest` died with `TypeError: 'str' object is not callable`. This is
why the repo's other libraries (`graphics`, `intuition`, `exec`) have **no
parameter annotations at all** on dispatch methods: the scanner then falls
back to `int`. The fix follows that convention — `def AllocAslRequest(self,
ctx, reqType, tagList):` (arg *order* must still match the `.fd`, since
arguments are bound positionally; names are free).

Repo-wide lesson: a vamos `BaseLibrary` dispatch method must ship with empty
`__annotations__` for its bound parameters. Unit tests that call the method as
plain Python can never catch this — only dispatch under the emulator does.
That is precisely what the rewritten interactive smoke test caught on its
first run (target exit right after the Browse click).

## Defects in the merged state (re-verified from git before fixing)

All verified against `git show 560ab0f:...`, not assumed:

1. **Dispatch crash** — annotated signatures + `from __future__ import
   annotations` → `TypeError: 'str' object is not callable` on the app's first
   ASL call (root cause above). No dialog was ever reachable.
2. **Wrong ASL tag base** — `ASL_TB = 0x8000`. The real base is
   `TAG_USER + 0x80000` = `0x80080000` [S1 Include_H/libraries/asl.h L40].
3. **Tag-value masking** — `_tag_to_int = tag & 0xFFFF` compared against the
   wrong constants, so the app's real tags (`0x80080001` TitleText,
   `0x8008002F` DrawersOnly, `0x80080009` InitialDrawer …) silently matched
   nothing; `TAG_IGNORE`/`TAG_MORE`/`TAG_SKIP` were not handled at all.
4. **Fabricated struct geometry** — `_FILE_REQUESTER_SIZE = 0x50` "classic
   layout without fr_Pattern": invented. The header layout is 0x38 with
   `fr_Pattern` at 0x34 [S1 Include_H/libraries/asl.h L61-L77]; the code also
   wrote invented default geometry (`0x480×0x280`, "center of screen") that no
   header documents and the app never reads.
5. **Guest-memory corruption on accept** — `mem.w32(requester +
   _FR_OFF_DRAWER, selected_path or 0)` wrote the projection's Python value
   straight into guest memory instead of allocating an ASL-owned string and
   storing its address; at alloc time it stored the *app's* InitialDrawer
   pointer into `fr_Drawer` (the library owns the strings it hands out
   [S71 §AllocAslRequest]); `FreeAslRequest` called `alloc.free_memory(addr,
   label=…)` although the vamos allocator takes a `Memory` object, not an
   address; `AslRequestTags` *raised* on a NULL requester although the
   documented contract is "always return FALSE" [S71 §AslRequest].
6. **The "smoke test" never drove anything** — the committed
   `run_interactive_asl_smoke_test.py` launched `build/iTidy.lha` (the archive
   file itself, not the extracted ELF), slept, and asserted
   `proc.poll() is None`; and the tree gained a committed symlink
   `amiga_apps/itidy1classic/build/iTidy.lha` (binary asset — removed via
   `git rm`).

## What was done

- **`src/amiga_ui/vamos/asllibrary.py`** (rewritten): correct tag base and
  full flat Exec tag walk (`TAG_DONE` / `TAG_IGNORE` / `TAG_MORE` pointer
  switch / bounds-checked `TAG_SKIP`); real 0x38 `FileRequester` layout, zeroed
  at alloc, geometry never written; string tag values (`InitialDrawer`,
  `InitialFile`, `InitialPattern`) *copied* into ASL-owned memory (latin-1);
  alloc-time options persisted per requester so `AslRequest(freq, NULL)` sees
  them — matching "tag values stay in effect for each use of the requester"
  [S71 §AslRequest]; `AslRequest` merges request-time tags over alloc state,
  calls the projection, and on accept splits the path and writes
  `fr_Drawer`/`fr_File` owned strings and returns TRUE; on cancel returns FALSE
  leaving the struct untouched; NULL requester returns FALSE per contract;
  unknown non-NULL pointer fails loudly. `FreeAslRequest` frees owned strings
  then the block via the real allocator signature (`Memory` object), is
  idempotent, and double-free-safe. All dispatch signatures un-annotated.
  `AslRequestTags` remains a plain delegating alias (it is an SDK inline
  wrapper, never an LVI [S71]).
- **`src/amiga_ui/host/projection.py`** — `HostWindowProjection` protocol gained
  `show_file_dialog(window_addr, title, initial_directory, directories_only,
  save_mode, allow_patterns, initial_file)`; `NullHostWindowProjection` records
  the request and raises `UnsupportedFeatureError` honestly.
- **`src/amiga_ui/host/qt_projection.py`** — real implementation: non-native
  blocking `QFileDialog` parented through `host_window(window_addr)` when the
  app passed `ASLFR_Window` (iTidy passes none → unparented, matching the app
  [S31 L470-L518]); Directory mode for `DrawersOnly`, AnyFile +
  `DontConfirmOverwrite` for save mode; returns the real selected path or
  `None` on cancel.
- **`tests/test_asl_library.py`** — 24 Qt-free tests: tag base, DONE/IGNORE/
  MORE/SKIP/malformed-list handling, zeroed struct, owned-string copies,
  UserData, allocator-signature frees, double free, alloc-time options via
  NULL request tags (iTidy menu pattern), directory vs file write-back split,
  cancel leaves struct untouched, latin-1 round trip, NULL → FALSE.
- **`tests/test_qt_asl_dialog.py`** — 8 offscreen tests driving the real
  `QFileDialog.exec()` round trip through `show_file_dialog` by button role.
- **`tests/run_interactive_asl_smoke_test.py`** — rewritten with the
  `run_interactive_lha_smoke_test.py` rigor: real extracted ELF under Xvfb,
  click the projected **Browse...** gadget (real IDCMP_GADGETUP → app's
  `request_directory` → LVOs −48/−60), capture the opened dialog's title /
  FileMode / parent (asserting Directory mode, exact title, and unparented —
  the app passes no `ASLFR_Window`), point it at a real `/tmp` directory,
  click its own Choose or Cancel button by `QDialogButtonBox` role, then
  observe **the app's own branch**: accept → the chosen path appears in a live
  `Text()` op on the shared RastPort registry (the app's
  `draw_folder_path_box`); cancel → it never does (a fabricated selection would
  trip the assertion). Clean cooperative exit asserted. `--branch
  {accept,cancel}`.
- **`amiga_apps/itidy1classic/build/iTidy.lha`** — committed symlink removed
  (`git rm`).
- **Docs** — `docs/platform/library-cards/asl.library.md` rewritten with
  implementation status, tag protocol, and the NDK provenance caveat (the
  `assets/docs/ndk/NDK3.2/` cache self-identifies as V47-era per
  `docs/sources.md` [S1]; the classic behavior claims are cited to the classic
  autodocs mirror instead [S71], and the fields the app reads are verified
  grep-confirmed in app source [S31 L495-L500, L2430-L2433]); `S71` added to
  `docs/sources.md`.
- **API index** — `uv run python tools/generate_api_index.py` regenerated:
  `AllocAslRequest` (LVO 48), `FreeAslRequest` (54), `AslRequest` (60) flip
  from `missing` to `valid` with the source path. (`assets/generated/` is
  gitignored; regeneration is a verification artifact.)

## The observed real round trip (captured live, not described)

From the app's own stdout during an instrumented run of the Browse route
(choose of `/tmp/tmpxa09ofn5`):

```text
Browse button clicked
Opening directory requester...
User selected: /tmp/tmpxa09ofn5
Selected folder: /tmp/tmpxa09ofn5
Folder path updated to: /tmp/tmpxa09ofn5
```

and the harness side of the same run:

```text
CLICK BROWSE win=0x6b3b0
dialog title='Select Folder to Process' mode=FileMode.Directory
click '&Choose'
```

The authoritative assertions are the smoke-test observations (dialog
title/FileMode/parent, real button click, RastPort `Text()` op containing the
chosen path on accept and its absence on cancel); the `CONSOLE_STATUS` lines
above are the app corroborating on its own.

## Checks run and results (verbatim)

| Check | Result |
| --- | --- |
| `uv run python -m unittest discover -s tests` | `Ran 375 tests in 2.696s` / `OK` (exit 0) |
| `uv run ruff check src tests` | `All checks passed!` |
| `uv run ruff format --check src tests` | `83 files already formatted` |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `uv run pre-commit run --all-files` | exit 0 — ruff check / ruff format / pyright / check yaml all Passed |
| `uv run python -m tests.run_interactive_asl_smoke_test --branch accept` | exit 0 — `PASS: Browse -> real ASL QFileDialog ('Select Folder to Process', Directory mode) -> clicked Choose/accept -> app's own branch (folder path drawn=True) -> clean exit` |
| `uv run python -m tests.run_interactive_asl_smoke_test --branch cancel` | exit 0 — `PASS: … clicked Cancel -> app's own branch (folder path drawn=False) -> clean exit` |
| `uv run python -m tests.run_interactive_lha_smoke_test --branch continue` | exit 0 — `PASS: LHA-not-found EasyRequestArgs -> real QMessageBox -> clicked Continue -> app's own branch (checkbox after=False) -> clean exit` (regression check on the neighbor route) |
| `uv run python tools/generate_api_index.py` | ASL LVOs 48/54/60 → `valid` |

(The first accept-branch run of the rewritten smoke test **failed** with
`dialog_seen=False` and target exit right after the Browse click — that
failure is what surfaced the annotation-dispatch root cause; it passes since
the fix.)

## Remaining uncertainty

- `ASLFR_DoPatterns` patterns are carried to the projection but not yet
  applied as `QFileDialog` name filters; hidden-file visibility has no public
  PySide6 6.11.1 option, so that classic behavior is not translated. Both are
  recorded as known gaps on the library card.
- `AbortAslRequest`/`ActivateAslRequest` remain unimplemented (no target
  calls them; the API index honestly shows them `missing`).
- Geometry fields (`fr_LeftEdge` …) are never written (the app never reads
  them; classic ASL would manage them itself).

## Whether merged

Yes: `fix/host-asl-directory-requester` merged into `development` with
`git merge --no-ff` after all gates above passed. The branch is retained per
repo policy.

## Next recommended increment

Pattern-filter translation (`ASLFR_DoPatterns` → `QNameFilter`) and
positive/negative gadget text (`ASLFR_PositiveText`/`ASLFR_NegativeText` →
button labels) for the file-mode requesters, each from a fresh branch off the
updated `development`. A repo-wide guard test asserting that every
`BaseLibrary` dispatch method has empty parameter annotations would keep the
root cause from ever recurring.
