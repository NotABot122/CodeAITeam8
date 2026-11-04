"""Deterministic scoring, stage estimation, and the adaptive selector."""
from __future__ import annotations

import random
import unittest

from diagnostic.models import InvalidResponse
from diagnostic.scoring import accumulate_points, estimate_concept, score_response, stage_posterior
from diagnostic.selector import DONE, fixed_plan, fixed_step, next_step, wants_explain
from diagnostic.state import ExplainRecord, DiagnosticState

from tests.diag_helpers import content, make_result

C = content()
RULES = C.config.scoring


def concept_of(item_id):
    return C.items[item_id].concept


class ScoringOneAnswer(unittest.TestCase):
    def test_choice_right_and_wrong(self):
        item = C.items["log-1a"]
        self.assertTrue(score_response(item, "a").passed)
        wrong = score_response(item, "b")
        self.assertFalse(wrong.passed)
        self.assertEqual(wrong.misconception, "reads_wrong_column")
        self.assertIn("temperature", wrong.picked_why)

    def test_order_gets_partial_credit_but_only_the_full_order_passes(self):
        item = C.items["rep-2b"]
        perfect = score_response(item, list(item.answer))
        self.assertEqual((perfect.credit, perfect.passed), (1.0, True))
        swapped = list(item.answer)
        swapped[0], swapped[1] = swapped[1], swapped[0]
        partial = score_response(item, swapped)
        self.assertEqual(partial.credit, 0.5)
        self.assertFalse(partial.passed)
        self.assertEqual(partial.misconception, "skips_start_value")

    def test_sort_passes_at_its_pass_credit_and_names_the_misplaced_card_idea(self):
        item = C.items["dec-2a"]                       # 5 cards, pass at 0.8
        right = dict(item.answer)
        self.assertTrue(score_response(item, right).passed)
        one_off = dict(right, t35="notheat")
        result = score_response(item, one_off)
        self.assertEqual(result.credit, 0.8)
        self.assertTrue(result.passed)
        two_off = dict(one_off, t36="notheat")
        failed = score_response(item, two_off)
        self.assertFalse(failed.passed)
        self.assertEqual(failed.misconception, "at_least_means_over")

    def test_responses_that_do_not_fit_are_rejected_not_scored(self):
        for item_id, bad in [("log-1a", "zzz"), ("log-1a", 5), ("rep-2b", ["s1", "s2"]), ("rep-2b", "s1"),
                             ("dec-2a", {"t34": "heat"}), ("dec-2a", {"t34": "nope", "t35": "heat", "t36": "heat",
                                                                       "t20": "heat", "t38": "heat"})]:
            with self.assertRaises(InvalidResponse, msg=(item_id, bad)):
                score_response(C.items[item_id], bad)


