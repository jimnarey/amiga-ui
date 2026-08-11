---
title: "iTidy Run Log"
status: log
depends_on:
  - "compatibility-notes.md"
  - "../../workflows/error-driven-porting.md"
citations_used: []
---

# iTidy Run Log

Purpose: Append-only, dated record of what has actually been run against `iTidy` and observed, so a blocker that has already been diagnosed is not re-investigated from scratch.

Needed for:
- Confirming whether `compatibility-notes.md`'s prose is still current.
- Picking up work without re-deriving the current frontier from raw logs.

Depends on:
- `compatibility-notes.md`
- `../../workflows/error-driven-porting.md`

Status: Log. Append-only — see the convention in `../../workflows/error-driven-porting.md`.

Notes:
- Do not duplicate data already captured inside a run's own artifact folder (the exact command, stdout, stderr, `vamos.log`, full diagnostic text, return code). Each entry points at that folder instead of restating its contents. Anything worth recording here is what the artifact folder cannot tell you on its own: a short human-readable label for skimming, what repo change (if any) followed the run, and what to do next.

## Entries

Newest entry last. Do not edit or delete earlier entries.

### 2026-08-09 — Missing `icon.library` blocks startup past core-library setup

- Artifacts: `artifacts/runs/20260809T014634Z-probe-itidy/` (four earlier same-day runs under `artifacts/runs/20260809T01*` reached the same blocker; two still-earlier runs that day failed on launcher bugs unrelated to `iTidy` itself, both since fixed)
- Change: none — recorded for triage.
- Next: implement `icon.library` (or the part of it `iTidy` needs first) per `../../runtime/writing-a-library-impl.md`, then rerun and add a new entry here.
