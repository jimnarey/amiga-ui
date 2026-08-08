---
title: "Tracing And Debugging"
status: draft
depends_on:
  - "vamos-overview.md"
  - "headless-gui.md"
citations_used:
  - "S7"
  - "S9"
---

# Tracing And Debugging

Purpose: Describe how to collect useful diagnostics from `vamos` runs.

Needed for:
- The error-driven development loop.

Depends on:
- `vamos-overview.md`
- `headless-gui.md`

Status: Draft.

Notes:
- Include logging flags, expected log files, and what to capture for model consumption.

## Summary

Every meaningful `vamos` run in this project should produce enough evidence for the next iteration decision. `Vamos` itself supports verbose logging, channel-based logging, log-file output, and deep memory tracing [S7 L492-L599]. The `amitools` test helper also shows a practical pattern for repeatable execution: build the `vamos` command explicitly, insert `--` before the Amiga program, disable timestamps when useful, and capture return code, stdout, stderr, and an optional `vamos.log` file [S9 L172-L247].

## Minimum Capture Set

For an app run that is expected to teach the model something, capture at least:

- the exact `vamos` invocation
- return code
- stdout
- stderr
- any `vamos` log file
- any files or metadata changed by the run

This is the minimum evidence needed to tell whether a change:

- fixed the current blocker,
- moved the failure boundary,
- or only changed symptoms.

## Logging Levels

### Default Exploration

For the first pass on a failure, prefer normal stdout/stderr plus targeted library logging. `Vamos` documents `-v` for more general runtime information, `-l` for channel-based logging, and `-L` to redirect logs to a file [S7 L492-L532]. In practice, this means the project should begin with:

- normal process output
- selected library channels such as `dos` or `exec`
- file-based logs when the output is long enough that it should be inspected separately

### Deep Inspection

Use memory tracing only when ordinary library and process logs are not enough. `Vamos` documents `-t` and `-T` for memory tracing and warns that this is slow [S7 L534-L599]. Deep tracing is therefore a debugging escalator, not a default mode.

## Repeatability Rules

The project should favor stable, machine-reviewable output:

1. Run the same command again after each change.
2. Keep the mounted environment explicit.
3. Prefer file-based logs for long traces.
4. Suppress timestamps when the tooling path allows it, since the helper runner shows that `--no-ts` can make output easier to diff across iterations [S9 L169-L176].

## Host-Side GUI Checks

Before blaming an Amiga-side compatibility change for a GUI failure, verify that the host GUI path is healthy. The project smoke-test launcher:

```bash
./tests/run_gui_smoke_test.sh
```

should be treated as a quick sanity check for:

- the Python environment
- PySide6 imports
- the `Xvfb` wrapper
- the basic Qt Widgets window path

If this smoke test fails, the problem is probably outside the Amiga application logic.

## Suggested Capture Pattern

For a serious app-porting iteration, the terminal transcript or note should answer these questions in order:

1. What command was run?
2. What was the first actionable failure?
3. Which layer did it appear to belong to?
4. What changed before the rerun?
5. What is the new stopping point?

If those five answers are recorded, another model or a later human reviewer can usually resume the work without re-discovering the same failure chain.
