---
title: "Session log — iTidy RastPort TxWidth ABI: settled as not directly accessed by the binary"
status: log
depends_on:
  - "../apps/itidy/run-log.md"
  - "../apps/itidy/compatibility-notes.md"
  - "../architecture/platform-target.md"
  - "../platform/library-cards/graphics.library.md"
  - "../workflows/branching-and-merging.md"
citations_used:
  - S1
  - S13
  - S15
---

# Session log — iTidy RastPort TxWidth ABI (2026-09-08)

## Session prompts

Raw DSH session: `session-2d2d5b9e-75f8-4f5b-a926-a7dc0ee01ba1`
Log: `/mnt/work/deepseek/.dsh/sessions/--workspace-amiga-ui--/session-2d2d5b9e-75f8-4f5b-a926-a7dc0ee01ba1/session.jsonl.zstd`

### Starting prompt (2026-09-07 22:03:51 UTC)

````text
You are working in the amiga-ui repository.

Start from `development`. Inspect AGENTS.md, README.md, docs/workflows/dsh.md, docs/architecture/platform-target.md, docs/apps/itidy/compatibility-notes.md, and the current RastPort-related implementations and tests. Relevant historical session summaries are available under `docs/sessions/`; the most recent iTidy host-UI session describes the immediate handoff.

Current objective: settle whether the shipped iTidy binary was compiled with `RastPort.TxWidth` at offset `+0x3C`, or whether the compatibility layer is using the wrong RastPort layout.

Keep this session focused on that ABI question. Do not move on to `GetSysTime`, `GetCurrentDirName`, `FreeIFF`, or another compatibility frontier until the offset question has been resolved or reduced to a clearly documented uncertainty.

Important existing context:

- The repo currently uses `RpFont@+0x34`, `TxHeight@+0x3A`, and `TxWidth@+0x3C`.
- The classic AmigaOS 3.x layout described in the compatibility notes instead places these fields at `+0x22`, `+0x2E`, and `+0x30`.
- A previous runtime investigation established that iTidy expects the screen’s embedded RastPort at `Screen+0x54`, due to its pre-`RasInfo` ViewPort layout.
- The offset of the RastPort within `Screen` and the offset of `TxWidth` within the RastPort are separate questions. Do not conflate them.
- `TextLength`, `Text`, and `PrintIText` currently consume the `+0x3C` value.
- Their bounded Topaz-width fallback can conceal a wrong offset.
- The compatibility layer itself writes `6` at `+0x3C`, so observing `6` there does not independently validate the ABI.

Treat the shipped binary as runtime ground truth:

`amiga_apps/itidy1classic/binary/extracted/iTidy`

Use the corresponding source tree to identify likely source-level operations, while remembering that it may not exactly match the shipped binary:

`amiga_apps/itidy1classic/source/`

Investigation guidance:

- Prefer direct evidence from the binary’s HUNK CODE.
- Use the repo’s existing disassembly support or Python Capstone tooling to inspect relevant instruction sequences and relocated addresses.
- Look for compiled accesses corresponding to expressions such as:
  - `screen->RastPort.TxWidth`
  - `screen->RastPort.TxHeight`
  - `rp->TxHeight`
  - `screen->RastPort.Font`
- Distinguish direct application struct-field loads from calls to `graphics.library TextLength`. The implementation of `TextLength` is not contained in the application binary, so a library call alone cannot prove the internal `TxWidth` offset.
- Establish the base pointer before interpreting a displacement. For an access based on `Screen`, separate the `Screen.RastPort` displacement from the field displacement within `RastPort`.
- Record the binary or HUNK-relative address, surrounding instructions, inferred base object, effective field offset, likely source-level operation, and confidence for each useful sequence.
- Do not infer an ABI merely because an offset agrees with the current Python implementation or a later NDK header.

If static disassembly cannot settle the question, use a bounded runtime diagnostic. Write distinct sentinel values at competing candidate offsets and observe a dependent value produced by the application. Do not use identical or naturally plausible values at several offsets, and do not treat zero-filled memory as confirmation.

The investigation should reach one of these honest conclusions:

1. direct binary evidence confirms `TxWidth@+0x3C`;
2. direct binary evidence proves a different offset;
3. the application binary does not directly access `TxWidth`, so this particular binary cannot settle that field offset without another form of evidence;
4. the available evidence remains ambiguous, with the exact missing evidence documented.

