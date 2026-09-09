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

Notes:
- Each entry should eventually include status, owner, source to consult next, and decision trigger.

## Summary

These are the unresolved technical questions that still matter enough to shape implementation order. They are narrower than the deferred-decision list: each one should be answerable by a source check, a targeted `vamos` run, or one small implementation experiment.

## Active Questions

### Immediate Compatibility-Risk Register

These are implementation assumptions that could otherwise become invisible as
the GUI frontier advances. A passing iTidy screenshot is not, by itself, proof
of their general classic semantics.

1. **RastPort draw modes.** The current renderer reduces vector/fill modes to
   `JAM1 -> APen`, `JAM2 -> BPen`, approximates `INVERSVID` by swapping those
   roles, and performs `COMPLEMENT` as host RGB XOR. Establish the source-bit,
   pattern, bitplane-depth, and write-mask behavior from authoritative classic
   evidence before treating any of those reductions as general. A solid
   `RectFill` is the smallest useful discriminating experiment.
2. **Text modes.** `Text` currently paints foreground glyphs but does not write
   the JAM2 background cells. `PrintIText` ignores `IntuiText.DrawMode`. The
   claim that `IntuiText.DrawMode` is a separate value set from RastPort modes
   is not established by the available header or `PrintIText` AutoDoc.
3. **New-window RastPort initialization.** The repo initializes a window-owned
   RastPort with semantic screen pens and JAM1 because that makes iTidy's
   observed drawing sequence coherent. This is a target-informed compatibility
   hypothesis, not yet a proven general `OpenWindow` contract; distinguish it
   from the documented JAM2 result of `InitRastPort`.
4. **Remaining structure offsets.** `Screen.RastPort@+0x54` has direct evidence
   from the shipped binary, but other `Screen` fields and the repo's internal
   RastPort font/metric offsets remain model choices. `GadgetID@+0x26` has strong
   header agreement but has not been closed against the shipped binary. Keep
   the detailed evidence in `docs/apps/itidy/compatibility-notes.md` authoritative.
5. **Evidence provenance.** The cache named `assets/docs/ndk/NDK3.2/` contains
   files identifying themselves as later AmigaOS 4.1/V47 material. Treat them
   as field-by-field corroboration, not a blanket classic 3.0-3.1 authority.
   The available iTidy source also differs from the shipped binary in known
   areas and must not silently override binary evidence.
6. **Wired but semantically incomplete APIs.** Scanner-valid methods that only
   record a call or omit required mutation can vanish from defaulted-call
   analysis. In particular, graphics View/ViewPort, palette, bitmap/blit,
   RastPort-attribute, and pen-allocation methods need an explicit
   `recorded-but-unimplemented` status until real target pressure supplies the
   necessary semantics.
7. **GUI test isolation.** The latest aggregate run passed 200 of 201 tests; an
   Xvfb test failed only with inherited `QT_QPA_PLATFORM=offscreen` and passed
   separately. Determine whether the test or runner should sanitize that
   environment before describing the complete suite as green.

### 1. What Is The Smallest Realistic `sys:` Tree That Gets `iTidy` To A Useful Window?

Status: **answered for the current CLI launch path.** The prepared runtime now
reaches and displays the main application window. Keep the missing preference
files and Workbench-launch fixture as separate fidelity questions rather than
treating the useful-window milestone as open.

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

Current state and next experiment:
The repo now projects the application window and replays its custom RastPort
drawing, but the GadTools controls, menus, requesters, and live host-event loop
remain absent. Project the initial BUTTON/TEXT/CYCLE/CHECKBOX gadget set next,
then compare the result against the app's documented and source-visible behavior
rather than against abstract visual nostalgia [S11 L15-L26] [S12 L43-L50].

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
