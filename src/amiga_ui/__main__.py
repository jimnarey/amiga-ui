"""Module entrypoint for ``python -m amiga_ui``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