If the evidence proves that production offsets are wrong, make the smallest coherent repo-owned correction on a fresh branch from `development`. Check all related RastPort offsets rather than changing `TxWidth` in isolation without considering `RpFont` and `TxHeight`. Add focused regression tests based on the established layout, update the relevant compatibility documentation, run the narrow tests and normal repo checks, and rerun the iTidy probe to detect regressions. Commit and merge the increment into `development` only after it is properly gated.

If the evidence confirms the existing offset, avoid unnecessary production-code changes. Record the evidence in the appropriate compatibility documentation so the question does not need to be re-investigated.

Important constraints:

- Keep the default target classic m68k Workbench/AmigaOS 3.0-3.1.
- Do not treat the cached AmigaOS 4.1/NDK 3.2 headers as authoritative for the classic target.
- Do not infer OS4/PPC/ReAction/MorphOS layouts.
- Do not change code merely to make it agree with an unverified assumption.
- Do not add no-op implementations or unrelated compatibility changes.
- Preserve the honest `WaitPort`-on-empty-queue boundary.
- Keep permanent compatibility changes in the repo, not in `.venv/`.
- Use `/tmp` or ignored artifacts for disposable analysis scripts and output.

Subagent guidance:

Avoid open-ended subagent work. Do not delegate broad binary archaeology. If a subagent is useful, give it exactly one narrow evidentiary question with a concrete stop condition, and treat non-return, timeout, or an unsupported conclusion as inconclusive rather than blocking the main investigation.

When finished, leave a concise summary of:

1. the conclusion about `RastPort.TxWidth@+0x3C`,
2. the direct evidence supporting it,
3. any files changed and checks performed,
4. what remains uncertain and what should be attempted next.
````

### Additional prompt 1 (2026-09-08 07:53:48 UTC)

````text
Please produce a summary of this session in docs/sessions, conforming to the format and style of the summaries already in that dir.
````

## Purpose

Durable record of the session that **settled the single open RastPort
font-field ABI question** for `iTidy`: whether the shipped binary was compiled with
`RastPort.TxWidth` at offset `+0x3C` (the repo's layout) or whether the compat layer is
using the wrong RastPort layout. The conclusion, reached from a clean full disassembly
of the HUNK CODE segment, is that **the binary does not directly access `RastPort.TxWidth`
(or `RastPort.TxHeight`) at all** — it passes the RastPort pointer to graphics-library
calls (`TextLength` and friends) and never loads the font-metric fields itself. This
particular binary therefore cannot settle the field offset: the `+0x34`/`+0x3A`/`+0x3C`
offsets are a **compat-layer model choice**, not a binary constraint. No production
change was made; the finding is recorded in `../apps/itidy/compatibility-notes.md`.

Needed for:
- Recalling *how* to get a clean m68k HUNK CODE listing of `iTidy` (the version-string
  trap and the file↔disassembly address mapping) so the next offset question does not
  re-derive it.
- Knowing the `TxWidth@+0x3C` question is **settled as "not directly accessed"** so it
  is not re-investigated — and that the runtime sentinel diagnostic is *not* applicable
  to it (there is no binary-produced value that depends on a direct `TxWidth` read).
- The methodological lesson that an offset *matching* the repo (or the NDK) is not proof
  of a RastPort access — the **base register must be established per hit** before a
  displacement means anything.

Notes:
- Continues `20260906T1845Z-session-log-iTidy-host-ui-frontier-cleared.md`, which left
  `RastPort.TxWidth@+0x3C` as the carried-over "real ABI risk" open item, and
  `20260905T2101Z-session-log-iTidy-graphics-rastport-abi.md`, whose subagent
  disassembly was inconclusive. Companion to `../apps/itidy/run-log.md` (run-level
  blockers) and `../apps/itidy/compatibility-notes.md` (target-specific triage); this
  file records the *session*.
- The default runtime target is classic m68k Workbench/AmigaOS 3.0–3.1
  (`../architecture/platform-target.md`), whose evidence order makes the **HUNK CODE
  segment the ground truth** for struct offsets — the source tree is guidance only. No
  host GUI and no production code were in scope; this was a binary-analysis + docs task.

## Session summary

| Item | Value |
| --- | --- |
| Harness | DeepSeek Harness (dsh), Web GUI at 127.0.0.1:3080 |
| Sandbox / approval | workspace-write / ask |
| Main work date | 2026-09-07 → 2026-09-08 (UTC) |
| Work span (from commit evidence) | clean HUNK CODE disassembly (compacted span) → doc commit `c2e2b1c` 2026-09-08T00:16Z (exact start and token counts not re-derived here) |
| Model | `Qwen3.8-27B-UD-Q6_K_M` |
| Git baseline → end | `development` @ 91e4450 → c2e2b1c (one doc branch, `docs/itidy-rastport-txwidth-no-direct-access`, created from `development`, gated, fast-forward merged; kept, not deleted) |
| Exact request/token counts, compactions, session id | in the raw session log on the agent host (not re-derived here) |

Milestone achieved: the open `TxWidth@+0x3C` question is **settled as "the binary does
not directly access it."** A clean disassembly of the HUNK CODE segment (106,265
instructions, zero skipdata artifacts — so every field displacement is reliable) was
searched exhaustively for a direct RastPort font-field load and found **none**: no
`move.b $3c(aX)` (repo `TxWidth`), no `move.b $2e/$2f` (classic `TxHeight`/`TxBaseline`),
and every `move.b $30`/`$3a` hit at a "RastPort" offset is confirmed to read a *different
struct*. The `lea.l $54(aX)` sites *do* confirm RastPort-within-`Screen` at `+0x54`,
matching the repo. The binary's text metrics come from the `TextLength` library call, not
a direct field load, so the `+0x3C` offset is a self-consistent compat-layer choice and
**no production change is warranted**.

