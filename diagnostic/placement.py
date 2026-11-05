"""Turn the evidence (and optional model advice) into a placement.

The deterministic stage from the answers is the floor. The model may move a stage by
at most one, and only when the student's own words, quoted exactly, support the move.
Its focus order, stance and wording are used only after they pass checks; otherwise
rules and fixed text from the content files take over. The student always gets a
placement, with or without a model.

The starting problem comes from the proto engine's manifest, so the result plugs
straight into `python -m engine.cli` (see diagnostic/handoff.py).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from engine.manifest import Manifest

from . import game
from .ai.parse import Advice
from .content import Content
from .contract import CONTRACT_VERSION
from .models import MASTERED, ConceptEstimate, NodeState
from .safety import check_student_text
from .stance import choose_stance
from .state import EXPLAIN_ANSWERED, DiagnosticState

MODEL_CONFIDENCE_CAP = 0.75         # a model-adjusted stage is never reported as more certain than this
MAX_TEACHER_NOTE_CHARS = 400

POLICY_RULES, POLICY_AGENT, POLICY_FIXED = "stage_rules", "agent", "fixed_order"


@dataclass
class ConceptPlacement:
    concept: str
    zone: str
    stage: int                          # final stage (after any bounded model adjustment)
    game_stage: int                     # stage from the answers alone
    confidence: float
    borderline: bool
    goal_weight: float
    misconceptions: List[str]
    adjustment: Optional[Dict[str, Any]] = None
    start_nodes: List[str] = field(default_factory=list)


@dataclass
class Route:
    """Matches evaluation/schemas/route_next.schema.json (output)."""
    next_task_id: str
    reason: str
    policy: str
    fallback: bool
    stance: str

    def to_dict(self) -> Dict[str, Any]:
        return {"contract_version": CONTRACT_VERSION, **self.__dict__}


@dataclass
class Placement:
    concepts: Dict[str, ConceptPlacement]
    focus_order: List[str]
    route: Route
    practice_ahead: List[str]
    student_message: str
    goal_connection: str
    teacher_note: str
    used_model: bool
    model_id: str
    model_fallback: bool                # a model was configured but its help was not used
    notes: List[str] = field(default_factory=list)

    @property
    def stages(self) -> Dict[str, int]:
        return {c: p.stage for c, p in self.concepts.items()}

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Placement":
        fields = dict(data)
        fields["concepts"] = {c: ConceptPlacement(**v) for c, v in data["concepts"].items()}
        fields["route"] = Route(**data["route"])
        return cls(**fields)


# Stage merge -----------------------------------------------------------------------

def _merge_concept(estimate: ConceptEstimate, advice: Optional[Advice], state: DiagnosticState) -> tuple:
    """(final stage, confidence, adjustment record or None)."""
    if advice is None or estimate.concept not in advice.reads:
        return estimate.stage, estimate.confidence, None
    read = advice.reads[estimate.concept]
    if read.stage == estimate.stage:
        return estimate.stage, estimate.confidence, None
    record = state.explain.get(estimate.concept)
    if record is None or record.status != EXPLAIN_ANSWERED or not record.text:
        reason = "no_words_to_support_it"
    elif abs(read.stage - estimate.stage) != 1:
        reason = "change_larger_than_one_stage"
    elif not read.quotes:
        reason = "no_matching_quote"
    else:
        confidence = min(read.confidence, MODEL_CONFIDENCE_CAP)
        return read.stage, round(confidence, 3), {
            "from": estimate.stage, "to": read.stage, "applied": True,
            "quotes": list(read.quotes), "rationale": read.rationale,
        }
    return estimate.stage, estimate.confidence, {"from": estimate.stage, "to": read.stage, "applied": False,
                                                 "reason": reason}


def _start_nodes(content: Content, concept: str, stage: int, node_states: Mapping[str, NodeState]) -> List[str]:
    """Where in this concept's branch the student should begin: the next tier up (or review at the top)."""
    target_tier = min(stage + 1, 3)
    nodes = [n for n in content.tree.concept_nodes(concept) if n.tier == target_tier]
    if stage < 3:
        nodes = [n for n in nodes if node_states[n.id].status != MASTERED] or nodes
    return [n.id for n in nodes]


# Routing -------------------------------------------------------------------------------

def _route(manifest: Manifest, finals: Mapping[str, int], stance: str, policy: str, fallback: bool) -> tuple:
    """(Route, practice_ahead). Never skips a level: every student works toward the same objectives."""
    levels = manifest.levels_in_order()
    first = levels[0]
    practice_by_concept = {}
    for practice in manifest.practice_problems:
        practice_by_concept.setdefault(practice.concept, []).append(practice)

    def starter_practice(concept: str) -> Optional[str]:
        options = sorted((p for p in practice_by_concept.get(concept, []) if p.target_stage == 1), key=lambda p: p.id)
        return options[0].id if options else None

    next_task, reason = first.id, "Start at the first level; the evidence shows a ready start."
    first_concept = first.concepts[0] if first.concepts else None
    if first_concept and finals.get(first_concept, 0) == 0:
        practice = starter_practice(first_concept)
        if practice:
            next_task = practice
            reason = f"Start with a practice problem on {first_concept}; the quest showed a gap there."

    ahead: List[str] = []
    for level in levels[1:]:
        for concept in level.concepts:
            if finals.get(concept, 0) == 0:
                practice = starter_practice(concept)
                if practice and practice not in ahead:
                    ahead.append(practice)
    return Route(next_task, reason, policy, fallback, stance), ahead


