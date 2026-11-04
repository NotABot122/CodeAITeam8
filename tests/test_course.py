"""The adaptive path across projects: judging, deciding, quizzes, and full journeys."""
import json
import shutil
import unittest

import yaml

from engine import REPO_ROOT
from engine.ai import ModelError, ModelReply, ScriptedProvider
from engine.content import check_content
from engine.course import (ALL_DONE, NEW_THEME, NEXT_TOPIC, REVISION, STEADY, STRONG, STRUGGLED, ConceptEvidence,
                           Course, CourseError, assess, decide, load_catalog)
from engine.demo import GET_EXCLUSIVE, GET_GOOD, GET_UNSORTED_TUPLES, STRONG as STRONG_SUBMISSIONS
from engine.grader import Grader
from engine.progress import ProgressRecord
from engine.project import load_project
from engine.quiz import grade_quiz, public_questions
from engine.rubric import RubricGrader
from engine.stages import ConceptState
from tests.helpers import TempDirMixin, project

PROJECTS = REPO_ROOT / "projects"
CATALOG = load_catalog(PROJECTS)


class RubricOnly(ScriptedProvider):
    """Scores every quiz answer at Stage 2. Any other request (AI hints) fails, so hints fall back."""

    def complete(self, system, prompt, max_tokens, tools=None, require_tool=False):
        self.requests.append({"system": system, "prompt": prompt})
        if tools and tools[0].name == "score_answer":
            return score(2)
        raise ModelError("only quiz scoring in this test")


def ev(concept, level, attempts=1, hints=0, practice=False):
    return ConceptEvidence(concept, level, attempts, hints, hints, practice, 1)


def score(stage=2, feedback="Good start. Add an example."):
    return ModelReply(tool_name="score_answer", tool_input={"stage": stage, "feedback": feedback})


class AssessTests(unittest.TestCase):
    def record(self, attempts, hints, routing=()):
        p = project()
        return ProgressRecord("s", p.id, {c: ConceptState() for c in p.manifest.concept_ids()}, None,
                              attempts=attempts, hints_seen=hints, routing_log=list(routing))

    def test_levels(self):
        th = CATALOG.thresholds
        strong = assess(project(), self.record({f"level-{i}": 1 for i in range(1, 5)}, {}), th)
        self.assertEqual({e.level for e in strong.values()}, {STRONG})
        steady = assess(project(), self.record({"level-1": 3, "level-2": 1, "level-3": 1, "level-4": 1},
                                               {"level-1": 1}), th)
        self.assertEqual(steady["database_retrieval"].level, STEADY)
        hard = assess(project(), self.record({"level-1": 4, "level-2": 1, "level-3": 2, "level-4": 1},
                                             {"level-1": 3, "level-3": 2}), th)
        self.assertEqual((hard["database_retrieval"].level, hard["loops"].level), (STRUGGLED, STRUGGLED))
        practiced = assess(project(), self.record(
            {"level-1": 2, "practice-db-count": 1, "level-2": 1, "level-3": 1, "level-4": 1}, {},
            [{"selected": "practice-db-count", "reason": "practice_assigned"}]), th)
        self.assertEqual(practiced["database_retrieval"].level, STRUGGLED)


class DecideTests(unittest.TestCase):
    def test_struggle_gives_revision_for_the_worst_concept(self):
        rec = decide(CATALOG, "data-logic", None, {"database_retrieval": ev("database_retrieval", STRUGGLED, 4, 3),
                                                   "loops": ev("loops", STRUGGLED, 4, 0),
                                                   "functions": ev("functions", STRONG)}, {}, ["data-logic"], True)
        self.assertEqual((rec.kind, rec.options[0].project), (REVISION, "revision-database-retrieval"))
        self.assertEqual(rec.options[1].kind, NEXT_TOPIC)

    def test_struggling_again_after_that_revision_moves_on(self):
        rec = decide(CATALOG, "", "loops", {"loops": ev("loops", STRUGGLED, 5, 2)}, {}, ["data-logic"], True)
        self.assertEqual(rec.kind, NEXT_TOPIC)
        self.assertEqual(rec.options[1].project, "revision-loops")

    def test_strong_goes_to_the_least_mastered_topic(self):
        evidence = {c: ev(c, STRONG) for c in ("database_retrieval", "conditionals", "loops", "functions")}
        rec = decide(CATALOG, "data-logic", None, evidence, {"functions": 1, "loops": 1}, ["data-logic"], True)
        self.assertEqual((rec.kind, rec.options[0].project), (NEXT_TOPIC, "weather-collections"))
        self.assertIn("aced", rec.reason)

    def test_steady_offers_a_new_theme_only_when_possible(self):
        evidence = {"loops": ev("loops", STEADY, 3)}
        self.assertEqual(decide(CATALOG, "data-logic", None, evidence, {}, ["data-logic"], True).kind, NEW_THEME)
        self.assertEqual(decide(CATALOG, "data-logic", None, evidence, {}, ["data-logic"], False).kind, NEXT_TOPIC)
        self.assertEqual(decide(CATALOG, "collections", None, {"lists": ev("lists", STEADY, 3)}, {},
                                ["data-logic", "collections"], True).kind, ALL_DONE)


