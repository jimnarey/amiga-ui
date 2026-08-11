---
title: "iTidy Observed Behavior"
status: draft
depends_on:
  - "overview.md"
citations_used:
  - "S11"
  - "S12"
  - "S30"
  - "S31"
  - "S33"
  - "S34"
  - "S35"
---

# iTidy Observed Behavior

Purpose: Record what `iTidy` appears to do from a user and system point of view.

Needed for:
- Defining compatibility targets before implementation details.

## Confirmed User-Facing Behavior

The main workflow is straightforward: launch the app from Workbench, choose a target folder, pick ordering and recursion options, optionally enable backups, and start a run that rearranges icons and resizes drawers [S12 L79-L95]. The main window exposes the expected controls for folder selection, icon order, recursive cleanup, backup toggling, window-position policy, advanced settings, and settings save/load [S12 L99-L145] [S31 L121-L142].

The app also exposes two higher-level maintenance flows beyond simple tidying:

- default-tool analysis and repair for project icons whose launch tool is missing [S12 L213-L250]
- restore of earlier icon/layout backups created through the LhA path [S12 L254-L299]

## Confirmed Filesystem And Layout Behavior

The published docs repeatedly state that `iTidy` only changes Workbench `.info` files and drawer/window layout metadata, not ordinary user data files [S11 L150-L153] [S12 L5-L8]. That matches the app's scope as a layout and metadata utility rather than a general file manager.

On the scanning side, the source uses filesystem-level pattern matching for `.info` files instead of browsing every entry and deciding later [S35 L306-L346]. A separate pre-scan counts folders containing icons and respects the "skip hidden folders" preference by refusing folders whose own `.info` file is missing [S33 L126-L218]. This lines up with the manual's warning that some folders may be skipped unless hidden-folder filtering is turned off [S12 L354-L358].

## Confirmed Default-Tool Behavior

The manual says `iTidy` can scan for missing default tools, batch replace them, single-file replace them, and restore default-tool backups separately from icon-layout backups [S12 L223-L250]. The GUI code also builds the system PATH list after the main window opens, which suggests that default-tool validation is treated as a normal runtime feature rather than a purely static startup check [S31 L1196-L1212].

## Confirmed Backup Behavior

When icon backups are enabled, `iTidy` creates LhA archives of relevant `.info` files before making changes and later restores those archives through a dedicated restore window [S12 L118-L119] [S12 L256-L299]. The backup code looks for `LhA` in `C:LhA`, `SYS:C/LhA`, or `SYS:Tools/LhA`, then runs it through `Execute()` with `NIL:` handles [S32 L93-L119] [S32 L162-L195]. That means backup success depends on more than file I/O alone: command execution and command-path setup matter too.

## Confirmed Limitations And Visible Quirks

The upstream manual documents several behaviors that should not be mistaken for compatibility bugs in this project:

- Workbench may cache drawer geometry until windows are reopened or Workbench is restarted [S12 L309-L328]
- folders shown through Workbench's "All Files" view use temporary icons that `iTidy` will not process [S12 L348-L352]
- older icon-library versions on Workbench 3.0 or 3.1 can make OS3.5+ color icons appear visually misaligned even when the underlying positions are technically correct [S12 L314-L320]

## Source-Derived Behavior To Validate Against The Release Binary

Some useful details are visible in the source but should still be treated as "needs runtime confirmation" when assessing the released binary:

- the scanner explicitly skips `Disk.info` volume icons and "left out" backdrop icons [S35 L366-L395]
- CLI launch is allowed, but Workbench-only behaviors such as program-tooltype parsing are skipped in that mode [S30 L303-L309] [S30 L623-L638]
- PATH parsing is deferred until after the main window is open, which may affect when default-tool features become fully available [S31 L1196-L1212]
