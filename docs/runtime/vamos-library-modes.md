---
title: "Vamos Library Modes"
status: draft
depends_on:
  - "vamos-overview.md"
citations_used:
  - "S8"
---

# Vamos Library Modes

Purpose: Explain `vamos`, `amiga`, `auto`, `fake`, and `off` library modes.

Needed for:
- Choosing the correct strategy when a library is missing or partially supported.

Depends on:
- `vamos-overview.md`

Status: Draft.

Notes:
- Add guidance on when to fake a library and when that would hide real bugs.

## Summary

`Vamos` can handle libraries in `off`, `auto`, `vamos`, `amiga`, and `fake` modes [S8 L40-L55]. Those modes are one of the main reasons this project is viable: they let a run mix Python-implemented libraries, original Amiga libraries, and temporary stub behavior while we discover what a real application actually needs [S8 L18-L32].

## The Modes

`Vamos` defines the modes as follows [S8 L46-L55]:

- `off`: opening the library always fails
- `auto`: try a `vamos` library first, then an Amiga library
- `vamos`: only use a `vamos` library
- `amiga`: only use an original Amiga library
- `fake`: create a dummy library whose calls return `0` in `d0`

## Project Guidance

### `vamos`

Use `vamos` mode when:

- the library is already implemented well enough in Python,
- or the project is actively implementing that library as host-side logic.

This is mandatory for `exec.library` and `dos.library`. The upstream docs state that `vamos` is not able to run correctly if those libraries are not of type `vamos` [S8 L151-L163].

### `auto`

Use `auto` as the normal exploratory default for non-core libraries. It keeps the run flexible without forcing an all-Python or all-original-library decision too early.

### `amiga`

Use `amiga` when:

- a real target app clearly depends on original library behavior,
- a Python replacement is missing or inaccurate,
- and the required original library can be provided cleanly in the runtime tree.

This is especially relevant for compatibility work that is trying to answer, "is the missing behavior in our translation layer, or is it already present in the original library?"

### `fake`

Use `fake` only as a short-lived diagnostic tool. A fake library can help the app get past an early `OpenLibrary()` failure and expose the next real blocker [S8 L22-L32], but it can also create false progress because every dummy function returns a neutral value rather than real behavior.

The project should therefore treat `fake` mode as acceptable when:

- it is being used to reveal the next missing dependency,
- the resulting behavior is clearly documented as provisional,
- and no one mistakes "the app got further" for "the app is now supported."

### `off`

Use `off` when a library should fail clearly and immediately. This is useful when:

- the dependency is out of scope,
- a fallback path should be tested,
- or a misleading partial environment would create confusing symptoms.

## Versions And Path-Specific Overrides

`Vamos` also supports per-library version overrides and path-specific library sections [S8 L92-L105] [S8 L122-L149]. Those features are useful, but the project should use them sparingly. If a run needs a version lie or a path-specific library override, that choice should be visible in the documented run configuration rather than hidden in a broad default.

## Working Rule

When choosing a library mode, prefer the option that makes the first real incompatibility visible with the least deception:

1. `vamos` for behavior we truly implement,
2. `auto` for broad exploratory work,
3. `amiga` when original-library behavior is the thing being tested,
4. `fake` only to expose the next blocker,
5. `off` when fast failure is more honest than a misleading environment.
