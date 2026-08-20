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

Notes:
- Treat this file as the durable history for `iTidy` runs. Pull forward the important facts from recent run artifacts instead of assuming those local files will still exist later. Each entry should preserve the first blocker, the useful evidence, any repo change that followed, and the next recommended step.

## Entries

### 2026-08-09 — Missing `icon.library` blocks startup past core-library setup

- Observed: repeated same-day probe runs converged on the same first app-level blocker: startup advanced past earlier launcher issues, then stopped because `icon.library` was missing during initial library setup.
- Change: none — recorded for triage.
- Next: implement `icon.library` (or the part of it `iTidy` needs first) per `../../runtime/writing-a-library-impl.md`, then rerun and add a new entry here.

### 2026-08-11 — Repo-owned `icon.library` seam advances startup to `graphics.library`

- Observed: a direct probe run now opens `icon.library` successfully and gets past the earlier missing-library failure. The next first blocker is `graphics.library`, which means the new `icon.library` override is being picked up by the in-process launcher.
- Change: added a minimal repo-owned `IconLibrary` implementation in `src/amiga_ui/vamos/icon_library.py`, registered it in `src/amiga_ui/vamos/extensions.py`, and tightened the launcher integration test so it asserts that `icon.library` opens at a non-zero address.
- Next: add the smallest honest `graphics.library` implementation needed for the next startup sequence, then rerun and record the next blocker rather than speculating ahead into wider drawing support.

### 2026-08-16 — Repo-owned stub libraries advance startup to dos.CreateDir with PROGDIR volume missing

- Observed: after implementing `icon.library`, `graphics.library`, `diskfont.library`, `workbench.library`, `gadtools.library`, and `asl.library` in a parallel fashion, the first non-library blocker was that `das.library` called `CreateDir(lock, 'PROGDIR:logs/')` which failed because the `PROGDIR:` volume name had no mapped path.
- Change: none — recorded for triage. The fix needs to either:
  1) define a `.cfg.path.auto_assigns` entry for `prog` in the launch config, or
  2) register a stub volume mapping programmatically via an extension hook before dos runs.
- Next: extend the repo's path manager extension point so it registers `PROGDIR:/sys/path/to/amiga_apps/<app>/binary/extracted` automatically when launching a probe run; rerun and record either the next missing library, structure issue, or GUI request.

### 2026-08-20 — PROGDIR volume registration fixed; GUI/window frontier reached

- Observed: `artifacts/runs/20260820T211914Z-probe-iTidy` still failed at `dos.CreateDir`/`Lock('PROGDIR:logs/')` because `PROGDIR:` was not registered when other `-V` volumes were present. After the launcher fix, `artifacts/runs/20260820T212739Z-probe-iTidy` resolves `PROGDIR:logs/` to `amiga_apps/itidy1classic/binary/extracted/logs/` and writes the app log successfully.
- Change: corrected the launcher's automatic `PROGDIR:` volume detection so other `-V` volume arguments do not suppress the `progdir:<app root>` volume. Added regression coverage for this case in `tests/test_vamos_launcher.py`.
- Next: continue from the new first blocker in the verified probe: `GetCurrentDirName` still returns the default failure value, `ENV:`/`ENVARC:` prefs paths are missing, `iffparse.library` reports `UNKNOWN(#8)`, and `intuition.library` reports `UNKNOWN(#100)`/`UNKNOWN(#85)` before the app exits with `Could not get visual info` and `Failed to open GUI window`.
