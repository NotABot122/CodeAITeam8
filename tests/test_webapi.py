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
        for i in range(2):
            self.svc.submit(sid, f"print({i})")
        res = self.svc.submit(sid, "print(2)")  # third failed try on Level 1: in-lesson help inserts practice
        state = res["state"]
        self.assertEqual(state["problem"]["kind"], "practice")
        self.assertIn(("practice", "current"), [(n["kind"], n["status"]) for n in state["path"]])
        self.assertTrue(any("practice" in n.lower() for n in res["outcome"]["notices"]))
        res = self.svc.submit(sid, REF)  # pass the practice: back to Level 1, which is not done yet
        self.assertEqual(res["state"]["problem"]["id"], "level-1")

    def test_struggling_without_in_lesson_help_gets_practice_after_the_level(self):
        self.svc.course.catalog.intervention["struggle_after"] = None  # the older, after-the-level behaviour
        sid = self.svc.new_student()["studentId"]
        for _ in range(3):
            self.svc.submit(sid, "print(1)")
        res = self.svc.submit(sid, REF)  # passes, but only on the 4th try
        state = res["state"]
        self.assertEqual(state["problem"]["kind"], "practice")
        self.assertEqual(state["path"][0]["status"], "done")

    def test_finish_then_next_step_then_review_quiz(self):
        sid = self.svc.new_student()["studentId"]
        for _ in range(3):
            self.svc.submit(sid, "print(1)")
        for _ in range(8):
            res = self.svc.submit(sid, REF)
            if res["state"]["complete"]:
                break
        step = res["state"]["nextStep"]
        self.assertEqual(step["options"][0]["kind"], "revision")
        self.assertEqual(len(res["state"]["concepts"]), 6)
        started = self.svc.start_next(sid, 0)["state"]
        self.assertEqual(started["problem"]["format"], "quiz")
        self.assertNotIn("answer", str(started["problem"]["questions"]).lower().replace("your answer", ""))
        with self.assertRaises(ApiError):
            self.svc.submit(sid, "print(1)")  # a quiz step takes answers, not code
        out = self.svc.answer(sid, {q["id"]: 0 if q["type"] == "predict" else "because" for q in started["problem"]["questions"]})
        self.assertIn("questionResults", out["outcome"])

    def test_bad_option_is_a_clear_error(self):
        sid = self.svc.new_student()["studentId"]
        with self.assertRaises(ApiError) as cm:
            self.svc.start_next(sid, 0)
        self.assertEqual(cm.exception.status, 400)

    def test_quest_runs_then_hands_over_to_the_lesson(self):
        q = self.svc.quest_start("cloud", "build_game")
        sid = q["student_id"]
        self.assertRegex(sid, r"^[0-9a-f]{32}$")  # one id format for quest, lesson and app
        self.assertEqual(self.svc.state(sid)["diagnostic"], "in_progress")
        step = q["first"]
        for _ in range(60):
            if step.get("done"):
                break
            st = step["step"]
            if st["type"] == "text":
                response = {"skip": True}
            elif st["type"] == "order":
                response = [c["id"] for c in st["cards"]]
            elif st["type"] == "sort":
                response = {c["id"]: st["buckets"][0]["id"] for c in st["cards"]}
            else:
                response = st["options"][0]["id"]
            self.svc.quest_answer(sid, response, 500)
            step = self.svc.quest_next(sid)
        self.assertTrue(step["done"])
        state = self.svc.state(sid)
        self.assertEqual(state["diagnostic"], "applied")
        self.assertIsNotNone(state["problem"])

    def test_quest_rejects_bad_input(self):
        with self.assertRaises(ApiError):
            self.svc.quest_start("not-a-buddy", "build_game")
        sid = self.svc.quest_start("cloud", "build_game")["student_id"]
        with self.assertRaises(ApiError) as cm:
            self.svc.quest_answer(sid, "zzz", 5)
        self.assertEqual(cm.exception.status, 422)
        with self.assertRaises(ApiError):
            self.svc.quest_next("STU-nope")

    def test_course_view_tracks_topics_and_reviews(self):
        sid = self.svc.new_student()["studentId"]
        v = self.svc.course_view(sid)
        self.assertEqual([t["status"] for t in v["topics"]], ["current", "upcoming"])
        self.assertEqual(len(v["concepts"]), 6)
        self.assertEqual(v["quest"]["status"], "none")
        for _ in range(3):
            self.svc.submit(sid, "print(1)")
        for _ in range(8):
            if self.svc.submit(sid, REF)["state"]["complete"]:
                break
        v = self.svc.course_view(sid)
        self.assertEqual(v["topics"][0]["status"], "done")
        self.assertTrue(v["nextStep"])
        self.svc.start_next(sid, 0)  # the recommended review
        v = self.svc.course_view(sid)
        self.assertTrue(v["now"]["isReview"])
        self.assertEqual(v["topics"][0]["status"], "done")

    def test_theme_needs_ai(self):
        sid = self.svc.new_student()["studentId"]
        with self.assertRaises(ApiError) as cm:
            self.svc.build_theme(sid, "pokemon")
        self.assertEqual(cm.exception.status, 503)


if __name__ == "__main__":
    unittest.main()
