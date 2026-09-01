"""Bespoke narrow-loop agent driver for this repo's error-driven-porting loop.

Deliberately a separate top-level package from ``src/amiga_ui`` (the shipped
translation layer): this is a development tool that operates *on* the repo,
not part of the product it produces. See ``agent/README.md`` for the design
rationale, and ``docs/research/local-agent-performance.md`` for the research
this implements.
"""
