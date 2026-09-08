---
title: "Session log — iTidy stateful-runtime frontier cleared (GetSysTime, GetCurrentDirName, FreeIFF)"
status: log
depends_on:
  - "../apps/itidy/run-log.md"
  - "../apps/itidy/compatibility-notes.md"
  - "../architecture/platform-target.md"
  - "../platform/library-cards/dos.library.md"
  - "../platform/library-cards/iffparse.library.md"
  - "../workflows/error-driven-porting.md"
  - "../workflows/branching-and-merging.md"
citations_used:
  - S1
  - S46
  - S48
  - S49
---

# Session log — iTidy stateful-runtime frontier cleared (2026-09-08)

Purpose: Durable record of the session that **cleared the entire stateful-runtime
frontier** for `iTidy`. Starting from a baseline where the `host-ui-required`
(visible-UI) frontier was already cleared (the prior
`20260906T1845Z-session-log-iTidy-host-ui-frontier-cleared.md`) and the
`RastPort.TxWidth` ABI question was already settled (the prior
`20260908T0755Z-session-log-iTidy-rastport-txwidth-no-direct-access.md`), this
session implemented the three remaining defaulted stateful calls — `timer.device`
`GetSysTime` (a coherent 1978-epoch system clock, not a constant), `dos.library`
`GetCurrentDirName` (derived from the process cwd lock, returning an Amiga-visible
name), and `iffparse.library` `FreeIFF` (an honest `AllocIFF`/`FreeIFF` handle
lifecycle, not a general IFF parser) — as meaningful emulated-state updates, each on
its own branch off updated `development`, gated, and fast-forward-merged. The fresh
probe now shows **no stateful-runtime defaulted call remaining**; the honest
`WaitPort`-on-empty-queue boundary stayed intact throughout.

Needed for:
- Recalling *how* each stateful call is implemented (the 1978 Amiga epoch, the
  cwd-lock `ami_path` source, the tracked handle lifecycle) so the same approach is
  not re-derived.
- Knowing the stateful-runtime frontier is now **cleared** — the next frontier is the
  prepared-runtime/prefs boundary (missing `ENV:`/`ENVARC:` prefs,
  `RAM:CRITICAL_FAILURE.log`, `S:User-Startup`), not the stateful calls.
- The scanner lesson that a method missing `ctx` as its second argument is a scanner
  **error**, not a warning: it is not wired as a trap and the call is silently
  defaulted (this is exactly why `FreeIFF` was the last one to go).
- The Amiga epoch fact (`1978-01-01`, 2922 days after Unix `1970`) so a future
  time-related call does not assume the Unix epoch.

Notes:
- Continues `20260908T0755Z-session-log-iTidy-rastport-txwidth-no-direct-access.md`
  (which left the stateful-runtime set as the carried-over next frontier) and
  `20260906T1845Z-session-log-iTidy-host-ui-frontier-cleared.md` (which left the same
  three calls as the next frontier after clearing the UI). Companion to
  `../apps/itidy/run-log.md` (run-level blockers, one dated entry per increment);
  this file records the *session* that closed the stateful frontier across all three.
- The default runtime target is classic m68k Workbench/AmigaOS 3.0–3.1
  (`../architecture/platform-target.md`); no OS4/PPC/ReAction/MorphOS behaviour was
  inferred, no host GUI was in scope, and the `RastPort.TxWidth` offset investigation
  was explicitly **not** reopened.

## Session summary

| Item | Value |
| --- | --- |
| Harness | DeepSeek Harness (dsh), Web GUI at 127.0.0.1:3080 |
| Sandbox / approval | workspace-write / ask |
| Main work date | 2026-09-08 (UTC+01:00) |
| Work span (from commit evidence) | first increment 10:28 → doc commit 11:58 local (≈1.5 h active across three gated increments + docs); the session span was compacted once mid-run |
| Model | `Qwen3.8-27B-UD-Q6_K_M` |
| Git baseline → end | `development` @ ecdd444 → b1c66f0 (three feature branches + one doc commit, each created from updated `development`, gated, fast-forward-merged; kept, not deleted) |
| Exact request/token counts, compactions, session id | in the raw session log on the agent host (not re-derived here) |

