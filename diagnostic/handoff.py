"""Hand a placed student to the lesson engine (`python -m engine.cli`).

The diagnostic and the lesson share one student id and one data directory, so a student
can go straight from the quest to `engine.cli show --student ID`. This module writes the
lesson's starting problem into the lesson engine's own progress record, using the lesson
engine's own types. It never skips a level, never seeds a stage, and never overwrites a
lesson that has already started.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from engine.events import EventLog
from engine.progress import JsonProgressStore, ProgressLoadError, ProgressRecord
from engine.project import Project
from engine.stages import initial_states

from .paths import PathLike

ROUTING_POLICY = "diagnostic"
ROUTING_REASON = "diagnostic_placement"


@dataclass(frozen=True)
class HandoffResult:
    applied: bool
    message: str
    problem_id: Optional[str] = None


def apply_placement(project: Project, data_dir: PathLike, student_id: str, problem_id: str,
                    stages: Optional[dict] = None) -> HandoffResult:
    """Set the lesson's current problem for a student who has not started the lesson."""
    manifest = project.manifest
    if not manifest.has_problem(problem_id):
        return HandoffResult(False, f"{problem_id!r} is not a problem in {project.title}")
    store = JsonProgressStore(data_dir)
    if not store.student_exists(student_id):
        return HandoffResult(False, f"no student {student_id}")
    try:
        existing = store.load(student_id, project.id)
    except ProgressLoadError:
        return HandoffResult(False, "the lesson progress record could not be read; nothing was changed")
    if existing is not None and (existing.passed_problems or existing.attempts):
        return HandoffResult(False, "the lesson has already started, so it was left as it is", existing.current_problem)

    origin: Optional[str] = None
    practice = manifest.practice(problem_id)
    if practice is not None:
        origin = next((lvl.id for lvl in manifest.levels_in_order() if practice.concept in lvl.concepts),
                      manifest.fallback_path[0])
    record = existing or ProgressRecord(student_id=student_id, project_id=project.id,
                                        concepts=initial_states(manifest.concept_ids()), current_problem=problem_id)
    record.current_problem, record.origin_level = problem_id, origin
    record.routing_log.append({"selected": problem_id, "reason": ROUTING_REASON, "policy": ROUTING_POLICY,
                               "stages": record.stages(),
                               "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    store.save(record)
    EventLog(data_dir).write("routing", student_id=student_id, project_id=project.id, selected=problem_id,
                             reason=ROUTING_REASON, stages=record.stages())
    return HandoffResult(True, f"the lesson will start at {problem_id}", problem_id)
