"""Student-facing operations over the engine. No HTTP in here, so it can be tested directly.

Every call opens the student's progress, does one thing through engine.session.Engine,
and returns plain dicts. Nothing here grades or routes; that stays in engine/.
"""
from __future__ import annotations

import re
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.cli import DEFAULT_DATA, DEFAULT_PROJECT, start_workspace
from engine.course import Course, CourseError
from engine.progress import ProgressRecord
from engine.project import Project
from engine.session import SubmitOutcome, UnknownStudent
from diagnostic.engine import NothingPending, NotFinished, UnknownQuest
from diagnostic.models import InvalidResponse
from diagnostic.store import InvalidStudentId
from engine.stages import MAX_STAGE, STAGE_NAMES

# Ids become folder names under the data directory, so only this shape is accepted.
STUDENT_ID = re.compile(r"^([0-9a-f]{32}|STU-[0-9a-f]{16,32})$")  # lesson-only students, or ones made by the readiness quest
MAX_CODE_CHARS = 20_000
MAX_THEME_CHARS = 300


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _status_of(problem_id: str, record: ProgressRecord) -> str:
    if problem_id in record.passed_problems:
        return "done"
    if not record.complete and problem_id == record.current_problem:
        return "current"
    return "todo"


def _problem_extras(project: Project, problem_id: str, record: ProgressRecord) -> Dict[str, Any]:
    problem = project.problem(problem_id)
    return {
        "number": problem.number,
        "concepts": list(problem.concepts),
        # Hints are revealed one at a time by the engine; only the counts leave here.
        "hintCount": len(problem.hints),
        "hintsSeen": record.hints_seen.get(problem.id, 0),
        "attempts": record.attempts.get(problem.id, 0),
    }