Milestone achieved: the entire stateful-runtime frontier is cleared. The three
increments moved `GetSysTime`, `GetCurrentDirName`, and `FreeIFF` from
`? CALL … -> (default)` to **real, hooked** entry points that update meaningful
emulated state. The probe progression proves it monotonically:
`artifacts/runs/20260908T084706Z-probe-iTidy` (3 stateful defaulted calls) →
`artifacts/runs/20260908T092408Z-probe-iTidy` (2: after `GetSysTime`) →
`artifacts/runs/20260908T095134Z-probe-iTidy` (1: after `GetCurrentDirName`) →
`artifacts/runs/20260908T104309Z-probe-iTidy` (**0 stateful defaulted calls**, after
`FreeIFF`). `tools/analyze_target_failure.py --latest` on the final probe reports no
stateful-runtime defaulted call remaining; the only items left are missing
prepared-runtime paths (`ENV:sys/*.prefs`, `RAM:CRITICAL_FAILURE.log`,
`S:User-Startup`). The app's *terminal* state did **not** change: it still ends at
the honest `WaitPort`-on-empty-queue `UnsupportedFeatureError` boundary
(`src/amiga_ui/vamos/exec_library.py` L72), exactly as designed and not a regression.

## What changed in the repo (in order)

| Commit | Branch (kept) | Change |
| --- | --- | --- |
| 24f6b0f | `feat/timer-get-sys-time` | New `RepoTimerDevice(BaseLibrary)` in `src/amiga_ui/vamos/timer_device.py`: `GetSysTime(dest)(a0)` writes `struct timeval` into the caller's 68k memory — `tv_secs` @ 0x00, `tv_micro` @ 0x04, both big-endian ULONG — on the classic **Amiga 1978 epoch** (`AMIGA_EPOCH = 1978-01-01 00:00:00 UTC`, not the Unix 1970 epoch), with a narrow replaceable clock source (`self.clock`, defaulting to UTC now) so exact seconds/microseconds are testable without the host wall clock; registered `"timer.device": RepoTimerDevice` in `src/amiga_ui/vamos/extensions.py`; `tests/test_timer_device.py` (9 cases, incl. an Amiga-vs-Unix cross-check asserting the 2922-day offset, a big-endian byte-order guard, and a scanner guard that `GetSysTime` is a wired `.fd` trap) |
| 7cefab0 | `feat/dos-get-current-dir-name` | New `RepoDosLibrary(DosLibrary)` in `src/amiga_ui/vamos/dos_library.py`: `GetCurrentDirName(buf, len)(d1, d2)` derives the result from the active process cwd lock (`lock.ami_path`, an **Amiga-visible** name such as `sys:T`, never the host `sys_path`), respects the buffer length with NUL termination and the documented `DOSTRUE`/`DOSFALSE` + `io_err` failure behaviour (`ERROR_LINE_TOO_LONG` for a too-small/zero buffer, `ERROR_OBJECT_WRONG_TYPE` when there is no cwd lock); registered `"dos.library": RepoDosLibrary` in `src/amiga_ui/vamos/extensions.py`; `tests/test_dos_library.py` (7 cases: success writes the Amiga name, the result is `ami_path` not the host path, over-small buffer truncates + `io_err`, zero-length fails, no-cwd-lock writes NUL + `io_err`, no-mem safe failure, and a scanner guard) |
| 53e469c | `feat/iffparse-freiff-lifecycle` | `src/amiga_ui/vamos/iffparse_library.py` rewritten from a constant-handle stub to a real handle lifecycle: `AllocIFF()()` allocates a tracked 256-byte block in the emulated address space (via `ctx.alloc.alloc_memory`, the same pattern as `diskfont`/`event_bridge`) and returns its address (a real allocation the caller may write through, e.g. `iff->iff_Stream`), and `FreeIFF(iff)(a0)` — signature fixed to take `ctx` (the missing `ctx` was why it was a scanner error and thus defaulted) — releases exactly the handles this instance allocated and ignores unknown/already-freed handles as an honest no-op; the remaining iffparse traps are left as the documented pre-existing no-op boundary (deliberately not a general IFF parser); `tests/test_iffparse_library.py` (9 cases: distinct tracked handles, real alloc address, no-alloc → NULL, release of a tracked handle, unknown-handle no-op, double-free frees exactly once, release-only-the-matching-handle, and a scanner guard that both are wired `.fd` traps) |
| b1c66f0 | `feat/iffparse-freiff-lifecycle` | `docs/apps/itidy/run-log.md` (a dated entry for the `FreeIFF` increment noting it completes the stateful frontier and pointing the next workstream at the prepared-runtime/prefs boundary) and `docs/apps/itidy/compatibility-notes.md` (`Current Status` updated from "the stateful calls are the frontier" to "the stateful frontier is cleared; the next workstream is the prepared-runtime/prefs boundary") |

