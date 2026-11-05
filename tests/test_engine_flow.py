"""End-to-end flows through the Engine."""
import unittest

from engine.demo import BUILD_GOOD, CLASSIFY_GOOD, GET_EXCLUSIVE, GET_GOOD, STRONG, STRUGGLING, SUMMARIZE_GOOD
from engine.events import EventLog
from engine.grader import GradeResult, UNGRADED
from engine.router import Decision
from tests.helpers import TempDirMixin


class UngradedGrader:
    def grade(self, *args):
        return GradeResult(UNGRADED, error_message="disk full")


class CrashingGrader:
    def grade(self, *args):
        raise RuntimeError("unexpected grader error")


class EngineFlowTests(TempDirMixin, unittest.TestCase):
    def run_all(self, engine, student_id, sources):
        outcomes = []
        for i, source in enumerate(sources):
            outcomes.append(engine.submit(student_id, self.write(f"{student_id}-{i}.py", source)))
        return outcomes

    def test_strong_student_goes_straight_through(self):
        engine = self.engine()
        sid = engine.new_student()
        outcomes = self.run_all(engine, sid, STRONG)
        self.assertTrue(all(o.passed for o in outcomes))
        self.assertTrue(outcomes[-1].complete)
        record, _ = engine.open(sid)
        self.assertEqual([e["selected"] for e in record.routing_log], ["level-2", "level-3", "level-4", None])
        self.assertEqual(set(record.stages().values()), {1})

    def test_struggling_student_gets_practice_and_converges(self):
        engine = self.engine()
        sid = engine.new_student()
        outcomes = self.run_all(engine, sid, STRUGGLING)
        self.assertTrue(outcomes[-1].complete)
        record, _ = engine.open(sid)
        path = [e["selected"] for e in record.routing_log]
        self.assertEqual(path, ["practice-db-count", "level-2", "level-3", "level-4", None])
        self.assertEqual(record.attempts["level-1"], 4)
        self.assertEqual(record.hints_seen["level-1"], 3)
        self.assertTrue(all(e["stages"] is not None for e in record.routing_log))

    def test_failed_attempt_keeps_problem_and_gives_hints(self):
        engine = self.engine()
        sid = engine.new_student()
        first, second = self.run_all(engine, sid, [GET_EXCLUSIVE, GET_EXCLUSIVE])
        self.assertFalse(first.passed)
        self.assertEqual(first.next_problem.id, "level-1")
        self.assertNotEqual(first.hint, second.hint)
        self.assertTrue(first.messages[0].startswith("Level 1: "))

    def test_progress_survives_new_engine(self):
        engine = self.engine()
        sid = engine.new_student()
        self.run_all(engine, sid, STRONG[:2])
        again = self.engine()
        problem, _ = again.current_problem(sid)
        self.assertEqual(problem.id, "level-3")
        self.assertIn("Levels passed: 1, 2", again.progress_view(sid))

    def test_router_error_falls_back_and_logs(self):
        def broken(*args, **kwargs):
            raise RuntimeError("boom")
        engine = self.engine(router=broken)
        sid = engine.new_student()
        outcomes = self.run_all(engine, sid, STRONG)
        self.assertIn("fixed order", " ".join(outcomes[0].notices))
        self.assertTrue(outcomes[-1].complete)
        events = EventLog(self.tmp).read()
        fallbacks = [e for e in events if e["event"] == "fallback"]
        self.assertEqual([e["reason"] for e in fallbacks], ["router_error"])
        self.assertEqual(fallbacks[0]["student_id"], sid)

    def test_router_returning_unknown_problem_falls_back(self):
        engine = self.engine(router=lambda *a, **k: Decision("level-99", "next_level"))
        sid = engine.new_student()
        outcome = self.run_all(engine, sid, STRONG[:1])[0]
        self.assertEqual(outcome.next_problem.id, "level-2")
        self.assertEqual([e["reason"] for e in EventLog(self.tmp).read() if e["event"] == "fallback"],
                         ["problem_not_in_manifest"])

    def test_adaptive_off_uses_fixed_order(self):
        engine = self.engine(adaptive=False)
        sid = engine.new_student()
        self.run_all(engine, sid, [GET_EXCLUSIVE, GET_EXCLUSIVE, GET_EXCLUSIVE, GET_GOOD])
        problem, _ = engine.current_problem(sid)
        self.assertEqual(problem.id, "level-2")  # no practice problem on the fixed path

    def test_ungraded_leaves_progress_alone(self):
        engine = self.engine(grader=UngradedGrader())
        sid = engine.new_student()
        outcome = engine.submit(sid, self.write("x.py", GET_GOOD))
        record, _ = engine.open(sid)
        self.assertEqual((outcome.status, record.attempts, record.current_problem), ("ungraded", {}, "level-1"))
        self.assertIn("wasn't counted", outcome.messages[0])

    def test_unexpected_grader_failure_is_ungraded_and_retry_works(self):
        engine = self.engine(grader=CrashingGrader())
        sid = engine.new_student()
        path = self.write("crash.py", GET_GOOD)
        result = engine.submit(sid, path)
        record, _ = engine.open(sid)
        self.assertEqual((result.status, record.attempts, record.current_problem), ("ungraded", {}, "level-1"))
        self.assertEqual(set(record.stages().values()), {0})
        from engine.grader import Grader
        engine.grader = Grader()
        self.assertTrue(engine.submit(sid, path).passed)

    def test_unexpected_hint_failure_uses_authored_hint(self):
        engine = self.engine()
        sid = engine.new_student()
        class BrokenHinter:
            def hint(self, *args, **kwargs):
                raise RuntimeError("provider failure")
        engine.hinter = BrokenHinter()
        result = engine.submit(sid, self.write("bad.py", GET_EXCLUSIVE))
        self.assertFalse(result.passed)
        self.assertTrue(result.hint)
        self.assertEqual(result.hint_source, "authored")
        self.assertTrue(any(e.get("reason") == "hint service unavailable" for e in EventLog(self.tmp).read()))

    def test_corrupt_progress_restarts_on_fallback(self):
        engine = self.engine()
        sid = engine.new_student()
        self.run_all(engine, sid, STRONG[:2])
        path = self.tmp / "progress" / sid / "weather-station.json"
        path.write_text("{broken")
        record, notices = engine.open(sid)
        self.assertEqual((record.current_problem, record.on_fallback), ("level-1", True))
        self.assertIn("couldn't be loaded", notices[0])
        backups = list(path.parent.glob("weather-station.corrupt-*.json"))
        self.assertEqual(backups[0].read_text(), "{broken")

    def test_student_ids_are_random_and_unique(self):
        engine = self.engine()
        ids = {engine.new_student() for _ in range(50)}
        self.assertEqual(len(ids), 50)
        self.assertTrue(all(len(i) == 32 for i in ids))


if __name__ == "__main__":
    unittest.main()