class StageEstimate(unittest.TestCase):
    def estimate(self, *outcomes):
        results = [make_result(i, ok, role) for i, ok, role in outcomes]
        return estimate_concept("loops", results, RULES)

    def test_no_answers_means_stage_zero_with_no_confidence(self):
        est = estimate_concept("loops", [], RULES)
        self.assertEqual((est.stage, est.confidence, est.borderline), (0, 0.0, True))

    def test_two_misses_at_tier_one_is_a_confident_stage_zero(self):
        est = self.estimate(("rep-1a", False, "first"), ("rep-1b", False, "twin"))
        self.assertEqual(est.stage, 0)
        self.assertGreater(est.confidence, 0.7)

    def test_passing_every_tier_is_stage_three(self):
        est = self.estimate(("rep-1a", True, "first"), ("rep-2a", True, "first"), ("rep-3a", True, "first"))
        self.assertEqual(est.stage, 3)

    def test_a_lucky_looking_top_pass_is_less_certain_than_a_confirmed_one(self):
        single = self.estimate(("rep-1a", True, "first"), ("rep-2a", True, "first"), ("rep-3a", True, "first"))
        confirmed = self.estimate(("rep-1a", True, "first"), ("rep-2a", True, "first"), ("rep-3a", True, "first"),
                                  ("rep-3b", True, "bonus"))
        self.assertEqual(confirmed.stage, 3)
        self.assertGreater(confirmed.confidence, single.confidence)

    def test_a_miss_after_a_pass_at_the_same_tier_pulls_the_stage_down(self):
        sure = self.estimate(("rep-1a", True, "first"), ("rep-2a", True, "first"), ("rep-3a", True, "first"))
        doubtful = self.estimate(("rep-1a", True, "first"), ("rep-2a", True, "first"), ("rep-3a", True, "first"),
                                 ("rep-3b", False, "bonus"))
        self.assertLess(doubtful.confidence, sure.confidence)

    def test_tier_one_pass_then_two_tier_two_misses_is_stage_one(self):
        est = self.estimate(("rep-1a", True, "first"), ("rep-2a", False, "first"), ("rep-2b", False, "twin"))
        self.assertEqual(est.stage, 1)

    def test_misconceptions_are_listed_once_in_order(self):
        results = [make_result("rep-1a", False), make_result("rep-1b", False)]
        results[0].misconception = "does_it_once"
        results[1].misconception = "does_it_once"
        self.assertEqual(estimate_concept("loops", results, RULES).misconceptions, ("does_it_once",))

    def test_posterior_is_a_probability_distribution(self):
        rng = random.Random(3)
        ids = [i for i in C.items if concept_of(i) == "loops"]
        for _ in range(50):
            results = [make_result(i, rng.random() < 0.5) for i in rng.sample(ids, rng.randint(1, len(ids)))]
            post = stage_posterior(results, RULES)
            self.assertAlmostEqual(sum(post), 1.0, places=6)
            self.assertTrue(all(0 <= p <= 1 for p in post))

    def test_more_correct_answers_never_lower_the_stage(self):
        """Replace misses with passes one at a time: the stage may only stay or rise."""
        rng = random.Random(11)
        ids = ["rep-1a", "rep-2a", "rep-3a", "rep-1b", "rep-2b", "rep-3b"]
        for _ in range(100):
            outcomes = [rng.random() < 0.5 for _ in ids]
            previous = estimate_concept("loops", [make_result(i, o) for i, o in zip(ids, outcomes)], RULES).stage
            for index in [k for k, o in enumerate(outcomes) if not o]:
                outcomes[index] = True
                stage = estimate_concept("loops", [make_result(i, o) for i, o in zip(ids, outcomes)], RULES).stage
                self.assertGreaterEqual(stage, previous)
                previous = stage

    def test_estimates_are_repeatable(self):
        results = [make_result("rep-1a", True), make_result("rep-2a", False)]
        self.assertEqual(estimate_concept("loops", results, RULES), estimate_concept("loops", results, RULES))


class NodePointRules(unittest.TestCase):
    def test_primary_node_earns_and_supporting_node_only_gains_on_a_pass(self):
        passed = accumulate_points([make_result("rep-3b", True)], C.items)
        self.assertEqual(passed["count_with_rule"].ratio, 1.0)
        self.assertEqual(passed["if_else_compare"].ratio, 1.0)        # poly-hierarchy: credit flows to both parents
        failed = accumulate_points([make_result("rep-3b", False)], C.items)
        self.assertEqual(failed["count_with_rule"].ratio, 0.0)
        self.assertNotIn("if_else_compare", failed)                   # a miss cannot punish the supporting skill

    def test_partial_credit_counts_proportionally(self):
        points = accumulate_points([make_result("rep-2b", False, credit=0.5)], C.items)
        self.assertEqual(points["running_total"].ratio, 0.5)


def play(student_id, answers):
    """Drive the selector with scripted outcomes: `answers(item) -> bool`. Returns the final state."""
    state = DiagnosticState(student_id, C.config.id, "not_sure")
    for _ in range(80):
        step = next_step(state, C)
        if step.kind == DONE:
            return state
        if step.kind == "item":
            item = C.items[step.id]
            state.served.append(item.id)
            ok = answers(item)
            state.results.append(make_result(item.id, ok, step.role))
            state.consecutive_misses = 0 if ok else state.consecutive_misses + 1
        elif step.kind == "booster":
            state.boosters_served.append(step.id)
            state.consecutive_misses = 0
        else:
            concept = next(c for c, p in C.explain.items() if p.id == step.id)
            state.explain[concept] = ExplainRecord(concept, "skipped")
    raise AssertionError("selector did not finish")


