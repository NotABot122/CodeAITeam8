"""The Engine: grade a submission, update stages, route, fall back, and save."""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from pathlib import Path

from . import grader as g
from .ai import ModelProvider
from .events import EventLog
from .feedback import messages_for, next_hint
from .hints import AIHinter
from .quiz import grade_quiz
from .rubric import RubricGrader
from .safety import ContentFilter
from .progress import ProgressLoadError, ProgressRecord, ProgressStore
from .project import Problem, Project
from .router import Decision, PROJECT_COMPLETE, next_problem
from .stages import MAX_STAGE, STAGE_NAMES, StageChange, initial_states, record_result

FALLBACK_MESSAGE = "The lesson will continue in a fixed order from here."
STRUGGLE_AFTER = None      # failed attempts on one level before a practice is inserted; None = off (see catalog.yaml)
STRUGGLE_MESSAGE = "Let\'s warm up with a short practice problem, then come back to this level."
PLANNED_PRACTICE = "planned_practice"
STRUGGLE_PRACTICE = "struggle_practice"
BACK_TO_LEVEL = "back_to_level"
DIAGNOSTIC_MISMATCH = "diagnostic_mismatch"

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
    hint_source: Optional[str] = None     # "ai" or "authored"
    question_results: List[dict] = field(default_factory=list)   # quiz problems only
    next_step: Optional[dict] = None      # set by Course when a project is complete


