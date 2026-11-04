import tempfile
import unittest
from pathlib import Path

from webapi.service import ApiError, Service

REF = (Path(__file__).resolve().parent.parent / "projects/weather-station/reference/solution.py").read_text()


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.svc = Service(Path(self.tmp.name))

    def test_new_student_state(self):
        s = self.svc.new_student()
        self.assertEqual(s["problem"]["id"], "level-1")
        self.assertEqual([n["status"] for n in s["path"]], ["current", "todo", "todo", "todo"])
        self.assertIn("get_readings", s["code"])
        self.assertNotIn("hints", s["problem"])  # hint text only arrives one at a time, via submit

    def test_bad_ids_are_rejected_before_touching_disk(self):
        for bad in ["../x", "zzz", "0" * 32, "", None]:
            with self.assertRaises(ApiError) as cm:
                self.svc.state(bad)
            self.assertEqual(cm.exception.status, 404)

    def test_submit_validates_input(self):
        sid = self.svc.new_student()["studentId"]
        with self.assertRaises(ApiError):
            self.svc.submit(sid, 5)
        with self.assertRaises(ApiError):
            self.svc.submit(sid, "x" * 20_001)

    def test_failing_then_passing_all_levels(self):
        sid = self.svc.new_student()["studentId"]
        first = self.svc.submit(sid, "print(1)")
        self.assertFalse(first["outcome"]["passed"])
        self.assertEqual(first["state"]["problem"]["attempts"], 1)
        for _ in range(4):
            res = self.svc.submit(sid, REF)
            if res["state"]["complete"]:
                break
        self.assertTrue(res["state"]["complete"])
        self.assertIsNone(res["state"]["problem"])

    def test_struggling_gets_practice_on_the_map(self):
        sid = self.svc.new_student()["studentId"]
        for _ in range(3):
            self.svc.submit(sid, "print(1)")
        res = self.svc.submit(sid, REF)  # passes, but only on the 4th try
        state = res["state"]
        self.assertEqual(state["problem"]["kind"], "practice")
        self.assertIn(("practice", "current"), [(n["kind"], n["status"]) for n in state["path"]])
        self.assertEqual(state["path"][0]["status"], "done")

    def test_theme_needs_ai(self):
        sid = self.svc.new_student()["studentId"]
        with self.assertRaises(ApiError) as cm:
            self.svc.build_theme(sid, "pokemon")
        self.assertEqual(cm.exception.status, 503)


if __name__ == "__main__":
    unittest.main()
