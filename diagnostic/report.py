"""The teacher report: stages, evidence, mistakes, and the placement. Never shown to students.

This is the export the evaluation plan calls for ("who is stuck on which sub-skill").
It has numbers because teachers need them. A plain dict, ready for JSON.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from engine.stages import STAGE_NAMES

from .content import Content
from .models import ConceptEstimate, NodeState
from .placement import Placement, node_view
from .scoring import accumulate_points, facet_totals
from .state import DiagnosticState


def teacher_report(content: Content, state: DiagnosticState, estimates: Mapping[str, ConceptEstimate],
                   node_states: Mapping[str, NodeState], placement: Placement) -> Dict[str, Any]:
    cfg = content.config
    goal = content.goals.get(state.goal_id) or content.default_goal()
    scored = len(state.results)
    answered_text = sum(1 for r in state.explain.values() if r.status == "answered")
    planned = (scored + len(state.boosters_served)) * cfg.limits.seconds_per_item + answered_text * cfg.limits.seconds_per_explain
    minutes_planned = round(planned / 60, 1)
    minutes = round(state.elapsed_ms_total / 60000, 1) if state.elapsed_ms_total else minutes_planned

    concepts = []
    for zone in content.zones:
        placed = placement.concepts[zone.concept]
        record = state.explain.get(zone.concept)
        concepts.append({
            "concept": zone.concept, "zone": zone.name, "stage": placed.stage, "stage_name": STAGE_NAMES[placed.stage],
            "stage_from_answers": placed.game_stage, "confidence": placed.confidence, "borderline": placed.borderline,
            "questions_asked": estimates[zone.concept].items_seen, "mistakes": placed.misconceptions,
            "adjusted_by_ai": placed.adjustment, "start_nodes": placed.start_nodes,
            "explain": None if record is None else {
                "status": record.status, "text": record.text, "stage": record.stage, "quotes": record.quotes,
                "flags": record.flags, "model_id": record.model_id, "rationale": record.rationale,
            },
        })
    totals = facet_totals(accumulate_points(state.results, content.items))
    held_back = sorted({flag for r in state.explain.values() for flag in r.flags if r.status == "flagged"})
    return {
        "student_id": state.student_id,
        "quest": {"id": cfg.id, "title": cfg.title, "version": cfg.version, "grade_band": cfg.grade_band},
        "started_at": state.started_at, "finished_at": state.finished_at,
        "questions_scored": scored, "breathers": len(state.boosters_served), "minutes_estimate": minutes,
        "minutes_planned": minutes_planned,
        "minutes_source": "measured" if state.elapsed_ms_total else "planned",
        "within_target_minutes": max(minutes, minutes_planned) <= cfg.limits.target_minutes,
        "fixed_order_fallback": {"used": state.on_fallback, "reason": state.fallback_reason},
        "goal": {"id": goal.id, "label": goal.label, "own_words": state.goal_text},
        "concepts": concepts,
        "skill_tree": node_view(content, node_states, placement),
        "placement": {
            "stance": placement.route.stance, "focus_order": placement.focus_order,
            "next_task_id": placement.route.next_task_id, "reason": placement.route.reason,
            "policy": placement.route.policy, "fallback": placement.route.fallback,
            "practice_ahead": placement.practice_ahead,
        },
        "point_totals": {facet: {"earned": round(e, 2), "possible": round(p, 2)} for facet, (e, p) in totals.items()},
        "teacher_note": placement.teacher_note,
        "ai": {"used": placement.used_model, "model_id": placement.model_id, "fell_back": placement.model_fallback},
        "content_filter": {"responses_held_back": held_back,
                           "follow_up": "Review the held-back responses with the student." if held_back else None},
        "notes": placement.notes,
    }