class Engine:
    def __init__(self, project: Project, store: ProgressStore, events: EventLog,
                 grader: Optional[g.Grader] = None, adaptive: bool = True,
                 router: Callable[..., Decision] = next_problem,
                 hint_provider: Optional[ModelProvider] = None,
                 initial_stages: Optional[Dict[str, int]] = None,
                 planned_practice: Optional[List[str]] = None,
                 struggle_after: Optional[int] = STRUGGLE_AFTER):
        self.project = project
        self.manifest = project.manifest
        self.store = store
        self.events = events
        self.grader = grader or g.Grader()
        self.adaptive = adaptive
        self.router = router
        self.initial_stages = dict(initial_stages or {})
        # Practice planned before its level (from the readiness diagnostic), and how many failed attempts
        # on a level count as struggling (then the concept\'s practice is inserted once).
        self.planned_practice = [p for p in (planned_practice or []) if self.manifest.practice(p) is not None]
        self.struggle_after = int(struggle_after) if struggle_after else None
        self.hinter = None
        self.rubric_grader = RubricGrader(hint_provider) if hint_provider is not None else None
        if hint_provider is not None:
            reference = project.reference_path.read_text() if project.reference_path.exists() else ""
            self.hinter = AIHinter(hint_provider, ContentFilter(), reference_source=reference)

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
        concepts = initial_states(self.manifest.concept_ids())
        for cid, state in concepts.items():
            state.stage = max(0, min(MAX_STAGE, int(self.initial_stages.get(cid, 0))))
        return ProgressRecord(
            student_id=student_id,
            project_id=self.project.id,
            concepts=concepts,
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
                if record.return_to and self.manifest.practice(record.current_problem) is not None:
                    decision = Decision(record.return_to, BACK_TO_LEVEL)
                    record.return_to = None
                else:
                    decision = self.router(self.manifest, record.stages(), list(record.passed_problems),
                                           record.current_problem, record.origin_level)
                    decision = self._planned_first(record, decision)
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

    def _planned_first(self, record: ProgressRecord, decision: Decision) -> Decision:
        """Before a level, do the practice the diagnostic planned for one of its concepts. Never skips a level."""
        level = self.manifest.level(decision.problem_id) if decision.problem_id else None
        if level is None or level.id in record.passed_problems:
            return decision
        for pid in self.planned_practice:
            practice = self.manifest.practice(pid)
            if practice.concept in level.concepts and pid not in record.passed_problems:
                anchor = record.current_problem if self.manifest.level(record.current_problem) else record.origin_level
                return Decision(pid, PLANNED_PRACTICE, anchor)
        return decision

    def _struggle(self, record: ProgressRecord, problem: Problem) -> Optional[Problem]:
        """After repeated failures on a level, insert its concept's practice once, then come back to the level.

        If the concept's stage came from the diagnostic, the student is doing worse than it predicted: the
        stage is lowered to 0 and a diagnostic_mismatch event is logged (live evidence on diagnostic accuracy).
        """
        level = self.manifest.level(problem.id)
        if (self.struggle_after is None or level is None or not self.adaptive or record.on_fallback
                or record.attempts.get(problem.id, 0) < self.struggle_after):
            return None
        for concept in level.concepts:
            if concept in record.interventions:
                continue
            practice = next((p for p in self.manifest.practice_problems
                             if p.concept == concept and p.id not in record.passed_problems), None)
            if practice is None:
                continue
            record.interventions.append(concept)
            state = record.concepts.get(concept)
            if state is not None and state.stage > 0 and self.initial_stages.get(concept, 0) > 0:
                state.stage, state.streak, state.streak_problems = 0, 0, []
                self.events.write("intervention", student_id=record.student_id, project_id=self.project.id,
                                  problem_id=problem.id, selected=practice.id, reason=DIAGNOSTIC_MISMATCH,
                                  stages=record.stages())
            record.return_to = problem.id
            self._apply(record, Decision(practice.id, STRUGGLE_PRACTICE, record.origin_level), "adaptive")
            self.events.write("intervention", student_id=record.student_id, project_id=self.project.id,
                              problem_id=problem.id, selected=practice.id, reason=STRUGGLE_PRACTICE,
                              stages=record.stages())
            return self.project.problem(practice.id)
        return None

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
        if problem.is_quiz:
            return SubmitOutcome("quiz", False, [f"{problem.label}: this step is a quiz. Answer its questions "
                                                 "instead of submitting code."], next_problem=problem, notices=notices)
        result = self.grader.grade(self.project, problem, submission_path)
        messages = messages_for(problem, result)

        if result.ungraded:
            self.events.write("ungraded", student_id=student_id, project_id=self.project.id,
                              problem_id=problem.id, reason=result.error_message or "grading unavailable")
            return SubmitOutcome(result.status, False, messages, next_problem=problem, notices=notices)

        record.attempts[problem.id] = record.attempts.get(problem.id, 0) + 1

        if not result.passed:
            hint, record.hints_seen[problem.id] = next_hint(problem, record.hints_seen.get(problem.id, 0))
            hint, source = self._ai_hint(record, problem, messages, submission_path, hint)
            inserted = self._struggle(record, problem)
            if inserted is not None:
                notices.append(STRUGGLE_MESSAGE)
            notices.extend(self._save(record))
            return SubmitOutcome(result.status, False, messages, hint=hint, next_problem=inserted or problem,
                                 notices=notices, hint_source=source if hint else None)

        return self._after_pass(record, problem, result.status, messages, notices)

    def answer(self, student_id: str, answers: Dict[str, object]) -> SubmitOutcome:
        """Grade the current quiz. answers maps question id to a choice index or written text."""
        record, notices = self.open(student_id)
        if record.complete:
            return SubmitOutcome("complete", True, ["You've finished the project. Nice work!"],
                                 complete=True, notices=notices)
        problem = self.project.problem(record.current_problem)
        if not problem.is_quiz:
            return SubmitOutcome("not_quiz", False, [f"{problem.label}: this step needs code. Submit your file."],
                                 next_problem=problem, notices=notices)
        result = grade_quiz(problem.label, problem.questions, answers or {}, self.rubric_grader)
        details = [r.to_dict() for r in result.results]
        record.attempts[problem.id] = record.attempts.get(problem.id, 0) + 1
        record.quiz_scores[problem.id] = {r.id: r.score for r in result.results if r.type == "explain"}
        if not result.passed:
            hint, record.hints_seen[problem.id] = next_hint(problem, record.hints_seen.get(problem.id, 0))
            notices.extend(self._save(record))
            return SubmitOutcome("failed", False, result.messages, hint=hint, next_problem=problem, notices=notices,
                                 hint_source="authored" if hint else None, question_results=details)
        outcome = self._after_pass(record, problem, "passed", result.messages, notices)
        outcome.question_results = details
        return outcome

    def _after_pass(self, record: ProgressRecord, problem: Problem, status: str, messages: List[str],
                    notices: List[str]) -> SubmitOutcome:
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
        return SubmitOutcome(status, True, messages, stage_changes=changes,
                             next_problem=following, complete=record.complete, notices=notices)

    def request_hint(self, student_id: str, submission_path=None) -> SubmitOutcome:
        """The student asked for a hint without submitting. Reveals the next authored hint (counted in
        hints_seen, like a hint after a failed run) and, for code problems with the AI on, lets the AI
        tutor phrase it from the current code. The attempt count does not change.

        status is "hint", "no_hints" (none left or none written) or "complete"."""
        record, notices = self.open(student_id)
        if record.complete:
            return SubmitOutcome("complete", True, [], complete=True, notices=notices)
        problem = self.project.problem(record.current_problem)
        seen = record.hints_seen.get(problem.id, 0)
        if seen >= len(problem.hints):
            return SubmitOutcome("no_hints", False, [], next_problem=problem, notices=notices)
        authored, record.hints_seen[problem.id] = next_hint(problem, seen)
        hint, source = authored, "authored"
        if not problem.is_quiz and submission_path is not None and self.hinter is not None:
            messages: List[str] = []
            try:
                result = self.grader.grade(self.project, problem, submission_path)
                if not result.ungraded and not result.passed:
                    messages = messages_for(problem, result)
            except Exception:  # a broken grader must not cost the student their hint
                messages = []
            if messages:
                hint, source = self._ai_hint(record, problem, messages, submission_path, authored)
        if source == "authored":
            self.events.write("hint", student_id=student_id, project_id=self.project.id, problem_id=problem.id,
                              source="authored", reason="requested")
        notices.extend(self._save(record))
        return SubmitOutcome("hint", False, [], hint=hint, next_problem=problem, notices=notices,
                             hint_source=source)

    def _ai_hint(self, record: ProgressRecord, problem: Problem, messages: List[str], submission_path,
                 authored: Optional[str]) -> Tuple[Optional[str], str]:
        """Try an AI hint. Fall back to the pre-authored hint on any problem."""
        if self.hinter is None:
            return authored, "authored"
        try:
            code = Path(submission_path).read_text()
        except (OSError, UnicodeDecodeError):
            code = ""
        result = self.hinter.hint(problem, messages, code, attempt=record.attempts.get(problem.id, 1))
        if result is None:
            self.events.write("hint", student_id=record.student_id, project_id=self.project.id,
                              problem_id=problem.id, source="authored", reason=self.hinter.last_rejection)
            return authored, "authored"
        self.events.write("hint", student_id=record.student_id, project_id=self.project.id, problem_id=problem.id,
                          source="ai", model_id=result.model_id, latency_ms=result.latency_ms)
        return result.text, "ai"

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
