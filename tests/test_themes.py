"""Themes, AI hints, and content filtering, using a scripted model (no network)."""
import copy
import json
import unittest

from engine.ai import ModelError, ModelReply, ScriptedProvider
from engine.events import EventLog
from engine.grader import Grader
from engine.hints import AIHinter, check_hint
from engine.progress import JsonProgressStore
from engine.project import load_project
from engine.safety import ContentFilter, screen_text
from engine.session import Engine
from engine.themes.builder import BUILT, FAILED, REFUSED, ThemeBuilder
from engine.themes.samples import POKEMON
from engine.themes.spec import ThemeError, parse_theme
from tests.helpers import TempDirMixin, project


def allow():
    return ModelReply(tool_name="screen_request", tool_input={"allowed": True, "category": "ok"})


def theme(data=None):
    return ModelReply(tool_name="create_theme", tool_input=copy.deepcopy(data or POKEMON))


class SpecTests(unittest.TestCase):
    def errors(self, **changes):
        data = copy.deepcopy(POKEMON)
        for key, value in changes.items():
            data[key] = value
        with self.assertRaises(ThemeError) as ctx:
            parse_theme(data)
        return " | ".join(ctx.exception.errors)

    def test_sample_is_valid_and_names_are_derived(self):
        spec = parse_theme(POKEMON)
        self.assertEqual(spec.functions["get"], "get_pokemon")
        self.assertEqual(spec.summary_keys["flagged"], "flagged_dex_numbers")

    def test_identifiers_are_strict(self):
        self.assertIn("reserved", self.errors(group_column="group"))
        self.assertIn("reserved", self.errors(table="type"))
        self.assertIn("lowercase", self.errors(table="pokedex; DROP TABLE x"))
        self.assertIn("lowercase", self.errors(name_column="Name"))

    def test_numbers_names_and_labels(self):
        bad_metric = dict(POKEMON["metric_a"], threshold=189.5)
        self.assertIn("threshold", self.errors(metric_a=bad_metric))
        few = dict(POKEMON["names"], Kanto=["Pikachu"] * 3)
        self.assertIn("12 to 40", self.errors(names=few))
        self.assertIn("must all be different", self.errors(normal_label="powerful"))
        self.assertIn("3 group", self.errors(groups=["Kanto", "Johto"]))

    def test_student_visible_text_is_filtered(self):
        self.assertIn("content filter", self.errors(story="Collect guns across the regions."))


class FilterTests(unittest.TestCase):
    def test_local_rules(self):
        self.assertEqual(screen_text("Email me at kid@example.com").category, "personal_information")
        self.assertEqual(screen_text("call 555-123-4567").category, "personal_information")
        self.assertEqual(screen_text("pokemon with guns").category, "violence")
        self.assertTrue(screen_text("Pokemon battles in Kanto").allowed)

    def test_normal_code_is_not_blocked(self):
        self.assertTrue(screen_text(project().reference_path.read_text()).allowed)
        self.assertTrue(screen_text("x = '2026-01-31'; rows = conn.execute(sql, (a, b)).fetchall()").allowed)

    def test_moderation_fails_closed(self):
        self.assertEqual(ContentFilter(ScriptedProvider([ModelError("down")])).screen_request("cats").category,
                         "filter_error")
        refused = ModelReply(tool_name="screen_request", tool_input={"allowed": False, "category": "gambling"})
        self.assertEqual(ContentFilter(ScriptedProvider([refused])).screen_request("casino").category, "gambling")


class BuilderTests(TempDirMixin, unittest.TestCase):
    def test_build_passes_quality_gate(self):
        provider = ScriptedProvider([allow(), theme()])
        result = ThemeBuilder(provider, self.tmp / "themes").build("I like pokemon")
        self.assertEqual(result.status, BUILT, result.category)
        self.assertTrue((result.project_path / "dataset" / "data.db").exists())
        self.assertIn("<student_request>", provider.requests[1]["prompt"])
        self.assertFalse(any(p.name.startswith(".building") for p in (self.tmp / "themes").iterdir()))

    def test_local_filter_refuses_without_model_call(self):
        provider = ScriptedProvider([])
        result = ThemeBuilder(provider, self.tmp / "themes").build("school shooting game")
        self.assertEqual((result.status, result.category, len(provider.requests)), (REFUSED, "violence", 0))

    def test_retry_fixes_invalid_spec(self):
        bad = copy.deepcopy(POKEMON)
        bad["table"] = "select"
        provider = ScriptedProvider([allow(), theme(bad), theme()])
        result = ThemeBuilder(provider, self.tmp / "themes").build("pokemon")
        self.assertEqual(result.status, BUILT)
        self.assertIn("reserved word", provider.requests[2]["prompt"])

    def test_two_invalid_specs_or_model_error_fail(self):
        bad = copy.deepcopy(POKEMON)
        bad["groups"] = ["Kanto"]
        self.assertEqual(ThemeBuilder(ScriptedProvider([allow(), theme(bad), theme(bad), theme(bad)]), self.tmp / "t")
                         .build("pokemon").status, FAILED)
        self.assertEqual(ThemeBuilder(ScriptedProvider([allow(), ModelError("timeout")]), self.tmp / "t")
                         .build("pokemon").status, FAILED)
        self.assertFalse((self.tmp / "t").exists() and any((self.tmp / "t").iterdir()))

    def test_overlong_request_refused(self):
        self.assertEqual(ThemeBuilder(ScriptedProvider([]), self.tmp).build("x" * 301).status, REFUSED)