class Service:
    def __init__(self, data_dir: Path = DEFAULT_DATA, project_path: Path = DEFAULT_PROJECT,
                 provider=None, ai_reason: Optional[str] = None, adaptive: bool = True):
        self.data_dir = Path(data_dir)
        self.provider = provider
        self.ai_reason = ai_reason
        self.adaptive = adaptive
        self.course = Course(self.data_dir, provider=provider, adaptive=adaptive)
        self._locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._locks_guard = threading.Lock()

    # Plumbing ---------------------------------------------------------------
    def _lock(self, student_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks[student_id]

    def _check_id(self, student_id: str) -> None:
        if not isinstance(student_id, str) or not STUDENT_ID.match(student_id):
            raise ApiError(404, "unknown_student", "That student id isn't valid.")
        if not self.course.store.student_exists(student_id):
            raise ApiError(404, "unknown_student", "No student with that id. Start a new session.")

    # State ------------------------------------------------------------------
    def _state(self, student_id: str) -> Dict[str, Any]:
        course = self.course
        state = course.state(student_id)
        engine = course.engine(student_id)
        record, _ = engine.open(student_id)
        project = engine.project
        manifest = project.manifest

        code = ""
        if state["problem"] and state["problem"]["format"] == "code":
            path_file = start_workspace(self.data_dir, student_id, project)
            try:
                code = path_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                code = ""
        if state["problem"]:
            state["problem"].update(_problem_extras(project, state["problem"]["id"], record))

        levels = sorted(manifest.levels, key=lambda lv: lv.number)
        path: List[Dict[str, Any]] = []
        for level in levels:
            title = project.problem(level.id).title
            path.append({"id": level.id, "kind": "level", "title": title, "number": level.number,
                         "status": _status_of(level.id, record), "concepts": list(level.concepts),
                         "afterLevelId": None})
        # A practice problem appears on the map once it has been assigned or passed.
        for practice in manifest.practice_problems:
            status = _status_of(practice.id, record)
            if status == "todo":
                continue
            parent = next((lv.id for lv in levels if practice.concept in lv.concepts), None)
            path.append({"id": practice.id, "kind": "practice", "title": practice.title, "number": None,
                         "status": status, "concepts": [practice.concept], "afterLevelId": parent})
        state.update({
            "code": code, "path": path, "onFallback": record.on_fallback,
            "streakLength": manifest.streak_length, "maxStage": MAX_STAGE,
            "stageNames": [STAGE_NAMES[i] for i in range(MAX_STAGE + 1)],
            "themed": project.root.parent != course.projects_root and project.topic != "revision",
            "aiAvailable": self.provider is not None,
        })
        return state

    # Operations -------------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        return {"ok": True, "project": self.course.default_project().title, "ai": self.provider is not None,
                "aiReason": None if self.provider is not None else self.ai_reason,
                "adaptive": self.adaptive}

    def new_student(self) -> Dict[str, Any]:
        return self._state(self.course.new_student())

    def state(self, student_id: str) -> Dict[str, Any]:
        self._check_id(student_id)
        with self._lock(student_id):
            return self._state(student_id)

    def submit(self, student_id: str, code: Any) -> Dict[str, Any]:
        self._check_id(student_id)
        if not isinstance(code, str):
            raise ApiError(400, "bad_request", "The code must be text.")
        if len(code) > MAX_CODE_CHARS:
            raise ApiError(400, "code_too_long", f"The code is longer than {MAX_CODE_CHARS:,} characters.")
        with self._lock(student_id):
            project = self.course.project_for(student_id)
            if project.problem(self.course.engine(student_id).open(student_id)[0].current_problem).is_quiz:
                raise ApiError(400, "bad_request", "This step is a quiz. Answer the questions instead.")
            path = start_workspace(self.data_dir, student_id, project)
            try:
                path.write_text(code, encoding="utf-8")
            except UnicodeEncodeError:
                raise ApiError(400, "bad_request", "The code has characters that can't be saved.") from None
            outcome = self._guard(lambda: self.course.submit(student_id, path))
            return {"outcome": self._outcome(outcome, project), "state": self._state(student_id)}

    def answer(self, student_id: str, answers: Any) -> Dict[str, Any]:
        self._check_id(student_id)
        if not isinstance(answers, dict) or not answers:
            raise ApiError(400, "bad_request", "Answer the questions first.")
        for key, value in answers.items():
            ok = (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, str) and len(value) <= 2000)
            if not isinstance(key, str) or not ok:
                raise ApiError(400, "bad_request", "One of the answers isn't valid.")
        with self._lock(student_id):
            project = self.course.project_for(student_id)
            outcome = self._guard(lambda: self.course.answer(student_id, answers))
            return {"outcome": self._outcome(outcome, project), "state": self._state(student_id)}

    def next_step(self, student_id: str) -> Optional[Dict[str, Any]]:
        self._check_id(student_id)
        return self._guard(lambda: self.course.next_step(student_id))

    def start_next(self, student_id: str, option: Any, theme: Any = None) -> Dict[str, Any]:
        self._check_id(student_id)
        if not isinstance(option, int) or isinstance(option, bool):
            raise ApiError(400, "bad_request", "Pick one of the options.")
        if theme is not None and (not isinstance(theme, str) or len(theme) > MAX_THEME_CHARS):
            raise ApiError(400, "request_too_long", f"Keep it under {MAX_THEME_CHARS} characters.")
        with self._lock(student_id):
            result = self._guard(lambda: self.course.start(student_id, option, (theme or "").strip() or None))
            return {"message": result["message"], "built": result.get("built", True), "state": self._state(student_id)}

    def build_theme(self, student_id: str, request: Any) -> Dict[str, Any]:
        self._check_id(student_id)
        if self.provider is None:
            raise ApiError(503, "ai_unavailable", "Themes need the AI tutor, which isn't available right now.")
        if not isinstance(request, str) or not request.strip():
            raise ApiError(400, "bad_request", "Tell us what you'd like your project to be about.")
        if len(request) > MAX_THEME_CHARS:
            raise ApiError(400, "request_too_long", f"Keep it under {MAX_THEME_CHARS} characters.")
        with self._lock(student_id):
            result = self._guard(lambda: self.course.build_theme(student_id, request.strip()))
            return {"built": bool(result.get("built")), "message": result["message"], "state": self._state(student_id)}

    def reset_theme(self, student_id: str) -> Dict[str, Any]:
        self._check_id(student_id)
        with self._lock(student_id):
            self._guard(lambda: self.course.reset_theme(student_id))
            return self._state(student_id)

    # Readiness quest ---------------------------------------------------------
    def quest_options(self) -> Dict[str, Any]:
        return self.course.diagnostic_options()

    def quest_start(self, buddy: Any, goal: Any) -> Dict[str, Any]:
        for value in (buddy, goal):
            if value is not None and (not isinstance(value, str) or len(value) > 40):
                raise ApiError(400, "bad_request", "Pick a buddy and a goal from the lists.")
        options = self.course.diagnostic_options()
        if buddy is not None and buddy not in {b["id"] for b in options["buddies"]}:
            raise ApiError(400, "bad_request", "Pick a buddy from the list.")
        if goal is not None and goal not in {g["id"] for g in options["goals"]}:
            raise ApiError(400, "bad_request", "Pick a goal from the list.")
        # The free-text goal is left out on purpose: the screen only offers taps.
        return self._guard(lambda: self.course.diagnostic_start(buddy, goal, None))

    def quest_next(self, student_id: str) -> Dict[str, Any]:
        self._check_id(student_id)
        with self._lock(student_id):
            return self._guard(lambda: self.course.diagnostic_next(student_id))

    def quest_answer(self, student_id: str, response: Any, elapsed_ms: Any) -> Dict[str, Any]:
        self._check_id(student_id)
        if elapsed_ms is not None and (not isinstance(elapsed_ms, int) or isinstance(elapsed_ms, bool) or not 0 <= elapsed_ms <= 3_600_000):
            elapsed_ms = None
        if isinstance(response, dict) and isinstance(response.get("text"), str) and len(response["text"]) > 1000:
            raise ApiError(400, "bad_request", "That answer is too long.")
        with self._lock(student_id):
            return self._guard(lambda: self.course.diagnostic_answer(student_id, response, elapsed_ms))

    def quest_finish(self, student_id: str) -> Dict[str, Any]:
        self._check_id(student_id)
        with self._lock(student_id):
            return self._guard(lambda: self.course.diagnostic_finish(student_id))

    @staticmethod
    def _guard(fn):
        try:
            return fn()
        except CourseError as err:
            raise ApiError(400, "course_error", str(err)) from None
        except (UnknownStudent, UnknownQuest, InvalidStudentId):
            raise ApiError(404, "unknown_student", "No student with that id.") from None
        except InvalidResponse as err:
            raise ApiError(422, "invalid_answer", str(err)) from None
        except (NothingPending, NotFinished) as err:
            raise ApiError(409, "quest_state", str(err)) from None

    # Serialising ------------------------------------------------------------
    @staticmethod
    def _outcome(outcome: SubmitOutcome, project: Project) -> Dict[str, Any]:
        names = {c.id: c.name for c in project.manifest.concepts}
        return {
            "status": outcome.status,
            "passed": outcome.passed,
            "messages": list(outcome.messages),
            "hint": outcome.hint,
            "hintSource": outcome.hint_source,
            "stageChanges": [
                {"concept": ch.concept, "conceptName": names.get(ch.concept, ch.concept),
                 "oldStage": ch.old_stage, "newStage": ch.new_stage,
                 "oldStageName": STAGE_NAMES[ch.old_stage], "newStageName": STAGE_NAMES[ch.new_stage]}
                for ch in outcome.stage_changes
            ],
            "complete": outcome.complete,
            "notices": list(outcome.notices),
            "questionResults": list(outcome.question_results or []),
            "nextStep": outcome.next_step,
        }
