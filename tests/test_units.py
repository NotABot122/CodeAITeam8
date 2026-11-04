"""Loop checker, stage tracker, router, feedback, and progress store."""
import json
import random
import unittest

from engine.feedback import next_hint
from engine.loop_checker import find_loop_problems
from engine.manifest import StageCriterion
from engine.progress import JsonProgressStore, ProgressLoadError, ProgressRecord
from engine.router import NEXT_LEVEL, NO_PRACTICE_REMAINING, PRACTICE_ASSIGNED, PROJECT_COMPLETE, next_problem
from engine.stages import ConceptState, initial_states, record_result
from tests.helpers import TempDirMixin, project

CRITERIA = {1: StageCriterion(3, None), 2: StageCriterion(2, None), 3: StageCriterion(1, 0)}


class LoopCheckerTests(unittest.TestCase):
    def test_loop_passes(self):
        src = "def summarize(r):\n    t = 0\n    for x in r:\n        t += x\n    out = []\n    out.sort()\n    return t\n"
        self.assertEqual(find_loop_problems(src, "summarize"), [])

    def test_comprehension_is_not_a_loop_and_calls_are_named(self):
        src = "def summarize(r):\n    a = [x for x in r]\n    return sum(a), max(a), len(a)\n"
        problems = find_loop_problems(src, "summarize")
        self.assertIn("must use a for or while loop", problems[0])
        self.assertTrue(any("sum() (line 3)" in p for p in problems))
        self.assertTrue(any("len() (line 3)" in p for p in problems))

    def test_nested_function_checked(self):
        src = "def summarize(r):\n    def helper():\n        return sorted(r)\n    while False:\n        pass\n    return helper()\n"
        self.assertEqual(len(find_loop_problems(src, "summarize")), 1)
        self.assertIn("sorted() (line 3)", find_loop_problems(src, "summarize")[0])

    def test_other_functions_ignored(self):
        self.assertEqual(find_loop_problems("def other(x):\n    return sum(x)\n", "summarize"), [])


