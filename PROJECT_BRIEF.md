## Objective

Setup this repository as a basis for automated development of an Amiga Workbench API translation layer, written in Python, to enable Workbench applications which do not access sound and graphics hardware directly, to be run on Linux and possibly other desktop OS's.

Much of the underlying work as been done as part of the vamos utility in the amitools project. This project is currently cloned within the working tree for reference. How to incorporate it logically and less crudely is something to come back to. Installing via pip/uv etc and not storing a copy of the repo is preferable.

## Automation

Development is to be principally done via OpenHands on a system with an RTX 5060Ti 16GB, using either gpt-oss:20b with a 128K context window or ministral-3:14b with a 64k context window, or a combination of the two. This means we need a clear feedback loop from running code to the model, access to any imported/library code for debugging and continuous documentation of progress, logically laid out, to mitigate the small context windows.

The repo will need an AGENTS.md file and a .openhands/setup.sh and probably a hooks.json.

The Amiga architecture should be documented, including stating which local files correspond with the various ROMs/binaries etc which make up the Amiga stack, in a way which is easy to parse for models with 64K/128K contexts.

OpenHands should have a comprehensive design ready to work with and the various stages/tasks in the project set out, ideally with a high level of independence, so the models can be put to work on parts of the solution without having to be aware of the entire project.

## Resources

The repository should distinguish clearly between redistributable resources which can be committed and copyrighted binary assets which cannot.

Redistributable or fetchable resources should be kept in the tree where practical. Where a resource can be downloaded from a stable public source, the repository should prefer a tracked download script over undocumented manual acquisition. This already applies to:

1. development and operating-system documentation under `assets/docs/`
2. the ClassAct 3.3 archive and extracted source/material under `assets/libs/`

Where a required binary resource cannot be kept in source control, the repository should keep an underscore-prefixed `.placeholder` file in the corresponding location. The placeholder files act as an inventory of expected assets and give the project a stable filename scheme even when the real binaries are absent. The real assets live alongside them in git-ignored paths when provided by the user.

Broadly, the required binary resource classes are:

1. AmigaOS ADF disk images, primarily Workbench and related system disks across the versions needed for reference and compatibility work.
2. Kickstart ROM images for the Amiga models and OS versions the project expects to use for reference material and compatibility testing.
3. Test application binaries and any accompanying Amiga-side support files needed to launch them realistically under `vamos`.
4. Selected system-side binary fragments or extracted files which may be needed to fill specific runtime gaps where `vamos` alone is not sufficient.

## GUI

The host GUI toolkit used in this project is PySide6, using Qt Widgets. Tkinter was seriously considered but the project needs both ordinary desktop controls and a significant amount of custom Workbench-style drawing and interaction. Qt Widgets provides many more widets, a more comprehensive painting system and several higher-level classes which are potentially useful.

The expected implementation pattern is to use ordinary Qt widgets where they are a good fit, custom-painted widgets where Amiga-specific behavior or visuals require it, and `QGraphicsView` only where a scene of interactive objects is genuinely the right model. The goal is not to reproduce every Amiga control as a canvas primitive by default, but to choose the lightest Qt mechanism which preserves the required behavior.

## Runtime environment

The project should support two distinct runtime modes:

1. Automated GUI testing in a headless Linux environment using `Xvfb`.
2. Human testing in a normal Linux desktop environment.

`Xvfb` is the standard automated test display server for this repository. Automated smoke tests and scripted GUI runs should use the project wrapper around `Xvfb`, so the host-side GUI layer can be exercised consistently without depending on a physical display or an already-running desktop session. The purpose of this mode is repeatable validation inside OpenHands and other non-interactive environments.

Human testing should be done in a normal Linux desktop session rather than through the headless path.

At a high level, getting started with this project in the OpenHands web UI should work as follows:

1. Start OpenHands in its full web GUI mode and open the browser interface. The current OpenHands documentation describes this as the `serve` mode and notes that it launches the local web GUI through Docker.
2. On first launch, configure the model/provider settings in the OpenHands settings dialog so the session uses the intended local or remote LLM.
3. Open a conversation with this repository available to the workspace using the OpenHands mechanism you choose, for example by launching the GUI with the repository mounted or by using the repository/workspace flow exposed by the UI.
4. Let any repository-specific bootstrap steps run, then verify the project environment from the OpenHands terminal by running the standard setup and validation commands such as `uv sync`, `./check_optional_deps.sh` and the GUI smoke test launcher.
5. Use OpenHands as an autonomous worker rather than as an interactive pair-programming tool: give it a clear objective, let it run the target app or smoke test, inspect the resulting errors, implement the next missing function or feature, update the documentation and continue iterating until it reaches a natural stopping point or needs human intervention.
