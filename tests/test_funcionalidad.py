import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gestorTiempos import MAX_SQLITE_INTEGER, milisegundos_a_tiempo
from gui_tk import RallyApp
from persistencia import (
    add_time,
    fill_times_penalitation,
    get_competition,
    get_stage_counts,
    get_times,
    start_connection,
)
from servicios import RallyService


class TemporaryDatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)
        self.service = RallyService()

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def create_competition(self, name="Rally", stages=2, participants=None):
        participants = participants or ["Ana", "Luis", "Marta"]
        ok, message = self.service.create_competition(name, stages, participants)
        self.assertTrue(ok, message)
        return get_competition(name)[0]


class CompetitionLifecycleTests(TemporaryDatabaseTestCase):
    def test_creates_reads_and_deletes_a_complete_competition(self):
        competition_id = self.create_competition(
            "Rally Norte", 2, ["Ana", "Luis"]
        )
        self.assertEqual(self.service.list_competitions(), ["Rally Norte"])

        self.assertTrue(
            self.service.add_time_str("Rally Norte", "Ana", 1, "1:00.000")[0]
        )
        info = self.service.get_competition_info("Rally Norte")
        self.assertEqual(info["id"], competition_id)
        self.assertEqual(info["participants"], ["Ana", "Luis"])

        self.assertTrue(self.service.delete_competition("Rally Norte")[0])
        self.assertIsNone(self.service.get_competition_info("Rally Norte"))

        connection, _cursor = start_connection()
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM competitions").fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM participants").fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM times").fetchone()[0], 0)
        connection.close()

    def test_duplicate_competition_does_not_leave_partial_participants(self):
        competition_id = self.create_competition(participants=["Ana", "Luis"])
        self.assertFalse(
            self.service.create_competition("Rally", 4, ["Otro"])[0]
        )

        connection, _cursor = start_connection()
        participants = connection.execute(
            "SELECT participant_name FROM participants WHERE competition_id = ? "
            "ORDER BY rowid",
            (competition_id,),
        ).fetchall()
        connection.close()
        self.assertEqual(participants, [("Ana",), ("Luis",)])

    def test_schema_initialization_is_idempotent_and_persistent(self):
        connection, _cursor = start_connection()
        expected_tables = {"competitions", "participants", "times"}
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        connection.close()
        self.assertTrue(expected_tables.issubset(tables))

        competition_id = self.create_competition(participants=["Ana"])
        connection, _cursor = start_connection()
        persisted = connection.execute(
            "SELECT id FROM competitions WHERE competition_name = 'Rally'"
        ).fetchone()
        connection.close()
        self.assertEqual(persisted, (competition_id,))


class LeaderboardTests(TemporaryDatabaseTestCase):
    def test_builds_complete_leaderboard_with_stages_totals_and_differences(self):
        self.create_competition(stages=2, participants=["Ana", "Luis", "Marta"])
        times = (
            ("Ana", 2, "1:01.000"),
            ("Ana", 1, "1:00.000"),
            ("Luis", 1, "1:02.000"),
            ("Luis", 2, "1:03.000"),
            ("Marta", 1, "1:01.500"),
            ("Marta", 2, "1:02.500"),
        )
        for participant, stage, time_text in times:
            self.assertTrue(
                self.service.add_time_str("Rally", participant, stage, time_text)[0]
            )

        leaderboard = self.service.get_competition_info("Rally")["leaderboard"]
        self.assertEqual(
            leaderboard,
            [
                {
                    "rank": 1,
                    "participant": "Ana",
                    "stage_times": [60_000, 61_000],
                    "total": 121_000,
                    "diff": 0,
                },
                {
                    "rank": 2,
                    "participant": "Marta",
                    "stage_times": [61_500, 62_500],
                    "total": 124_000,
                    "diff": 3_000,
                },
                {
                    "rank": 3,
                    "participant": "Luis",
                    "stage_times": [62_000, 63_000],
                    "total": 125_000,
                    "diff": 4_000,
                },
            ],
        )

    def test_default_stage_advances_only_when_the_current_stage_is_complete(self):
        competition_id = self.create_competition(
            stages=3, participants=["Ana", "Luis"]
        )
        participants = ["Ana", "Luis"]
        self.assertEqual(
            self.service.get_default_stage(competition_id, 3, participants), 1
        )

        self.assertTrue(add_time("Rally", 60_000, 1, "Ana"))
        self.assertEqual(
            self.service.get_default_stage(competition_id, 3, participants), 1
        )
        self.assertTrue(add_time("Rally", 61_000, 1, "Luis"))
        self.assertEqual(
            self.service.get_default_stage(competition_id, 3, participants), 2
        )
        self.assertTrue(add_time("Rally", 62_000, 2, "Ana"))
        self.assertEqual(
            self.service.get_default_stage(competition_id, 3, participants), 2
        )

    def test_formats_times_and_missing_values_for_the_table(self):
        self.assertEqual(milisegundos_a_tiempo(0), "0:00.000")
        self.assertEqual(milisegundos_a_tiempo(65_250), "1:05.250")
        self.assertEqual(self.service.format_time(None), "--:--.---")
        self.assertEqual(self.service.format_time(3_661_007), "61:01.007")