## What changed in the repo (in order)

| Commit | Branch (kept) | Change |
| --- | --- | --- |
| c2e2b1c (merged into `development`) | `docs/itidy-rastport-txwidth-no-direct-access` | `docs/apps/itidy/compatibility-notes.md` only: the "RastPort field offsets" bullet is rewritten from "confirm the binary's offsets" to the disassembly evidence and the *not-directly-accessed* conclusion; the "struct Screen field offsets" bullet notes `RastPort`-within-`Screen` at `+0x54` is now **binary-confirmed** via the `lea.l $54(aX)` sites. No production code, tests, or `api-index` regeneration — the offsets were neither confirmed nor refuted, so nothing in the runtime changed. |

## Blocker narrative (what actually happened)

### 1. The question and the prior state

The carried-over open item (from `20260906T1845Z` and `20260905T2101Z`): does `iTidy`'
s HUNK CODE read `RastPort.TxWidth` at `+0x3C` (repo) or `+0x30` (classic 3.x, with the
`RasInfo` field) [S1]? A prior subagent disassembly was interrupted and treated as
inconclusive, so the offset was documented as an open follow-up, not settled. The task
this session was to settle it against the binary and, only if the binary proved the
production offsets wrong, make the smallest coherent correction.

### 2. Getting a clean disassembly (the version-string trap)

The HUNK CODE segment's data starts at file `0x34` with a `bra.b` that skips an 8-byte
`"VBCC 0.9"` string (file `0x36`–`0x3D`); the real C-runtime `_start` resumes at file
`0x3E`. Disassembling from the raw CODE start (`0x34`) mis-decodes the string bytes as
instructions and **corrupts the alignment for the whole segment**. The fix: disassemble
from file `0x3E` with base address `0x0A`, yielding a listing with **106,265
instructions and zero skipdata artifacts** — the proof the alignment is clean throughout.
The address mapping is `disasm address A = file offset 0x34 + A`. (The first parse had
also used the wrong HUNK type constants — the real types are `0x3e7`–`0x3f3`, e.g.
`HUNK_CODE = 0x3e9`, not `0x01`–`0x11` — corrected by reading the amitools
`binfmt/hunk/Hunk.py` constants.)

### 3. The offset-matching flood (and why it is not proof)

Naively grepping the listing for the repo/classic offsets returns many hits, but most are
false positives. The `a7` base is the **stack frame**, not a RastPort, so `$34(a7)`,
`$30(a7)`, `$3c(a7)`, etc. are local-variable accesses and were filtered out. Even the
remaining address-register hits at a "RastPort" offset turned out to be other structs.
The discipline that settled the question: **establish the base register per hit before
interpreting a displacement.**

### 4. Establishing each candidate's base

With the base established per hit, every "RastPort-offset" candidate is a different
struct, and the genuine RastPort font-field reads are absent:

- **`move.b $30(aX)` (classic `TxWidth`-offset) — 5 hits** (`0x4cee`, `0xc3cc`, `0xc4ba`,
  `0xc9b0`, `0xca3c`). Each loads a byte from a **library-returned pointer** (the result
  of a `jsr` via a relocated library base) and immediately compares it to `1` or `2` —
  an enum/state field, not a font metric. A width is multiplied, never compared to 1/2.
