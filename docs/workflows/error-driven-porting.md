# Error Driven Porting

Purpose: Define the core development loop for getting GUI apps running one missing feature at a time.

Needed for:
- Day-to-day implementation work.

Depends on:
- `../runtime/tracing-and-debugging.md`
- `../apps/itidy/runbook.md`

Status: Draft.

Notes:
- Capture the loop: run app, capture failure, identify missing behavior, implement one fix, rerun, document result.

## Summary

The project should advance by repeatedly running a real application under a controlled `vamos` setup, capturing the first meaningful failure, implementing the smallest plausible fix, and then rerunning immediately. This is the preferred workflow because `vamos` already provides a configurable execution environment, logging/tracing features, and a natural command boundary between host options and the Amiga program being launched [S7 L64-L77] [S7 L81-L96] [S9 L172-L247].

## Why This Workflow Fits The Project

The first target application, `iTidy`, is a good match for this approach because it is a Workbench utility with clearly described behaviors: it arranges icon layouts, resizes drawer windows, validates default tools, and optionally creates LhA backups [S11 L15-L32] [S12 L43-L50]. Those are all behaviors that can fail in relatively isolated ways. A missing path mapping, a missing library function, a requester problem, or incorrect `.info` handling can each be treated as a narrow defect rather than as proof that the whole project architecture is wrong.

## Standard Loop

### 1. Prepare A Controlled Runtime

Start with a predictable `vamos` configuration and a minimal, explicit filesystem view. `Vamos` expects volumes, assigns, path settings, and runtime options to be configured either on the command line or in `.vamosrc`-style config files [S7 L64-L96]. Even the simple test config shipped with `amitools` shows the basic shape: define volumes, set up a `sys:` assign, and provide a command path [S10 L1-L14].

For this project, the runtime should be set up so that:

- the target binary is mounted predictably
- the needed assets and support files are mounted predictably
- the same run can be repeated without hidden host-state differences

### 2. Run The Real Program

Run the actual Amiga binary, not a hand-written synthetic approximation, unless a smaller reproduction is needed later. The existing `amitools` helper shows the basic invocation pattern: assemble `vamos` arguments, append `--`, then pass the Amiga-side program name and arguments [S9 L172-L197].

### 3. Capture The First Actionable Failure

Capture:

- return code
- stdout
- stderr
- any `vamos` log output
- any changed files or metadata

The same helper code shows both stdout/stderr capture and optional `vamos.log` generation [S9 L199-L247]. The project should prefer the first actionable failure, not the longest list of downstream symptoms.

### 4. Classify The Failure

Before changing code, classify the failure into one of a small number of buckets:

- path or assign problem
- missing library or wrong library mode
- missing function or incorrect return value
- incorrect struct or message handling
- requester/window/layout behavior mismatch
- host integration problem
- unsupported out-of-scope behavior

This classification step matters because `vamos` can operate with original Amiga libraries, Python `vamos` libraries, or fake libraries depending on configuration [S8 L18-L55]. Choosing the right remedy depends on knowing which layer failed first.

### 5. Implement One Fix

Implement the narrowest change that plausibly resolves the classified failure:

- add or correct a single library function
- improve one struct translation
- add one path/assign mapping
- supply one missing dependency
- translate one UI behavior into the host layer

Do not combine unrelated fixes in the same iteration unless the first defect cannot even be observed without them. The point of the loop is to keep cause and effect legible.

### 6. Rerun Immediately

Rerun the same invocation as soon as the change is in place. If the same failure persists, the fix was incomplete or aimed at the wrong layer. If a new earlier failure appears, update the diagnosis. If a later failure appears, record the previous issue as improved and move to the next blocker.

### 7. Record The Result

Update the relevant project docs with:

- what failed
- how it was diagnosed
- what changed
- what the new stopping point is

This is part of the workflow, not optional cleanup. The project is intentionally designed for small-context models, so each resolved or deferred failure should leave a short, readable trace.

## Working Rules

### Prefer Real App Pressure Over Abstract Completeness

Do not try to “finish Intuition” or “finish Workbench support” in the abstract. Implement the exact missing behavior needed to get the next real target action working.

### Prefer Host-Visible Evidence

When possible, validate a fix through host-visible evidence:

- the app opens further than before
- a requester now appears
- a `.info` file change is now correct
- a backup archive is now created
- a default tool scan now returns plausible results

For `iTidy`, these visible milestones are especially useful because the app explicitly limits itself to Workbench metadata and layout operations rather than modifying ordinary user data files [S11 L150-L153] [S12 L5-L8].

### Stop At Out-Of-Scope Boundaries

If the first blocker is actually direct hardware dependence or another full-emulation problem, stop and mark it clearly. `Vamos` itself documents that direct hardware-access software is outside its intended model [S7 L12-L17], and the project should not hide that by piling abstraction on top of the wrong target.

## Success Condition For One Iteration

An iteration is successful when all of the following are true:

1. The failure before the change was concrete and reproducible.
2. The implemented change was narrow enough to explain.
3. The rerun produced a better result or a clearer next blocker.
4. The new state was documented.

If those conditions are met, the project can make steady forward progress even when the overall compatibility target is still far away.