class AbandonmentTests(TemporaryDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.competition_id = self.create_competition()

    def test_fills_only_missing_times_with_worst_time_plus_ten_seconds(self):
        self.assertTrue(add_time("Rally", 60_000, 1, "Ana"))
        self.assertTrue(add_time("Rally", 65_000, 1, "Luis"))

        self.assertTrue(self.service.fill_missing_times("Rally", 1)[0])
        self.assertEqual(get_times("Ana", self.competition_id), [(60_000,)])
        self.assertEqual(get_times("Luis", self.competition_id), [(65_000,)])
        self.assertEqual(get_times("Marta", self.competition_id), [(75_000,)])
        self.assertEqual(get_stage_counts(self.competition_id), {1: 3})

        self.assertTrue(self.service.fill_missing_times("Rally", 1)[0])
        self.assertEqual(get_stage_counts(self.competition_id), {1: 3})

    def test_does_not_fill_without_a_base_time(self):
        self.assertFalse(self.service.fill_missing_times("Rally", 2)[0])
        self.assertEqual(get_stage_counts(self.competition_id), {})

    def test_rejects_abandonment_time_overflow_without_partial_writes(self):
        self.assertTrue(add_time("Rally", MAX_SQLITE_INTEGER, 1, "Ana"))
        self.assertFalse(self.service.fill_missing_times("Rally", 1)[0])
        self.assertEqual(get_times("Luis", self.competition_id), [])
        self.assertEqual(get_times("Marta", self.competition_id), [])


class PenaltyTests(TemporaryDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.competition_id = self.create_competition()

    def test_penalties_are_cumulative_and_isolated_by_participant_and_stage(self):
        self.assertTrue(add_time("Rally", 60_000, 1, "Ana"))
        self.assertTrue(add_time("Rally", 70_000, 1, "Luis"))
        self.assertTrue(add_time("Rally", 80_000, 2, "Ana"))

        self.assertTrue(self.service.penalize("Rally", 1, "Ana", "1.250")[0])
        self.assertTrue(self.service.penalize("Rally", 1, "Ana", 0.75)[0])

        self.assertEqual(get_times("Ana", self.competition_id), [(62_000,), (80_000,)])
        self.assertEqual(get_times("Luis", self.competition_id), [(70_000,)])

    def test_rejects_penalty_overflow_and_preserves_original_time(self):
        self.assertTrue(add_time("Rally", MAX_SQLITE_INTEGER, 1, "Ana"))
        self.assertFalse(
            fill_times_penalitation("Rally", 1, "Ana", 1)
        )
        self.assertEqual(
            get_times("Ana", self.competition_id), [(MAX_SQLITE_INTEGER,)]
        )


class FakeCombo:
    def __init__(self):
        self.values = None
        self.selected = None

    def __setitem__(self, key, value):
        if key != "values":
            raise KeyError(key)
        self.values = value

    def set(self, value):
        self.selected = value


class GuiLogicTests(unittest.TestCase):
    def test_table_sorting_handles_text_totals_and_missing_stage_times(self):
        rows = [
            {"participant": "Luis", "total": 130, "diff": 10, "stage_times": [60, 70]},
            {"participant": "ana", "total": 120, "diff": 0, "stage_times": [None, 120]},
            {"participant": "Marta", "total": 125, "diff": 5, "stage_times": [55, 70]},
        ]

        class FakeView:
            current_leaderboard = rows

            def _populate_table(self, sorted_rows, stages):
                self.sorted_rows = sorted_rows
                self.stages = stages

        view = FakeView()
        RallyApp.sort_by_column(view, "participant", 2)
        self.assertEqual(
            [row["participant"] for row in view.sorted_rows],
            ["ana", "Luis", "Marta"],
        )

        RallyApp.sort_by_column(view, "stage_1", 2)
        self.assertEqual(
            [row["participant"] for row in view.sorted_rows],
            ["Marta", "Luis", "ana"],
        )
        RallyApp.sort_by_column(view, "total", 2)
        self.assertEqual(
            [row["total"] for row in view.sorted_rows], [120, 125, 130]
        )
        self.assertEqual(view.stages, 2)

    def test_action_sources_receive_all_participants_and_stages(self):
        class FakeView:
            add_participant_combo = FakeCombo()
            penalize_participant_combo = FakeCombo()
            add_stage_combo = FakeCombo()
            fill_stage_combo = FakeCombo()
            penalize_stage_combo = FakeCombo()

        view = FakeView()
        RallyApp._update_action_sources(view, ["Ana", "Luis"], 3)

        for combo in (view.add_participant_combo, view.penalize_participant_combo):
            self.assertEqual(combo.values, ["Ana", "Luis"])
            self.assertEqual(combo.selected, "Ana")
        for combo in (
            view.add_stage_combo,
            view.fill_stage_combo,
            view.penalize_stage_combo,
        ):
            self.assertEqual(combo.values, ["1", "2", "3"])
            self.assertEqual(combo.selected, "1")


if __name__ == "__main__":
    unittest.main()
