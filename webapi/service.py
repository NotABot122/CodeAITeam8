"""Student-facing operations over the engine. No HTTP in here, so it can be tested directly.

Every call opens the student's progress, does one thing through engine.session.Engine,
and returns plain dicts. Nothing here grades or routes; that stays in engine/.
"""
from __future__ import annotations

import os
import re
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine import s3_storage
from engine.cli import DEFAULT_DATA, DEFAULT_PROJECT, start_workspace
from engine.course import Course, CourseError
from engine.progress import ProgressRecord
from engine.project import Project
from engine.safety import remove_contact_details
from engine.session import SubmitOutcome, UnknownStudent
from diagnostic.engine import NothingPending, NotFinished, UnknownQuest
from diagnostic.importer import ImportRejected
from diagnostic.models import InvalidResponse
from diagnostic.store import InvalidStudentId
from engine.stages import MAX_STAGE, STAGE_NAMES

from .blocks import python_to_blocks

# Ids become folder names under the data directory, so only this shape is accepted.
STUDENT_ID = re.compile(r"^([0-9a-f]{32}|STU-[0-9a-f]{16,32})$")  # lesson-only students, or ones made by the readiness quest
MAX_CODE_CHARS = 20_000
# Shown when an email address or phone number was taken out of the student's code before it was saved.
PRIVACY_NOTICE = ("We took an email address or phone number out of your code to keep your details private. "
                  "Your programs never need them.")
MAX_THEME_CHARS = 300
MAX_INTEREST_CHARS = 80         # the readiness check keeps at most max_goal_chars (diagnostic.yaml) of it


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _status_of(problem_id: str, record: ProgressRecord) -> str:
    if problem_id in record.passed_problems:
        return "done"
    if not record.complete and problem_id == record.current_problem:
        return "current"
    if not record.complete and problem_id == record.return_to:
        return "paused"   # a practice was inserted after repeated tries; the student comes back here
    return "todo"


# Why the current problem is a practice problem, from the routing reason that selected it.
_INSERTED = {"practice_assigned": "after_level", "struggle_practice": "struggle", "planned_practice": "planned"}


def _inserted(record: ProgressRecord) -> Optional[str]:
    for entry in reversed(record.routing_log):
        if entry.get("selected") == record.current_problem:
            return _INSERTED.get(entry.get("reason"))
    return None


def _problem_extras(project: Project, problem_id: str, record: ProgressRecord) -> Dict[str, Any]:
    problem = project.problem(problem_id)
    return {
        "number": problem.number,
        "concepts": list(problem.concepts),
        # Hints are revealed one at a time by the engine; only the counts leave here.
        "hintCount": len(problem.hints),
        "hintsSeen": record.hints_seen.get(problem.id, 0),
        "attempts": record.attempts.get(problem.id, 0),
        # Pre-authored, one per function the answer should use (functions.yaml).
        # None when the problem has no bank; [] when the answer needs no functions.
        "functions": None if problem.functions is None else
        [{"call": f["call"], "summary": f["summary"], "example": f["example"]} for f in problem.functions],
    }


