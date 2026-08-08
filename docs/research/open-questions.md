---
title: "Open Questions"
status: draft
depends_on:
  - "deferred-decisions.md"
  - "../runtime/vamos-gaps.md"
  - "../apps/itidy/compatibility-notes.md"
citations_used:
  - "S8"
  - "S11"
  - "S12"
  - "S30"
  - "S31"
  - "S32"
  - "S34"
  - "S48"
  - "S49"
---

# Open Questions

Purpose: Capture unresolved technical questions in one place.

Needed for:
- Keeping uncertainty explicit and searchable.

Depends on:
- `deferred-decisions.md`
- `../runtime/vamos-gaps.md`
- `../apps/itidy/compatibility-notes.md`

Status: Draft.

Notes:
- Each entry should eventually include status, owner, source to consult next, and decision trigger.

## Summary

These are the unresolved technical questions that still matter enough to shape implementation order. They are narrower than the deferred-decision list: each one should be answerable by a source check, a targeted `vamos` run, or one small implementation experiment.

## Active Questions

### 1. What Is The Smallest Realistic `sys:` Tree That Gets `iTidy` To A Useful Window?

Why it matters:
The app does more than load a binary. It wants startup-script information, Workbench preference files, and normal Workbench-facing paths [S31 L1196-L1212] [S34 L1275-L1318] [S48 L214-L265] [S49 L305-L347].

Next source or experiment:
Run `iTidy` under an explicitly tiny prepared tree, record the first missing-file or missing-assign failure, and expand only one runtime input at a time.

Decision trigger:
This question is answered once the app can open its main window predictably under a documented minimal tree.

### 2. Which Non-Core Libraries Need Real Amiga Implementations First?

Why it matters:
`Vamos` can mix library modes [S8 L40-L55], but the current app already touches icon handling, native GUI layers, and prefs parsing through non-core libraries [S30 L314-L389] [S31 L1006-L1085] [S48 L203-L266] [S49 L297-L347].

Next source or experiment:
Start with honest exploratory library settings, inspect the first repeated failure, and decide per library whether the next move is `amiga`, `vamos`, `auto`, or a clearly temporary fake.

Decision trigger:
This question is answered incrementally, library by library, when repeated runs show one stable best policy.

### 3. What Is The Minimum Workbench-Launch Fixture The Repo Must Provide?

Why it matters:
`iTidy` explicitly distinguishes CLI and Workbench launch, expects `_WBenchMsg`, and reads tooltypes from its own icon only during Workbench-style startup [S30 L623-L687] [S30 L287-L389]. A shell-style launch is useful for probing, but it is not the app's native operating mode [S12 L79-L95].

Next source or experiment:
Build the smallest believable `WBStartup` path and compare how far the app gets relative to a CLI-style probe.

Decision trigger:
This question is answered when Workbench launch either reaches meaningfully further than CLI launch or proves not to be the next blocker yet.

### 4. How Thin Can The Host GUI Translation Be Before It Stops Feeling Like Amiga UI?

Why it matters:
The current app locks the Workbench screen, requests GadTools `VisualInfo`, opens a classic menu and gadget setup, and then continues into user interaction [S31 L176-L227] [S31 L1006-L1085]. The project has already chosen Qt Widgets as the host surface, but it has not yet proven how much semantic translation versus custom presentation is required for Workbench-feeling behavior.

Next source or experiment:
Implement the simplest credible window, menu, and requester path first, then compare the result against the app's documented and source-visible behavior rather than against abstract visual nostalgia [S11 L15-L26] [S12 L43-L50].

Decision trigger:
This question is answered incrementally as soon as one visible screen path works well enough to judge which mismatches are semantic and which are merely cosmetic.

### 5. Which Dependencies Are Baseline Blockers And Which Are Optional Feature Gates?

Why it matters:
Not every missing input should block the same stage of progress. `iTidy` can fall back when some preference files are missing [S48 L214-L265] [S49 L293-L311], but backup support depends on finding `LhA` and executing it successfully [S32 L93-L119] [S32 L162-L195]. The user docs also present backup as one feature among several rather than as the sole reason the program exists [S12 L43-L50].

Next source or experiment:
Classify each missing dependency discovered during runs as launch blocker, main-window blocker, core workflow blocker, or optional later feature gate.

Decision trigger:
This question is answered per dependency once the classification is written down and used consistently in triage.

## Working Rule

If a question can be answered by one controlled run or one narrow code change, do that before turning it into a bigger design debate.
