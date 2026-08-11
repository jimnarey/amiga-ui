---
title: "Vamos Gaps"
status: draft
depends_on:
  - "vamos-overview.md"
  - "../architecture/compatibility-scope.md"
  - "../apps/itidy/dependencies.md"
citations_used:
  - "S7"
  - "S8"
  - "S30"
  - "S31"
  - "S32"
  - "S34"
  - "S48"
  - "S49"
---

# Vamos Gaps

Purpose: Track known `vamos` limitations relevant to GUI application support.

Needed for:
- Prioritizing implementation work and triaging failures.

## Summary

The project should treat `vamos` gaps as a practical compatibility backlog, not as a complaint that upstream is "missing features." Upstream already states that `vamos` is aimed mainly at console-style software, is not a full machine emulator, and is not the right base for direct hardware-access workloads [S7 L5-L17]. Those are design boundaries. The work here is to identify what must be added on top of that base so selected Workbench GUI applications can run usefully.

## Boundary Gaps We Should Not Fight

Three upstream boundaries should remain intact:

1. `vamos` is not a full UAE-style desktop emulator [S7 L16-L17].
2. direct hardware access is out of scope [S7 L12-L14].
3. core library handling may legitimately mix `vamos`, original Amiga, and fake libraries depending on the experiment [S8 L18-L32] [S8 L40-L55].

These are not bugs to "fix away." They are the reason the repo needs a translation layer, explicit runtime preparation, and careful target selection.

## Project-Relevant Gap Classes

### Workbench Launch Semantics

The first gap class is Workbench-style process launch rather than plain CLI execution. The current `iTidy` source checks for `_WBenchMsg`, treats `argc == 0` as Workbench launch, and parses its own icon tooltypes only in that mode [S30 L623-L687] [S30 L287-L389]. A run that merely starts the binary from a shell-like context can therefore answer useful early questions, but it does not prove Workbench compatibility.

This means the project still needs a believable model for:

- `WBStartup` contents,
- current-directory behavior derived from `WBArg` locks,
- icon/tooltype lookup during launch,
- and eventually the broader Workbench message model.

### GUI And Public-Screen Behavior

The second gap class is native GUI semantics. `iTidy` locks the Workbench screen, asks GadTools for `VisualInfo`, builds menus differently for Workbench 2.x and 3.x, opens a window with specific IDCMP flags, and only then marks the application ready [S31 L176-L227] [S31 L1006-L1085] [S31 L1188-L1212]. `Vamos` by itself does not turn those expectations into a visible host window system [S7 L5-L10].

That gap is larger than "one missing function." It includes:

- screen and window identity,
- menu and gadget construction,
- event delivery,
- and translation of Amiga GUI intent into host-side Qt behavior.

### Runtime Tree And System File Expectations

The third gap class is the difference between a runnable binary and a believable Amiga runtime tree. `iTidy` reads `ENV:sys/icontrol.prefs`, reads `ENV:sys/font.prefs`, parses `S:Startup-Sequence` and `S:User-Startup`, and expects `PROGDIR:`-relative paths to behave meaningfully [S48 L214-L265] [S49 L305-L347] [S34 L1275-L1318].

This is exactly the kind of behavior that falls between simplistic "binary launches" and true application usefulness. The project therefore needs deliberate policy for:

- which files belong in the prepared `sys:` tree,
- which missing files should fail,
- which can fall back cleanly,
- and which should be synthesized or translated on the host side.

### Non-Core Library Coverage

The fourth gap class is library support beyond the `vamos` baseline. Upstream library modes are flexible by design [S8 L40-L55], but real target apps still force concrete decisions. The current `iTidy` tree touches:

- `icon.library` through icon loading and tooltypes [S30 L314-L389],
- GUI libraries such as Intuition and GadTools through its main window path [S31 L1006-L1085],
- `iffparse.library` through preference-file parsing [S48 L203-L266] [S49 L297-L347].

The gap is therefore not just "implement more libraries." It is "decide, library by library, whether the next honest move is `vamos`, `amiga`, `auto`, or a short-lived fake."

### External Command And Helper Dependencies

The fifth gap class is secondary dependencies that live outside the immediate library surface. `iTidy` searches for `LhA` in common command locations and then shells out through `Execute()` when backup features are enabled [S32 L93-L119] [S32 L162-L195]. That means some feature failures will not be solved by GUI work alone.

These are especially important because they are often feature-specific rather than launch-blocking:

- they may be postponed intentionally,
- but they still need to be documented as real compatibility gaps rather than ignored.

### Device, Peripheral, And Secondary Subsystem Pressure

The sixth gap class is pressure from subsystems that are adjacent to the OS API surface but can easily widen into broad emulation work. `Vamos` does not present itself as a general device or desktop-session emulator; it presents itself as an API-level runtime with explicit direct-hardware boundaries [S7 L5-L17]. The project therefore needs to distinguish carefully between:

- a narrow API-level feature reached through normal libraries or devices,
- and a blocker that is really asking for broad audio, printer, serial, peripheral, or desktop integration support.

The presence of a sound- or device-related API name does not automatically make a feature out of scope. What matters is whether the feature is secondary and API-level, or whether it is expanding into subsystem emulation as a real implementation obligation.

## Current Triage Order

The repo should treat the present gap order as:

1. launch semantics and path/runtime-tree setup,
2. visible window/menu/requester/event behavior,
3. non-core library choices forced by the current app,
4. secondary prefs and polish paths such as font/theme parsing,
5. feature-specific helpers such as backup tooling,
6. stop-rule triage for device/peripheral/subsystem pressure.

That ordering matches both upstream `vamos` scope and the concrete way the first target app is written.

## Working Rule

When a run fails, ask two questions before changing code:

1. Is this a documented upstream boundary that the project should respect?
2. If not, does the missing behavior belong in repo-owned runtime preparation, repo-owned host translation, or a targeted library implementation?

If those two questions are answered explicitly, the next fix usually becomes much smaller.
