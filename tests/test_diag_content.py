"""Content loading and validation, and the skill tree."""
from __future__ import annotations

import unittest

from diagnostic.content import ContentError, check_content, load_content
from diagnostic.models import AVAILABLE, LOCKED, MASTERED, Node, NodePoints
from diagnostic.paths import DEFAULT_PROJECT
from diagnostic.tree import SkillTree, TreeError

from tests.diag_helpers import TempDirCase, content, edit_yaml, project

ITEMS = "diagnostic/items"


class RealContent(unittest.TestCase):
    def test_check_content_passes_against_the_project_manifest(self):
        result = check_content(DEFAULT_PROJECT)
        self.assertTrue(result.passed, result.problems)

    def test_every_manifest_concept_has_a_zone_and_explain_prompt(self):
        c = content()
        self.assertEqual(sorted(c.concepts()), sorted(project().manifest.concept_ids()))
        for concept in c.concepts():
            self.assertIn(concept, c.explain)

    def test_every_concept_has_at_least_two_questions_per_tier(self):
        c = content()
        for concept in c.concepts():
            for tier in (1, 2, 3):
                self.assertGreaterEqual(len(c.items_for(concept, tier)), 2, (concept, tier))

    def test_poly_hierarchy_nodes_exist(self):
        self.assertEqual(set(content().tree.multi_parent_nodes()), {"count_with_rule", "combine_helpers"})

    def test_every_wrong_option_names_a_misconception(self):
        for item in content().items.values():
            for option in item.options:
                if option.id != item.answer:
                    self.assertTrue(option.misconception, (item.id, option.id))

    def test_a_pass_cannot_be_reached_by_guessing_alone(self):
        for item in content().items.values():
            self.assertLessEqual(item.guess_chance, 0.34, item.id)

    def test_student_view_never_contains_the_answer_key(self):
        import random

        allowed = {"id", "type", "prompt", "options", "cards", "buckets"}
        for item in content().items.values():
            payload = item.public(random.Random(1))
            self.assertLessEqual(set(payload), allowed, item.id)
            for part in payload.get("options", []) + payload.get("cards", []) + payload.get("buckets", []):
                self.assertEqual(set(part), {"id", "text"}, item.id)     # no answer, bucket or misconception keys

    def test_order_cards_are_never_shown_already_solved(self):
        import random

        for item in content().items.values():
            if item.type == "order":
                for seed in range(20):
                    shown = [c["id"] for c in item.public(random.Random(seed))["cards"]]
                    self.assertNotEqual(shown, list(item.answer), (item.id, seed))


class BrokenContent(TempDirCase):
    def load(self, root):
        return load_content(root, project().manifest.concept_ids())

    def assertRejected(self, root, fragment):
        with self.assertRaises(ContentError) as caught:
            self.load(root)
        self.assertTrue(any(fragment in e for e in caught.exception.errors), caught.exception.errors)

    def test_missing_diagnostic_folder(self):
        with self.assertRaises(ContentError):
            load_content(self.tmp, [])

    def test_duplicate_item_id(self):
        root = self.copy_project()
        edit_yaml(root / ITEMS / "loops.yaml", lambda d: d["items"][1].update(id=d["items"][0]["id"]))
        self.assertRejected(root, "duplicate item id")

    def test_wrong_option_without_misconception(self):
        root = self.copy_project()
        edit_yaml(root / ITEMS / "loops.yaml", lambda d: d["items"][0]["options"][1].pop("misconception"))
        self.assertRejected(root, "needs a misconception")

    def test_two_correct_options(self):
        root = self.copy_project()

        def change(d):
            d["items"][0]["options"][1]["correct"] = True
            d["items"][0]["options"][1].pop("misconception")

        edit_yaml(root / ITEMS / "loops.yaml", change)
        self.assertRejected(root, "exactly one option must be correct")

    def test_unknown_node(self):
        root = self.copy_project()
        edit_yaml(root / ITEMS / "loops.yaml", lambda d: d["items"][0].update(nodes=["not_a_node"]))
        self.assertRejected(root, "unknown node")

    def test_primary_node_in_the_wrong_zone(self):
        root = self.copy_project()
        edit_yaml(root / ITEMS / "loops.yaml", lambda d: d["items"][0].update(nodes=["if_then"]))
        self.assertRejected(root, "belongs to 'conditionals'")

    def test_tier_with_only_one_question(self):
        root = self.copy_project()
        edit_yaml(root / ITEMS / "loops.yaml", lambda d: d.update(items=[i for i in d["items"] if i["id"] != "rep-1b"]))
        self.assertRejected(root, "at least 2 are needed")

    def test_sentence_too_long_for_the_grade_band(self):
        root = self.copy_project()
        long = " ".join(["word"] * 30)
        edit_yaml(root / ITEMS / "loops.yaml", lambda d: d["items"][0].update(prompt=long))
        self.assertRejected(root, "longer than 16 words")

    def test_banned_word_in_student_text(self):
        root = self.copy_project()
        edit_yaml(root / ITEMS / "loops.yaml", lambda d: d["items"][0]["options"][0].update(text="Your score is high"))
        self.assertRejected(root, "stays out of student-facing text")

    def test_cycle_in_the_tree(self):
        root = self.copy_project()

        def change(d):
            for node in d["nodes"]:
                if node["id"] == "read_a_log":
                    node["parents"] = ["sort_and_edges"]

        edit_yaml(root / "diagnostic/tree.yaml", change)
        self.assertRejected(root, "cycle")

    def test_all_problems_are_reported_together(self):
        root = self.copy_project()
        edit_yaml(root / ITEMS / "loops.yaml", lambda d: (d["items"][0].update(nodes=["not_a_node"]),
                                                          d["items"][1].update(type="mystery")))
        with self.assertRaises(ContentError) as caught:
            self.load(root)
        self.assertGreaterEqual(len(caught.exception.errors), 2)


