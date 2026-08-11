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
- Treat this file as the durable history for `iTidy` runs. Pull forward the important facts from recent run artifacts instead of assuming those local files will still exist later. Each entry should preserve the first blocker, the useful evidence, any repo change that followed, and the next recommended step.

## Entries

Newest entry last. Do not edit or delete earlier entries.

### 2026-08-09 — Missing `icon.library` blocks startup past core-library setup

- Observed: repeated same-day probe runs converged on the same first app-level blocker: startup advanced past earlier launcher issues, then stopped because `icon.library` was missing during initial library setup.
- Change: none — recorded for triage.
- Next: implement `icon.library` (or the part of it `iTidy` needs first) per `../../runtime/writing-a-library-impl.md`, then rerun and add a new entry here.
