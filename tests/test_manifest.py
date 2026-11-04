import random
import unittest

from engine.manifest import (ConceptDef, LevelDef, Manifest, ManifestError, PracticeDef, StageCriterion,
                             parse_manifest, print_manifest)
from tests.helpers import PROJECT_DIR

VALID = """
title: Demo
concepts:
  - {id: a, name: A}
stage_criteria:
  1: {max_attempts: 3}
levels:
  - {id: l1, number: 1, title: One, folder: levels/l1, concepts: [a], advance_at_stage: 1}
fallback_path: [l1]
"""


class ManifestTests(unittest.TestCase):
    def errors(self, text):
        with self.assertRaises(ManifestError) as ctx:
            parse_manifest(text)
        return " | ".join(ctx.exception.errors)

    def test_project_manifest_parses(self):
        manifest = parse_manifest((PROJECT_DIR / "manifest.yaml").read_text())
        self.assertEqual(manifest.streak_length, 1)
        self.assertEqual(manifest.fallback_path, ["level-1", "level-2", "level-3", "level-4"])
        self.assertEqual(manifest.level("level-3").loop_check, "summarize")

    def test_default_streak_length(self):
        self.assertEqual(parse_manifest(VALID).streak_length, 3)

    def test_invalid_streak_length(self):
        for bad in ("0", "11", "2.5", "true", "'3'"):
            self.assertIn("streak_length", self.errors(VALID + f"streak_length: {bad}\n"))

    def test_yaml_syntax_error_has_line(self):
        self.assertIn("line 2", self.errors("title: x\nconcepts: a: b\nlevels: []\n"))

    def test_missing_fields_all_named(self):
        message = self.errors("title: '  '\nconcepts: []\n")
        for name in ("title", "concepts", "levels", "stage_criteria", "fallback_path"):
            self.assertIn(name, message)

    def test_unknown_concept_and_bad_target_stage(self):
        text = VALID.replace("concepts: [a]", "concepts: [zz]") + \
            "practice_problems:\n  - {id: p, title: P, folder: p, concept: a, target_stage: 4}\n"
        message = self.errors(text)
        self.assertIn("'zz'", message)
        self.assertIn("target_stage", message)

    def test_fallback_mismatch(self):
        self.assertIn("'l9' is not a declared level", self.errors(VALID.replace("[l1]", "[l1, l9]")))
        text = VALID.replace("fallback_path: [l1]", "fallback_path: [l1]\n").replace(
            "levels:\n", "levels:\n  - {id: l2, number: 2, title: Two, folder: levels/l2, concepts: [a]}\n")
        self.assertIn("'l2' is missing", self.errors(text))

    def test_round_trip_property(self):
        rng = random.Random(1)
        for _ in range(200):
            concepts = [ConceptDef(f"c{i}", f"Concept {i}") for i in range(rng.randint(1, 4))]
            cids = [c.id for c in concepts]
            levels = [LevelDef(f"l{i}", i, f"Level {i}", f"levels/l{i}", rng.sample(cids, rng.randint(1, len(cids))),
                               rng.choice([None, 1, 2, 3]), rng.choice([None, "f"]))
                      for i in range(1, rng.randint(2, 5))]
            practice = [PracticeDef(f"p{i}", f"P {i}", f"practice/p{i}", rng.choice(cids), rng.randint(1, 3),
                                    rng.choice([None, "g"])) for i in range(rng.randint(0, 3))]
            criteria = {s: StageCriterion(rng.choice([None, 1, 2, 5]), rng.choice([None, 0, 2]))
                        for s in rng.sample([1, 2, 3], rng.randint(1, 3))}
            order = [lvl.id for lvl in levels]
            rng.shuffle(order)
            manifest = Manifest(title=f"T{rng.random()}", concepts=concepts, stage_criteria=criteria,
                                levels=levels, fallback_path=order, streak_length=rng.randint(1, 10),
                                practice_problems=practice,
                                dataset={"generator": "dataset/g.py", "database": "dataset/d.db"},
                                parameters={"x": rng.choice([None, 1, "s", [1, 2]])})
            self.assertEqual(parse_manifest(print_manifest(manifest)), manifest)

    def test_printer_writes_default_streak(self):
        self.assertIn("streak_length: 3", print_manifest(parse_manifest(VALID)))


if __name__ == "__main__":
    unittest.main()
