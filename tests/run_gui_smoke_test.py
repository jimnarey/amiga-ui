#!/usr/bin/env python3
"""Headless GUI smoke test that always runs under a temporary Xvfb session."""

from __future__ import annotations

import os
from contextlib import contextmanager

from amiga_ui.host.gui_smoke import run_smoke_gui
from amiga_ui.host.xvfb import XvfbSession, start_xvfb


@contextmanager
def _apply_session_environment(session: XvfbSession):
    tracked_keys = ("DISPLAY", "QT_QPA_PLATFORM")
    previous_values = {key: os.environ.get(key) for key in tracked_keys}
    session_env = session.build_env()
    try:
        os.environ["DISPLAY"] = session_env["DISPLAY"]
        os.environ["QT_QPA_PLATFORM"] = session_env["QT_QPA_PLATFORM"]
        yield
    finally:
        for key, previous_value in previous_values.items():
            if previous_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous_value


def main() -> int:
    with start_xvfb() as session:
        with _apply_session_environment(session):
            return run_smoke_gui()


if __name__ == "__main__":
    raise SystemExit(main())
