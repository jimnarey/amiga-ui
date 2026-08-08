---
title: "WBStartup"
status: draft
depends_on:
  - "../filesystem-and-launch.md"
citations_used:
  - "S1"
  - "S2"
---

# WBStartup

Purpose: Explain the Workbench startup message passed to launched applications.

Needed for:
- Correct handling of Workbench-launched apps.

Depends on:
- `../filesystem-and-launch.md`

Status: Draft.

Notes:
- Include ownership rules for contained locks and common startup code behavior.

## Summary

`WBStartup` is the Workbench launch message delivered to a newly started application. The NDK header defines it as a standard Exec message plus process, segment, argument-count, tool-window, and argument-list fields [S1 Include_H/workbench/startup.h L21-L28]. The Workbench library documentation adds the behavioral rule that compiler startup code often passes a pointer to this message through `argv` while setting `argc` to zero [S2 §WBStartup Message ¶1-2].

## Structure

The structure fields are:

- `sm_Message`
- `sm_Process`
- `sm_Segment`
- `sm_NumArgs`
- `sm_ToolWindow`
- `sm_ArgList` [S1 Include_H/workbench/startup.h L21-L28]

The Workbench documentation explains their intended meaning:

- `sm_Message` is the underlying Exec message,
- `sm_Process` identifies the created process,
- `sm_Segment` refers to the loaded code,
- `sm_NumArgs` counts the arguments,
- `sm_ArgList` points to the `WBArg` array [S2 §WBStartup Message ¶3-9]

## Practical Meaning

For compatibility work, the two most important fields are:

1. `sm_NumArgs`
2. `sm_ArgList`

Those determine what Workbench objects were used to start the application. The first `WBArg` is always the tool itself, and further entries represent selected projects or other selected icons depending on how launch occurred [S2 §WBStartup Message ¶10-13].

## Startup-Code Convention

The Workbench docs explicitly note that startup code commonly places the `WBStartup` pointer in `argv` and sets `argc` to zero [S2 §WBStartup Message ¶1-2]. That convention is important because many programs branch immediately on whether `argc == 0` to decide whether they were launched from Workbench or from the Shell.

The NDK examples reflect this split too: some examples provide a `wbmain(struct WBStartup *wbs)` entry point alongside a normal `main()` path [S1 Examples/Checkboxes.c L291-L295] [S1 Examples/Connect.c L191-L195].

## Ownership Boundary

Although the contained `WBArg` locks are discussed more fully in the `WBArg` and lock docs, the key ownership rule belongs here too: the Workbench startup message and its lock payload are Workbench-owned data. The documentation warns that Workbench unlocks those locks when the startup message is replied by startup code, not when the application chooses to release them [S2 §WBStartup Message ¶14-16].

## Working Rule

If an application is being launched "as if from Workbench," it is not enough to pass filenames. The project must provide a plausible `WBStartup` message with:

- the correct argument count,
- a correctly ordered `WBArg` array,
- and Workbench-style lock ownership semantics.
