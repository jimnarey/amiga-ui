## Objective

Setup this repository as a basis for automated development of an Amiga Workbench API translation layer, written in Python, to enable Workbench applications which do not access sound and graphics hardware directly, to be run on Linux and possibly other desktop OS's.

Much of the underlying work as been done as part of the vamos utility in the amitools project. This project is currently cloned within the working tree for reference. How to incorporate it logically and less crudely is something to come back to. Installing via pip/uv etc and not storing a copy of the repo is preferable.

## Automation

Development is to be principally done via OpenHands on a system with an RTX 5060Ti 16GB, using either gpt-oss:20b with a 128K context window or ministral-3:14b with a 64k context window, or a combination of the two. This means we need a clear feedback loop from running code to the model, access to any imported/library code for debugging and continuous documentation of progress, logically laid out, to mitigate the small context windows.

The repo will need an AGENTS.md file and a .openhands/setup.sh and probably a hooks.json.

The Amiga architecture should be documented, including stating which local files correspond with the various ROMs/binaries etc which make up the Amiga stack, in a way which is easy to parse for models with 64K/128K contexts.

OpenHands should have a comprehensive design ready to work with and the various stages/tasks in the project set out, ideally with a high level of independence, so the models can be put to work on parts of the solution without having to be aware of the entire project.

## Resources

Where possible, external resources such as Amiga binaries, disk images and documentation should be kept in the project and committed. Where development includes the use of copyrighted material then this will need to be kept in a git ignored directory with users required to provide their own copies of the files concerned. For obvious reasons this should be a last resort.

A full list of required resources is needed. In addition to ROMs/binaries and a suitable GUI app to test with, operating system and development documentation will probably be essential.

## GUI

The intention is to use tkinter for the GUI. The flexible canvas component, unopinionated approach to threading and liklihood of ongoing development/maintenance are the primary reasons for this. However, other options should be considered.

The right choice of UI framework will depend on the concurrency requirements and deciding on an approach to drawing Amiga application components. It may be possible to simply use a framework's build in widgets in place of e.g. an Amiga button but applications with bespoke components may require something canvas-like. 

## Runtime environment

Even if OpenHands is, for example, capable of drawing tkinter interface components and testing them headlessly some sort of human testing and refinement is inevitable. The project may therefore have to be run in an envioronment with a Linux desktop. How to approach this is unknown. If a desktop is needed, the project will use a variant of one of the XFCE/KDE images in this project - https://github.com/jimnarey/server_containers -  with OpenHands and Ollama running in containers on the same host. I do not want to dive into using docker compose networking yet and instead treat Ollama and OpenHands as LAN services. The server containers project does not have an OpenHands service yet but I will add this shortly. The installation of OpenHands, beyond local project configuration, is not the concern of this project.