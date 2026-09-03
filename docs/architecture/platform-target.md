---
title: "Platform Target"
status: draft
depends_on:
  - "compatibility-scope.md"
citations_used:
  - "S1"
  - "S11"
  - "S12"
---

# Platform Target

Purpose: Pin the AmigaOS version family that implementations, docs, generated indexes, and autonomous-agent decisions should assume by default.

Needed for:
- Preventing accidental drift from classic Workbench behavior into later AmigaOS, OS4, AROS, or MorphOS assumptions.
- Deciding whether an API function is baseline behavior, optional compatibility behavior, or out of target.

## Default Target

The default runtime target is classic m68k AmigaOS / Workbench 3.0 and 3.1. In library-version terms, treat V39 and V40 behavior as the normal compatibility baseline unless an app-specific note says otherwise.

This does not exclude older documented APIs. Functions introduced in V36 or V37 remain valid baseline dependencies when a Workbench 3.x application uses them, because Workbench 3.0/3.1 includes those earlier API surfaces. `gadtools.library/GetVisualInfoA()` is an example: it is a V36 GadTools function and is in target for a Workbench 3.x app.

## Later Classic Releases

Use AmigaOS 3.1.4 and 3.2 material as modern classic reference documentation, not as permission to assume later runtime behavior. APIs introduced in V46 or V47 should be treated as later-classic reference material unless the target app explicitly detects or requires them.

Use AmigaOS 3.5 and 3.9 behavior only as optional compatibility behavior when a real target app exposes an app-visible reason for it. For `iTidy`, icon.library V44+ color-icon behavior is such an optional compatibility area; it is not the default platform baseline.

## Out Of Target

Do not infer OS4, PPC, ReAction, AROS, or MorphOS behavior for the default implementation path. If a source or header appears to describe an OS4-era structure or API, verify that the current m68k target binary actually depends on it before changing repo-owned runtime structures.

## Evidence Order

When diagnosing an app failure, prefer evidence in this order:

1. The shipped target binary's observed `vamos` calls and run artifacts.
2. The target app source and app-specific documentation, when available.
3. Classic NDK FD/SFD/header files and AutoDocs, with version gates preserved.
4. Project-authored summaries under `docs/`.
5. Decompiled ROM or ADF-contained code only when redistributable documentation and available source do not explain the behavior.

If these sources disagree, stop and document the conflict rather than silently choosing a later platform model.

## API Index Policy

The generated API index must record the FD source, function version markers where available, and whether a function is part of the classic baseline, later classic compatibility, later classic reference material, or out of target. Missing FD data should be treated as a bootstrap problem before concluding that a library function is unavailable.
