---
title: "Deferred Decisions"
status: draft
depends_on:
  - "../architecture/gui-strategy.md"
  - "../runtime/headless-gui.md"
  - "../assets/libraries-and-toolkits.md"
citations_used:
  - "S8"
  - "S16"
  - "S20"
  - "S21"
  - "S22"
  - "S23"
  - "S31"
  - "S32"
  - "S48"
  - "S49"
---

# Deferred Decisions

Purpose: Track decisions intentionally postponed until more evidence exists.

Needed for:
- Avoiding accidental drift in project direction.

Depends on:
- `../architecture/gui-strategy.md`
- `../runtime/headless-gui.md`
- `../assets/libraries-and-toolkits.md`

Status: Draft.

Notes:
- Include why each decision was deferred and what event should reopen it.

## Summary

Several major project choices are now settled: the host GUI toolkit is PySide6 with Qt Widgets, Linux is the primary host baseline, and `Xvfb` is the standard headless test display path. The remaining deferred decisions are the ones that genuinely depend on evidence from real app runs rather than on more up-front theorizing.

## Deferred Items

### 1. The First Canonical Prepared `sys:` Tree

Holding decision:
Build the first serious `sys:` tree empirically from app pressure rather than trying to declare a final canonical tree in advance.

Why it is deferred:
The current `iTidy` code already reaches into several different runtime areas: Workbench screen/window setup, `ENV:sys/icontrol.prefs`, `ENV:sys/font.prefs`, `S:Startup-Sequence`, `S:User-Startup`, and optional `LhA` command locations [S31 L1006-L1085] [S31 L1196-L1212] [S32 L93-L119] [S48 L214-L265] [S49 L305-L347]. The minimum useful tree should therefore be discovered by runs, not guessed.

Reopen when:
The first repeatable `iTidy` run reaches a clear blocker caused by a missing file, assign, or command rather than by missing host-side semantics.

### 2. Per-Library Policy For Non-Core Libraries

Holding decision:
Start exploratory runs with flexible library policy and tighten each non-core library to `vamos`, `amiga`, `auto`, or a documented temporary fake only when evidence forces the choice.

Why it is deferred:
Upstream `vamos` is explicitly designed to mix modes per library [S8 L40-L55]. Locking every non-core library decision in advance would hide the useful signal that the first real app runs will provide.

Reopen when:
The same library is implicated repeatedly enough that a documented long-term policy is more honest than ad hoc per-run choices.

### 3. Breadth Of Add-On Toolkit Support

Holding decision:
Keep ClassAct 3.3 staged and documented, but do not yet promise broad add-on toolkit compatibility.

Why it is deferred:
ClassAct is present because real apps may need it, not because it is part of the minimal Workbench contract [S16]. Until a concrete target depends on it, promising broad toolkit support would create scope without evidence.

Reopen when:
The next selected real application after `iTidy`, or a later `iTidy` feature branch, demonstrably requires ClassAct behavior.

### 4. Secondary Headless Or Cross-Platform Display Paths

Holding decision:
Standardize on `Xvfb` for automated Linux runs now and defer Weston headless, Wayland-specific tuning, and non-Linux host support.

Why it is deferred:
`Xvfb` already provides the needed virtual X11 surface for Qt Widgets automation [S20 §Description ¶1-2]. Weston headless and Wayland client paths are real options, but they add operational variability that the project does not currently need [S21 §Running Weston on a headless system item 1] [S22 §DESCRIPTION ¶1-4] [S23 §Qt Wayland Client ¶1-3].

Reopen when:
Linux plus `Xvfb` is stable enough that alternative display backends would solve a demonstrated problem rather than just offer variety.

### 5. The Second And Third Reference Applications

Holding decision:
Keep the repo ready for additional apps, but choose them only after one app has a documented useful execution path.

Why it is deferred:
The project already has enough real pressure from `iTidy` to exercise Workbench launch, native GUI layers, path handling, prefs parsing, and optional external tools. Adding more targets before one path is working would mostly multiply uncertainty.

Reopen when:
`iTidy` has reached a natural milestone such as stable main-window launch, a working folder-selection path, or a documented hard scope boundary.

## Working Rule

A decision belongs in this file only if deferring it is intentional and healthy. If the team already knows the answer, it should be documented elsewhere as a current project rule rather than left here as pretend uncertainty.
