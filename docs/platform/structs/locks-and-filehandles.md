# Locks And Filehandles

Purpose: Explain Amiga filesystem handles, ownership, and common mistakes.

Needed for:
- Safe path handling and accurate Workbench argument processing.

Depends on:
- `../filesystem-and-launch.md`
- `../library-cards/dos.library.md`

Primary sources:
- AmigaOS 3 Developer: `dos.library` autodocs
- AmigaOS Documentation Wiki: Workbench Library

Status: Stub.

Notes:
- Include the rule that Workbench-owned locks must not be unlocked by the application.
