import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gestorTiempos import tiempo_a_milisegundos
from persistencia import (
    add_competition,
    add_time,
    fill_times,
    fill_times_penalitation,
    get_competition,
    get_participants,
    get_times,
)
from servicios import RallyService


class TemporaryDatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()


class TimeParsingTests(unittest.TestCase):
    def test_accepts_strict_time_format(self):
        valid_times = {
            "0:00.001": 1,
            "0:59.999": 59_999,
            "1:05.250": 65_250,
            "123:59.999": 7_439_999,
        }
        for value, expected in valid_times.items():
            with self.subTest(value=value):
                self.assertEqual(tiempo_a_milisegundos(value), expected)

    def test_rejects_invalid_or_ambiguous_times(self):
        invalid_times = (
            None,
            "",
            "0:00.000",
            "1:5.000",
            "1:60.000",
            "1:75.000",
            "1:05",
            "1:05.00",
            "1:05.0000",
            "-1:05.000",
            "1:05,000",
            "abc",
        )
        for value in invalid_times:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    tiempo_a_milisegundos(value)


class CompetitionValidationTests(TemporaryDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = RallyService()

    def test_creates_a_valid_competition_with_normalized_names(self):
        ok, _message = self.service.create_competition(
            "  Rally Norte  ", 3, ["  Ana  ", "Luis"]
        )

        self.assertTrue(ok)
        competition = get_competition("Rally Norte")
        self.assertIsNotNone(competition)
        self.assertEqual(get_participants(competition[0]), ["Ana", "Luis"])

    def test_rejects_non_integer_stage_count(self):
        for stages in ("3", 3.0, True, None, 0, -1):
            with self.subTest(stages=stages):
                ok, _message = self.service.create_competition(
                    f"Rally {stages!r}", stages, ["Ana"]
                )
                self.assertFalse(ok)

    def test_rejects_empty_duplicate_or_invalid_participants(self):
        invalid_lists = (
            [],
            [""],
            ["Ana", "  "],
            ["Ana", "ana"],
            ["Ana", " ANA "],
            ["Ana", None],
        )
        for index, participants in enumerate(invalid_lists):
            with self.subTest(participants=participants):
                ok, _message = self.service.create_competition(
                    f"Rally {index}", 2, participants
                )
                self.assertFalse(ok)

    def test_rejects_names_longer_than_database_limit(self):
        long_name = "x" * 256
        self.assertFalse(self.service.create_competition(long_name, 1, ["Ana"])[0])
        self.assertFalse(self.service.create_competition("Rally", 1, [long_name])[0])


class StageAndParticipantValidationTests(TemporaryDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = RallyService()
        ok, message = self.service.create_competition("Rally", 3, ["Ana", "Luis"])
        self.assertTrue(ok, message)
        self.competition_id = get_competition("Rally")[0]

    def test_saves_and_overwrites_a_valid_time(self):
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:02.345")[0])
        self.assertEqual(get_times("Ana", self.competition_id), [(62_345,)])

        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:03.000")[0])
        self.assertEqual(get_times("Ana", self.competition_id), [(63_000,)])

    def test_rejects_invalid_time_without_writing(self):
        for time_value in (
            "1:75.000",
            "1:05",
            "0:00.000",
            "-1:05.000",
            65_000,
            None,
        ):
            with self.subTest(time_value=time_value):
                ok, _message = self.service.add_time_str(
                    "Rally", "Ana", 1, time_value
                )
                self.assertFalse(ok)
        self.assertEqual(get_times("Ana", self.competition_id), [])

    def test_rejects_stage_outside_competition_or_non_integer(self):
        invalid_stages = (0, 4, -1, 1.0, True, "1", None)
        for stage in invalid_stages:
            with self.subTest(stage=stage):
                ok, _message = self.service.add_time_str(
                    "Rally", "Ana", stage, "1:00.000"
                )
                self.assertFalse(ok)
        self.assertEqual(get_times("Ana", self.competition_id), [])

    def test_rejects_unknown_or_empty_participant(self):
        for participant in ("Otro", "ana", "", "   ", None):
            with self.subTest(participant=participant):
                ok, _message = self.service.add_time_str(
                    "Rally", participant, 1, "1:00.000"
                )
                self.assertFalse(ok)
        self.assertEqual(get_times("Ana", self.competition_id), [])

    def test_rejects_invalid_stage_when_filling_abandonments(self):
        for stage in (0, 4, 1.0, "1"):
            with self.subTest(stage=stage):
                self.assertFalse(self.service.fill_missing_times("Rally", stage)[0])

    def test_validates_penalty_and_applies_exact_milliseconds(self):
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0])

        invalid_penalties = (0, -1, True, "texto", "NaN", "Infinity", "0.0001")
        for penalty in invalid_penalties:
            with self.subTest(penalty=penalty):
                self.assertFalse(self.service.penalize("Rally", 1, "Ana", penalty)[0])

        self.assertTrue(self.service.penalize("Rally", 1, "Ana", "1.125")[0])
        self.assertEqual(get_times("Ana", self.competition_id), [(61_125,)])

    def test_rejects_penalty_for_invalid_context(self):
        self.assertTrue(self.service.add_time_str("Rally", "Ana", 1, "1:00.000")[0])
        self.assertFalse(self.service.penalize("Rally", 4, "Ana", 1)[0])
        self.assertFalse(self.service.penalize("Rally", 1, "Otro", 1)[0])
        self.assertFalse(self.service.penalize("Inexistente", 1, "Ana", 1)[0])


class PersistenceBoundaryTests(TemporaryDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(add_competition("Rally", 2, ["Ana", "Luis"]))
        self.competition_id = get_competition("Rally")[0]

    def test_persistence_rejects_invalid_time_references(self):
        invalid_calls = (
            ("Rally", 1_000, 0, "Ana"),
            ("Rally", 1_000, 3, "Ana"),
            ("Rally", 1_000, 1, "Otro"),
            ("Rally", 0, 1, "Ana"),
            ("Rally", -1, 1, "Ana"),
            ("Rally", 1_000.0, 1, "Ana"),
        )
        for arguments in invalid_calls:
            with self.subTest(arguments=arguments):
                self.assertFalse(add_time(*arguments))
        self.assertEqual(get_times("Ana", self.competition_id), [])

    def test_persistence_rejects_invalid_abandonment_and_penalty_context(self):
        self.assertFalse(fill_times("Rally", 0))
        self.assertFalse(fill_times("Rally", 3))
        self.assertFalse(fill_times_penalitation("Rally", 1, "Otro", 1_000))
        self.assertFalse(fill_times_penalitation("Rally", 1, "Ana", 0))

    def test_persistence_rejects_duplicate_participants(self):
        self.assertFalse(add_competition("Duplicados", 1, ["Ana", "ana"]))
        self.assertIsNone(get_competition("Duplicados"))


if __name__ == "__main__":
    unittest.main()
