"""The Engine: grade a submission, update stages, route, fall back, and save."""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from . import grader as g
from .events import EventLog
from .feedback import messages_for, next_hint
from .progress import ProgressLoadError, ProgressRecord, ProgressStore
from .project import Problem, Project
from .router import Decision, PROJECT_COMPLETE, next_problem
from .stages import MAX_STAGE, STAGE_NAMES, StageChange, initial_states, record_result

FALLBACK_MESSAGE = "The lesson will continue in a fixed order from here."

# Reasons logged when a student moves to the fallback path.
ROUTER_ERROR = "router_error"
NOT_IN_MANIFEST = "problem_not_in_manifest"
LOAD_FAILURE = "progress_load_failure"
ADAPTIVE_DISABLED = "adaptive_routing_disabled"


class UnknownStudent(Exception):
    pass


@dataclass
class SubmitOutcome:
    status: str
    passed: bool
    messages: List[str]
    hint: Optional[str] = None
    stage_changes: List[StageChange] = field(default_factory=list)
    next_problem: Optional[Problem] = None
    complete: bool = False
    notices: List[str] = field(default_factory=list)


class Engine:
    def __init__(self, project: Project, store: ProgressStore, events: EventLog,
                 grader: Optional[g.Grader] = None, adaptive: bool = True,
                 router: Callable[..., Decision] = next_problem):
        self.project = project
        self.manifest = project.manifest
        self.store = store
        self.events = events
        self.grader = grader or g.Grader()
        self.adaptive = adaptive
        self.router = router

    # Students and records ---------------------------------------------------
    def new_student(self) -> str:
        """Create a student with a random id. No personal information is accepted."""
        while True:
            student_id = uuid.uuid4().hex
            if not self.store.student_exists(student_id):
                break
        self.store.register_student(student_id)
        self.open(student_id)
        return student_id

    def _fresh_record(self, student_id: str) -> ProgressRecord:
        return ProgressRecord(
            student_id=student_id,
            project_id=self.project.id,
            concepts=initial_states(self.manifest.concept_ids()),
            current_problem=self.manifest.fallback_path[0],
        )

    def open(self, student_id: str) -> Tuple[ProgressRecord, List[str]]:
        """Load the student's progress, or start it. Returns (record, notices)."""
        if not self.store.student_exists(student_id):
            raise UnknownStudent(f"no student with id {student_id}")
        notices: List[str] = []
        try:
            record = self.store.load(student_id, self.project.id)
        except ProgressLoadError:
            self.store.quarantine(student_id, self.project.id)
            record = self._fresh_record(student_id)
            notices.append("Your saved progress couldn't be loaded, so you're starting again at Level 1. "
                           + FALLBACK_MESSAGE)
            self._switch_to_fallback(record, LOAD_FAILURE)
            notices.extend(self._save(record))
            return record, notices

        if record is None:
            record = self._fresh_record(student_id)
            if not self.adaptive:
                self._switch_to_fallback(record, ADAPTIVE_DISABLED)
            notices.extend(self._save(record))
        elif not self.adaptive and not record.on_fallback:
            self._switch_to_fallback(record, ADAPTIVE_DISABLED)
            if not record.complete and self.manifest.level(record.current_problem) is None:
                self._apply(record, self._fallback_decision(record), "fallback")
            notices.extend(self._save(record))
        return record, notices

    def _save(self, record: ProgressRecord) -> List[str]:
        try:
            self.store.save(record)
            return []
        except OSError:
            return ["Your progress wasn't saved this time. It will be saved again after your next submission."]

    # Fallback ---------------------------------------------------------------
    def _switch_to_fallback(self, record: ProgressRecord, reason: str) -> None:
        record.on_fallback = True
        self.events.write("fallback", student_id=record.student_id, project_id=self.project.id,
                          problem_id=record.current_problem, reason=reason)

    def _fallback_decision(self, record: ProgressRecord) -> Decision:
        path = self.manifest.fallback_path
        passed_positions = [i for i, level_id in enumerate(path) if level_id in record.passed_problems]
        position = passed_positions[-1] + 1 if passed_positions else 0
        if position >= len(path):
            return Decision(None, PROJECT_COMPLETE)
        return Decision(path[position], "fallback_next_level")

    def _apply(self, record: ProgressRecord, decision: Decision, policy: str) -> None:
        record.current_problem = decision.problem_id
        record.origin_level = decision.origin_level
        record.complete = decision.problem_id is None
        entry = {"selected": decision.problem_id, "reason": decision.reason, "policy": policy,
                 "stages": record.stages(),
                 "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        record.routing_log.append(entry)
        self.events.write("routing", student_id=record.student_id, project_id=self.project.id,
                          selected=decision.problem_id, reason=decision.reason, stages=record.stages())

    def _route(self, record: ProgressRecord) -> List[str]:
        notices: List[str] = []
        if self.adaptive and not record.on_fallback:
            try:
                decision = self.router(self.manifest, record.stages(), list(record.passed_problems),
                                       record.current_problem, record.origin_level)
                if decision.problem_id is not None and not self.manifest.has_problem(decision.problem_id):
                    raise LookupError(NOT_IN_MANIFEST)
                self._apply(record, decision, "adaptive")
                return notices
            except Exception as exc:  # any routing failure falls back
                reason = NOT_IN_MANIFEST if str(exc) == NOT_IN_MANIFEST else ROUTER_ERROR
                self._switch_to_fallback(record, reason)
                notices.append(FALLBACK_MESSAGE)
        self._apply(record, self._fallback_decision(record), "fallback")
        return notices

    # Submissions ------------------------------------------------------------
    def current_problem(self, student_id: str) -> Tuple[Optional[Problem], List[str]]:
        record, notices = self.open(student_id)
        if record.complete:
            return None, notices
        return self.project.problem(record.current_problem), notices

    def submit(self, student_id: str, submission_path) -> SubmitOutcome:
        record, notices = self.open(student_id)
        if record.complete:
            return SubmitOutcome("complete", True, ["You've finished the project. Nice work!"],
                                 complete=True, notices=notices)

        problem = self.project.problem(record.current_problem)
        result = self.grader.grade(self.project, problem, submission_path)
        messages = messages_for(problem, result)

        if result.ungraded:
            self.events.write("ungraded", student_id=student_id, project_id=self.project.id,
                              problem_id=problem.id, reason=result.error_message or "grading unavailable")
            return SubmitOutcome(result.status, False, messages, next_problem=problem, notices=notices)

        record.attempts[problem.id] = record.attempts.get(problem.id, 0) + 1

        if not result.passed:
            hint, record.hints_seen[problem.id] = next_hint(problem, record.hints_seen.get(problem.id, 0))
            notices.extend(self._save(record))
            return SubmitOutcome(result.status, False, messages, hint=hint, next_problem=problem, notices=notices)

        changes = record_result(
            record.concepts, problem.concepts, problem.id,
            attempts=record.attempts[problem.id], hints_used=record.hints_seen.get(problem.id, 0),
            criteria=self.manifest.stage_criteria, streak_length=self.manifest.streak_length,
        )
        if problem.id not in record.passed_problems:
            record.passed_problems.append(problem.id)
        notices.extend(self._route(record))
        notices.extend(self._save(record))
        following = None if record.complete else self.project.problem(record.current_problem)
        return SubmitOutcome(result.status, True, messages, stage_changes=changes,
                             next_problem=following, complete=record.complete, notices=notices)

    # Progress view ----------------------------------------------------------
    def progress_view(self, student_id: str) -> str:
        try:
            record, notices = self.open(student_id)
        except ProgressLoadError:
            return "Your progress couldn't be loaded right now."
        lines = [f"{self.project.title}", ""]
        lines += notices
        lines.append("Concepts:")
        streak_length = self.manifest.streak_length
        for concept in self.manifest.concepts:
            state = record.concepts[concept.id]
            line = f"  {concept.name:<20} Stage {state.stage} ({STAGE_NAMES[state.stage]})"
            if state.stage < MAX_STAGE:
                line += f"   streak {state.streak}/{streak_length} toward Stage {state.stage + 1}"
            else:
                line += "   highest stage reached"
            lines.append(line)
        levels_passed = [self.manifest.level(pid).number for pid in record.passed_problems if self.manifest.level(pid)]
        practice_passed = [pid for pid in record.passed_problems if self.manifest.practice(pid)]
        lines.append("")
        lines.append("Levels passed: " + (", ".join(str(n) for n in sorted(levels_passed)) or "none yet"))
        if practice_passed:
            lines.append("Practice passed: " + ", ".join(self.project.problem(p).title for p in practice_passed))
        if record.complete:
            lines.append("Current: project complete")
        else:
            problem = self.project.problem(record.current_problem)
            kind = "Level" if problem.kind == "level" else "Practice problem"
            lines.append(f"Current: {problem.title} ({kind})")
        if record.on_fallback:
            lines.append("Path: fixed order")
        return "\n".join(lines)