def start_concept(manifest: Manifest, task_id: Optional[str]) -> Optional[str]:
    """The concept of the problem the lesson starts with (a level's first concept, or a practice's concept)."""
    if not task_id:
        return None
    practice = manifest.practice(task_id)
    if practice is not None:
        return practice.concept
    level = manifest.level(task_id)
    return level.concepts[0] if level is not None and level.concepts else None


# Entry point -----------------------------------------------------------------------------

def build_placement(content: Content, manifest: Manifest, state: DiagnosticState,
                    estimates: Mapping[str, ConceptEstimate], node_states: Mapping[str, NodeState],
                    advice: Optional[Advice], model_id: str = "", model_configured: bool = False) -> Placement:
    goal = content.goals.get(state.goal_id) or content.default_goal()
    notes: List[str] = []
    concepts: Dict[str, ConceptPlacement] = {}
    any_applied = False
    for zone in content.zones:
        est = estimates[zone.concept]
        stage, confidence, adjustment = _merge_concept(est, advice, state)
        any_applied = any_applied or bool(adjustment and adjustment["applied"])
        concepts[zone.concept] = ConceptPlacement(
            concept=zone.concept, zone=zone.name, stage=stage, game_stage=est.stage, confidence=confidence,
            borderline=est.borderline if adjustment is None or not adjustment["applied"] else confidence < 0.6,
            goal_weight=goal.emphasis.get(zone.concept, 0.5), misconceptions=list(est.misconceptions),
            adjustment=adjustment,
        )
    for placed in concepts.values():
        placed.start_nodes = _start_nodes(content, placed.concept, placed.stage, node_states)

    # Focus order: the model's if it is a complete list of known concepts, else by need and goal.
    by_need = sorted(concepts.values(), key=lambda p: (p.stage, -p.goal_weight, content.concepts().index(p.concept)))
    focus = [p.concept for p in by_need]
    used_focus = False
    if advice is not None and sorted(advice.focus_order) == sorted(focus):
        focus, used_focus = list(advice.focus_order), advice.focus_order != focus

    stages = {c: p.stage for c, p in concepts.items()}
    confident = {c: not p.borderline for c, p in concepts.items()}
    stance = choose_stance(stages, confident)
    if advice is not None and advice.stance and advice.stance == choose_stance(stages, confident):
        stance = advice.stance
    elif advice is not None and advice.stance:
        notes.append(f"Model suggested {advice.stance}; the rules chose {stance}.")

    policy = POLICY_FIXED if state.on_fallback else (POLICY_AGENT if (any_applied or used_focus) else POLICY_RULES)
    model_failed = model_configured and advice is None
    route, ahead = _route(manifest, stages, stance, policy, state.on_fallback or model_failed)

    cfg = content.config
    # "First stop" names where the lesson really starts, not the weakest concept: the lesson never skips a level.
    first = start_concept(manifest, route.next_task_id)
    told = [first] + [c for c in focus if c != first] if first else focus
    student_message = game.default_student_message(content, state, told)
    goal_connection = f"Your goal is: {goal.label}."
    teacher_note = _teacher_summary(content, concepts, focus, state)
    if advice is not None:
        check = check_student_text(advice.student_message, cfg.banned_student_words,
                                   cfg.reading.max_sentence_words, cfg.reading.max_word_length)
        if check.ok:
            student_message = advice.student_message
        elif advice.student_message:
            notes.append("The model's message for the student was replaced: " + ", ".join(check.reasons))
        link = check_student_text(advice.goal_connection, cfg.banned_student_words,
                                  cfg.reading.max_sentence_words, cfg.reading.max_word_length)
        if link.ok:
            goal_connection = advice.goal_connection
        if advice.teacher_note and "<" not in advice.teacher_note:
            teacher_note = (advice.teacher_note[:MAX_TEACHER_NOTE_CHARS] + " " + teacher_note)[:MAX_TEACHER_NOTE_CHARS * 2]

    return Placement(concepts=concepts, focus_order=focus, route=route, practice_ahead=ahead,
                     student_message=student_message, goal_connection=goal_connection, teacher_note=teacher_note,
                     used_model=advice is not None, model_id=model_id, model_fallback=model_failed, notes=notes)


def _teacher_summary(content: Content, concepts: Mapping[str, ConceptPlacement], focus: List[str],
                     state: DiagnosticState) -> str:
    solid = [p.zone for p in concepts.values() if p.stage >= 2]
    gaps = [p.zone for p in concepts.values() if p.stage == 0]
    parts = []
    if solid:
        parts.append("Solid in: " + ", ".join(solid) + ".")
    if gaps:
        parts.append("Needs a first look at: " + ", ".join(gaps) + ".")
    if focus:
        parts.append("Work on " + content.zone_for(focus[0]).name + " first.")
    return " ".join(parts) or "Not enough evidence yet."


def node_view(content: Content, node_states: Mapping[str, NodeState], placement: Placement) -> List[Dict[str, Any]]:
    """The skill tree with the student's placement marked, for teachers and the tree endpoint."""
    start = {n for p in placement.concepts.values() for n in p.start_nodes}
    rows = []
    for nid in content.tree.order:
        node, state = content.tree.node(nid), node_states[nid]
        rows.append({"node": nid, "name": node.name, "concept": node.concept, "tier": node.tier,
                     "parents": list(node.parents), "status": state.status, "start_here": nid in start,
                     "ratio": None if state.ratio is None else round(state.ratio, 3), "evidence": state.evidence,
                     "csta": list(node.csta)})
    return rows
