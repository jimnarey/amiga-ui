---
title: "Sources"
status: reference
depends_on: []
citations_used: []
---

# Sources

This file is the external source registry for the documentation in `docs/`.

Project-authored documentation is authoritative for project-specific decisions. External references are for factual validation, historical behavior, API details, and source provenance.

## Reference Notation

Use numbered inline references in the body text, not per-file source lists.

### Format

- Basic form: `[S<n>]`
- With a granular locator: `[S<n> <locator>]`

Examples:

- `Workbench launches pass a WBStartup message rather than CLI argc/argv [S2 §WBStartup Message ¶1-4].`
- `Vamos uses the -V switch to define volumes [S7 L103-L113].`
- `The 3.2 NDK archive was published as NDK3.2.lha [S1].`

### Locator Rules

Prefer the narrowest locator that a reviewer can verify directly from the cited source.

Use these locator styles:

- `Lx-Ly`
  Use for GitHub file pages and other sources where line numbers are stable and visible.
- `§Heading ¶n`
  Use for prose web pages when the claim lives under a named section.
- `§Heading ¶n-m`
  Use when several consecutive paragraphs under the same heading support the claim.
- `p.n`
  Use for PDFs, books, or scans with stable page numbers.
- `p.n-m`
  Use for a page range.
- `tbl.n`, `fig.n`, `item n`
  Use when the source is best verified through a table, figure, or enumerated item.

### Citation Placement

- Put the reference at the end of the sentence or paragraph it supports.
- If one sentence contains several distinct factual claims from different sources, split the sentence or cite each claim separately.
- If a whole paragraph is derived from one source span, a single citation at the end of the paragraph is acceptable.

### Stability Rules

- Do not renumber existing sources casually.
- Add new sources by appending the next number.
- If a source URL changes materially, add a new source number instead of silently reusing the old one.
- Prefer exact source pages and exact file pages over site home pages.

## Registered Sources

