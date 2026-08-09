"""Compatibility wrapper for the package-owned GUI smoke test."""

from amiga_ui.host.gui_smoke import run_smoke_gui


def main() -> int:
    return run_smoke_gui()


if __name__ == "__main__":
    raise SystemExit(main())
