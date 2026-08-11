import re
import tempfile
import unittest
from pathlib import Path

from amitools.vamos.main import RET_CODE_CONFIG_ERROR

from amiga_ui.config import PROJECT_ROOT
from amiga_ui.vamos.launcher import run_vamos_in_process

_ICON_LIBRARY_OPEN_RE = re.compile(r"OpenLibrary: 'icon\.library' V0 -> [0-9a-fA-F]{6}")


class VamosLauncherIntegrationTest(unittest.TestCase):
    def test_returns_config_error_when_binary_argument_is_missing(self) -> None:
        exit_code = run_vamos_in_process(args=[])

        self.assertEqual(exit_code, RET_CODE_CONFIG_ERROR)

    def test_runs_itidy_in_process_and_writes_a_vamos_log(self) -> None:
        app_dir = PROJECT_ROOT / "amiga_apps/itidy1classic/binary/extracted"
        app_binary = app_dir / "iTidy"
        if not app_binary.is_file():
            self.skipTest("iTidy binary is not present in the working tree")

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            runtime = _LauncherRuntimeFixture.create(temp_dir)
            vamos_log_path = temp_dir / "vamos.log"

            exit_code = run_vamos_in_process(
                args=runtime.build_itidy_args(app_dir=app_dir, vamos_log_path=vamos_log_path)
            )

            self.assertNotEqual(exit_code, RET_CODE_CONFIG_ERROR)
            self.assertTrue(vamos_log_path.is_file(), "expected launcher to write a vamos log")

            log_text = vamos_log_path.read_text(encoding="utf-8")
            self.assertIn("setup exec.library", log_text)
            self.assertIn("setup dos.library", log_text)
            self.assertRegex(log_text, _ICON_LIBRARY_OPEN_RE)


class _LauncherRuntimeFixture:
    def __init__(self, root: Path, sys_root: Path, work_root: Path, volumes_root: Path) -> None:
        self.root = root
        self.sys_root = sys_root
        self.work_root = work_root
        self.volumes_root = volumes_root

    @classmethod
    def create(cls, root: Path) -> "_LauncherRuntimeFixture":
        sys_root = root / "sys"
        work_root = root / "work"
        volumes_root = root / "volumes"

        for path in (sys_root, work_root, volumes_root):
            path.mkdir(parents=True, exist_ok=True)

        for relative_dir in ("C", "S", "Libs", "Devs", "L", "T"):
            (sys_root / relative_dir).mkdir(exist_ok=True)

        (sys_root / "S" / "startup-sequence").write_text(
            "; test launcher runtime\n",
            encoding="utf-8",
        )
        return cls(root=root, sys_root=sys_root, work_root=work_root, volumes_root=volumes_root)

    def build_itidy_args(self, *, app_dir: Path, vamos_log_path: Path) -> list[str]:
        return [
            "-S",
            "--vols-base-dir",
            str(self.volumes_root),
            "--auto-volumes",
            "off",
            "--auto-assigns",
            "off",
            "-V",
            "root:/",
            "-V",
            f"app:{app_dir}",
            "-V",
            f"sys:{self.sys_root}",
            "-V",
            f"work:{self.work_root}",
            "-a",
            "c:sys:C",
            "-a",
            "libs:sys:Libs",
            "-a",
            "s:sys:S",
            "-a",
            "l:sys:L",
            "-a",
            "devs:sys:Devs",
            "-a",
            "t:sys:T",
            "-p",
            "c:",
            "--cwd",
            "sys:T",
            "-C",
            "68000",
            "-m",
            "2048",
            "-H",
            "abort",
            "-P",
            "-l",
            "dos:info,exec:info",
            "-L",
            str(vamos_log_path),
            "app:iTidy",
        ]


if __name__ == "__main__":
    unittest.main()
