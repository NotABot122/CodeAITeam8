"""Choose the next question. A pure function of the saved state and the content.

Adaptive plan, one zone (concept) at a time:
  1. Ladder: ask a tier-1 question. A pass moves up a tier. A miss brings a *twin*
     (same tier, different wording). Passing the twin keeps the tier (borderline);
     missing it too ends the ladder.
  2. Tell-the-guide: if the student reached tier 1, offer one short "explain it" prompt.
  3. After all zones, a bonus round re-checks big claims (stage >= bonus_min_stage)
     whose confidence is still low, up to max_bonus_items.
A breather (unscored easy question) appears after several misses in a row.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from .content import Content
from .models import ROLE_BONUS, ROLE_FIRST, ROLE_TWIN, TIERS, Item
from .scoring import estimate_concept
from .state import KIND_BOOSTER, KIND_EXPLAIN, KIND_ITEM, DiagnosticState

DONE = "done"


@dataclass(frozen=True)
class Step:
    kind: str                        # item | explain | booster | done
    id: Optional[str] = None
    role: str = ROLE_FIRST
    reason: str = ""


def _pick(state: DiagnosticState, content: Content, concept: str, tier: int) -> Optional[Item]:
    """An unseen question at this tier, the same one every time for the same student."""
    unseen = sorted((i for i in content.items_for(concept, tier) if i.id not in state.served), key=lambda i: i.id)
    if not unseen:
        return None
    return random.Random(f"{state.student_id}:{concept}:{tier}").choice(unseen)


def _ladder_step(state: DiagnosticState, content: Content, concept: str, zones_unstarted: int) -> Optional[Step]:
    limits = content.config.limits
    mine = [r for r in state.results if r.concept == concept and r.role != ROLE_BONUS]
    if mine and (len(mine) >= limits.max_items_per_zone or len(state.results) + zones_unstarted >= limits.max_scored_items):
        return None
    for tier in TIERS:
        at_tier = [r for r in mine if r.tier == tier]
        if not at_tier:
            item = _pick(state, content, concept, tier)
            return Step(KIND_ITEM, item.id, ROLE_FIRST, f"{concept}: start tier {tier}") if item else None
        passes = sum(1 for r in at_tier if r.passed)
        fails = len(at_tier) - passes
        if len(at_tier) == 1 and passes == 0:
            twin = _pick(state, content, concept, tier)
            return Step(KIND_ITEM, twin.id, ROLE_TWIN, f"{concept}: confirm a miss at tier {tier}") if twin else None
        if passes >= 1 and passes >= fails:
            continue
        return None
    return None


def _bonus_step(state: DiagnosticState, content: Content) -> Optional[Step]:
    limits = content.config.limits
    if len(state.results) >= limits.max_scored_items:
        return None
    if sum(1 for r in state.results if r.role == ROLE_BONUS) >= limits.max_bonus_items:
        return None
    candidates = []
    for order, zone in enumerate(content.zones):
        if any(r.concept == zone.concept and r.role == ROLE_BONUS for r in state.results):
            continue
        estimate = estimate_concept(zone.concept, state.results, content.config.scoring)
        if estimate.stage < limits.bonus_min_stage or estimate.confidence >= limits.bonus_confidence_target:
            continue
        item = _pick(state, content, zone.concept, estimate.stage)
        if item is not None:
            candidates.append((-estimate.stage, order, item))
    if not candidates:
        return None
    _, _, item = sorted(candidates, key=lambda c: (c[0], c[1]))[0]
    return Step(KIND_ITEM, item.id, ROLE_BONUS, f"{item.concept}: re-check a stage claim")


def wants_explain(state: DiagnosticState, content: Content, concept: str) -> bool:
    """Ask for typed words only where they add information: the child got started on the
    concept, the answers alone leave real doubt, and the per-quest typing budget is not spent."""
    limits = content.config.limits
    if content.explain_for(concept) is None or concept in state.explain:
        return False
    if len(state.explain) >= limits.max_explain_prompts:
        return False
    estimate = estimate_concept(concept, state.results, content.config.scoring)
    return estimate.stage >= 1 and estimate.confidence < limits.explain_below_confidence


def next_step(state: DiagnosticState, content: Content) -> Step:
    limits = content.config.limits
    if state.consecutive_misses >= limits.misses_before_booster and len(state.boosters_served) < limits.max_boosters:
        unseen = [b for b in content.boosters if b.id not in state.boosters_served]
        if unseen:
            return Step(KIND_BOOSTER, unseen[0].id, ROLE_FIRST, "breather after several misses")

    zones = content.zones
    for index, zone in enumerate(zones):
        concept = zone.concept
        unstarted = sum(1 for later in zones[index + 1:] if not any(r.concept == later.concept for r in state.results))
        step = _ladder_step(state, content, concept, unstarted)
        if step is not None:
            return step
        if any(r.concept == concept for r in state.results) and wants_explain(state, content, concept):
            return Step(KIND_EXPLAIN, content.explain_for(concept).id, ROLE_FIRST, f"{concept}: tell the guide")

    bonus = _bonus_step(state, content)
    return bonus if bonus is not None else Step(DONE, reason="quest finished")


def zone_complete(state: DiagnosticState, content: Content, concept: str) -> bool:
    """True once a zone's questions (and its tell-the-guide prompt, if it applies) are done."""
    if state.on_fallback:
        waiting = [i for i in (state.fixed_queue or []) if i not in state.served and content.items[i].concept == concept]
        return not waiting and any(r.concept == concept for r in state.results)
    if not any(r.concept == concept for r in state.results):
        return False
    if _ladder_step(state, content, concept, 0) is not None:
        return False
    return not wants_explain(state, content, concept)


# Fixed-order fallback ---------------------------------------------------------

def fixed_plan(state: DiagnosticState, content: Content) -> List[str]:
    """Every zone's tier 1, 2, 3 questions in order. Used when adaptive selection fails."""
    plan: List[str] = []
    for zone in content.zones:
        for tier in TIERS:
            item = _pick(state, content, zone.concept, tier)
            if item is not None:
                plan.append(item.id)
    return plan


def fixed_step(state: DiagnosticState) -> Step:
    queue = [i for i in (state.fixed_queue or []) if i not in state.served]
    if not queue:
        return Step(DONE, reason="fixed order finished")
    return Step(KIND_ITEM, queue[0], ROLE_FIRST, "fixed order")