## Blocker narrative (what actually happened)

### 1. The frontier at session start

The session started from `development` @ ecdd444 (clean tree), the state after the
`host-ui-required` frontier was cleared and the `RastPort.TxWidth` ABI was settled. A
fresh probe (`artifacts/runs/20260908T084706Z-probe-iTidy`) confirmed the frontier
rather than assuming it: the only remaining defaulted calls were the three
stateful-runtime ones — `timer.device` `GetSysTime` (17x, the highest frequency,
driven by startup time reads), `dos.library` `GetCurrentDirName` (2x), and
`iffparse.library` `FreeIFF` (1x, logged as `54 UNKNOWN(#8) from PC=04b81c -> d0=0
(default)`). The task constraint was explicit — "implement a coherent system clock,
not a constant or an empty success", "derive the result from the active process, CLI,
lock, or vamos path state rather than returning a hard-coded directory", and "the
current AllocIFF dummy handle and no-op lifecycle must not be treated as complete
merely because FreeIFF stops appearing as defaulted". `GetSysTime` was taken first as
the highest-frequency call.

### 2. Increment 1 — `timer.device` `GetSysTime` (the 1978 epoch)

`GetSysTime(dest)(a0)` fills the caller's `struct timeval` (`tv_secs` @ 0x00,
`tv_micro` @ 0x04, both big-endian ULONG [S1 `devices/timer.h`]). The key correctness
risk was the **epoch**: the classic Amiga clock counts seconds from
**1978-01-01 00:00:00 UTC**, not the Unix 1970 epoch — 2922 days later. The repo's
own source of truth is `amitools/vamos/lib/dos/AmiTime.py` (the `2922` days between
Jan-1 1970 and Jan-1 1978), and `dos.library` `DateStamp` routes `time.time()` through
`sys_to_ami_time`. The implementation computes `tv_secs = int((clock() -
AMIGA_EPOCH).total_seconds())` (clamped to a valid `ULONG`) and `tv_micro =
now.microsecond`, and writes both to the caller's memory with `mem.w32` (big-endian).
The clock source is a narrow replaceable callable (`self.clock`, defaulting to UTC
now) so the tests pin exact seconds/microseconds without depending on the host wall
clock; the cross-check test asserts the Amiga value is exactly `2922 * 86400` seconds
behind the Unix value for the same instant. After this increment the probe
(`artifacts/runs/20260908T092408Z`) showed 2 remaining stateful calls.

### 3. Increment 2 — `dos.library` `GetCurrentDirName` (from the cwd lock)

`GetCurrentDirName(buf, len)(d1, d2)` must return an **Amiga-visible** directory name,
not an accidental host filesystem path. The source of the name is the active process
cwd lock: `lock = self.get_current_dir(ctx)` (the upstream `dos.library` helper,
`lock_mgr.get_by_b_addr(ctx.process.get_current_dir() >> 2)`) and the result is
`lock.ami_path` (e.g. `sys:T`, matching the `--cwd sys:T` invocation) — never
`lock.sys_path` (the host path). The implementation respects the supplied buffer
length and the documented DOS failure contract: it NUL-terminates, returns
`DOSTRUE` (`0xFFFFFFFF`) on success, and on failure writes NUL (where there is room),
sets `io_err` via `setioerr`, and returns `DOSFALSE` (`0`) — `ERROR_LINE_TOO_LONG`
(120) for a too-small or zero-length buffer, `ERROR_OBJECT_WRONG_TYPE` (212) when
there is no cwd lock. This made the app's "Error getting current directory" stdout
signal disappear and `GetCurrentDirName` now returns `sys:T`. After this increment the
probe (`artifacts/runs/20260908T095134Z`) showed 1 remaining stateful call.

### 4. Increment 3 — `iffparse.library` `FreeIFF` (the honest handle lifecycle)