class QuizTests(TempDirMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quiz = load_project(PROJECTS / "revision-loops").problem("level-1")

    def answers(self, q1=1, q2=1, q3="It builds the total, so it starts before the loop."):
        return {"q1": q1, "q2": q2, "q3": q3}

    def test_public_questions_hide_answers(self):
        shown = public_questions(self.quiz.questions)
        self.assertTrue(all("answer" not in q and "rubric" not in q and "explanation" not in q for q in shown))

    def test_wrong_predict_shows_explanation_and_fails(self):
        result = grade_quiz("Level 1", self.quiz.questions, self.answers(q1=0))
        self.assertFalse(result.passed)
        self.assertIn("0 -> 4 -> 5 -> 8", result.results[0].explanation)
        self.assertIsNone(result.results[1].explanation)

    def test_explain_scored_or_saved(self):
        grader = RubricGrader(ScriptedProvider([score(2)]))
        result = grade_quiz("Level 1", self.quiz.questions, self.answers(), grader)
        self.assertTrue(result.passed)
        self.assertEqual((result.results[2].score, result.results[2].feedback), (2, "Good start. Add an example."))
        ungraded = grade_quiz("Level 1", self.quiz.questions, self.answers(), RubricGrader(ScriptedProvider([ModelError("x")])))
        self.assertTrue(ungraded.passed)
        self.assertIsNone(ungraded.results[2].score)

    def test_explain_must_be_written_and_appropriate(self):
        self.assertFalse(grade_quiz("Level 1", self.quiz.questions, self.answers(q3="  ")).passed)
        provider = ScriptedProvider([score(3)])
        blocked = grade_quiz("Level 1", self.quiz.questions, self.answers(q3="email me at kid@school.org"),
                             RubricGrader(provider))
        self.assertFalse(blocked.passed)
        self.assertEqual(provider.requests, [])

    def test_bad_feedback_is_dropped(self):
        result = grade_quiz("Level 1", self.quiz.questions, self.answers(),
                            RubricGrader(ScriptedProvider([score(1, "```total = 0```")])))
        self.assertEqual((result.results[2].score, result.results[2].feedback), (1, None))

    def test_content_check_catches_a_wrong_marked_answer(self):
        copy = self.tmp / "revision-loops"
        shutil.copytree(PROJECTS / "revision-loops", copy)
        path = copy / "levels" / "review" / "questions.yaml"
        questions = yaml.safe_load(path.read_text())
        questions[0]["answer"] = 0
        path.write_text(yaml.safe_dump(questions))
        manifest = (copy / "manifest.yaml").read_text().replace("../weather-station", str(PROJECTS / "weather-station"))
        (copy / "manifest.yaml").write_text(manifest)
        result = check_content(load_project(copy))
        self.assertFalse(result.passed)
        self.assertTrue(any("prints '8'" in p for p in result.problems))


class JourneyTests(TempDirMixin, unittest.TestCase):
    def course(self, provider=None):
        return Course(self.tmp, provider=provider, grader=Grader(timeout_s=5))

    def submit(self, course, sid, source):
        return course.submit(sid, self.write(f"{sid[:6]}-{len(list(self.tmp.iterdir()))}.py", source))

    def reference(self, folder):
        return (PROJECTS / folder / "reference" / "solution.py").read_text()

    def test_strong_student_moves_to_a_new_topic_and_keeps_stages(self):
        course = self.course()
        sid = course.new_student()
        outcomes = [self.submit(course, sid, s) for s in STRONG_SUBMISSIONS]
        step = outcomes[-1].next_step
        self.assertEqual((step["kind"], step["options"][0]["project"]), (NEXT_TOPIC, "weather-collections"))
        self.assertEqual(course.next_step(sid), step)
        with self.assertRaises(CourseError):
            course.start(sid, 5)
        course.start(sid, 0)
        state = course.state(sid)
        self.assertEqual(state["project"]["id"], "weather-collections")
        concepts = {c["id"]: c["stage"] for c in state["concepts"]}
        self.assertEqual((concepts["functions"], concepts["lists"]), (1, 0))   # carried over from part 1
        record, _ = course.engine(sid).open(sid)
        self.assertEqual(record.concepts["functions"].stage, 1)
        final = [self.submit(course, sid, self.reference("weather-collections")) for _ in range(4)][-1]
        self.assertEqual(final.next_step["kind"], ALL_DONE)
        stages = {c["id"]: c["stage"] for c in course.state(sid)["concepts"]}
        # Lists is practiced in Levels 1 and 3, so two first-try passes give Stage 2.
        self.assertEqual((stages["lists"], stages["dictionaries"], stages["functions"]), (2, 2, 2))

    def test_struggling_student_gets_revision_with_questions(self):
        course = self.course(RubricOnly())
        sid = course.new_student()
        for source in (GET_UNSORTED_TUPLES, GET_EXCLUSIVE, GET_EXCLUSIVE, GET_GOOD):
            self.submit(course, sid, source)
        rest = STRONG_SUBMISSIONS[1:]
        # The practice problem comes after Level 1 for a 4-attempt pass.
        self.submit(course, sid, GET_GOOD + "\ndef count_readings(conn, s):\n    return conn.execute("
                                            "'SELECT COUNT(*) FROM daily_readings WHERE station_id = ?', (s,))"
                                            ".fetchone()[0]\n")
        for source in rest:
            outcome = self.submit(course, sid, source)
        step = outcome.next_step
        self.assertEqual((step["kind"], step["options"][0]["project"]), (REVISION, "revision-database-retrieval"))
        course.start(sid, 0)
        state = course.state(sid)
        self.assertEqual((state["problem"]["format"], len(state["problem"]["questions"])), ("quiz", 3))
        self.assertEqual(self.submit(course, sid, GET_GOOD).status, "quiz")
        wrong = course.answer(sid, {"q1": 0, "q2": 1, "q3": "placeholders keep values as data"})
        self.assertFalse(wrong.passed)
        right = course.answer(sid, {"q1": 1, "q2": 1, "q3": "placeholders keep values as data"})
        self.assertTrue(right.passed)
        self.assertEqual(right.question_results[2]["score"], 2)
        done = self.submit(course, sid, self.reference("revision-database-retrieval"))
        self.assertTrue(done.complete)
        self.assertEqual((done.next_step["kind"], done.next_step["options"][0]["project"]),
                         (NEXT_TOPIC, "weather-collections"))
        self.assertIn("Review done", done.next_step["reason"])
        profile = course.store.profile(sid)
        self.assertEqual([c["project_id"] for c in profile["completed"]],
                         ["weather-station", "revision-database-retrieval"])
        self.assertEqual(profile["concepts"]["database_retrieval"], 2)   # reviews top out at Meeting

    def test_third_try_counts_as_struggling_with_the_agreed_thresholds(self):
        # Every failed attempt shows a hint, so passing on try 3 means 2 hints: "struggled".
        course = self.course()
        sid = course.new_student()
        for source in (GET_EXCLUSIVE, GET_EXCLUSIVE) + tuple(STRONG_SUBMISSIONS):
            outcome = self.submit(course, sid, source)
        self.assertEqual(outcome.next_step["kind"], REVISION)

    def test_steady_student_with_ai_is_offered_a_new_theme(self):
        course = self.course(RubricOnly())
        course.catalog.thresholds["struggled"]["min_hints"] = 3      # leave room for a steady band
        sid = course.new_student()
        for source in (GET_EXCLUSIVE, GET_EXCLUSIVE) + tuple(STRONG_SUBMISSIONS):
            outcome = self.submit(course, sid, source)
        self.assertEqual(outcome.next_step["kind"], NEW_THEME)
        with self.assertRaises(CourseError):
            course.start(sid, 0)        # needs a theme request

    def test_old_progress_records_still_load(self):
        course = self.course()
        sid = course.new_student()
        path = self.tmp / "progress" / sid / "weather-station.json"
        data = json.loads(path.read_text())
        data.pop("quiz_scores")
        path.write_text(json.dumps(data))
        self.assertEqual(course.state(sid)["problem"]["id"], "level-1")


class CatalogContentTests(unittest.TestCase):
    def test_every_catalog_project_passes_its_content_check(self):
        folders = [t.project for t in CATALOG.topics] + list(CATALOG.revision.values())
        for folder in folders:
            with self.subTest(project=folder):
                result = check_content(load_project(PROJECTS / folder))
                self.assertTrue(result.passed, result.problems)

    def test_every_concept_has_a_revision_project(self):
        self.assertEqual(sorted(CATALOG.revision), sorted(CATALOG.concepts))


if __name__ == "__main__":
    unittest.main()
