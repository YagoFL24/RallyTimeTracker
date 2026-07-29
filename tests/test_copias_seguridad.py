import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from copias_seguridad import validate_backup
from servicios import RallyService


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)
        self.service = RallyService()
        ok, message = self.service.create_competition(
            "Original", 2, ["Ana", "Luis"]
        )
        self.assertTrue(ok, message)
        self.assertTrue(
            self.service.add_time_str("Original", "Ana", 1, "1:00.000")[0]
        )

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_manual_backup_is_valid_and_listed(self):
        ok, message, backup = self.service.create_database_backup("manual")
        self.assertTrue(ok, message)
        path = Path(backup["path"])
        self.assertTrue(path.is_file())
        self.assertTrue(validate_backup(path))
        backups, directory, error = self.service.list_database_backups()
        self.assertIsNone(error)
        self.assertEqual(Path(directory), Path(directory).resolve())
        self.assertEqual(Path(directory), path.parent)
        self.assertEqual(backups[0]["name"], path.name)
        self.assertEqual(backups[0]["reason"], "manual")

    def test_restore_reverts_database_and_creates_safety_backup(self):
        ok, message, backup = self.service.create_database_backup("manual")
        self.assertTrue(ok, message)
        self.assertTrue(
            self.service.add_time_str("Original", "Luis", 1, "1:02.000")[0]
        )
        self.assertTrue(
            self.service.create_competition("Temporal", 1, ["Marta"])[0]
        )

        ok, message, safety_backup = self.service.restore_database_backup(
            backup["path"]
        )
        self.assertTrue(ok, message)
        self.assertEqual(safety_backup["reason"], "pre_restore")
        self.assertIsNone(self.service.get_competition_info("Temporal"))
        original = self.service.get_competition_info("Original")
        results = {
            (row["participant_name"], row["stage_number"]): row
            for row in original["results"]
        }
        self.assertEqual(results[("Ana", 1)]["time_ms"], 60_000)
        self.assertIsNone(results[("Luis", 1)]["time_ms"])
        self.assertTrue(Path(safety_backup["path"]).is_file())

    def test_invalid_restore_does_not_change_current_database(self):
        invalid = Path("invalida.db")
        invalid.write_bytes(b"no es sqlite")
        before = self.service.get_competition_info("Original")
        ok, _message, safety_backup = self.service.restore_database_backup(invalid)
        self.assertFalse(ok)
        self.assertIsNone(safety_backup)
        after = self.service.get_competition_info("Original")
        self.assertEqual(before["participants"], after["participants"])
        self.assertEqual(before["results"], after["results"])

    def test_keeps_only_last_ten_startup_backups(self):
        for _index in range(12):
            self.assertTrue(
                self.service.create_database_backup("startup")[0]
            )
        backups, _directory, error = self.service.list_database_backups()
        self.assertIsNone(error)
        startup = [item for item in backups if item["reason"] == "startup"]
        self.assertEqual(len(startup), 10)

    def test_import_creates_pre_import_backup(self):
        export_path = Path("original.csv")
        self.assertTrue(
            self.service.export_competition("Original", export_path)[0]
        )
        ok, message, imported_name = self.service.import_competition(export_path)
        self.assertTrue(ok, message)
        self.assertEqual(imported_name, "Original_importada")
        backups, _directory, error = self.service.list_database_backups()
        self.assertIsNone(error)
        self.assertIn("pre_import", {item["reason"] for item in backups})


if __name__ == "__main__":
    unittest.main()
