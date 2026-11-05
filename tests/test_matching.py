"""Pairing a student with a project: interests pick the story, the readiness check's results pick the start."""
import unittest

from diagnostic.simulation import profile_student, respond
from engine.course import Course
from engine.grader import Grader
from engine.matching import interest_words, match_story, skill_fit
from tests.helpers import TempDirMixin

CHOICES = [
    {"project": "weather-station", "goals": ["weather_report", "not_sure"], "interests": ["weather", "science"]},
    {"project": "monster-arena", "goals": ["build_game"], "interests": ["game", "video game", "monster"]},
    {"project": "wildlife-watch", "goals": ["find_facts"], "interests": ["animal", "bird", "nature"]},
]
NAMES = {"database_retrieval": "Database Retrieval", "conditionals": "Conditionals", "loops": "Loops", "functions": "Functions"}


class StoryMatchTests(unittest.TestCase):
    def test_the_goal_alone_picks_its_story(self):
        m = match_story(CHOICES, "build_game", "Make a game", None, "weather-station")
        self.assertEqual(m.project, "monster-arena")
        self.assertIn('"Make a game"', m.reasons[0])
        self.assertIsNone(m.theme_idea)

    def test_typed_interests_match_keywords_with_plurals_and_phrases(self):
        self.assertEqual(interest_words("I love Animals, BIRDS and stories!"), ["i", "love", "animal", "bird", "and", "story"])
        m = match_story(CHOICES, "not_sure", "I'm not sure yet", "I like video games", "weather-station")
        self.assertEqual(m.project, "monster-arena")
        self.assertEqual(m.fits[0].words, ["game", "video game"])

    def test_two_matching_words_outweigh_a_tapped_goal(self):
        m = match_story(CHOICES, "build_game", "Make a game", "animals and birds", "weather-station")
        self.assertEqual(m.project, "wildlife-watch")

    def test_no_signal_keeps_the_original_project(self):
        for goal in (None, "not_sure"):
            m = match_story(CHOICES, goal, None, None, "weather-station")
            self.assertEqual(m.project, "weather-station")
            self.assertIn("switch below", m.reasons[0])

    def test_unmatched_words_become_a_theme_idea(self):
        m = match_story(CHOICES, "not_sure", None, "soccer", "weather-station")
        self.assertEqual((m.project, m.theme_idea), ("weather-station", "soccer"))

    def test_reasons_quote_catalog_keywords_not_the_students_words(self):
        m = match_story(CHOICES, None, None, "my cat Whiskers is the best animal", "weather-station")
        self.assertEqual(m.project, "wildlife-watch")
        self.assertNotIn("Whiskers", " ".join(m.reasons))


class SkillFitTests(unittest.TestCase):
    def test_only_trusted_results_show_up(self):
        decisions = {
            "database_retrieval": {"stage": 3, "used": True},
            "conditionals": {"stage": 2, "used": False},        # not confident: never shown as a strength
            "loops": {"stage": 0, "used": True},
            "functions": {"stage": 1, "used": True},
        }
        decisions["functions"] = {"stage": 0, "used": True}     # a confident gap with no practice problem
        fit = skill_fit(decisions, NAMES, planned={"loops"})
        self.assertEqual((fit.strengths, fit.warm_ups, fit.new_ideas), (["Database Retrieval"], ["Loops"], ["Functions"]))
        text = " ".join(fit.reasons).lower()
        self.assertIn("database retrieval", text)
        self.assertIn("warm-up on loops", text)
        self.assertIn("functions will be newer to you", text)
        for word in ("stage", "score", "grade", "confidence", "%"):
            self.assertNotIn(word, text)

    def test_nothing_confident_gives_a_neutral_line(self):
        fit = skill_fit({"loops": {"stage": 2, "used": False}}, NAMES)
        self.assertEqual(fit.reasons, ["You'll build it one level at a time, with hints when you need them."])


class CourseMatchTests(TempDirMixin, unittest.TestCase):
    def quest(self, course, profile, goal, words=None):
        student = profile_student(profile)
        started = course.diagnostic_start(buddy="cloud", goal=goal, goal_text=words)
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
            step = course.diagnostic_next(sid)
        return sid, step

    def test_typed_interests_choose_the_project_the_lesson_opens(self):
        course = Course(self.tmp, grader=Grader(timeout_s=5))
        sid, result = self.quest(course, "strong", "not_sure", "I like animals and birds")
        self.assertEqual(course.core_project_for(sid), "wildlife-watch")
        self.assertEqual(course.state(sid)["project"]["title"], course._project(course.projects_root / "wildlife-watch").title)
        match = result["match"]
        self.assertEqual(match["project"], "wildlife-watch")
        self.assertTrue(match["because"] and match["fit"])
        self.assertTrue(any("you won't repeat the basics" in line for line in match["fit"]), match["fit"])
        choices = course.project_choices(sid)
        self.assertEqual([c["project"] for c in choices["choices"] if c["suggested"]], ["wildlife-watch"])
        self.assertEqual(choices["match"]["project"], "wildlife-watch")

    def test_a_student_with_gaps_is_told_about_the_warm_up(self):
        course = Course(self.tmp, grader=Grader(timeout_s=5))
        sid, result = self.quest(course, "struggling", "build_game")
        self.assertEqual(result["match"]["project"], "monster-arena")
        profile = course.store.profile(sid)
        gaps = [c for c, d in profile["diagnostic"]["decisions"].items() if d["used"] and d["stage"] == 0]
        self.assertTrue(gaps)                                   # the simulated student has confident gaps
        fit = " ".join(result["match"]["fit"])
        if profile["planned_practice"]["problems"]:
            self.assertIn("warm-up", fit)
        for concept in gaps:
            self.assertIn(course.catalog.name(concept).lower(), fit.lower())

    def test_personal_details_in_interests_are_dropped_and_never_used(self):
        course = Course(self.tmp, grader=Grader(timeout_s=5))
        started = course.diagnostic_start(buddy="cloud", goal="not_sure", goal_text="games, email me at kid@example.com")
        self.assertTrue(started["notices"])
        from diagnostic.store import DiagnosticStore
        self.assertIsNone(DiagnosticStore(self.tmp).load(started["student_id"]).goal_text)
        self.assertEqual(course.suggested_project(started["student_id"]), "weather-station")

    def test_students_who_skip_the_check_get_no_match(self):
        course = Course(self.tmp, grader=Grader(timeout_s=5))
        sid = course.new_student()
        self.assertIsNone(course.project_match(sid))
        self.assertIsNone(course.project_choices(sid)["match"])


if __name__ == "__main__":
    unittest.main()
