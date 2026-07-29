import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database_schema import SCHEMA_VERSION
from persistencia import (
    get_competition,
    get_participant_records,
    get_stage_results,
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

    def create_competition(self, stages=3, participants=None):
        participants = participants or ["Ana", "Luis", "Marta"]
        ok, message = self.service.create_competition(
            "Rally", stages, participants
        )
        self.assertTrue(ok, message)
        return get_competition("Rally")[0]


class ExplicitStageStatusTests(TemporaryDatabaseTestCase):
    def test_provisional_differences_compare_equal_progress(self):
        self.create_competition(stages=3, participants=["Ana", "Luis", "Marta"])
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0])
        self.assertTrue(self.service.add_time_str("Rally", "Luis", 1, "1:02.500")[0])

        leaderboard = self.service.get_competition_info("Rally")["leaderboard"]
        rows = {row["participant"]: row for row in leaderboard}
        self.assertEqual(rows["Ana"]["diff"], 0)
        self.assertEqual(rows["Luis"]["diff"], 2_500)
        self.assertIsNone(rows["Marta"]["diff"])
        self.assertEqual(
            [row["participant"] for row in leaderboard],
            ["Ana", "Luis", "Marta"],
        )

        self.assertTrue(self.service.add_time_str("Rally", "Ana", 2, "1:01.000")[0])
        leaderboard = self.service.get_competition_info("Rally")["leaderboard"]
        self.assertEqual(leaderboard[0]["participant"], "Ana")
        self.assertEqual(leaderboard[0]["completed_stages"], 2)
        self.assertEqual(leaderboard[0]["diff"], 0)

    def test_pending_is_only_shown_after_the_stage_has_started(self):
        self.create_competition(stages=2, participants=["Ana", "Luis"])
        info = self.service.get_competition_info("Rally")
        rows = {row["participant"]: row for row in info["leaderboard"]}
        self.assertEqual(
            [self.service.format_stage_result(result) for result in rows["Ana"]["stage_results"]],
            ["-", "-"],
        )

        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0])
        info = self.service.get_competition_info("Rally")
        rows = {row["participant"]: row for row in info["leaderboard"]}
        self.assertEqual(
            [self.service.format_stage_result(result) for result in rows["Ana"]["stage_results"]],
            ["1:00.000", "-"],
        )
        self.assertEqual(
            [self.service.format_stage_result(result) for result in rows["Luis"]["stage_results"]],
            ["Pendiente", "-"],
        )

    def test_schema_enforces_foreign_keys_unique_results_and_stage_range(self):
        competition_id = self.create_competition(stages=1, participants=["Ana"])
        connection, _cursor = start_connection()
        self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        participant_id = connection.execute(
            "SELECT id FROM participants WHERE competition_id=?", (competition_id,)
        ).fetchone()[0]

        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO stage_results (participant_id, stage_number) VALUES (?, 1)",
                (participant_id,),
            )
        connection.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO stage_results (participant_id, stage_number) VALUES (?, 2)",
                (participant_id,),
            )
        connection.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE stage_results SET status='finished', time_ms=NULL "
                "WHERE participant_id=? AND stage_number=1",
                (participant_id,),
            )
        connection.rollback()
        connection.close()

    def test_new_competition_creates_pending_result_for_every_stage(self):
        competition_id = self.create_competition(stages=2, participants=["Ana", "Luis"])
        results = get_stage_results(competition_id)

        self.assertEqual(len(results), 4)
        self.assertEqual({row["status"] for row in results}, {"pending"})
        self.assertTrue(all(row["time_ms"] is None for row in results))

    def test_finished_requires_time_and_can_be_reverted_to_pending(self):
        competition_id = self.create_competition(participants=["Ana"])
        self.assertFalse(
            self.service.set_result_status("Rally", "Ana", 1, "Finalizado", "")[0]
        )
        self.assertTrue(
            self.service.set_result_status(
                "Rally", "Ana", 1, "Finalizado", "1:00.000"
            )[0]
        )
        self.assertTrue(
            self.service.set_result_status("Rally", "Ana", 1, "Pendiente")[0]
        )
        result = get_stage_results(competition_id, "Ana")[0]
        self.assertEqual(result["status"], "pending")
        self.assertIsNone(result["time_ms"])
        self.assertEqual(result["previous_time_ms"], 60_000)
        self.assertEqual(result["revision_count"], 1)

    def test_no_presented_has_no_time_and_can_continue_next_stage(self):
        competition_id = self.create_competition(stages=2, participants=["Ana"])
        self.assertTrue(
            self.service.set_result_status("Rally", "Ana", 1, "No presentado")[0]
        )
        self.assertTrue(
            self.service.add_time_str("Rally", "Ana", 2, "1:02.000")[0]
        )
        results = get_stage_results(competition_id, "Ana")
        self.assertEqual(
            [(row["status"], row["time_ms"]) for row in results],
            [("dns", None), ("finished", 62_000)],
        )

    def test_fill_missing_marks_stage_dnf_but_keeps_participant_active(self):
        competition_id = self.create_competition(stages=2, participants=["Ana", "Luis"])
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0])
        self.assertTrue(self.service.fill_missing_times("Rally", 1)[0])

        luis = get_stage_results(competition_id, "Luis")
        self.assertEqual((luis[0]["status"], luis[0]["time_ms"]), ("stage_dnf", 70_000))
        self.assertEqual(luis[1]["status"], "pending")
        self.assertEqual(get_participant_records(competition_id)[1]["rally_status"], "active")

    def test_disqualified_is_last_keeps_time_and_can_be_reverted(self):
        competition_id = self.create_competition(stages=1, participants=["Ana", "Luis"])
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0])
        self.assertTrue(self.service.add_time_str("Rally", "Luis", 1, "1:01.000")[0])
        self.assertTrue(
            self.service.set_result_status("Rally", "Luis", 1, "Descalificado")[0]
        )
        info = self.service.get_competition_info("Rally")
        self.assertEqual(
            [row["participant"] for row in info["leaderboard"]],
            ["Ana", "Luis"],
        )
        luis = info["leaderboard"][-1]
        self.assertEqual(luis["rank"], "DSQ")
        self.assertIsNone(luis["diff"])
        self.assertEqual(luis["classification_status"], "Descalificado")
        self.assertEqual(luis["stage_times"], [61_000])
        self.assertEqual(luis["stage_results"][0]["status"], "finished")

        self.assertTrue(
            self.service.set_result_status(
                "Rally", "Luis", 1, "Finalizado", "1:01.000"
            )[0]
        )
        records = get_participant_records(competition_id)
        self.assertEqual(records[1]["rally_status"], "active")
        self.assertEqual(len(self.service.get_competition_info("Rally")["leaderboard"]), 2)

    def test_disqualified_are_sorted_by_timed_stages_then_total(self):
        self.create_competition(
            stages=3, participants=["Ana", "Luis", "Marta", "Pablo"]
        )
        for participant, stage, time_text in (
            ("Ana", 1, "1:10.000"),
            ("Ana", 2, "1:30.000"),
            ("Luis", 1, "1:00.000"),
            ("Marta", 1, "0:50.000"),
            ("Pablo", 1, "0:55.000"),
        ):
            self.assertTrue(
                self.service.add_time_str("Rally", participant, stage, time_text)[0]
            )
        self.assertTrue(
            self.service.set_result_status(
                "Rally", "Luis", 2, "No finalizado"
            )[0]
        )
        for participant, stage in (("Luis", 3), ("Marta", 2), ("Pablo", 2)):
            self.assertTrue(
                self.service.set_result_status(
                    "Rally", participant, stage, "Descalificado"
                )[0]
            )

        leaderboard = self.service.get_competition_info("Rally")["leaderboard"]
        self.assertEqual(
            [row["participant"] for row in leaderboard],
            ["Ana", "Luis", "Marta", "Pablo"],
        )
        self.assertEqual([row["rank"] for row in leaderboard], [1, "DSQ", "DSQ", "DSQ"])
        self.assertEqual(
            [row["completed_stages"] for row in leaderboard[1:]],
            [2, 1, 1],
        )
        self.assertEqual(
            [self.service.format_stage_result(result) for result in leaderboard[1]["stage_results"]],
            ["1:00.000", "NF 1:40.000", "DSQ"],
        )
        self.assertTrue(all(row["diff"] is None for row in leaderboard[1:]))


