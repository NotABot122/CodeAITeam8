import datetime as dt
import sqlite3
import unittest

from engine.project import load_module
from tests.helpers import PROJECT_DIR, TempDirMixin

generator = load_module(PROJECT_DIR / "dataset" / "generate.py", "_test_generator")


class DatasetTests(TempDirMixin, unittest.TestCase):
    def rows(self, path):
        conn = sqlite3.connect(str(path))
        try:
            return conn.execute("SELECT * FROM daily_readings ORDER BY station_id, date").fetchall()
        finally:
            conn.close()

    def test_shape_and_invariants(self):
        rows = self.rows(generator.generate(self.tmp / "w.db"))
        self.assertEqual(len(rows), 1095)
        self.assertEqual(len({(r[0], r[1]) for r in rows}), 1095)
        self.assertEqual({r[0] for r in rows}, {"ST-A", "ST-B", "ST-C"})
        for station, date, high, low, rain in rows:
            self.assertEqual(len(date), 10)
            dt.date.fromisoformat(date)
            self.assertLessEqual(low, high)
            self.assertTrue(-30.0 <= low <= 50.0 and -30.0 <= high <= 50.0 and 0.0 <= rain <= 200.0)
            for value in (high, low, rain):
                self.assertEqual(value, round(value, 1))
        dates = sorted({r[1] for r in rows})
        self.assertEqual((dates[0], dates[-1], len(dates)), ("2026-01-01", "2026-12-31", 365))

    def test_boundaries_per_station(self):
        rows = self.rows(generator.generate(self.tmp / "w.db"))
        for station in ("ST-A", "ST-B", "ST-C"):
            mine = [r for r in rows if r[0] == station]
            self.assertTrue(any(r[2] == 35.0 for r in mine))
            self.assertTrue(any(r[2] == 34.9 for r in mine))
            self.assertTrue(any(r[4] == 20.0 for r in mine))
            self.assertTrue(any(r[4] == 19.9 for r in mine))
            self.assertTrue(any(r[2] >= 35.0 and r[4] >= 20.0 for r in mine))
        self.assertEqual(len([r for r in rows if r[0] == "ST-A" and r[1].startswith("2026-01")]), 31)

    def test_same_seed_same_rows_and_replace(self):
        first = self.rows(generator.generate(self.tmp / "a.db", seed=5))
        path = generator.generate(self.tmp / "b.db", seed=5)
        self.assertEqual(first, self.rows(path))
        generator.generate(path, seed=5)  # replacing keeps exactly the new rows
        self.assertEqual(len(self.rows(path)), 1095)
        self.assertNotEqual(first, self.rows(generator.generate(self.tmp / "c.db", seed=6)))

    def test_unwritable_target_leaves_no_file(self):
        target = self.tmp / "missing-dir" / "w.db"
        self.assertEqual(generator.main(["--out", str(target)]), 1)
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
