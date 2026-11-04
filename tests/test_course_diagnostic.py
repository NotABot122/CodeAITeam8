"""The readiness diagnostic feeding the Course: seeding stages and placing the first problem."""
import unittest

from diagnostic.simulation import play, profile_student, respond
from engine.course import Course, CourseError, seed_from_placement
from engine.demo import GET_EXCLUSIVE
from engine.grader import Grader
from tests.helpers import TempDirMixin

RULES = {"min_confidence": 0.8, "use_borderline": False}


class SeedRuleTests(unittest.TestCase):
    def test_only_confident_non_borderline_results_are_used(self):
        placement = {"concepts": {
            "loops": {"stage": 3, "confidence": 0.93, "borderline": False},
            "conditionals": {"stage": 2, "confidence": 0.61, "borderline": False},
            "functions": {"stage": 1, "confidence": 0.85, "borderline": True},
        }}
        d = seed_from_placement(placement, RULES)
        self.assertEqual((d["loops"]["used"], d["conditionals"]["used"], d["functions"]["used"]), (True, False, False))
        self.assertIn("below 0.8", d["conditionals"]["reason"])
        self.assertTrue(seed_from_placement(placement, {"min_confidence": 0.8, "use_borderline": True})
                        ["functions"]["used"])


class CourseDiagnosticTests(TempDirMixin, unittest.TestCase):
    def course(self):
        return Course(self.tmp, grader=Grader(timeout_s=5))

    def quest(self, course, name):
        """Play a whole quest through the Course methods, as a UI would."""
        student = profile_student(name)
        started = course.diagnostic_start(buddy="cloud", goal=student.goal)
        sid, step, n = started["student_id"], started["first"], 0
        while not step.get("done"):
            n += 1
            view = step["step"]
            content = course.diagnostic().content
            if view["kind"] == "explain":
                response = {"skip": True}
            else:
                item = content.items.get(view["id"]) or next(b for b in content.boosters if b.id == view["id"])
                response = respond(student, item, n)
            course.diagnostic_answer(sid, response, elapsed_ms=8000)
            self.assertEqual(course.state(sid)["diagnostic"], "in_progress")
            step = course.diagnostic_next(sid)
        return sid, student

    def test_quest_through_the_course_seeds_and_places(self):
        course = self.course()
        sid, student = self.quest(course, "strong")
        state = course.state(sid)
        self.assertEqual(state["diagnostic"], "applied")          # applied automatically when the quest ended
        seeded = course.store.profile(sid)["diagnostic"]["seeded"]
        self.assertTrue(seeded)
        for concept, stage in seeded.items():
            self.assertLessEqual(stage, student.latent[concept])  # never seeded above the true level here
        stages = {c["id"]: c["stage"] for c in state["concepts"]}
        record, _ = course.engine(sid).open(sid)
        for concept, stage in seeded.items():
            self.assertEqual((stages[concept], record.concepts[concept].stage), (stage, stage))
        self.assertEqual(state["problem"]["id"], record.current_problem)

    def test_lucky_guesses_are_not_seeded(self):
        course = self.course()
        out = play(course.diagnostic(), profile_student("guesser"))
        summary = course.apply_diagnostic(out["student_id"])
        self.assertTrue(all(stage == 0 for stage in summary["seeded"].values()))
        self.assertTrue(any(not d["used"] for d in summary["decisions"].values()))

    def test_started_lesson_keeps_its_place_and_apply_is_idempotent(self):
        course = self.course()
        out = play(course.diagnostic(), profile_student("strong"))
        sid = out["student_id"]
        course.submit(sid, self.write("x.py", GET_EXCLUSIVE))            # the lesson has started
        before, _ = course.engine(sid).open(sid)
        summary = course.apply_diagnostic(sid)
        after, _ = course.engine(sid).open(sid)
        self.assertTrue(summary["lesson_already_started"])
        self.assertEqual((after.attempts, after.current_problem), (before.attempts, before.current_problem))
        self.assertEqual(course.apply_diagnostic(sid), summary)
        self.assertTrue(course.store.profile(sid)["concepts"])           # the profile still learns the stages

    def test_unfinished_quest_is_not_applied(self):
        course = self.course()
        sid = course.diagnostic_start()["student_id"]
        with self.assertRaises(CourseError):
            course.apply_diagnostic(sid)
        self.assertEqual(course.state(sid)["diagnostic"], "in_progress")
        self.assertEqual(course.state(course.new_student())["diagnostic"], "none")


if __name__ == "__main__":
    unittest.main()
