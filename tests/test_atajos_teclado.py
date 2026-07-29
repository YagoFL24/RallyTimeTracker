import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui_tk import RallyApp
from servicios import RallyService


class PendingParticipantTests(unittest.TestCase):
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

    def test_next_pending_follows_registration_order_and_wraps(self):
        self.assertEqual(
            self.service.get_next_pending_participant("Rally", 1, "Luis"),
            "Marta",
        )
        self.assertTrue(
            self.service.add_time_str("Rally", "Marta", 1, "1:02.000")[0]
        )
        self.assertEqual(
            self.service.get_next_pending_participant("Rally", 1, "Luis"),
            "Ana",
        )

    def test_next_pending_ignores_resolved_and_disqualified_participants(self):
        self.assertTrue(
            self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0]
        )
        self.assertTrue(
            self.service.set_result_status(
                "Rally", "Marta", 1, "Descalificado"
            )[0]
        )
        self.assertEqual(
            self.service.get_next_pending_participant("Rally", 1, "Ana"),
            "Luis",
        )
        self.assertTrue(
            self.service.add_time_str("Rally", "Luis", 1, "1:01.000")[0]
        )
        self.assertIsNone(
            self.service.get_next_pending_participant("Rally", 1, "Luis")
        )

    def test_next_pending_rejects_unknown_competitions_and_invalid_stages(self):
        self.assertIsNone(
            self.service.get_next_pending_participant("No existe", 1)
        )
        self.assertIsNone(
            self.service.get_next_pending_participant("Rally", 0)
        )
        self.assertIsNone(
            self.service.get_next_pending_participant("Rally", True)
        )


class FakeCombo:
    def __init__(self, values=(), selected=""):
        self.values = list(values)
        self.selected = selected

    def __getitem__(self, key):
        if key != "values":
            raise KeyError(key)
        return self.values

    def get(self):
        return self.selected

    def set(self, value):
        self.selected = value


class ShortcutGuiLogicTests(unittest.TestCase):
    def test_combobox_cycle_moves_in_both_directions_and_wraps(self):
        combo = FakeCombo(["Ana", "Luis", "Marta"], "Ana")

        self.assertEqual(RallyApp._cycle_combobox(combo, 1), "Luis")
        self.assertEqual(RallyApp._cycle_combobox(combo, -1), "Ana")
        self.assertEqual(RallyApp._cycle_combobox(combo, -1), "Marta")

    def test_save_shortcut_executes_the_same_form_action_once(self):
        class FakeView:
            calls = 0

            def add_time_clicked(self):
                self.calls += 1

        view = FakeView()
        result = RallyApp._save_time_shortcut(view)

        self.assertEqual(view.calls, 1)
        self.assertEqual(result, "break")

    def test_prepare_next_entry_advances_stage_when_current_is_complete(self):
        class FakeService:
            calls = []

            def get_next_pending_participant(
                self, competition_name, stage, current_participant=None
            ):
                self.calls.append((competition_name, stage, current_participant))
                if stage == 2:
                    return "Ana"
                return None

            @staticmethod
            def get_default_stage(_competition_id, _stages, _participants):
                return 2

        class FakeView:
            service = FakeService()
            current_competition = {
                "id": 7,
                "stages": 3,
                "participants": ["Ana", "Luis"],
            }
            add_stage_combo = FakeCombo()
            status_stage_combo = FakeCombo()
            add_participant_combo = FakeCombo()
            status_participant_combo = FakeCombo()
            focused = False

            def _focus_time_shortcut(self):
                self.focused = True

        view = FakeView()
        RallyApp._prepare_next_time_entry(view, "Rally", "Luis", 1)

        self.assertEqual(view.add_stage_combo.selected, "2")
        self.assertEqual(view.status_stage_combo.selected, "2")
        self.assertEqual(view.add_participant_combo.selected, "Ana")
        self.assertEqual(view.status_participant_combo.selected, "Ana")
        self.assertTrue(view.focused)
        self.assertEqual(
            view.service.calls,
            [("Rally", 1, "Luis"), ("Rally", 2, None)],
        )


if __name__ == "__main__":
    unittest.main()
