"""Tests for the ``amiga-ui`` CLI: the GUI launch path and the Qt boundary.

Covers, without a display:

- parsing of the new ``run`` subcommand (defaults and overrides) and that the
  existing subcommands still parse;
- the Qt boundary: importing the CLI module and running a plain ``probe`` must
  NOT import PySide6 (checked in fresh interpreters so ambient imports from
  other test modules cannot mask a regression);
- that ``run_gui_launch`` installs a real :class:`QtHostWindowProjection` when
  no projection is injected, and that the CLI ``run`` command reuses the
  probe's prepared vamos arguments and passes ``projection=None`` (so the real
  Qt projection is created);
- that an ordinary (non-GUI) run installs the no-op
  :class:`NullHostWindowProjection` instead;
- a bounded end-to-end GUI launch (fresh interpreter, offscreen Qt,
  ``--auto-close-after``) that proves the visible shell enters and exits
  cleanly with no manual interaction.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from amiga_ui import cli
from amiga_ui.config import DEFAULT_PROBE_TIMEOUT_SECONDS, PROJECT_ROOT

ITIDY_BINARY = PROJECT_ROOT / "amiga_apps" / "itidy1classic" / "binary" / "extracted" / "iTidy"


def _run_python(
    code: str,
    *,
    env_overrides: dict[str, str] | None = None,
    env_remove: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    """Run ``code`` in a fresh interpreter (no ambient module state)."""

    env = dict(os.environ)
    env.pop("QT_QPA_PLATFORM", None)
    for name in env_remove:
        env.pop(name, None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
        timeout=180,
    )


class RunSubcommandParsingTest(unittest.TestCase):
    """The ``run`` subcommand parses with the documented defaults/overrides."""

    def test_run_parses_defaults(self) -> None:
        args = cli._build_parser().parse_args(["run", str(ITIDY_BINARY)])

        self.assertEqual(args.binary, ITIDY_BINARY)
        self.assertEqual(args.timeout, DEFAULT_PROBE_TIMEOUT_SECONDS)
        self.assertIsNone(args.auto_close_after)
        self.assertIs(args.func, cli._run_cmd)

    def test_run_parses_overrides(self) -> None:
        args = cli._build_parser().parse_args(
            ["run", str(ITIDY_BINARY), "--timeout", "30", "--auto-close-after", "2.5"]
        )

        self.assertEqual(args.timeout, 30)
        self.assertEqual(args.auto_close_after, 2.5)

    def test_existing_subcommands_still_parse(self) -> None:
        parser = cli._build_parser()
        probe = parser.parse_args(["probe", str(ITIDY_BINARY), "--direct"])
        self.assertIs(probe.func, cli._run_probe)
        smoke = parser.parse_args(["smoke-gui", "--direct", "--duration-ms", "100"])
        self.assertIs(smoke.func, cli._run_smoke_gui)
        check = parser.parse_args(["check"])
        self.assertIs(check.func, cli._run_check)


class QtBoundaryTest(unittest.TestCase):
    """Plain (non-GUI) CLI paths must not import PySide6.

    Each check runs in a *fresh* interpreter: an in-process ``sys.modules``
    check would be masked if another test module in the same run already
    imported PySide6.
    """

    def test_cli_module_import_does_not_import_qt(self) -> None:
        completed = _run_python("import sys, amiga_ui.cli; print('PYSIDE', 'PySide6' in sys.modules)")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("PYSIDE False", completed.stdout)

    def test_probe_direct_does_not_import_qt(self) -> None:
        code = (
            "import sys\n"
            "from amiga_ui.cli import main\n"
            "rc = main(['probe', '/nonexistent/binary', '--direct'])\n"
            "print('RC', rc)\n"
            "print('PYSIDE', 'PySide6' in sys.modules)\n"
        )
        completed = _run_python(code)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("RC 1", completed.stdout)  # preflight failure for the missing binary
        self.assertIn("PYSIDE False", completed.stdout)


class GuiLaunchInstallTest(unittest.TestCase):
    """The GUI launch path installs the real Qt projection (offscreen)."""

    @classmethod
    def setUpClass(cls) -> None:
        # Offscreen QApplication for the in-process checks (platform pinned only
        # at construction, per tests/test_host_qt_projection.py's pattern).
        from PySide6.QtWidgets import QApplication

        previous = os.environ.get("QT_QPA_PLATFORM")
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        try:
            cls._app = QApplication.instance() or QApplication([])
        finally:
            if previous is None:
                os.environ.pop("QT_QPA_PLATFORM", None)
            else:
                os.environ["QT_QPA_PLATFORM"] = previous

    def tearDown(self) -> None:
        # Drop any projected windows between tests.
        from PySide6.QtWidgets import QApplication

        instance = QApplication.instance()
        if isinstance(instance, QApplication):
            for widget in list(instance.allWidgets()):
                if widget is not None and widget.parent() is None:
                    widget.deleteLater()
            instance.processEvents()

    def test_run_gui_launch_creates_qt_host_window_projection(self) -> None:
        # With no projection injected, run_gui_launch must construct the real
        # QtHostWindowProjection. The run itself fails fast (no usable target),
        # so the method exits before the event loop (rc 1, no windows).
        import amiga_ui.host.qt_projection as qt_projection
        from amiga_ui.host.run_command import run_gui_launch

        created: list[object] = []
        real_cls = qt_projection.QtHostWindowProjection

        class _Recording(real_cls):  # type: ignore[misc, valid-type]
            def __init__(self, app, *args, **kwargs):
                super().__init__(app, *args, **kwargs)
                created.append(self)

        with mock.patch.object(qt_projection, "QtHostWindowProjection", _Recording):
            rc = run_gui_launch(vamos_args=["-S"], timeout=10)

        self.assertEqual(rc, 1)  # no app-facing window projected
        self.assertEqual(len(created), 1)

    def test_run_command_reuses_probe_args_and_passes_none_projection(self) -> None:
        # The CLI run command must hand the SAME prepared probe arguments to the
        # GUI launch path and pass projection=None (so the real Qt projection is
        # installed, not a test double).
        import amiga_ui.host.run_command as run_command

        captured: dict[str, Any] = {}

        def _fake_run_gui_launch(*, vamos_args, timeout=None, auto_close_after=None, projection=None):
            captured["vamos_args"] = vamos_args
            captured["timeout"] = timeout
            captured["auto_close_after"] = auto_close_after
            captured["projection"] = projection
            return 0

        with mock.patch.object(run_command, "run_gui_launch", _fake_run_gui_launch):
            rc = cli.main(["run", str(ITIDY_BINARY)])

        self.assertEqual(rc, 0)
        self.assertIs(captured["projection"], None)
        args = captured["vamos_args"]
        # The prepared probe argument shape (same as _build_probe_args): the
        # target's directory is mounted as the app: volume and the target is
        # exec'd by its Amiga-side path.
        self.assertIn("-V", args)
        self.assertIn(f"app:{ITIDY_BINARY.parent}", args)
        self.assertIn("--cwd", args)
        self.assertIn("sys:T", args)
        self.assertEqual(args[-1], "app:iTidy")


class NullProjectionTest(unittest.TestCase):
    """An ordinary (non-GUI) run installs the no-op null projection."""

    def test_plain_run_installs_null_projection(self) -> None:
        import tempfile

        from amiga_ui.host.projection import NullHostWindowProjection
        from amiga_ui.vamos.launcher import VamosSessionRunner
        from tests.test_vamos_launcher import _LauncherRuntimeFixture

        with tempfile.TemporaryDirectory(prefix="amiga-ui-nullproj-") as root:
            fixture = _LauncherRuntimeFixture.create(Path(root))
            # A missing app binary fails fast at exec, AFTER the library
            # manager (and its installed projection) is configured.
            args = fixture.build_itidy_args(
                app_dir=fixture.volumes_root / "missing-app",
                vamos_log_path=Path(root) / "vamos.log",
            )
            args[-1] = "app:missing-binary"
            (fixture.volumes_root / "missing-app").mkdir(parents=True, exist_ok=True)

            runner = VamosSessionRunner(args)
            runner.run()

            slm = runner.slm
            if slm is None:
                self.fail("the run must reach library-manager setup")
            self.assertIsInstance(slm.host_projection, NullHostWindowProjection)


class NoDisplayTest(unittest.TestCase):
    """``run`` fails *clearly* (rc 2) when no usable host display is available.

    Running this in-process is unsafe: on the xcb platform with no display,
    Qt's ``QApplication`` constructor aborts the process (SIGABRT) rather than
    raising, which would kill the test runner. A fresh interpreter isolates that.
    """

    @unittest.skipUnless(ITIDY_BINARY.is_file(), "iTydy binary not present")
    def test_run_fails_cleanly_without_display(self) -> None:
        code = (
            "import sys\n"
            f"binary = {str(ITIDY_BINARY)!r}\n"
            "from amiga_ui.cli import main\n"
            "rc = main(['run', binary, '--auto-close-after', '1'])\n"
            "print('RC', rc)\n"
        )
        completed = _run_python(
            code,
            env_overrides={"QT_QPA_PLATFORM": "xcb"},
            env_remove=("DISPLAY", "WAYLAND_DISPLAY"),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)  # interpreter itself exits cleanly
        self.assertIn("RC 2", completed.stdout)
        self.assertIn("no usable host display", completed.stderr)


class BoundedGuiLaunchTest(unittest.TestCase):
    """The bounded end-to-end GUI launch: the visible shell enters and exits
    cleanly with no manual interaction (offscreen Qt, --auto-close-after)."""

    @unittest.skipUnless(ITIDY_BINARY.is_file(), "iTydy binary not present")
    def test_run_command_enters_and_exits_cleanly(self) -> None:
        code = (
            "import sys\n"
            f"binary = {str(ITIDY_BINARY)!r}\n"
            "from amiga_ui.cli import main\n"
            "rc = main(['run', binary, '--auto-close-after', '0.7', '--timeout', '120'])\n"
            "print('RC', rc)\n"
            "print('PYSIDE', 'PySide6' in sys.modules)\n"
        )
        completed = _run_python(code, env_overrides={"QT_QPA_PLATFORM": "offscreen"})
        self.assertEqual(completed.returncode, 0, f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
        out = completed.stdout
        # The interactive scheduler reached its honest automation timeout; it
        # did not turn an empty WaitPort into a fabricated event.
        self.assertIn("interactive wait timed out", completed.stderr)
        self.assertIn("no message was fabricated", completed.stderr)
        # The real Qt projection was used (a titled host window was projected).
        self.assertIn("PYSIDE True", out)
        self.assertIn("iTidy v1.0 - Icon Cleanup Tool", out)
        # The shell entered, printed its projected windows, and exited on the
        # automation timer (no manual interaction).
        self.assertIn("projected window(s) remain", out)
        self.assertIn("host shell exited", out)
        self.assertIn("RC 3", out)


if __name__ == "__main__":
    unittest.main()