| No. | Title | URL | Typical locator style | Notes |
| --- | --- | --- | --- | --- |
| `S1` | AmigaOS 3.2 NDK archive | https://aminet.net/dev/misc/NDK3.2.lha | `p.n`, archive-internal path, or none | Direct archive fetched into the docs cache. |
| `S2` | Workbench Library | https://wiki.amigaos.net/wiki/Workbench_Library | `§Heading ¶n-m` | Workbench API behavior and startup conventions. |
| `S3` | AmigaOS Manual: Workbench | https://wiki.amigaos.net/wiki/AmigaOS_Manual%3A_Workbench | `§Heading ¶n-m` | General Workbench behavior and concepts. |
| `S4` | AmigaOS Apps Development | https://wiki.amigaos.net/wiki/AmigaOS_Apps_Development | `§Heading ¶n-m` | Development overview and tool links. |
| `S5` | `dos.library` autodocs | https://developer.amigaos3.net/autodocs/dos.library/ | `§Heading ¶n-m` | Detailed DOS API and data model reference. |
| `S6` | Recommended reading for the Amiga Developer | https://developer.amigaos3.net/article/13-recommended-reading-amiga-developer | `§Heading ¶n-m` | Reading-priority and background guidance. |
| `S7` | `vamos` user documentation | https://github.com/jimnarey/amitools/blob/3b57f2052ee76c28bbc5e4256227f62dca7b1c9f/docs/vamos.md | `Lx-Ly` | Commit-pinned GitHub file page for the bootstrap checkout. |
| `S8` | `vamos` library documentation | https://github.com/jimnarey/amitools/blob/3b57f2052ee76c28bbc5e4256227f62dca7b1c9f/docs/vamos-lib.md | `Lx-Ly` | Commit-pinned GitHub file page for library behavior. |
| `S9` | `vamos` helper runner | https://github.com/jimnarey/amitools/blob/3b57f2052ee76c28bbc5e4256227f62dca7b1c9f/test/helper/runner.py | `Lx-Ly` | Useful for tracing and runtime invocation patterns. |
| `S10` | `vamos` sample config | https://github.com/jimnarey/amitools/blob/3b57f2052ee76c28bbc5e4256227f62dca7b1c9f/test/test.vamosrc | `Lx-Ly` | Useful as a configuration reference. |
| `S11` | `iTidy` source README | https://github.com/Kwezza/iTidy/blob/v1/README.md | `Lx-Ly` | Upstream app overview. |
| `S12` | `iTidy` manual | https://github.com/Kwezza/iTidy/blob/v1/docs/manual/iTidy.md | `Lx-Ly` | App behavior and usage details. |
| `S13` | `iTidy` source archive | https://github.com/Kwezza/iTidy/archive/refs/heads/v1.zip | none | Exact source archive used during bootstrap. |
| `S14` | Aminet `iTidy` package page | https://aminet.net/package/util/wb/iTidy | `item n` or named subsection | Metadata for the released binary package. |
| `S15` | Aminet `iTidy` archive | https://aminet.net/util/wb/iTidy.lha | none | Direct binary archive. |
| `S16` | Aminet `classact33` package page | https://aminet.net/package/dev/gui/classact33 | `item n` or named subsection | Metadata and contents listing for ClassAct 3.3. |
| `S17` | Aminet `classact33` archive | https://aminet.net/dev/gui/classact33.lha | none | Direct archive fetched by the helper script. |
| `S18` | Qt for X11 Requirements | https://doc.qt.io/qt-6.10/linux-requirements.html | `§Heading tbl.1` or `§Heading ¶n-m` | Confirms the `xcb` platform plugin used by Qt Widgets on X11. |
| `S19` | Qt Platform Abstraction | https://doc.qt.io/qt-6/qpa.html | `§Heading ¶n-m` | Defines `QT_QPA_PLATFORM` selection and documents `qminimal`. |
| `S20` | `Xvfb` manual page | https://xorg.freedesktop.org/archive/X11R7.5/doc/man/man1/Xvfb.1.html | `§Description ¶n-m` | Primary reference for the virtual X server used by the project. |
| `S21` | Running Weston | https://wayland.pages.freedesktop.org/weston/toc/running-weston.html | `§Heading item n` or `§Heading ¶n-m` | Documents the available Weston backends, including `headless`. |
| `S22` | `weston(1)` manual page | https://manpages.debian.org/testing/weston/weston.1.en.html | `§Heading ¶n-m` | Confirms `headless` backend behavior and Xwayland support. |
| `S23` | Wayland and Qt | https://doc.qt.io/qt-6.8/wayland-and-qt.html | `§Heading ¶n-m` | Reference for Qt Wayland client support. |
| `S24` | Icon Library | https://wiki.amigaos.net/wiki/Icon_Library | `§Heading ¶n-m` or `Lx-Ly` | Official overview of `.info` files, `DiskObject`, and icon library functions. |
| `S25` | AmigaOS Manual: Workbench Fundamentals | https://wiki.amigaos.net/wiki/AmigaOS_Manual%3A_Workbench_Fundamentals | `§Heading ¶n-m` | Official description of icon types and basic Workbench interaction. |
| `S26` | Intuition Library | https://wiki.amigaos.net/wiki/Intuition_Library | `§Heading ¶n-m` | Official overview of Intuition screens, windows, menus, gadgets, and requesters. |
| `S27` | Window Communication | https://wiki.amigaos.net/wiki/Window_Communication | `§Heading ¶n-m` | Official description of IDCMP, window events, and system versus application gadgets. |
| `S28` | Intuition Gadgets | https://wiki.amigaos.net/wiki/Intuition_Gadgets | `§Heading ¶n-m` | Official overview of gadget roles and GadTools as a higher-level helper library. |
| `S29` | `iTidy` Makefile | https://github.com/Kwezza/iTidy/blob/v1/Makefile | `Lx-Ly` | Build target, compiler, CPU target, and source-module list. |
| `S30` | `iTidy` `main_gui.c` | https://github.com/Kwezza/iTidy/blob/v1/src/main_gui.c | `Lx-Ly` | Launch mode, Workbench startup, and early runtime checks. |
| `S31` | `iTidy` `GUI/main_window.c` | https://github.com/Kwezza/iTidy/blob/v1/src/GUI/main_window.c | `Lx-Ly` | Main-window UI, menus, requesters, and deferred PATH initialization. |
| `S32` | `iTidy` `backup_lha.c` | https://github.com/Kwezza/iTidy/blob/v1/src/backup_lha.c | `Lx-Ly` | LhA detection, command construction, and archive creation behavior. |
| `S33` | `iTidy` `folder_scanner.c` | https://github.com/Kwezza/iTidy/blob/v1/src/folder_scanner.c | `Lx-Ly` | Recursive folder pre-scan and hidden-folder handling. |
| `S34` | `iTidy` `icon_types.c` | https://github.com/Kwezza/iTidy/blob/v1/src/icon_types.c | `Lx-Ly` | Icon metadata handling, icon-library version use, and PATH parsing. |
| `S35` | `iTidy` `icon_management.c` | https://github.com/Kwezza/iTidy/blob/v1/src/icon_management.c | `Lx-Ly` | `.info` scanning rules and scan-time exclusions. |
| `S36` | Tags | https://wiki.amigaos.net/wiki/Tags | `§Heading ¶n-m` | TagItem conventions and control-tag meanings. |
| `S37` | `exec.library` autodocs index | https://developer.amigaos3.net/autodocs/exec.library/ | `item n` | Overview of the Exec function surface. |
| `S38` | `OpenLibrary()` autodoc | https://developer.amigaos3.net/autodocs/exec.library/OpenLibrary.html | `§Heading ¶n-m` | Process-versus-task caveats around opening libraries. |
| `S39` | `AddTask()` autodoc | https://developer.amigaos3.net/autodocs/exec.library/AddTask.html | `§Heading ¶n-m` | Defines the low-level task model and its DOS limitations. |
| `S40` | `GetMsg()` autodoc | https://developer.amigaos3.net/autodocs/exec.library/GetMsg.html | `§Heading ¶n-m` | Message-port receive semantics. |
| `S41` | `WaitPort()` autodoc | https://developer.amigaos3.net/autodocs/exec.library/WaitPort.html | `§Heading ¶n-m` | Waiting semantics for message ports. |
| `S42` | `gadtools.library` autodocs index | https://developer.amigaos3.net/autodocs/gadtools.library/ | `item n` | Core GadTools function surface. |
| `S43` | `graphics.library` autodocs index | https://developer.amigaos3.net/autodocs/graphics.library/ | `item n` | Core drawing and raster operations. |
| `S44` | `utility.library` autodocs index | https://developer.amigaos3.net/autodocs/utility.library/ | `item n` | Utility helpers including tag functions. |
| `S45` | `iTidy` `file_directory_handling.c` | https://github.com/Kwezza/iTidy/blob/v1/src/file_directory_handling.c | `Lx-Ly` | Real-world `TagItem` use for icon save/update paths. |
| `S46` | IFFParse Library | https://wiki.amigaos.net/wiki/IFFParse_Library | `§Heading ¶n-m` | Official overview of `iffparse.library`, `IFFHandle`, streams, and context management. |
| `S47` | Parsing IFF | https://wiki.amigaos.net/wiki/Parsing_IFF | `§Heading ¶n-m` | Official explanation of `ParseIFF()`, `PropChunk()`, `FindProp()`, and parsing modes. |
| `S48` | `iTidy` `Settings/IControlPrefs.c` | https://github.com/Kwezza/iTidy/blob/v1/src/Settings/IControlPrefs.c | `Lx-Ly` | Shows `iffparse.library` use for `ENV:sys/icontrol.prefs`. |
| `S49` | `iTidy` `window_management.c` | https://github.com/Kwezza/iTidy/blob/v1/src/window_management.c | `Lx-Ly` | Shows `iffparse.library` use for `ENV:sys/font.prefs` and Workbench screen setup. |
| `S50` | Programming in the Amiga Environment | https://wiki.amigaos.net/wiki/Programming_in_the_Amiga_Environment | `§Heading ¶n-m` | High-level official overview of multitasking, memory protection, shared libraries, and dynamic memory behavior. |
| `S51` | Introduction to Exec | https://wiki.amigaos.net/wiki/Introduction_to_Exec | `§Heading ¶n-m` or `Lx-Ly` | Official overview of Exec tasking, dynamic memory allocation, and library loading behavior. |
| `S52` | Libraries | https://wiki.amigaos.net/wiki/Libraries | `§Heading ¶n-m` | Official overview of Amiga shared libraries and the broader library families. |
| `S53` | `LoadSeg()` autodoc | https://developer.amigaos3.net/autodocs/dos.library/LoadSeg.html | `§FUNCTION ¶n-m`, `§RESULT ¶n`, `§NOTES ¶n-m` | Primary reference for Amiga load modules and seglists. |
| `S54` | Exec Libraries | https://wiki.amigaos.net/wiki/Exec_Libraries | `§Heading ¶n-m` | Official explanation of library base pointers, vector tables, and open/close/expunge behavior. |
| `S55` | AmigaDOS Data Structures | https://wiki.amigaos.net/wiki/AmigaDOS_Data_Structures | `§Heading ¶n-m` | Official explanation of `Process`-side DOS data structures and cleanup behavior. |
| `S56` | `AllocVec()` autodoc | https://developer.amigaos3.net/autodocs/exec.library/AllocVec.html | `§FUNCTION ¶n-m`, `§WARNING ¶n-m` | Primary reference for task-context memory allocation behavior. |
| `S57` | User Interfaces | https://doc.qt.io/qt-6/topics-ui.html | `§Qt Widgets User Interfaces ¶n-m` or `§Comparison of UI Technologies tbl.1` | Official comparison of Qt Widgets and Qt Quick, including desktop suitability. |
| `S58` | PySide6 `QtWidgets` module index | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/index.html | `§Detailed Description ¶n-m`, `§Widgets ¶n-m`, `§Layouts ¶n-m` | Official overview of Qt Widgets classes, layouts, model/view, and custom widget structure. |
| `S59` | PySide6 `QMainWindow` | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html | `§Synopsis ¶n-m` or none | Official reference for menu bars, toolbars, dock widgets, and status bars in a main window. |
| `S60` | `QMenuBar` | https://doc.qt.io/qt-6/qmenubar.html | `§Properties`, `§Public Functions`, or none | Official reference for menu-bar behavior and the `nativeMenuBar` property. |
| `S61` | Threads and QObjects | https://doc.qt.io/qtforpython-6/overviews/qtdoc-threads-qobject.html | `§QObject Reentrancy ¶n-m`, `§Per-Thread Event Loop ¶n-m`, `§Signals and Slots Across Threads ¶n-m` | Official Qt threading rules for `QObject` and GUI event delivery. |
| `S62` | Qt Style Sheets | https://doc.qt.io/qtforpython-6/overviews/qtwidgets-stylesheet.html | `§Overview ¶n-m` | Official description of style-sheet behavior and precedence over conflicting widget property styling. |
| `S63` | PySide6 `QFileDialog` | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QFileDialog.html | `§Detailed Description ¶n-m` or none | Official reference for file and directory dialogs and their options. |
| `S64` | PySide6 `QWidget` | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html | `§Detailed Description ¶n-m` or none | Official reference for the base widget class, event handling, and painting behavior. |
| `S65` | Styles and Style Aware Widgets | https://doc.qt.io/qtforpython-6/overviews/qtwidgets-style-reference.html | `§Customizing a Style ¶n-m`, `§QStyle Functions ¶n-m` | Official guidance for style-aware custom drawing with `QStyle` and `QStyleOption`. |
| `S66` | Qt for Python tutorials | https://doc.qt.io/qtforpython-6/tutorials/ | `§Qt Widgets: Basic tutorials item n` | Official entry point for basic widget examples and tutorials. |