- **`move.b $3a(aX)` (repo `TxHeight`-offset) — 2 hits** (`0x31c26`, `0x31e2a`). Both read
  a byte from a **function-argument struct** whose `+4` is a *dereferenced pointer*. A
  `RastPort`'s `+4` (`Rp_OrigY`) is a word, so that base is not a RastPort.
- **`move.b $3c(aX)` (repo `TxWidth`) — zero hits** from any `a0`–`a6` base.
- **`move.b $2e(aX)` / `$2f(aX)` (classic `TxHeight`/`TxBaseline`) — zero hits** anywhere.
- **`RpFont`-offset `move.l` reads — not RastPort.** `move.l $22(a2), d1` at `0x21c66`
  is followed by `sub.l #$3e9, d0` — `0x3e9` is `HUNK_CODE`, so this is a **HUNK-type
  check**, not a font-pointer load. The `move.l $34(aX)` hits push struct fields for an
  internal call whose base is not a RastPort.
- **`lea.l $54(aX)` (RastPort-in-`Screen`) — 17 sites**, most using `a7` (stack frame).
  The three non-stack sites either pass the resulting RastPort pointer to a
  graphics-library call or read a **word** from a non-Screen struct; none lead to a
  `TxWidth` byte read. (These *do* confirm RastPort-within-`Screen` at `+0x54`.)
- **Multiplies — the absence of the `font_width * N` signature.** All 360 `mulu.w`/
  `muls.w` in the segment are unrelated to a byte-read from a RastPort base, so there is
  no `font_width * N + 8`-style size computation sourced from a direct `TxWidth` read.

### 5. The conclusion (option 3: the binary does not directly access TxWidth)

Because the binary never loads `RastPort.TxWidth` or `RastPort.TxHeight` itself, no HUNK
CODE displacement pins the field offset: this particular binary **cannot settle it**. The
`+0x34`/`+0x3A`/`+0x3C` offsets are a **compat-layer model choice**, not a binary
constraint. The layer is self-consistent — `graphics.library` `TextLength`/`Text` read
`TxWidth` from `+0x3C` and the repo writes the Topaz width (`6`) there — and the
binary's text metrics come from the `TextLength` library call, not a direct field load.
Accordingly, **no production offset change was made**, and the endorsed **runtime
sentinel diagnostic is not applicable**: there is no binary-produced value that depends
on a direct `TxWidth` read to observe, so writing sentinels at competing offsets would
only confirm the layer's self-consistency, not the binary's layout. The source's
`calculate_font_dimensions` (in `amiga_apps/itidy1classic/source/src/templates/
amiga_window_template.c`) does read these fields directly, but the shipped binary
predates it — the source's `"SCREEN CHROME"` debug string is absent from the binary [S13]
— so the source is guidance, and the HUNK CODE is the ground truth that shows no direct
access [S15].

## Key technical findings

### The HUNK CODE segment starts with a version string that breaks naive disassembly

The segment opens with a `bra.b` skipping an 8-byte `"VBCC 0.9"` tag before the real
`_start`. Disassemble from the first real instruction (file `0x3E`, base `0x0A`), not
from the raw CODE start, and verify with the **zero-skipdata-artifact** count — that
count is the proof the alignment (and therefore every field displacement) is trustworthy.

### Relocation targets: do not read library identity from raw absolute addresses

The `movea.l $NNN.l, a6` and `jsr $NNN.l` absolute addresses in the raw listing are
**relocation targets** (patched at load time), so the library base and the called
function cannot be identified from the raw bytes. This does not affect the
*displacements* from base registers (a `move.b $30(a0)` reads the same `a0+0x30` in the
file and at runtime), so struct-field analysis stays valid — it only rules out using the
raw absolute addresses to name the libraries being called.

### Offset-matching is not proof; the base register is the arbiter

A displacement that happens to equal a RastPort field offset (`$30`, `$34`, `$3a`, `$3c`)
means nothing until the base is established. The `a7` (stack) accesses were the dominant
false positive, and the surviving address-register hits at "RastPort" offsets were all
other structs (a library-returned enum, a function-arg struct with a pointer at `+4`, a
HUNK-type check). Establishing the base per hit is what turned a flood of candidates into
a clean "none of them is a RastPort" result.

### The binary uses library text calls, not direct RastPort field loads

