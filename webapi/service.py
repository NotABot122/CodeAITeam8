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
from engine.events import EventLog
from engine.progress import JsonProgressStore, ProgressRecord
from engine.project import Problem, Project, load_project
from engine.session import Engine, SubmitOutcome, UnknownStudent
from engine.stages import MAX_STAGE, STAGE_NAMES

# Ids become folder names under the data directory, so only this shape is accepted.
STUDENT_ID = re.compile(r"^[0-9a-f]{32}$")
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


def _problem_dict(problem: Problem, record: ProgressRecord) -> Dict[str, Any]:
    return {
        "id": problem.id,
        "kind": problem.kind,
        "title": problem.title,
        "number": problem.number,
        "label": problem.label,
        "instructions": problem.instructions,
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
        self.default_project_path = Path(project_path)
        self.provider = provider
        self.ai_reason = ai_reason
        self.adaptive = adaptive
        self.store = JsonProgressStore(self.data_dir)
        self.events = EventLog(self.data_dir)
        self._locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._locks_guard = threading.Lock()

    # Plumbing ---------------------------------------------------------------
    def _lock(self, student_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks[student_id]

    def _check_id(self, student_id: str) -> None:
        if not isinstance(student_id, str) or not STUDENT_ID.match(student_id):
            raise ApiError(404, "unknown_student", "That student id isn't valid.")
        if not self.store.student_exists(student_id):
            raise ApiError(404, "unknown_student", "No student with that id. Start a new session.")

    def _project_for(self, student_id: str) -> Project:
        folder = self.store.active_project(student_id)
        if folder and Path(folder).is_dir():
            return load_project(folder)
        return load_project(self.default_project_path)

    def _engine(self, project: Project) -> Engine:
        return Engine(project, self.store, self.events, hint_provider=self.provider, adaptive=self.adaptive)

    # State ------------------------------------------------------------------
    def _state(self, engine: Engine, project: Project, student_id: str,
               extra_notices: Optional[List[str]] = None) -> Dict[str, Any]:
        record, notices = engine.open(student_id)
        manifest = project.manifest
        notices = list(extra_notices or []) + notices

        problem = None if record.complete else project.problem(record.current_problem)
        path_file = start_workspace(self.data_dir, student_id, project)
        try:
            code = path_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            code = ""

        path: List[Dict[str, Any]] = []
        for level in sorted(manifest.levels, key=lambda lv: lv.number):
            path.append({"id": level.id, "kind": "level", "title": level.title, "number": level.number,
                         "status": _status_of(level.id, record), "concepts": list(level.concepts),
                         "afterLevelId": None})
        # A practice problem appears on the map once it has been assigned or passed.
        for practice in manifest.practice_problems:
            status = _status_of(practice.id, record)
            if status == "todo":
                continue
            parent = next((lv.id for lv in sorted(manifest.levels, key=lambda lv: lv.number) if practice.concept in lv.concepts), None)
            path.append({"id": practice.id, "kind": "practice", "title": practice.title, "number": None,
                         "status": status, "concepts": [practice.concept], "afterLevelId": parent})

        concepts = []
        for concept in manifest.concepts:
            state = record.concepts[concept.id]
            concepts.append({"id": concept.id, "name": concept.name, "stage": state.stage,
                             "stageName": STAGE_NAMES[state.stage], "streak": state.streak})
        return {
            "studentId": student_id,
            "project": {"id": project.id, "title": project.title},
            "complete": record.complete,
            "onFallback": record.on_fallback,
            "notices": notices,
            "problem": _problem_dict(problem, record) if problem else None,
            "code": code,
            "path": path,
            "concepts": concepts,
            "streakLength": manifest.streak_length,
            "maxStage": MAX_STAGE,
            "stageNames": [STAGE_NAMES[i] for i in range(MAX_STAGE + 1)],
        }

    # Operations -------------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        project = load_project(self.default_project_path)
        return {"ok": True, "project": project.title, "ai": self.provider is not None,
                "aiReason": None if self.provider is not None else self.ai_reason,
                "adaptive": self.adaptive}

    def new_student(self) -> Dict[str, Any]:
        project = load_project(self.default_project_path)
        engine = self._engine(project)
        student_id = engine.new_student()
        return self._state(engine, project, student_id)

    def state(self, student_id: str) -> Dict[str, Any]:
        self._check_id(student_id)
        with self._lock(student_id):
            project = self._project_for(student_id)
            return self._state(self._engine(project), project, student_id)

    def submit(self, student_id: str, code: Any) -> Dict[str, Any]:
        self._check_id(student_id)
        if not isinstance(code, str):
            raise ApiError(400, "bad_request", "The code must be text.")
        if len(code) > MAX_CODE_CHARS:
            raise ApiError(400, "code_too_long", f"The code is longer than {MAX_CODE_CHARS:,} characters.")
        with self._lock(student_id):
            project = self._project_for(student_id)
            engine = self._engine(project)
            path = start_workspace(self.data_dir, student_id, project)
            try:
                path.write_text(code, encoding="utf-8")
            except UnicodeEncodeError:
                raise ApiError(400, "bad_request", "The code has characters that can't be saved.") from None
            try:
                outcome = engine.submit(student_id, path)
            except UnknownStudent:
                raise ApiError(404, "unknown_student", "No student with that id.") from None
            return {"outcome": self._outcome(outcome, project), "state": self._state(engine, project, student_id)}

    def build_theme(self, student_id: str, request: Any) -> Dict[str, Any]:
        self._check_id(student_id)
        if self.provider is None:
            raise ApiError(503, "ai_unavailable", "Themes need the AI tutor, which isn't available right now.")
        if not isinstance(request, str) or not request.strip():
            raise ApiError(400, "bad_request", "Tell us what you'd like your project to be about.")
        if len(request) > MAX_THEME_CHARS:
            raise ApiError(400, "request_too_long", f"Keep it under {MAX_THEME_CHARS} characters.")
        from engine.themes.builder import BUILT, ThemeBuilder  # imported late: only needed with AI on

        with self._lock(student_id):
            result = ThemeBuilder(self.provider, self.data_dir / "themes").build(request.strip())
            self.events.write("theme", student_id=student_id, source=result.status,
                              category=result.category, model_id=self.provider.model_id)
            project = self._project_for(student_id)
            if result.status != BUILT:
                return {"built": False, "message": result.message,
                        "state": self._state(self._engine(project), project, student_id)}
            themed = load_project(result.project_path)
            self.store.set_active_project(student_id, str(themed.root))
            engine = self._engine(themed)
            engine.open(student_id)
            return {"built": True, "message": result.message,
                    "state": self._state(engine, themed, student_id)}

    def reset_theme(self, student_id: str) -> Dict[str, Any]:
        self._check_id(student_id)
        with self._lock(student_id):
            self.store.set_active_project(student_id, None)
            project = self._project_for(student_id)
            return self._state(self._engine(project), project, student_id)

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
        }
