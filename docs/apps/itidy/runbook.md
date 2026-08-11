---
title: "iTidy Runbook"
status: draft
depends_on:
  - "dependencies.md"
  - "../../workflows/error-driven-porting.md"
  - "../../runtime/tracing-and-debugging.md"
  - "../../runtime/vamos-path-mapping.md"
  - "../../runtime/workbench-integration-boundaries.md"
  - "../../host-gui/README.md"
  - "../../workflows/external-helpers-and-shellouts.md"
citations_used:
  - "S7"
  - "S9"
  - "S11"
  - "S12"
  - "S30"
  - "S31"
---

# iTidy Runbook

Purpose: Define the exact procedure for running and debugging `iTidy`.

Needed for:
- Repeatable failure capture during development.

Depends on:
- `dependencies.md`
- `../../workflows/error-driven-porting.md`
- `../../runtime/tracing-and-debugging.md`
- `../../runtime/vamos-path-mapping.md`
- `../../runtime/workbench-integration-boundaries.md`
- `../../host-gui/README.md`
- `../../workflows/external-helpers-and-shellouts.md`

Status: Draft.

Notes:
- Include expected assets, command lines, logs, and output artifacts.

## Summary

The default investigation order for `iTidy` is:

1. prove the host Python and GUI path is healthy;
2. run the released Amiga binary under a minimal explicit `vamos` environment;
3. fix the first real blocker;
4. graduate from CLI-style probing to Workbench-style launch semantics as soon as basic loading works.

This order matches the app's design. The source makes clear that `iTidy` distinguishes Shell and Workbench launch, while the user docs define the normal interaction flow through the GUI and Workbench icon system [S12 L79-L95] [S30 L277-L380] [S30 L623-L687].

## What To Run

Use the released app files under `amiga_apps/itidy1classic/binary/extracted/` as the default runtime target. Use the unpacked source tree under `amiga_apps/itidy1classic/source/` for diagnosis and implementation clues, not as proof that the shipped binary behaves identically.

## Host Preflight

Before touching `vamos`, run the host-side checks:

```bash
uv sync
./check_dependencies.sh
uv run python tests/run_gui_smoke_test.py
```

If `uv` cannot write to its normal cache location in a restricted environment, run it with `UV_CACHE_DIR` redirected to a writable location such as `/tmp/uv-cache`.

The smoke test is not an `iTidy` test. It only proves that the host Python, PySide6, and `Xvfb` path are alive before Amiga-side debugging begins.

## Required Runtime Inputs

Every serious `iTidy` run needs:

- the `iTidy` release files from `amiga_apps/itidy1classic/binary/extracted/`
- a prepared host directory that will be mapped as `sys:`
- any required support content under that runtime tree, especially `C:`, `S:`, `Libs:`, `Devs:`, and writable locations for logs and backups
- a test directory containing real `.info` files, not just plain files or Workbench temporary pseudo-icons [S12 L348-L352]

Raw ADF files are not enough on their own for `vamos`; they are reference media, not a directly mountable directory tree.

## Baseline Shell-Launch Probe

Use Shell-style launch first to answer the simplest questions: does the binary load, do the volume and assign mappings make sense, and which library or path problem appears first? `Vamos` expects explicit volume, assign, path, and config settings to be provided either on the command line or through a config file, and the helper code in `amitools` shows the standard `vamos ... -- program` command shape plus log capture [S7 L79-L117] [S7 L150-L237] [S9 L172-L247].

Template command:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run vamos -S \
  -V app:/absolute/path/to/amiga_apps/itidy1classic/binary/extracted \
  -V sys:/absolute/path/to/prepared/sys \
  -V work:/absolute/path/to/runtime-scratch \
  -a c:sys:C \
  -a libs:sys:Libs \
  -a s:sys:S \
  -a l:sys:L \
  -a devs:sys:Devs \
  -p c: \
  --cwd app: \
  -C 68000 \
  -m 2048 \
  -H abort \
  -P \
  -l dos:info,exec:info \
  -L work:vamos.log \
  app:iTidy
```

Project rules for this baseline:

- use `-S` so developer-local `.vamosrc` state cannot leak in [S7 L81-L94]
- use explicit volumes and assigns rather than `root:` shortcuts [S7 L102-L169]
- use `-H abort` so out-of-scope hardware access fails honestly [S7 L334-L365]
- keep the CPU at `68000` first because that matches the upstream build target [S29 L24-L30]

## Interpreting The First Probe

CLI launch is expected to be incomplete. The source explicitly skips Workbench-only tooltype parsing when no `WBStartup` message is present [S30 L303-L309] [S30 L623-L638]. That means a Shell-style probe is successful if it gets far enough to reveal:

- missing libraries,
- broken assigns,
- bad path handling,
- missing command execution support,
- or early GUI/window failures.

It is not meant to be the final correctness test.

## Workbench-Style Probe

Once basic loading is working, the next target is a Workbench-like launch fixture. `iTidy` checks for `_WBenchMsg`, reads tooltypes from its own icon, and changes to the program directory before looking up the icon data [S30 L314-L380] [S30 L623-L687]. A serious compatibility run therefore needs to provide:

- believable `WBStartup` contents,
- the program icon and its tooltypes,
- correct current-directory behavior,
- and the normal Workbench distinction between GUI launch and CLI launch.

The first meaningful success criterion for this phase is: the app reaches its main window, opens attached Workbench-style UI resources, and becomes ready for interaction [S31 L1191-L1212].

## Evidence To Capture On Every Iteration

Capture the same evidence on each run:

- exact `vamos` command
- return code
- stdout
- stderr
- `vamos` log file
- any changed `.info` files
- any created backup archives or restore artifacts

This follows the repeatable capture pattern already documented for the project and mirrors the `amitools` helper's explicit command and log handling [S9 L172-L247].

## High-Value Milestones

Treat these as the natural checkpoint sequence:

1. Binary loads under `vamos` with explicit mappings.
2. No immediate failure on missing core libraries or bad assigns.
3. Workbench-style launch metadata is accepted. See `../../runtime/workbench-integration-boundaries.md` for which Workbench behaviors belong to this stage versus later-phase integration.
4. Main window opens. See `../../host-gui/README.md` for host-side widget, menu, and translation rules once this becomes real UI work.
5. Folder requester works. See `../../host-gui/menus-dialogs-and-requesters.md` for the project's requester defaults.
6. A small test drawer is scanned and laid out.
7. Default-tool analysis produces plausible results.
8. Backup and restore work with `LhA`. See `../../workflows/external-helpers-and-shellouts.md` for how to triage this dependency.

The milestone order matters because later features build on earlier ones. For example, backup success is not a good next goal if the app cannot yet open its main window or find folders to process.