class AdaptiveSelector(unittest.TestCase):
    def test_a_child_who_passes_everything_climbs_each_ladder_once(self):
        state = play("STU-a", lambda item: True)
        for concept in C.concepts():
            mine = [r for r in state.results if r.concept == concept and r.role == "first"]
            self.assertEqual(sorted(r.tier for r in mine), [1, 2, 3])
        self.assertLessEqual(len(state.results), C.config.limits.max_scored_items)

    def test_a_miss_brings_a_twin_and_two_misses_end_the_zone(self):
        state = play("STU-b", lambda item: item.tier > 1 and item.concept != "loops")
        loops = [r for r in state.results if r.concept == "loops"]
        self.assertEqual([(r.tier, r.role) for r in loops], [(1, "first"), (1, "twin")])

    def test_twins_are_different_questions_from_the_first(self):
        state = play("STU-c", lambda item: False)
        ids = [r.item_id for r in state.results]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_zone_is_always_visited_within_the_cap(self):
        rng = random.Random(5)
        for n in range(60):
            state = play(f"STU-{n:04d}", lambda item: rng.random() < 0.55)
            self.assertLessEqual(len(state.results), C.config.limits.max_scored_items, n)
            for concept in C.concepts():
                self.assertTrue(any(r.concept == concept for r in state.results), (n, concept))

    def test_the_same_student_gets_the_same_questions(self):
        first = [r.item_id for r in play("STU-same", lambda item: item.tier == 1).results]
        second = [r.item_id for r in play("STU-same", lambda item: item.tier == 1).results]
        self.assertEqual(first, second)

    def test_a_breather_appears_after_several_misses_and_is_not_scored(self):
        state = play("STU-d", lambda item: False)
        self.assertGreaterEqual(len(state.boosters_served), 1)
        self.assertLessEqual(len(state.boosters_served), C.config.limits.max_boosters)
        self.assertNotIn(state.boosters_served[0], [r.item_id for r in state.results])

    def test_bonus_questions_only_recheck_stage_two_or_higher_claims(self):
        state = play("STU-e", lambda item: True)
        for r in (r for r in state.results if r.role == "bonus"):
            self.assertGreaterEqual(estimate_concept(r.concept, [x for x in state.results if x is not r], RULES).stage, 2)
        self.assertLessEqual(sum(1 for r in state.results if r.role == "bonus"), C.config.limits.max_bonus_items)

    def test_typed_answers_are_capped_and_skipped_when_the_stage_is_already_clear(self):
        state = DiagnosticState("STU-f", C.config.id, "not_sure")
        for item_id in ("rep-1a", "rep-1b"):
            state.results.append(make_result(item_id, False))
        self.assertFalse(wants_explain(state, C, "loops"))            # stage 0: no typing asked
        state = DiagnosticState("STU-g", C.config.id, "not_sure")
        state.results += [make_result("rep-1a", True), make_result("rep-2a", False), make_result("rep-2b", False)]
        self.assertTrue(wants_explain(state, C, "loops"))             # unsure about a started concept
        state.explain = {c: ExplainRecord(c, "skipped") for c in ("database_retrieval", "conditionals")}
        self.assertFalse(wants_explain(state, C, "loops"))            # typing budget spent


class FixedOrderFallback(unittest.TestCase):
    def test_plan_covers_every_zone_and_tier_in_order(self):
        state = DiagnosticState("STU-h", C.config.id, "not_sure")
        plan = fixed_plan(state, C)
        self.assertEqual([C.items[i].tier for i in plan], [1, 2, 3] * 4)
        self.assertEqual([C.items[i].concept for i in plan], [c for c in C.concepts() for _ in range(3)])

    def test_fixed_step_walks_the_plan_then_finishes(self):
        state = DiagnosticState("STU-i", C.config.id, "not_sure", on_fallback=True)
        state.fixed_queue = fixed_plan(state, C)
        seen = []
        while True:
            step = fixed_step(state)
            if step.kind == DONE:
                break
            seen.append(step.id)
            state.served.append(step.id)
        self.assertEqual(seen, state.fixed_queue)


if __name__ == "__main__":
    unittest.main()