class SkillTreeRules(unittest.TestCase):
    def tree(self):
        return SkillTree([
            Node("a", "A", "x", 1), Node("b", "B", "x", 2, ("a",)), Node("c", "C", "y", 1),
            Node("d", "D", "y", 2, ("b", "c")),                       # two parents
        ])

    @staticmethod
    def points(**ratios):
        out = {}
        for node, ratio in ratios.items():
            pts = NodePoints()
            pts.possible["conceptual"], pts.earned["conceptual"], pts.evidence = 1.0, ratio, 1
            out[node] = pts
        return out

    def test_untouched_roots_are_available_and_the_rest_locked(self):
        states = self.tree().evaluate({}, 0.5, 0.75)
        self.assertEqual({k: v.status for k, v in states.items()}, {"a": AVAILABLE, "b": LOCKED, "c": AVAILABLE, "d": LOCKED})

    def test_passing_a_parent_unlocks_the_child(self):
        states = self.tree().evaluate(self.points(a=0.6), 0.5, 0.75)
        self.assertEqual(states["a"].status, AVAILABLE)
        self.assertEqual(states["b"].status, AVAILABLE)

    def test_mastery_needs_the_master_threshold(self):
        states = self.tree().evaluate(self.points(a=1.0), 0.5, 0.75)
        self.assertEqual(states["a"].status, MASTERED)

    def test_a_multi_parent_node_needs_every_parent(self):
        tree = self.tree()
        only_one = tree.evaluate(self.points(a=1.0, b=1.0), 0.5, 0.75)
        self.assertEqual(only_one["d"].status, LOCKED)
        both = tree.evaluate(self.points(a=1.0, b=1.0, c=1.0), 0.5, 0.75)
        self.assertEqual(both["d"].status, AVAILABLE)

    def test_a_locked_node_does_not_unlock_its_children_even_with_points(self):
        tree = SkillTree([Node("a", "A", "x", 1), Node("b", "B", "x", 2, ("a",)), Node("c", "C", "x", 3, ("b",))])
        states = tree.evaluate(self.points(b=1.0, c=1.0), 0.5, 0.75)     # b has points but a was never passed
        self.assertEqual(states["b"].status, LOCKED)
        self.assertEqual(states["c"].status, LOCKED)

    def test_rejects_cycles_unknown_parents_and_duplicates(self):
        with self.assertRaises(TreeError):
            SkillTree([Node("a", "A", "x", 1, ("b",)), Node("b", "B", "x", 1, ("a",))])
        with self.assertRaises(TreeError):
            SkillTree([Node("a", "A", "x", 1, ("ghost",))])
        with self.assertRaises(TreeError):
            SkillTree([Node("a", "A", "x", 1), Node("a", "A2", "x", 1)])


if __name__ == "__main__":
    unittest.main()
