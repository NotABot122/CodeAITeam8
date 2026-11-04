"""Stage per concept, earned by evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from .manifest import StageCriterion

MAX_STAGE = 3
STAGE_NAMES = {0: "Missing", 1: "Beginning", 2: "Meeting", 3: "Exceeding"}


@dataclass
class ConceptState:
    stage: int = 0
    streak: int = 0
    streak_problems: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"stage": self.stage, "streak": self.streak, "streak_problems": list(self.streak_problems)}

    @classmethod
    def from_dict(cls, data: dict) -> "ConceptState":
        return cls(stage=int(data["stage"]), streak=int(data["streak"]),
                   streak_problems=[str(p) for p in data["streak_problems"]])


@dataclass(frozen=True)
class StageChange:
    concept: str
    old_stage: int
    new_stage: int


def initial_states(concept_ids: Iterable[str]) -> Dict[str, ConceptState]:
    return {cid: ConceptState() for cid in concept_ids}


def record_result(
    states: Dict[str, ConceptState],
    concepts: Iterable[str],
    problem_id: str,
    attempts: int,
    hints_used: int,
    criteria: Dict[int, StageCriterion],
    streak_length: int,
) -> List[StageChange]:
    """Update states in place for a passed problem. Return the stages that rose."""
    changes = []
    for concept in concepts:
        state = states.setdefault(concept, ConceptState())
        if state.stage >= MAX_STAGE:
            state.stage, state.streak, state.streak_problems = MAX_STAGE, 0, []
            continue
        criterion = criteria.get(state.stage + 1)
        if criterion is None or not criterion.is_met(attempts, hints_used):
            state.streak, state.streak_problems = 0, []
            continue
        if problem_id in state.streak_problems:
            continue  # the same problem can't count twice toward one streak
        state.streak += 1
        state.streak_problems.append(problem_id)
        if state.streak >= streak_length:
            old = state.stage
            state.stage, state.streak, state.streak_problems = old + 1, 0, []
            changes.append(StageChange(concept, old, state.stage))
    return changes
