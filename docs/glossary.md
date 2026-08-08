---
title: "Glossary"
status: draft
depends_on:
  - "platform/amiga-primer.md"
  - "platform/data-types-and-conventions.md"
citations_used:
  - "S1"
  - "S2"
  - "S5"
  - "S24"
  - "S25"
---

# Glossary

Purpose: Define recurring Amiga and project terms in one compact place.

Needed for:
- Small-context models that need quick definitions without opening large manuals.

Depends on:
- `platform/amiga-primer.md`
- `platform/data-types-and-conventions.md`

Status: Draft.

Notes:
- Add concise entries for BPTR, BSTR, lock, drawer, tool, project, assign, segment, `WBStartup`, and `DiskObject`.

## Terms

`APTR`
An untyped absolute pointer used widely in Amiga APIs. It is a real byte-addressed pointer, unlike `BPTR` [S1 Include_H/exec/types.h L70-L77].

`assign`
An AmigaDOS logical name that maps to one or more Amiga paths, commonly used for names such as `c:`, `libs:`, or `s:` in runtime environments [S5 §Path names and current directories ¶1-9].

`BPTR`
A BCPL-style longword pointer used by AmigaDOS structures. It stores the byte address shifted right by two and must be converted with `BADDR()` when treated as a normal address [S1 Include_H/dos/dos.h L130-L143].

`BSTR`
A BCPL-style string pointer. The pointed-to string stores its length in the first byte rather than relying only on NUL termination [S1 Include_H/dos/dos.h L132-L147].

`DiskObject`
The in-memory representation of a Workbench `.info` file. It carries icon type, Tool Types, default tool, icon position, and optional drawer or tool metadata [S24 L13-L29] [S24 L48-L75].

`drawer`
The Workbench term for a directory-like container shown as an icon and window rather than just as a pathname entry [S25 §Icons ¶1-6].

`lock`
An AmigaDOS location handle used for directories and other filesystem objects. Locks are central to current-directory state and to Workbench argument passing [S5 §Path names and current directories ¶6-8].

`project`
A Workbench icon type representing a data file or similar object that is normally launched through a default tool rather than by executing the file directly [S2 §Argument Passing in Workbench ¶2-4].

`segment`
In Workbench startup context, the loaded code segment reference handed to the launched program through `WBStartup.sm_Segment` [S1 Include_H/workbench/startup.h L21-L28].

`tool`
A Workbench icon type representing an executable program launched directly by Workbench [S2 §Argument Passing in Workbench ¶2-4].

`Tool Types`
Free-format strings stored in icon metadata and used to carry application-specific configuration settings in Workbench icons [S24 L48-L53].

`WBArg`
The pair of `wa_Lock` and `wa_Name` used by Workbench to describe one launched or selected object [S1 Include_H/workbench/startup.h L30-L33].

`WBStartup`
The Workbench startup message delivered to a program launched from Workbench instead of ordinary CLI arguments [S2 §WBStartup Message ¶1-2] [S1 Include_H/workbench/startup.h L21-L28].
