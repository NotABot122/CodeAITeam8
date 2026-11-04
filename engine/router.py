"""Choose the next problem after a pass. Pure and deterministic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from .manifest import Manifest

NEXT_LEVEL = "next_level"
PRACTICE_ASSIGNED = "practice_assigned"
NO_PRACTICE_REMAINING = "no_practice_remaining"
PROJECT_COMPLETE = "project_complete"


@dataclass(frozen=True)
class Decision:
    problem_id: Optional[str]
    reason: str
    origin_level: Optional[str] = None   # the level that led to an assigned practice problem


def next_problem(
    manifest: Manifest,
    stages: Dict[str, int],
    passed: Iterable[str],
    current: str,
    origin_level: Optional[str] = None,
) -> Decision:
    passed = set(passed)
    anchor_id = current if manifest.level(current) is not None else origin_level
    anchor = manifest.level(anchor_id) if anchor_id else None
    if anchor is None:
        raise ValueError(f"cannot route from {current!r}: no level to continue from")

    following = manifest.next_level(anchor.id)
    if following is None:
        return Decision(None, PROJECT_COMPLETE)

    if anchor.advance_at_stage is not None:
        for concept in anchor.concepts:
            stage = stages.get(concept, 0)
            if stage >= anchor.advance_at_stage:
                continue
            for practice in manifest.practice_problems:
                if practice.concept == concept and practice.target_stage == stage + 1 and practice.id not in passed:
                    return Decision(practice.id, PRACTICE_ASSIGNED, anchor.id)
            return Decision(following.id, NO_PRACTICE_REMAINING)

    return Decision(following.id, NEXT_LEVEL)
