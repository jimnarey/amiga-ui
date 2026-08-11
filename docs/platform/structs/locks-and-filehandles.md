---
title: "Locks And Filehandles"
status: draft
depends_on:
  - "../filesystem-and-launch.md"
  - "../library-cards/dos.library.md"
  - "wbarg.md"
citations_used:
  - "S1"
  - "S2"
  - "S5"
---

# Locks And Filehandles

Purpose: Explain Amiga filesystem handles, ownership, and common mistakes.

Needed for:
- Safe path handling and accurate Workbench argument processing.

## Summary

Amiga filesystem code uses locks and file handles as distinct concepts. For this project, the important part is that Workbench launch and AppMessage argument handling are lock-based. The `dos.library` overview describes the current directory itself as a lock and explains that `CurrentDir()` and `Lock()` are central to directory access [S5 §Path names and current directories ¶6-8].

## Locks Are Location Context

In Workbench startup and AppMessage argument passing, a lock is the stable location anchor and the filename is often only relative to that lock [S2 §WBStartup Message ¶10-16] [S2 §The AppMessage Structure ¶1-9]. That is why many Amiga examples first convert a lock into a path context before touching `wa_Name`.

The NDK examples show two common patterns:

- `NameFromLock()` followed by `AddPart()` to build a concrete path [S1 Examples/Backfill/Backfill.c L85-L93]
- `CurrentDir(lock)` followed by relative file operations and later restoration of the old directory [S1 DAControl+trackfile/DAControl/start.c L183-L195]

## Workbench-Owned Locks

The Workbench docs give a strict ownership warning: applications must never call `UnLock()` on a `wa_Lock`, because those locks belong to Workbench and are released when the startup message is replied [S2 §WBStartup Message ¶14]. The same warning also applies to the program's initial current-directory lock as returned by the first `CurrentDir()` call in the Workbench environment [S2 §WBStartup Message ¶14-16].

This is one of the easiest compatibility details to get subtly wrong. A host-side translation that treats these as ordinary caller-owned locks may appear to work and then fail on process exit.

## File Handles Are Different

Workbench launch also interacts badly with assumptions about file handles. A Workbench-started program does not automatically have valid `stdin`, `stdout`, and `stderr` handles [S2 §Launching ¶2-4]. So when a program expects CLI-style file handles, the issue is not just "path handling" but also the distinction between:

- lock-based location context,
- ordinary opened file handles,
- and absent standard streams.

## Working Rule

For this project, lock handling should follow three conservative rules:

1. do not treat a `WBArg` lock as caller-owned,
2. restore old current-directory state after temporary `CurrentDir()` changes,
3. keep lock semantics separate from plain string-path handling for as long as possible.