`FreeIFF(iff)(a0)` was the last defaulted call, and it was defaulted for a specific,
fixable reason: its signature was `FreeIFF(self, iff)` — missing `ctx` as the second
argument — so `LibImplScanner` marked it a **scanner error** and did not wire it into
the jump table. The fix was to make it `FreeIFF(self, ctx)` and read the handle from
`A0`. But the task required more than silencing the warning: the `AllocIFF`/`FreeIFF`
lifecycle had to be **honest**, not a dummy. Inspecting the app source
(`window_management.c` L290-L347 [S49] and `Settings/IControlPrefs.c` L225-L266 [S48])
showed the observed path is `iff = AllocIFF()` → `file = Open("ENV:sys/font.prefs")`
fails (the prefs file is absent in the runtime) → `FreeIFF(iff)` — the app never
reaches `OpenIFF`/`ParseIFF`/`CurrentChunk`. So the smallest semantic unit is an honest
`AllocIFF`/`FreeIFF` handle lifecycle, **not** a general IFF parser. `AllocIFF()()`
now allocates a tracked 256-byte block (via `ctx.alloc.alloc_memory`, the same pattern
as `diskfont`/`event_bridge`) and returns its address — a real allocation the caller
may write through (`iff->iff_Stream`), matching the `IFFHandle` model [S46] — and
`FreeIFF(iff)` releases exactly the handles this instance allocated (freeing the
memory) and ignores unknown or already-freed handles as an honest no-op. The remaining
iffparse traps were left as the documented pre-existing no-op boundary rather than
expanded into a parser. After this increment the probe
(`artifacts/runs/20260908T104309Z`) showed **0** stateful defaulted calls.

## Key technical findings

### The Amiga epoch is 1978, not 1970

`GetSysTime`'s `struct timeval.tv_secs` counts from `1978-01-01 00:00:00 UTC`, not the
Unix `1970` epoch [S1 `devices/timer.h`; `amitools/vamos/lib/dos/AmiTime.py`]. The 2922-day
offset was pinned by a test that computes both the Amiga and Unix second counts for the
same instant and asserts their difference is exactly `2922 * 86400`. Any future
time-related call (timers, `DateStamp`, file timestamps) must use the 1978 epoch, not
assume the Unix one.

### A scanner *error* is not a warning — it is a silently-defaulted trap

The reason `FreeIFF` (and 25 other iffparse traps) were defaulted was a bad signature:
`FreeIFF(self, iff)` omits `ctx` as the second argument, which `LibImplScanner` reports
as an **error**, meaning the method is *not* installed as a valid trap. A valid method
must begin `self, ctx`; extra arguments (if any) must exactly match the `.fd` entry.
Adding `ctx` and reading the register explicitly is what wired `FreeIFF`. The same
diagnostic (`LibImplScanner().scan(...)` → `get_error_func_names()`) is the fast way to
find out *why* a named method is not being called.

### Per-session state in `__init__` is safe for a refcounted library

The `IffParseLibrary` handle-tracking dict lives in `__init__`. This is safe because
`amitools` instantiates the impl **once** on the first `OpenLibrary` and shares the
instance across subsequent opens (ref count): `VLibManager.open_lib_name` calls
`get_vlib_by_name` first and only calls `impl_cls()` when no vlib exists yet
(`amitools/vamos/libcore/mgr.py`). So `__init__` state persists for the whole session,
matching the existing `timer_device`/`diskfont` pattern.

### An Amiga-visible name is `lock.ami_path`, never `lock.sys_path`

`GetCurrentDirName` must surface a name the Amiga app recognises. The cwd lock carries
both: `ami_path` (e.g. `sys:T`) and `sys_path` (the host path). Returning `sys_path`
would leak a host filesystem path into the emulated app. The implementation uses
`ami_path` only, and the test asserts the result is the Amiga name, not the host path.

### The smallest semantic unit beats a general parser

The iffparse fix resisted the temptation to implement `OpenIFF`/`ParseIFF`/
`CurrentChunk` (a general IFF parser). The observed path only allocates a parser, fails
to open an absent prefs file, and frees the parser, so an honest `AllocIFF`/`FreeIFF`
handle lifecycle was the complete fix. The rest of the table is a documented no-op
boundary, and the module docstring says so rather than claiming the library is complete.

## Latent defects and follow-ups (not fixed this session)

