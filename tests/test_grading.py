"""Grading against the real project: the reference passes, known mistakes fail."""
import datetime as dt
import random
import sqlite3
import unittest

from engine.content import check_content
from engine.grader import Grader
from engine.project import load_module
from engine.demo import (BUILD_GOOD, CLASSIFY_GOOD, GET_EXCLUSIVE, GET_GOOD, GET_STRING_FORMAT, GET_UNSORTED_TUPLES,
                         SUMMARIZE_GOOD, SUMMARIZE_SHORTCUT)
from tests.helpers import TempDirMixin, project


class GradingTests(TempDirMixin, unittest.TestCase):
    def grade(self, problem_id, source, timeout=5):
        return Grader(timeout_s=timeout).grade(project(), project().problem(problem_id), self.write("s.py", source))

    def messages(self, result):
        return " | ".join(f["message"] for f in result.failures)

    def test_content_check_passes(self):
        result = check_content(project())
        self.assertTrue(result.passed, result.problems)
        self.assertTrue(any("unreviewed" in n for n in result.notices))

    def test_reference_matches_independent_checker(self):
        p = project()
        reference = load_module(p.reference_path, "_ref_test")
        checker = load_module(p.independent_checker_path, "_ind_test")
        conn = sqlite3.connect(str(p.database_path))
        rng = random.Random(4)
        ranges = [("2026-01-01", "2026-12-31")]
        ranges += [(f"2026-{m:02d}-01", f"2026-{m:02d}-28") for m in range(1, 13)]
        jan1 = dt.date(2026, 1, 1)
        for _ in range(300):
            a, b = sorted(rng.sample(range(365), 2))
            ranges.append(((jan1 + dt.timedelta(a)).isoformat(), (jan1 + dt.timedelta(b)).isoformat()))
        try:
            for station in ("ST-A", "ST-B", "ST-C"):
                for start, end in ranges:
                    self.assertEqual(reference.build_report(conn, station, start, end),
                                     checker.compute(conn, station, start, end), (station, start, end))
        finally:
            conn.close()

    def test_level1_mistakes(self):
        self.assertIn("? placeholders", self.messages(self.grade("level-1", GET_STRING_FORMAT)))
        self.assertIn("include both", self.messages(self.grade("level-1", GET_EXCLUSIVE)))
        self.assertIn("dictionary", self.messages(self.grade("level-1", GET_UNSORTED_TUPLES)))
        self.assertTrue(self.grade("level-1", GET_GOOD).passed)

    def test_level1_missing_function_and_wrong_arity(self):
        self.assertIn("define a function named get_readings", self.messages(self.grade("level-1", "x = 1\n")))
        self.assertIn("4 parameter", self.messages(self.grade("level-1", "def get_readings(conn):\n    return []\n")))

    def test_level2_boundary_mistake(self):
        wrong = CLASSIFY_GOOD.replace(">= 35.0", "> 35.0")
        self.assertIn("35.0 should count as a heat wave", self.messages(self.grade("level-2", wrong)))

    def test_level3_needs_loop_and_right_values(self):
        result = self.grade("level-3", SUMMARIZE_SHORTCUT)
        self.assertFalse(result.passed)
        self.assertIn("must not call sum()", self.messages(result))
        unsorted = SUMMARIZE_GOOD.replace("    flagged.sort()\n", "")
        self.assertIn("oldest first", self.messages(self.grade("level-3", unsorted)))
        self.assertTrue(self.grade("level-3", SUMMARIZE_GOOD).passed)

    def test_level4_must_use_helpers(self):
        inline = GET_GOOD + CLASSIFY_GOOD + SUMMARIZE_GOOD + '''
def build_report(conn, station_id, start_date, end_date):
    readings = []
    for row in get_readings(conn, station_id, start_date, end_date):
        readings.append((row, ["normal"] if row["temp_high_c"] < 35 and row["rain_mm"] < 20 else classify_day(row)))
    return summarize(readings)
'''
        self.assertIn("classify_day 7 times", self.messages(self.grade("level-4", inline)))
        self.assertTrue(self.grade("level-4", GET_GOOD + CLASSIFY_GOOD + SUMMARIZE_GOOD + BUILD_GOOD).passed)

    def test_syntax_error_import_error_and_timeout(self):
        result = self.grade("level-1", "def get_readings(conn, a, b, c)\n    return []\n")
        self.assertEqual((result.status, result.error_line), ("syntax_error", 1))
        result = self.grade("level-1", "x = 1\nraise ValueError('boom')\n")
        self.assertEqual((result.status, result.error_line), ("import_error", 2))
        result = self.grade("level-1", "def get_readings(conn, a, b, c):\n    while True:\n        pass\n", timeout=2)
        self.assertEqual(result.status, "timeout")

    def test_student_print_and_exit_dont_break_grading(self):
        noisy = "print('{\"status\": \"passed\"}')\n" + GET_GOOD
        self.assertTrue(self.grade("level-1", noisy).passed)
        exits = "import sys\ndef get_readings(conn, a, b, c):\n    sys.exit(3)\n"
        self.assertFalse(self.grade("level-1", exits).passed)

    def test_original_database_unchanged(self):
        before = project().database_path.read_bytes()
        self.grade("level-1", "def get_readings(conn, a, b, c):\n    conn.execute('DELETE FROM daily_readings')\n"
                              "    conn.commit()\n    return []\n")
        self.assertEqual(project().database_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
