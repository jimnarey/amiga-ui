"""Helpers for managing Xvfb from Python and the command line."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import PROJECT_ROOT

DEFAULT_SCREEN_SPEC = "1280x1024x24"
DEFAULT_QT_QPA_PLATFORM = "xcb"
DEFAULT_DISPLAY_RANGE = range(90, 111)
X11_SOCKET_DIR = Path("/tmp/.X11-unix")


class XvfbError(RuntimeError):
    """Base error raised by the project Xvfb helper."""


class XvfbUnavailableError(XvfbError):
    """Raised when the Xvfb executable is not available."""


class XvfbSocketError(XvfbError):
    """Raised when the X11 socket directory has an unexpected shape."""


class XvfbStartError(XvfbError):
    """Raised when no usable Xvfb display can be started."""


@dataclass
class XvfbSession:
    """One live Xvfb instance and its associated runtime files."""

    display: str
    runtime_dir: Path
    log_path: Path
    process: subprocess.Popen[Any]

    def build_env(self, env: Mapping[str, str] | None = None) -> dict[str, str]:
        """Return an environment configured to use this Xvfb display."""

        merged = os.environ.copy()
        if env is not None:
            merged.update(dict(env))
        merged["DISPLAY"] = self.display
        merged.setdefault("QT_QPA_PLATFORM", DEFAULT_QT_QPA_PLATFORM)
        return merged

    def close(self) -> None:
        """Stop the Xvfb process and remove its temporary files."""

        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        shutil.rmtree(self.runtime_dir, ignore_errors=True)

    def __enter__(self) -> XvfbSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def run_with_xvfb(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    capture_output: bool = False,
    text: bool = False,
    timeout: int | None = None,
    screen_spec: str | None = None,
    requested_display: str | None = None,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """Run a command under a temporary Xvfb instance."""

    with start_xvfb(screen_spec=screen_spec, requested_display=requested_display) as session:
        return subprocess.run(
            command,
            cwd=PROJECT_ROOT if cwd is None else cwd,
            env=session.build_env(env),
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            check=False,
        )


def start_xvfb(
    *,
    screen_spec: str | None = None,
    requested_display: str | None = None,
) -> XvfbSession:
    """Start an Xvfb instance and return a managed session object."""

    ensure_xvfb_available()
    validate_x11_socket_dir()

    screen_spec = os.environ.get("AMIGA_UI_XVFB_SCREEN", DEFAULT_SCREEN_SPEC) if screen_spec is None else screen_spec
    requested_display = os.environ.get("AMIGA_UI_XVFB_DISPLAY") if requested_display is None else requested_display
    runtime_dir = Path(tempfile.mkdtemp(prefix="amiga-ui-xvfb.", dir="/tmp"))
    log_path = runtime_dir / "xvfb.log"

    try:
        if requested_display:
            return _start_on_candidate(
                requested_display,
                screen_spec=screen_spec,
                runtime_dir=runtime_dir,
                log_path=log_path,
            )
        return _start_on_first_available_display(
            screen_spec=screen_spec,
            runtime_dir=runtime_dir,
            log_path=log_path,
        )
    except Exception:
        shutil.rmtree(runtime_dir, ignore_errors=True)
        raise


def ensure_xvfb_available() -> None:
    """Raise if Xvfb is not available on the host."""

    if shutil.which("Xvfb") is None:
        raise XvfbUnavailableError("Xvfb is not available. Run ./check_dependencies.sh for guidance.")


def validate_x11_socket_dir(path: Path = X11_SOCKET_DIR) -> None:
    """Validate the expected shape of the X11 socket directory."""

    if not path.is_dir():
        return

    socket_owner_uid = path.stat().st_uid
    socket_mode = oct(path.stat().st_mode & 0o7777)[2:]
    if socket_owner_uid != 0 and socket_owner_uid != os.geteuid():
        raise XvfbSocketError(
            f"{path} is owned by uid {socket_owner_uid}, but Xvfb expects root ownership.\n"
            f"Suggested host fix: sudo chown root:root {path}"
        )
    if socket_mode != "1777":
        raise XvfbSocketError(
            f"{path} has mode {socket_mode}, but Xvfb expects 1777.\nSuggested host fix: sudo chmod 1777 {path}"
        )


def _start_on_first_available_display(
    *,
    screen_spec: str,
    runtime_dir: Path,
    log_path: Path,
) -> XvfbSession:
    last_error: str | None = None
    for candidate_number in DEFAULT_DISPLAY_RANGE:
        candidate = f":{candidate_number}"
        try:
            return _start_on_candidate(
                candidate,
                screen_spec=screen_spec,
                runtime_dir=runtime_dir,
                log_path=log_path,
            )
        except XvfbStartError as exc:
            last_error = str(exc)

    message = "Unable to find a usable Xvfb display."
    if last_error:
        message = f"{message}\nLast Xvfb output: {last_error}"
    raise XvfbStartError(message)


def _start_on_candidate(
    candidate: str,
    *,
    screen_spec: str,
    runtime_dir: Path,
    log_path: Path,
) -> XvfbSession:
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            ["Xvfb", candidate, "-screen", "0", screen_spec, "-nolisten", "tcp"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=PROJECT_ROOT,
        )

    if not _wait_for_xvfb_start(process, log_path):
        failure_message = _read_start_failure_message(log_path)
        process.wait(timeout=5)
        raise XvfbStartError(f"Unable to start Xvfb on display {candidate}.\nXvfb output: {failure_message}")

    return XvfbSession(
        display=candidate,
        runtime_dir=runtime_dir,
        log_path=log_path,
        process=process,
    )


def _wait_for_xvfb_start(process: subprocess.Popen[Any], log_path: Path) -> bool:
    for _ in range(20):
        if process.poll() is not None:
            return False
        time.sleep(0.1)
    return True


def _read_start_failure_message(log_path: Path) -> str:
    if not log_path.is_file():
        return ""
    return " ".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()).strip()


def _normalize_cli_command(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="amiga-ui-xvfb",
        description="Run a command under a temporary Xvfb session.",
    )
    parser.add_argument(
        "--screen",
        default=None,
        help=f"screen specification passed to Xvfb (default: {DEFAULT_SCREEN_SPEC})",
    )
    parser.add_argument(
        "--display",
        default=None,
        help="specific display to request, for example :99",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="command to run, optionally preceded by --",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    command = _normalize_cli_command(args.command)
    if not command:
        parser.print_usage(sys.stderr)
        return 64

    try:
        completed = run_with_xvfb(
            command,
            capture_output=False,
            text=True,
            screen_spec=args.screen,
            requested_display=args.display,
        )
    except XvfbUnavailableError as exc:
        print(str(exc), file=sys.stderr)
        return 127
    except XvfbError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