def pathway_view(record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """What the student sees of their pathway: no stance, stages, teacher note or routing details."""
    if not record:
        return None
    current = record.get("current", 0)
    return {
        "id": record["id"], "title": record["title"], "summary": record["summary"],
        "message": record["student_message"], "decidedBy": record["decided_by"], "grade": record.get("grade"),
        "standards": [{"id": s["id"], "skill": s["skill"]} for s in record.get("standards") or []],
        "steps": [{"title": s["title"], "status": "done" if i < current else "current" if i == current else "todo"}
                  for i, s in enumerate(record.get("steps") or [])],
    }


class Service:
    def __init__(self, data_dir: Path = DEFAULT_DATA, project_path: Path = DEFAULT_PROJECT,
                 provider=None, ai_reason: Optional[str] = None, adaptive: bool = True, theme_provider=None):
        self.data_dir = Path(data_dir)
        self.provider = provider
        self.ai_reason = ai_reason
        self.adaptive = adaptive
        self.trace = None            # engine.ai_trace.TraceLog when the server runs with --dev
        self.guardrail = None        # engine.guardrail.BedrockGuardrail when synced and AI is on
        self.theme_provider = theme_provider
        self.course = Course(self.data_dir, provider=provider, adaptive=adaptive, theme_provider=theme_provider)
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
            if state["problem"]["format"] == "code":
                state["problem"]["support"] = engine.support_view(record, project.problem(state["problem"]["id"]), code)
            inserted = _inserted(record) if manifest.practice(state["problem"]["id"]) is not None else None
            # Only a practice inserted after repeated tries promises a way back to one known level.
            back = record.return_to if inserted == "struggle" else None
            state["problem"].update({
                "inserted": inserted,
                "returnTo": {"id": back, "title": project.problem(back).title} if back and manifest.has_problem(back) else None,
            })

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
            "pathway": pathway_view(course.store.profile(student_id).get("pathway")),
            # When "Make it yours" applies: "now" (first topic), "later" (a pathway step on it is ahead), or None.
            "themeable": course.theme_target(student_id),
        })
        return state

    # Operations -------------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        return {"ok": True, "project": self.course.default_project().title, "ai": self.provider is not None,
                "aiReason": None if self.provider is not None else self.ai_reason,
                "adaptive": self.adaptive, "dev": getattr(self, "trace", None) is not None,
                "devLocked": getattr(self, "trace", None) is not None and getattr(self, "inspector_locked", False),
                "safety": self.guardrail.label if getattr(self, "guardrail", None) else "local rules",
                "storage": s3_storage.current().describe() if s3_storage.current() else "local disk"}

    # Dev-only AI inspector (webapi.server --dev) -----------------------------------
    def _trace(self):
        trace = getattr(self, "trace", None)
        if trace is None:
            raise ApiError(404, "not_found", "No such endpoint.")
        return trace

    def dev_info(self) -> Dict[str, Any]:
        from engine.ai_trace import FEATURES, RETRIEVAL_FEATURE
        self._trace()
        model = getattr(self.provider, "model_id", None)
        # Every feature goes through the one provider, so they share the configured model ($CODEAI_MODEL_ID).
        return {"ai": self.provider is not None, "aiReason": None if self.provider is not None else self.ai_reason,
                "model": model, "modelSource": "CODEAI_MODEL_ID" if os.environ.get("CODEAI_MODEL_ID") else "default",
                "safety": self.guardrail.label if self.guardrail else "local rules",
                "features": [{"name": name, "what": what,
                              "model": getattr(self.theme_provider, "model_id", None) or model if "Theme designer" in name else model}
                             for _, name, what in FEATURES]
                + ([{"name": "Safety guardrail (student input / model output)",
                     "what": "Amazon Bedrock Guardrail made from our classroom rules: denied topics, words, personal "
                             "info, content and prompt-attack filters. Local rules decide if it can't answer.",
                     "model": self.guardrail.label}] if self.guardrail else [])
                + [dict(RETRIEVAL_FEATURE, model=self._curriculum_source())]}

    @staticmethod
    def _curriculum_source() -> Optional[str]:
        from engine.curriculum import CurriculumError, load_curriculum
        try:
            c = load_curriculum()
        except CurriculumError:
            return None
        return f"{c.source} (version {c.version_id})" if c.version_id else c.source

    def dev_calls(self, after: int) -> Dict[str, Any]:
        return {"calls": self._trace().after(after)}

    def dev_clear(self) -> Dict[str, Any]:
        self._trace().clear()
        return {"ok": True}

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
            removed = self._save_code(path, code)
            outcome = self._guard(lambda: self.course.submit(student_id, path))
            return self._with_privacy_notice({"outcome": self._outcome(outcome, project), "state": self._state(student_id)}, removed)

    def hint(self, student_id: str, code: Any = None) -> Dict[str, Any]:
        """A hint on request. For a code problem the current editor text is saved first, so the AI tutor
        (when on) can phrase the hint from it. Not a submission: attempts don't change."""
        self._check_id(student_id)
        if code is not None and not isinstance(code, str):
            raise ApiError(400, "bad_request", "The code must be text.")
        if isinstance(code, str) and len(code) > MAX_CODE_CHARS:
            raise ApiError(400, "code_too_long", f"The code is longer than {MAX_CODE_CHARS:,} characters.")
        with self._lock(student_id):
            project = self.course.project_for(student_id)
            record, _ = self.course.engine(student_id).open(student_id)
            path = None
            if not record.complete and not project.problem(record.current_problem).is_quiz and isinstance(code, str):
                path = start_workspace(self.data_dir, student_id, project)
                removed = self._save_code(path, code)
            else:
                removed = 0
            outcome = self._guard(lambda: self.course.request_hint(student_id, path))
            return self._with_privacy_notice({"outcome": self._outcome(outcome, project), "state": self._state(student_id)}, removed)

    @staticmethod
    def _save_code(path: Path, code: str) -> int:
        """Save the editor text as the student's workspace file, without email addresses or phone numbers.
        Returns how many were taken out."""
        code, removed = remove_contact_details(code)
        try:
            path.write_text(code, encoding="utf-8")
        except UnicodeEncodeError:
            raise ApiError(400, "bad_request", "The code has characters that can't be saved.") from None
        s3_storage.changed(path)
        return removed

    @staticmethod
    def _with_privacy_notice(result: Dict[str, Any], removed: int) -> Dict[str, Any]:
        if removed:
            result["outcome"]["notices"].insert(0, PRIVACY_NOTICE)
            result["state"]["notices"].insert(0, PRIVACY_NOTICE)      # the lesson page shows state notices
        return result

    @staticmethod
    def to_blocks(code: Any) -> Dict[str, Any]:
        """Python -> block workspace for the editor's Blocks mode. Parses only; never runs the code."""
        if not isinstance(code, str):
            raise ApiError(400, "bad_request", "The code must be text.")
        if len(code) > MAX_CODE_CHARS:
            raise ApiError(400, "code_too_long", f"The code is longer than {MAX_CODE_CHARS:,} characters.")
        return python_to_blocks(code)

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

    # Project choice --------------------------------------------------------------
    def project_choices(self, student_id: str) -> Dict[str, Any]:
        self._check_id(student_id)
        return self._guard(lambda: self.course.project_choices(student_id))

    def choose_project(self, student_id: str, project: Any) -> Dict[str, Any]:
        self._check_id(student_id)
        if not isinstance(project, str) or len(project) > 80:
            raise ApiError(400, "bad_request", "Pick one of the projects in the list.")
        with self._lock(student_id):
            self._guard(lambda: self.course.choose_project(student_id, project))
            return {"state": self._state(student_id), **self.course.project_choices(student_id)}

    def course_view(self, student_id: str) -> Dict[str, Any]:
        """The student's whole course at a glance: topics, finished work, ideas, and what's next."""
        self._check_id(student_id)
        with self._lock(student_id):
            course = self.course
            profile = course.store.profile(student_id)
            engine = course.engine(student_id)
            record, _ = engine.open(student_id)
            project = engine.project
            catalog = course.catalog
            done_topics = {c.get("topic") for c in profile.get("completed") or [] if c.get("topic") != "revision"}
            if record.complete and project.topic != "revision":
                done_topics.add(project.topic)
            topics = []
            for t in catalog.topics:
                if t.id in done_topics:
                    status = "done"
                elif project.topic == t.id and not record.complete:
                    status = "current"
                else:
                    status = "upcoming"
                topics.append({"id": t.id, "title": t.title, "status": status,
                               "concepts": [catalog.name(c) for c in t.concepts]})
            stages = {c: int(s) for c, s in (profile.get("concepts") or {}).items()}
            for cid, st in record.concepts.items():
                stages[cid] = max(stages.get(cid, 0), int(st.stage))
            reviews = []
            for c in profile.get("completed") or []:
                if c.get("topic") == "revision" and c.get("revision_concept"):
                    reviews.append(catalog.name(c["revision_concept"]))
            diag = profile.get("diagnostic") or {}
            return {
                "studentId": student_id,
                "now": {"project": project.title, "isReview": project.topic == "revision", "complete": record.complete},
                "topics": topics,
                "reviewsDone": reviews,
                "concepts": [{"id": c, "name": n, "stage": stages.get(c, 0), "stageName": STAGE_NAMES[min(3, stages.get(c, 0))],
                              "inProject": c in record.concepts and not record.complete}
                             for c, n in catalog.concepts.items()],
                "quest": {"status": course.diagnostic_status(student_id),
                          "seeded": [catalog.name(c) for c, v in (diag.get("seeded") or {}).items() if v > 0]},
                "nextStep": (profile.get("next_step") or {}).get("reason") if record.complete else None,
                "stageNames": [STAGE_NAMES[i] for i in range(MAX_STAGE + 1)],
            }

    # Lesson pathway (Strands Decider 2B) ------------------------------------------
    def pathway(self, student_id: str, grade: Any) -> Dict[str, Any]:
        self._check_id(student_id)
        if not isinstance(grade, int) or isinstance(grade, bool):
            raise ApiError(400, "bad_request", "Pick your grade.")
        with self._lock(student_id):
            record = self._guard(lambda: self.course.decide_pathway(student_id, grade))
            return {"pathway": pathway_view(record), "state": self._state(student_id)}

    # Readiness quest ---------------------------------------------------------
    def quest_options(self) -> Dict[str, Any]:
        return self.course.diagnostic_options()

    def quest_start(self, buddy: Any, goal: Any, interests: Any = None) -> Dict[str, Any]:
        for value in (buddy, goal):
            if value is not None and (not isinstance(value, str) or len(value) > 40):
                raise ApiError(400, "bad_request", "Pick a buddy and a goal from the lists.")
        if interests is not None and (not isinstance(interests, str) or len(interests) > MAX_INTEREST_CHARS):
            raise ApiError(400, "request_too_long", f"Keep it under {MAX_INTEREST_CHARS} characters.")
        options = self.course.diagnostic_options()
        if buddy is not None and buddy not in {b["id"] for b in options["buddies"]}:
            raise ApiError(400, "bad_request", "Pick a buddy from the list.")
        if goal is not None and goal not in {g["id"] for g in options["goals"]}:
            raise ApiError(400, "bad_request", "Pick a goal from the list.")
        # "What are you into?" is optional free text. The quest screens it (diagnostic.safety.clean_goal_text):
        # personal details, filtered words or instructions to the AI mean it's dropped, and the student is told.
        return self._guard(lambda: self.course.diagnostic_start(buddy, goal, (interests or "").strip() or None))

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

    # Starting from an earlier lesson's results (diagnostic/importer.py) ------------------------
    def import_samples(self) -> Dict[str, Any]:
        return {"samples": self.course.import_samples()}

    def import_previous(self, sample: Any = None, data: Any = None) -> Dict[str, Any]:
        """Exactly one of: a sample student's id, or the JSON of a results file. Returns {result, state}."""
        if (sample is None) == (data is None):
            raise ApiError(400, "bad_request", "Pick a sample student or choose a results file.")
        if sample is not None and not isinstance(sample, str):
            raise ApiError(400, "bad_request", "Pick one of the sample students in the list.")
        if data is not None and not isinstance(data, dict):
            raise ApiError(400, "import_rejected", "The file must be one JSON object, like the sample files.")
        try:
            result = self.course.import_previous(data=data, sample=sample)
        except ImportRejected as err:
            raise ApiError(400, "import_rejected", " ".join(err.problems)) from None
        return {"result": result, "state": self._state(result["student_id"])}

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
            "explanation": outcome.explanation,
            "mistake": outcome.mistake,
            "stuck": list(outcome.stuck or []),
        }
