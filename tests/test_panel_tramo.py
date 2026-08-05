import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from servicios import RallyService
from gui_tk import RallyApp


class StageDashboardTests(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)
        self.service = RallyService()
        ok, message = self.service.create_competition(
            "Rally", 2, ["Ana", "Luis", "Marta"]
        )
        self.assertTrue(ok, message)

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_current_stage_lists_only_active_missing_results_as_pending(self):
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0])
        dashboard = self.service.get_stage_dashboard("Rally")
        self.assertEqual(dashboard["stage"], 1)
        self.assertEqual(dashboard["counts"]["pending"], 2)
        self.assertEqual(dashboard["counts"]["finished"], 1)
        self.assertEqual(
            [row["participant"] for row in dashboard["rows"][:2]],
            ["Luis", "Marta"],
        )

        self.assertTrue(self.service.retire_from_rally("Rally", "Luis", 1, False)[0])
        dashboard = self.service.get_stage_dashboard("Rally", 2)
        rows = {row["participant"]: row for row in dashboard["rows"]}
        self.assertFalse(rows["Luis"]["pending"])
        self.assertEqual(rows["Luis"]["result_status_label"], "No participa")
        self.assertEqual(dashboard["counts"]["pending"], 2)

    def test_modified_result_is_highlighted_with_previous_value(self):
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0])
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:01.250")[0])
        dashboard = self.service.get_stage_dashboard("Rally", 1)
        ana = next(row for row in dashboard["rows"] if row["participant"] == "Ana")
        self.assertTrue(ana["modified"])
        self.assertEqual(ana["previous_time_ms"], 60_000)
        self.assertEqual(ana["revision_count"], 1)
        self.assertEqual(ana["alert"], "Resultado modificado")
        self.assertEqual(dashboard["counts"]["modified"], 1)

    def test_disqualified_missing_stage_is_shown_as_dsq_not_pending(self):
        self.assertTrue(
            self.service.set_result_status(
                "Rally", "Marta", 1, "Descalificado"
            )[0]
        )
        dashboard = self.service.get_stage_dashboard("Rally", 2)
        marta = next(
            row for row in dashboard["rows"] if row["participant"] == "Marta"
        )
        self.assertFalse(marta["pending"])
        self.assertEqual(marta["result_status"], "dsq")
        self.assertEqual(marta["result_status_label"], "Descalificado")
        self.assertEqual(marta["alert"], "-")
        self.assertEqual(dashboard["counts"]["dsq"], 1)

    def test_dashboard_advances_when_active_stage_is_resolved(self):
        for participant, time_text in (
            ("Ana", "1:00.000"),
            ("Luis", "1:01.000"),
            ("Marta", "1:02.000"),
        ):
            self.assertTrue(
                self.service.add_time_str("Rally", participant, 1, time_text)[0]
            )
        dashboard = self.service.get_stage_dashboard("Rally")
        self.assertEqual(dashboard["stage"], 2)
        self.assertEqual(dashboard["counts"]["pending"], 3)

    def test_fill_button_requires_a_base_time_and_pending_participants(self):
        dashboard = self.service.get_stage_dashboard("Rally", 1)
        self.assertFalse(RallyApp._dashboard_can_fill_missing(dashboard))

        self.assertTrue(
            self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0]
        )
        dashboard = self.service.get_stage_dashboard("Rally", 1)
        self.assertTrue(RallyApp._dashboard_can_fill_missing(dashboard))

        self.assertTrue(self.service.fill_missing_times("Rally", 1)[0])
        dashboard = self.service.get_stage_dashboard("Rally", 1)
        self.assertFalse(RallyApp._dashboard_can_fill_missing(dashboard))

    def test_fill_button_uses_the_stage_displayed_in_the_dashboard(self):
        class Value:
            def get(self):
                return "2"

        class FakeService:
            fill_calls = []

            @staticmethod
            def get_stage_dashboard(competition, stage):
                if (competition, stage) != ("Rally", 2):
                    return None
                return {
                    "counts": {"pending": 2},
                    "rows": [
                        {"time_ms": 60_000},
                        {"time_ms": None},
                        {"time_ms": None},
                    ],
                }

            def fill_missing_times(self, competition, stage):
                self.fill_calls.append((competition, stage))
                return True, "Abandonos rellenados."

        class View:
            current_competition = {"name": "Rally"}
            dashboard_stage_var = Value()
            dashboard_window = object()
            service = FakeService()
            status = None
            refreshed = False

            def set_status(self, message, ok):
                self.status = (message, ok)

            def on_select_competition(self):
                self.refreshed = True

        view = View()
        with patch("gui_tk.messagebox.askyesno", return_value=True) as confirm:
            RallyApp._fill_missing_from_dashboard(view)

        self.assertEqual(view.service.fill_calls, [("Rally", 2)])
        self.assertEqual(view.status, ("Abandonos rellenados.", True))
        self.assertTrue(view.refreshed)
        confirm.assert_called_once()

    def test_rejects_unknown_competition_or_stage(self):
        self.assertIsNone(self.service.get_stage_dashboard("No existe"))
        self.assertIsNone(self.service.get_stage_dashboard("Rally", 0))
        self.assertIsNone(self.service.get_stage_dashboard("Rally", 3))

    def test_loading_pending_driver_prepares_main_result_forms(self):
        class Value:
            def __init__(self, value=""):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        class Tree:
            def selection(self):
                return ("row",)

            def item(self, _item, _option):
                return ("Luis",)

        class Entry:
            focused = False

            def focus_set(self):
                self.focused = True

        class View:
            dashboard_tree = Tree()
            dashboard_stage_var = Value("2")
            _dashboard_rows_by_participant = {
                "Luis": {"time_ms": None, "result_status": "pending"}
            }
            service = RallyService()
            add_participant_combo = Value()
            penalize_participant_combo = Value()
            status_participant_combo = Value()
            add_stage_combo = Value()
            fill_stage_combo = Value()
            penalize_stage_combo = Value()
            status_stage_combo = Value()
            add_time_var = Value()
            status_time_var = Value()
            result_status_var = Value()
            add_time_entry = Entry()

            def lift(self):
                self.lifted = True

            def set_status(self, message, ok=True):
                self.status = (message, ok)

        view = View()
        RallyApp._load_dashboard_selection(view)
        self.assertEqual(view.add_participant_combo.get(), "Luis")
        self.assertEqual(view.status_participant_combo.get(), "Luis")
        self.assertEqual(view.add_stage_combo.get(), "2")
        self.assertEqual(view.status_stage_combo.get(), "2")
        self.assertEqual(view.result_status_var.get(), "Finalizado")
        self.assertEqual(view.add_time_var.get(), "")
        self.assertTrue(view.add_time_entry.focused)


if __name__ == "__main__":
    unittest.main()
