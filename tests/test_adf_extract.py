import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amiga_ui.adf_extract import discover_adf_images, extract_adf, extraction_output_dir


class AdfDiscoveryTest(unittest.TestCase):
    def test_discovers_real_adfs_and_ignores_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            (root / "amigaos_3.1_workbench.adf").write_bytes(b"ADF")
            (root / "_amigaos_3.1_workbench.adf.placeholder").write_text("", encoding="utf-8")
            (root / "notes.txt").write_text("", encoding="utf-8")

            self.assertEqual(discover_adf_images(root), [root / "amigaos_3.1_workbench.adf"])

    def test_uses_stem_based_output_directory(self) -> None:
        self.assertEqual(
            extraction_output_dir(Path("assets/adf/amigaos_3.1_workbench.adf"), Path("out")),
            Path("out/amigaos_3.1_workbench"),
        )


class AdfExtractionTest(unittest.TestCase):
    def test_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            adf = root / "disk.adf"
            adf.write_bytes(b"ADF")
            out_root = root / "out"
            (out_root / "disk").mkdir(parents=True)

            result = extract_adf(adf, output_root=out_root)

            self.assertFalse(result.ok)
            self.assertIn("already exists", result.error)

    def test_invokes_xdftool_read_only_unpack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            adf = root / "disk.adf"
            adf.write_bytes(b"ADF")
            out_root = root / "out"

            with patch("amiga_ui.adf_extract.subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = ""
                run.return_value.stderr = ""

                result = extract_adf(adf, output_root=out_root)

            self.assertTrue(result.ok)
            command = run.call_args.args[0]
            self.assertEqual(command[1:5], ["-m", "amitools.tools.xdftool", "-r", str(adf.resolve())])
            self.assertEqual(command[5], "unpack")
            self.assertEqual(command[6], str((out_root / "disk").resolve()))


if __name__ == "__main__":
    unittest.main()