class ThemedGradingTests(TempDirMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        from pathlib import Path
        cls._root = tempfile.TemporaryDirectory()
        result = ThemeBuilder(ScriptedProvider([allow(), theme()]), Path(cls._root.name)).build("pokemon")
        cls.project = load_project(result.project_path)
        cls.reference = cls.project.reference_path.read_text()

    @classmethod
    def tearDownClass(cls):
        cls._root.cleanup()

    def grade(self, problem_id, source):
        return Grader(timeout_s=5).grade(self.project, self.project.problem(problem_id), self.write("s.py", source))

    def messages(self, result):
        return " | ".join(f["message"] for f in result.failures)

    def test_mistakes_are_caught(self):
        exclusive = self.reference.replace("dex_number >= ? AND dex_number <= ?", "dex_number > ? AND dex_number < ?")
        self.assertIn("include both", self.messages(self.grade("level-1", exclusive)))
        strict = self.reference.replace('entry["attack"] >= 100.0', 'entry["attack"] > 100.0')
        self.assertIn("should count as 'powerful'", self.messages(self.grade("level-2", strict)))
        shortcut = self.reference.replace("    flagged.sort()\n", "    flagged = sorted(flagged)\n", 1)
        self.assertIn("must not call sorted()", self.messages(self.grade("level-3", shortcut)))
        inline = self.reference.replace("entries.append((row, classify_pokemon(row)))",
                                        "entries.append((row, ['regular']))")
        self.assertIn("classify_pokemon", self.messages(self.grade("level-4", inline)))

    def test_student_reaches_the_end(self):
        engine = Engine(self.project, JsonProgressStore(self.tmp), EventLog(self.tmp), grader=Grader(timeout_s=5))
        sid = engine.new_student()
        path = self.write("solution.py", self.reference)
        outcomes = [engine.submit(sid, path) for _ in range(4)]
        self.assertTrue(all(o.passed for o in outcomes))
        self.assertTrue(outcomes[-1].complete)


GOOD_HINT = "Look at the comparison signs in your WHERE clause. Should the first and last numbers be included?"


class AIHintTests(TempDirMixin, unittest.TestCase):
    WRONG = "def get_readings(conn, a, b, c):\n    return []\n"

    def engine(self, provider):
        return Engine(project(), JsonProgressStore(self.tmp), EventLog(self.tmp), grader=Grader(timeout_s=5),
                      hint_provider=provider)

    def submit(self, provider, code=None):
        engine = self.engine(provider)
        sid = engine.new_student()
        return sid, engine.submit(sid, self.write("s.py", code or self.WRONG))

    def test_ai_hint_used_and_prompt_is_private(self):
        provider = ScriptedProvider([ModelReply(text=GOOD_HINT)])
        sid, outcome = self.submit(provider)
        self.assertEqual((outcome.hint, outcome.hint_source), (GOOD_HINT, "ai"))
        prompt = provider.requests[0]["system"] + provider.requests[0]["prompt"]
        self.assertNotIn(sid, prompt)
        self.assertNotIn("date >= ? AND date <= ?", prompt)   # the reference solution is never sent
        self.assertIn("<student_code>", prompt)
        events = [e for e in EventLog(self.tmp).read() if e["event"] == "hint"]
        self.assertEqual(events[0]["source"], "ai")

    def test_falls_back_to_authored_hint(self):
        first_hint = project().problem("level-1").hints[0]
        for reply in (ModelError("throttled"), ModelReply(text="```python\nreturn rows\n```"),
                      ModelReply(text="Try: def get_readings(conn, s, a, b): ..."),
                      ModelReply(text="Use a gun to fix it.")):
            with self.subTest(reply=reply):
                _sid, outcome = self.submit(ScriptedProvider([reply]))
                self.assertEqual((outcome.hint, outcome.hint_source), (first_hint, "authored"))

    def test_code_with_personal_info_is_not_sent(self):
        provider = ScriptedProvider([ModelReply(text=GOOD_HINT)])
        _sid, outcome = self.submit(provider, "# by sam@school.org\n" + self.WRONG)
        self.assertEqual((outcome.hint_source, provider.requests), ("authored", []))

    def test_hint_checks(self):
        reference = project().reference_path.read_text()
        self.assertIsNone(check_hint(GOOD_HINT, reference))
        self.assertEqual(check_hint("x" * 401, reference), "too long")
        self.assertEqual(check_hint('Write "WHERE station_id = ? AND date >= ? AND date <= ? " ORDER BY date', reference),
                         "copies the reference solution")
        self.assertEqual(check_hint("SELECT * FROM daily_readings WHERE station_id = ?", reference), "contains code")


if __name__ == "__main__":
    unittest.main()