class RallyRetirementTests(TemporaryDatabaseTestCase):
    def test_active_participants_rank_ahead_of_retired_during_rally(self):
        self.create_competition(stages=3, participants=["Ana", "Lucas", "Marta"])
        for participant, time_text in (
            ("Ana", "1:00.000"),
            ("Lucas", "0:59.000"),
            ("Marta", "1:01.000"),
        ):
            self.assertTrue(
                self.service.add_time_str("Rally", participant, 1, time_text)[0]
            )
        self.assertTrue(
            self.service.retire_from_rally("Rally", "Lucas", 1, True)[0]
        )

        leaderboard = self.service.get_competition_info("Rally")["leaderboard"]
        self.assertEqual(
            [row["participant"] for row in leaderboard],
            ["Ana", "Marta", "Lucas"],
        )
        self.assertEqual([row["rank"] for row in leaderboard], [1, 2, 3])
        self.assertEqual(leaderboard[-1]["classification_status"], "Retirado")

    def test_retire_after_finished_stage_preserves_time_and_reactivate(self):
        competition_id = self.create_competition(stages=3, participants=["Ana"])
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0])
        self.assertTrue(
            self.service.retire_from_rally("Rally", "Ana", 1, True)[0]
        )
        participant = get_participant_records(competition_id)[0]
        self.assertEqual(participant["rally_status"], "retired")
        self.assertEqual(participant["retired_after_stage"], 1)
        self.assertEqual(
            self.service.get_competition_info("Rally")["leaderboard"][0][
                "classification_status"
            ],
            "Retirado",
        )

        self.assertTrue(self.service.reactivate("Rally", "Ana")[0])
        participant = get_participant_records(competition_id)[0]
        self.assertEqual(participant["rally_status"], "active")
        self.assertIsNone(participant["retired_after_stage"])

    def test_retire_during_stage_applies_dnf_and_stops_future_pending_stages(self):
        competition_id = self.create_competition(stages=3, participants=["Ana", "Luis"])
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0])
        self.assertTrue(
            self.service.retire_from_rally("Rally", "Luis", 1, False)[0]
        )
        results = get_stage_results(competition_id, "Luis")
        self.assertEqual((results[0]["status"], results[0]["time_ms"]), ("stage_dnf", 70_000))
        self.assertEqual([row["status"] for row in results[1:]], ["pending", "pending"])

    def test_retired_are_ordered_after_finishers_by_completed_stages(self):
        self.create_competition(stages=2, participants=["Ana", "Luis", "Marta"])
        for participant, stage, time_text in (
            ("Ana", 1, "1:00.000"),
            ("Ana", 2, "1:00.000"),
            ("Luis", 1, "0:59.000"),
            ("Marta", 1, "1:01.000"),
        ):
            self.assertTrue(self.service.add_time_str("Rally", participant, stage, time_text)[0])
        self.assertTrue(self.service.retire_from_rally("Rally", "Luis", 1, True)[0])
        self.assertTrue(self.service.retire_from_rally("Rally", "Marta", 1, True)[0])

        leaderboard = self.service.get_competition_info("Rally")["leaderboard"]
        self.assertEqual([row["participant"] for row in leaderboard], ["Ana", "Luis", "Marta"])
        self.assertEqual(
            [row["classification_status"] for row in leaderboard],
            ["Clasificado", "Retirado", "Retirado"],
        )