class StageTrackerTests(unittest.TestCase):
    def test_first_try_pass_raises_one_stage(self):
        states = initial_states(["a"])
        changes = record_result(states, ["a"], "p1", 1, 0, CRITERIA, 1)
        self.assertEqual((states["a"].stage, len(changes)), (1, 1))

    def test_too_many_attempts_resets_streak(self):
        states = {"a": ConceptState(stage=0, streak=1, streak_problems=["p0"])}
        record_result(states, ["a"], "p1", 4, 3, CRITERIA, 2)
        self.assertEqual((states["a"].stage, states["a"].streak), (0, 0))

    def test_streak_needs_distinct_problems(self):
        states = initial_states(["a"])
        for _ in range(3):
            record_result(states, ["a"], "p1", 1, 0, CRITERIA, 3)
        self.assertEqual((states["a"].stage, states["a"].streak), (0, 1))
        record_result(states, ["a"], "p2", 1, 0, CRITERIA, 3)
        record_result(states, ["a"], "p3", 1, 0, CRITERIA, 3)
        self.assertEqual((states["a"].stage, states["a"].streak), (1, 0))

    def test_stage_three_cap_and_unmapped_concepts(self):
        states = {"a": ConceptState(stage=3), "b": ConceptState(stage=1, streak=0)}
        record_result(states, ["a"], "p", 1, 0, CRITERIA, 1)
        self.assertEqual((states["a"].stage, states["b"].stage), (3, 1))

    def test_random_sequences_never_fall_and_replay(self):
        rng = random.Random(3)
        for _ in range(300):
            seq = [(rng.choice("ab"), f"p{rng.randint(1, 6)}", rng.randint(1, 5), rng.randint(0, 3))
                   for _ in range(rng.randint(1, 40))]
            length = rng.randint(1, 4)
            runs = []
            for _ in range(2):
                states = initial_states(["a", "b"])
                previous = {"a": 0, "b": 0}
                for concept, pid, attempts, hints in seq:
                    record_result(states, [concept], pid, attempts, hints, CRITERIA, length)
                    for cid, st in states.items():
                        self.assertTrue(previous[cid] <= st.stage <= 3)
                        self.assertLessEqual(st.stage - previous[cid], 1)
                        previous[cid] = st.stage
                runs.append({k: v.to_dict() for k, v in states.items()})
            self.assertEqual(runs[0], runs[1])


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.m = project().manifest

    def test_ready_student_advances(self):
        d = next_problem(self.m, {"database_retrieval": 1}, ["level-1"], "level-1")
        self.assertEqual((d.problem_id, d.reason), ("level-2", NEXT_LEVEL))

    def test_struggling_student_gets_practice(self):
        d = next_problem(self.m, {"database_retrieval": 0}, ["level-1"], "level-1")
        self.assertEqual((d.problem_id, d.reason, d.origin_level), ("practice-db-count", PRACTICE_ASSIGNED, "level-1"))

    def test_practice_then_next_level_or_none_remaining(self):
        d = next_problem(self.m, {"database_retrieval": 1}, ["level-1", "practice-db-count"],
                         "practice-db-count", "level-1")
        self.assertEqual(d.problem_id, "level-2")
        d = next_problem(self.m, {"database_retrieval": 0}, ["level-1", "practice-db-count"],
                         "practice-db-count", "level-1")
        self.assertEqual((d.problem_id, d.reason), ("level-2", NO_PRACTICE_REMAINING))

    def test_level_three_struggle_still_reaches_level_four(self):
        d = next_problem(self.m, {"loops": 0}, ["level-3", "practice-rainy-days"], "practice-rainy-days", "level-3")
        self.assertEqual(d.problem_id, "level-4")

    def test_last_level_completes(self):
        d = next_problem(self.m, {}, ["level-4"], "level-4")
        self.assertEqual((d.problem_id, d.reason), (None, PROJECT_COMPLETE))

    def test_deterministic(self):
        args = (self.m, {"conditionals": 0}, ["level-1", "level-2"], "level-2")
        self.assertEqual(next_problem(*args), next_problem(*args))


class HintTests(unittest.TestCase):
    def test_hints_in_order_then_repeat_last(self):
        problem = project().problem("level-1")
        seen, shown = 0, []
        for _ in range(5):
            hint, seen = next_hint(problem, seen)
            shown.append(hint)
        self.assertEqual(shown[:3], problem.hints)
        self.assertEqual(shown[3:], [problem.hints[-1]] * 2)


class ProgressStoreTests(TempDirMixin, unittest.TestCase):
    def test_round_trip_property(self):
        rng = random.Random(9)
        store = JsonProgressStore(self.tmp)
        for i in range(100):
            record = ProgressRecord(
                student_id=f"s{i}", project_id="weather-station",
                concepts={c: ConceptState(rng.randint(0, 3), rng.randint(0, 2), [f"p{rng.randint(1, 3)}"])
                          for c in ("a", "b")},
                current_problem=rng.choice([None, "level-2"]), origin_level=rng.choice([None, "level-1"]),
                attempts={"level-1": rng.randint(1, 9)}, hints_seen={"level-1": rng.randint(0, 3)},
                passed_problems=["level-1"], on_fallback=rng.random() < 0.5, complete=rng.random() < 0.5,
                routing_log=[{"selected": "level-2", "reason": "next_level"}],
            )
            store.save(record)
            self.assertEqual(store.load(f"s{i}", "weather-station"), record)

    def test_corrupt_or_incomplete_record(self):
        store = JsonProgressStore(self.tmp)
        path = self.tmp / "progress" / "s1" / "weather-station.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not json")
        with self.assertRaises(ProgressLoadError):
            store.load("s1", "weather-station")
        path.write_text(json.dumps({"student_id": "s1"}))
        with self.assertRaises(ProgressLoadError):
            store.load("s1", "weather-station")


if __name__ == "__main__":
    unittest.main()