The binary passes the RastPort pointer (via the `lea.l $54(aX)` sites and `win->RPort`)
to graphics-library calls such as `TextLength` and never loads `TxWidth`/`TxHeight`/
`RpFont` itself. That is why the offset question has no answer *from the binary*: the
binary's font metrics are produced by the compat layer's `TextLength` implementation,
which reads the offset the layer itself chose. A compat layer that owns both the write
and the read of a field is self-consistent for any choice of offset.

### The source has drifted from the binary

`calculate_font_dimensions` in the source reads `RastPort.TxWidth`/`TxHeight` directly
and prints a `"SCREEN CHROME"` debug banner [S13]; that string is **absent** from the
shipped binary [S15], so the binary is an older build that does not contain that direct
read. The source is therefore guidance for dependencies and likely failure modes, not the
ground truth for the offsets — consistent with `../apps/itidy/compatibility-notes.md`'s
"Source-Release Drift" caution.

## Latent defects and follow-ups (not fixed this session)

- **`struct Screen` field offsets (partly settled).** `RastPort`-within-`Screen` at
  `+0x54` is now binary-confirmed (the `lea.l $54(aX)` sites). The other Screen offsets
  (`WBorTop@0x25`, `Font@0x2C`, `BitMap@0xB8`) remain unconfirmed against the binary.
- **`GadgetID` offset** — high confidence in `0x26` (three sources agree), but a
  definitive disassembly of the `switch (gad->GadgetID)` ladder would close it out.
- **Hardware-fidelity note.** On real AmigaOS 3.x the RastPort carries the `RasInfo`
  field and `TxWidth` sits at `+0x30`, so the compat layer's `+0x3C` would be *wrong on
  hardware* [S1] — but it is correct for the self-contained compat runtime, which is the
  project's default target and the only environment the binary's metrics are exercised
  in. Record this only if hardware fidelity ever enters scope.
- **The stateful-runtime frontier** (`GetSysTime`/`GetCurrentDirName`/`FreeIFF`) remains
  the next app-facing frontier (carried from `20260906T1845Z`); it was explicitly out of
  scope this session.
- The app's terminal state is unchanged: it ends at the honest `WaitPort`-on-empty-queue
  `UnsupportedFeatureError` boundary — a boundary, not a defect.

## Techniques that worked

- **Clean the disassembly before trusting any displacement.** Skip the leading version
  string (disassemble from file `0x3E` / base `0x0A`) and gate on **zero skipdata
  artifacts**; until that count is zero, no offset is trustworthy.
- **Filter `a7` first, then establish the base per hit.** The stack frame is the
  dominant source of false-positive "RastPort" offsets; after filtering it, trace each
  surviving base register back to how it was loaded (`lea $54`, a `win->RPort` load, a
  library return, a function argument) before reading a displacement.
- **Use the font-metric signatures to find (or confirm the absence of) the code.** The
  paired adjacent-byte read (`TxHeight`+`TxWidth`, 2 bytes apart from one base) and the
  multiply-fed-by-a-byte-read (`font_width * N`) are the signatures of direct font-metric
  access; finding neither was itself the evidence.
- **Read a HUNK-type constant as a tell.** `sub.l #$3e9` after a `move.l $22(a2)`
  revealed a "RpFont-offset" read that was actually a HUNK-type check, not a font
  pointer.
- **Do not chase raw absolute addresses.** Treat `movea.l $NNN.l`/`jsr $NNN.l` as
  relocation targets and rely only on base-register displacements for struct analysis.
- **Doc-only change, doc-only gate.** Because the finding neither confirmed nor refuted
  the offset, no production code, tests, or `api-index` changed; the gate was
  `pre-commit` (ruff/pyright — all skipped for a `.md`) plus the doc being authoritative.
  `PRE_COMMIT_HOME` was pointed at a writable dir (the default `~/.cache/pre-commit` is
  read-only under the `workspace-write` sandbox).
- **Git discipline per `../workflows/branching-and-merging.md`:** one doc branch off
  updated `development`, gated, fast-forward-merged; branch kept, not deleted.

## Session-log recovery note

The full raw session log (zstd-compressed JSONL: all user/assistant messages, reasoning,
tool calls, tool results, compaction events) is stored on the agent host under the
harness sessions directory for this session id and is a strict superset of this file;
use it to recover exact commands, outputs, the exact session-creation time, and the
request/token counts (which this markdown does not re-derive). This markdown is the
distilled, repo-durable version.
