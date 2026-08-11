import subprocess
import tempfile
import unittest
from pathlib import Path

from amiga_ui.host.xvfb import (
    XvfbSession,
    _normalize_cli_command,
    validate_x11_socket_dir,
)


class XvfbHelpersTest(unittest.TestCase):
    def test_normalize_cli_command_strips_separator(self) -> None:
        self.assertEqual(
            _normalize_cli_command(["--", "python", "-V"]),
            ["python", "-V"],
        )

    def test_normalize_cli_command_leaves_plain_command_unchanged(self) -> None:
        self.assertEqual(
            _normalize_cli_command(["python", "-V"]),
            ["python", "-V"],
        )

    def test_build_env_sets_display_and_default_qt_platform(self) -> None:
        process = subprocess.Popen(["true"])
        runtime_dir = Path(tempfile.mkdtemp())
        session: XvfbSession | None = None
        try:
            session = XvfbSession(
                display=":99",
                runtime_dir=runtime_dir,
                log_path=runtime_dir / "xvfb.log",
                process=process,
            )
            env = session.build_env({"LANG": "C"})

            self.assertEqual(env["DISPLAY"], ":99")
            self.assertEqual(env["QT_QPA_PLATFORM"], "xcb")
            self.assertEqual(env["LANG"], "C")
        finally:
            if session is not None:
                session.close()

    def test_build_env_preserves_explicit_qt_platform(self) -> None:
        process = subprocess.Popen(["true"])
        runtime_dir = Path(tempfile.mkdtemp())
        session: XvfbSession | None = None
        try:
            session = XvfbSession(
                display=":101",
                runtime_dir=runtime_dir,
                log_path=runtime_dir / "xvfb.log",
                process=process,
            )
            env = session.build_env({"QT_QPA_PLATFORM": "minimal"})

            self.assertEqual(env["DISPLAY"], ":101")
            self.assertEqual(env["QT_QPA_PLATFORM"], "minimal")
        finally:
            if session is not None:
                session.close()

    def test_validate_x11_socket_dir_allows_missing_directory(self) -> None:
        missing_path = Path(tempfile.mkdtemp()) / "missing-x11-socket-dir"
        validate_x11_socket_dir(missing_path)


if __name__ == "__main__":
    unittest.main()
