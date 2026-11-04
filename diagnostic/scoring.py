"""Deterministic scoring: one answer -> credit, many answers -> a stage per concept.

Stage evidence (tier ladder): a pass at tier N is evidence for Stage N.

The stage is estimated with the standard guess-and-slip model: given each answer
(and each question's own chance of being passed by guessing), which true stage makes
the whole pattern most likely? Confidence is that stage's probability. This handles
lucky guesses, ties between a miss and a twin pass, and the bonus round in one place,
with no hand-tuned special cases. The slip rate and prior live in diagnostic.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .models import (CHOICE_LIKE, FACETS, MAX_STAGE, ORDER, ConceptEstimate, InvalidResponse, Item, ItemResult,
                     NodePoints, ScoringRules)

@dataclass(frozen=True)
class ItemScore:
    credit: float
    passed: bool
    misconception: Optional[str]
    picked_why: Optional[str] = None     # the kind sentence tied to the wrong option picked


def _check_choice(item: Item, response: Any) -> str:
    valid = {o.id for o in item.options}
    if not isinstance(response, str) or response not in valid:
        raise InvalidResponse("pick one of the answer choices")
    return response


def _check_order(item: Item, response: Any) -> List[str]:
    ids = [c.id for c in item.cards]
    if not isinstance(response, list) or sorted(map(str, response)) != sorted(ids):
        raise InvalidResponse("put every card in a spot, once each")
    return [str(r) for r in response]


def _check_sort(item: Item, response: Any) -> Dict[str, str]:
    if not isinstance(response, dict):
        raise InvalidResponse("put every card in a box")
    buckets = {b.id for b in item.buckets}
    if set(response) != {c.id for c in item.cards} or any(v not in buckets for v in response.values()):
        raise InvalidResponse("put every card in one of the boxes")
    return {str(k): str(v) for k, v in response.items()}


def score_response(item: Item, response: Any) -> ItemScore:
    """Score one answer. Raises InvalidResponse when the answer does not fit the question."""
    if item.type in CHOICE_LIKE:
        picked = _check_choice(item, response)
        right = picked == item.answer
        option = next(o for o in item.options if o.id == picked)
        return ItemScore(1.0 if right else 0.0, right, None if right else option.misconception,
                         None if right else option.why)
    if item.type == ORDER:
        order = _check_order(item, response)
        hits = sum(1 for given, want in zip(order, item.answer) if given == want)
        credit = hits / len(item.answer)
        passed = credit >= item.pass_credit
        return ItemScore(credit, passed, None if passed else item.misconception)
    placed = _check_sort(item, response)
    hits = sum(1 for card_id, bucket in item.answer.items() if placed[card_id] == bucket)
    credit = hits / len(item.answer)
    passed = credit >= item.pass_credit
    misconception = None
    if not passed:
        wrong = [c for c in item.cards if placed[c.id] != item.answer[c.id] and c.misconception]
        misconception = wrong[0].misconception if wrong else item.misconception
    return ItemScore(credit, passed, misconception)


# Stage estimate -------------------------------------------------------------

def stage_posterior(results: Iterable[ItemResult], rules: ScoringRules) -> List[float]:
    """P(true stage = 0..3 | the answers), under the guess-and-slip model.

    For a child whose true stage is s, a tier-t question is passed with probability
    (1 - slip) when s >= t, and with the question's own guess chance when s < t. The
    answers multiply into a likelihood for each s, which is combined with the prior.
    """
    post = list(rules.prior)
    for r in results:
        for stage in range(MAX_STAGE + 1):
            p_pass = (1.0 - rules.slip) if stage >= r.tier else r.guess_chance
            post[stage] *= p_pass if r.passed else (1.0 - p_pass)
    total = sum(post)
    if total <= 0:
        return list(rules.prior)
    return [p / total for p in post]


def estimate_concept(concept: str, results: Iterable[ItemResult], rules: ScoringRules) -> ConceptEstimate:
    """Most likely stage for one concept, with the probability that it is right as confidence."""
    mine = [r for r in results if r.concept == concept]
    if not mine:
        return ConceptEstimate(concept, 0, 0.0, True, 0)
    post = stage_posterior(mine, rules)
    stage = 0
    for candidate in range(1, MAX_STAGE + 1):
        if post[candidate] > post[stage] + 1e-9:     # ties go to the lower stage
            stage = candidate
    confidence = round(post[stage], 3)
    misconceptions: List[str] = []
    for r in mine:
        if not r.passed and r.misconception and r.misconception not in misconceptions:
            misconceptions.append(r.misconception)
    return ConceptEstimate(concept, stage, confidence, confidence < rules.borderline_below, len(mine),
                           tuple(misconceptions))


def estimate_all(concepts: Iterable[str], results: List[ItemResult], rules: ScoringRules) -> Dict[str, ConceptEstimate]:
    return {c: estimate_concept(c, results, rules) for c in concepts}


# Node points -----------------------------------------------------------------

def accumulate_points(results: Iterable[ItemResult], items: Mapping[str, Item]) -> Dict[str, NodePoints]:
    """Spread each answer's credit over the skill-tree nodes it tests (the spec's P_node).

    The first node is the one being tested: it earns the credit and counts the
    question as possible points either way. Supporting nodes (poly-hierarchy) only
    gain when the answer passes, so a miss on a combined question cannot
    punish a skill that may not be the problem.
    """
    points: Dict[str, NodePoints] = {}
    for result in results:
        item = items[result.item_id]
        for index, node_id in enumerate(item.nodes):
            if index > 0 and not result.passed:
                continue
            pts = points.setdefault(node_id, NodePoints())
            pts.possible[item.facet] += 1.0
            pts.earned[item.facet] += result.credit
            pts.evidence += 1
    return points


def facet_totals(points: Mapping[str, NodePoints]) -> Dict[str, Tuple[float, float]]:
    """(earned, possible) per facet across the whole tree, for the teacher report."""
    totals = {f: (0.0, 0.0) for f in FACETS}
    for pts in points.values():
        for f in FACETS:
            e, p = totals[f]
            totals[f] = (e + pts.earned[f], p + pts.possible[f])
    return totals
