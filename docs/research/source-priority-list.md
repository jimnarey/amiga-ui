---
title: "Source Priority List"
status: draft
depends_on:
  - "../assets/documentation-sources.md"
  - "../runtime/vamos-overview.md"
  - "../apps/itidy/overview.md"
citations_used:
  - "S1"
  - "S2"
  - "S5"
  - "S6"
  - "S7"
  - "S8"
  - "S11"
  - "S12"
  - "S13"
  - "S15"
  - "S16"
  - "S17"
  - "S24"
  - "S26"
  - "S46"
---

# Source Priority List

Purpose: Rank upstream sources so contributors know what to consult first.

Needed for:
- Efficient documentation writing and debugging.

## Summary

Not all upstream sources are equally useful for this repo. The project should read the most decision-shaping and most falsifiable sources first, and only then widen out into broader conceptual material. This is especially important for small-context models, where loading the wrong source family too early wastes both context and time.

## Priority Order

### 1. Project-Authored Docs

Consult the authored docs in `docs/` first for current project decisions, repo policy, and terminology. These files are the authoritative layer for this repository's chosen approach. External sources validate facts; they do not override settled project decisions silently.

### 2. Pinned `vamos` Upstream Docs

When the question is about runtime behavior, configuration, path mapping, or library modes, the first external sources should be the pinned `vamos` docs in the source registry [S7] [S8]. They are the closest thing to a runtime contract for this project.

Use them first for questions such as:

- how `vamos` wants volumes and assigns expressed,
- how library modes behave,
- what upstream explicitly does and does not promise.

### 3. Real Target-App Documentation And Source

When the question is "what does this app actually expect?", the next priority is the target app's own manual, README, and then its specific source files [S11] [S12]. The public docs explain the intended user-facing behavior; the source resolves ambiguity when the docs are broad or stale.

Working rule:

- README and manual first for feature intent,
- specific source file second for exact runtime expectations,
- comments last when they conflict with executable behavior.

### 4. NDK Headers And Autodocs

When the question is about a concrete API contract, structure layout, tag meaning, or function lifetime rule, prefer the NDK and autodoc material over higher-level summaries [S1] [S5]. These are the sources most likely to answer "what does this field mean?" or "who owns this memory?" without extra interpretation.

### 5. Focused Official Concept Pages

When the question is architectural rather than per-function, use narrowly targeted official concept pages such as:

- Workbench behavior [S2]
- icon semantics [S24]
- Intuition behavior [S26]
- structured IFF parsing [S46]

Use these after the lower-level contract sources, not before them.

### 6. Package Pages And Archives

Package pages and release archives are useful for provenance, release contents, and acquisition checks, not for fine-grained API semantics. That is why the `iTidy` and ClassAct archive/package sources sit lower in the stack for design work even though they remain important operational references [S13] [S15] [S16] [S17].

## Conflict Rules

When sources disagree, prefer:

1. project-authored docs for repository policy,
2. pinned `vamos` docs for `vamos` behavior,
3. target-app source over target-app README or manual for exact implementation behavior,
4. NDK headers and autodocs over wiki summaries for API and struct contracts,
5. package pages and archives only for provenance or contents checks.

The Amiga developer reading guide is useful here as a general sanity check because it points readers toward grounding themselves in primary technical material rather than relying on folklore [S6].

## Working Rule

Choose the narrowest source that can falsify the claim you are about to make. If a claim can be checked in one autodoc page or one pinned source file, do not load an entire broader reference chapter first.