- **Library cards not updated.** There is no `timer.device` library card; the
  `dos.library.md` and `iffparse.library.md` cards exist but were not updated to reflect
  the new `GetCurrentDirName` and `AllocIFF`/`FreeIFF` implementations. Updating them is
  a small doc follow-up.
- **The iffparse library is not a full IFF parser.** Only the `AllocIFF`/`FreeIFF`
  handle lifecycle is real; the other 26 traps remain no-op boundary stubs (still
  scanner errors, unwired). A run that actually reaches `OpenIFF`/`ParseIFF`/
  `CurrentChunk` (e.g. with a populated `ENV:sys/*.prefs`) would surface them as new
  defaulted calls and would be the trigger to implement them — not before.
- **The prepared-runtime/prefs boundary is the next frontier.** With the stateful
  frontier cleared, the only remaining analyzer items are missing prepared-runtime
  paths — `ENV:sys/font.prefs`, `ENV:sys/Workbench.prefs`, `ENV:sys/icontrol.prefs`,
  `ENVARC:sys/font.prefs`, `RAM:CRITICAL_FAILURE.log`, `S:User-Startup`, and `T` — which
  need a decision on prepared runtime files, assigns, or better DOS path behaviour.
- The app's terminal state is unchanged: it ends at the honest
  `WaitPort`-on-empty-queue `UnsupportedFeatureError` boundary
  (`src/amiga_ui/vamos/exec_library.py` L72) — a boundary, not a defect, and not
  counted as a regression.

## Techniques that worked

- **One branch per coherent increment, ff-merged after each gate.** Three increments,
  three branches (`feat/timer-get-sys-time`, `feat/dos-get-current-dir-name`,
  `feat/iffparse-freiff-lifecycle`), each created from updated `development`, gated, and
  fast-forward-merged before the next started; no unrelated guesses bundled, no branches
  deleted. The doc commit rode the `FreeIFF` branch since it records that increment.
- **Confirm the frontier with a fresh probe, then re-probe after each increment.** Each
  increment re-ran `uv run amiga-ui probe` and read the new `artifacts/runs/…` to prove
  the call was no longer defaulted before moving on; the four probe artifacts
  (`20260908T084706Z` → `20260908T092408Z` → `20260908T095134Z` →
  `20260908T104309Z`) form a monotone 3→2→1→0 progression of stateful defaulted calls.
- **Keep a `LibImplScanner` guard on every new `.fd` method.** A method must take
  `ctx` first (+ exact FD arg count) or the scanner drops it and the call is silently
  lost. Each test module carries a guard; for `FreeIFF` the guard asserts it is no
  longer in `get_error_func_names()`/`get_invalid_func_names()`.
- **Make the clock source injectable.** `GetSysTime` reads a replaceable `self.clock`
  callable (default UTC now), so exact seconds/microseconds and the 1978-epoch offset
  are asserted deterministically without the host wall clock or the binary.
- **Use narrow, single-purpose fakes in the tests (no binary dependency).** Each test
  module builds a minimal `_FakeCpu`/`_FakeMem`/`_FakeAlloc`/`_FakeTaskAccess` that
  records exactly the side effect under test (big-endian writes, `io_err`, freed
  handles), so the semantics are pinned without the iTidy binary.
- **Document the boundary instead of faking completeness.** The iffparse fix left the
  rest of the table as a documented no-op boundary (module docstring) rather than
  expanding into a general parser or claiming the library is done.
- **Git discipline per `../workflows/branching-and-merging.md`:** narrow tests
  (`tests.test_timer_device` 9 OK, `tests.test_dos_library` 7 OK,
  `tests.test_iffparse_library` 9 OK) + full suite (142 OK) + `amiga-ui probe` +
  `tools/analyze_target_failure.py --latest` + `pre-commit` (ruff check + ruff format +
  pyright; `PRE_COMMIT_HOME=/tmp/pre-commit-home` under the `workspace-write` sandbox)
  before each merge; branches kept, not deleted.

## Session-log recovery note

The full raw session log (zstd-compressed JSONL: all user/assistant messages,
reasoning, tool calls, tool results, compaction events) is stored on the agent host
under the harness sessions directory for this session id and is a strict superset of
this file; use it to recover exact commands, outputs, the exact session-creation time,
and the request/token counts (which this markdown does not re-derive). This markdown is
the distilled, repo-durable version.