class LegacyStateMigrationTests(TemporaryDatabaseTestCase):
    def test_migrates_existing_times_to_finished_and_missing_to_pending(self):
        data_dir = Path("data")
        data_dir.mkdir()
        database_path = data_dir / "datos.db"
        connection = sqlite3.connect(database_path)
        connection.execute(
            "CREATE TABLE competitions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "competition_name varchar2(255) UNIQUE, numberOfStages int)"
        )
        connection.execute(
            "CREATE TABLE participants (competition_id int, participant_name varchar2(255))"
        )
        connection.execute(
            "CREATE TABLE times (competition_id int, time int, numberOfStage int, "
            "participant varchar2(255))"
        )
        connection.execute(
            "INSERT INTO competitions VALUES (1, 'Legado', 2)"
        )
        connection.executemany(
            "INSERT INTO participants VALUES (1, ?)", (("Ana",), ("Luis",))
        )
        connection.execute(
            "INSERT INTO times VALUES (1, 60000, 1, 'Ana')"
        )
        connection.commit()
        connection.close()

        migrated, _cursor = start_connection()
        self.assertEqual(migrated.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        migrated.close()
        self.assertTrue((data_dir / "datos.v1.backup.db").exists())

        competition_id = get_competition("Legado")[0]
        ana = get_stage_results(competition_id, "Ana")
        luis = get_stage_results(competition_id, "Luis")
        self.assertEqual(
            [(row["status"], row["time_ms"]) for row in ana],
            [("finished", 60_000), ("pending", None)],
        )
        self.assertEqual([row["status"] for row in luis], ["pending", "pending"])


if __name__ == "__main__":
    unittest.main()
