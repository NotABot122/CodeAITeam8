"""The Course: one student profile across projects, and what to do next.

After a student finishes a project, each of its concepts is judged from that
project's evidence (attempts, hints, practice problems) using the catalog
thresholds:

- struggled on any concept  -> a revision project for the weakest concept
                               (a review quiz, then a scaffolded coding task)
- strong on every concept   -> the next topic, picked by lowest mastery
- otherwise (steady)        -> the same topic in a new theme, or the next topic

The profile keeps a stage per concept across projects. A new project starts
each concept at the profile's stage, so evidence keeps building.

This module is the entry point for interfaces (CLI, web API). Its methods
return plain data that converts to JSON.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from . import REPO_ROOT
from .ai import ModelProvider
from .events import EventLog
from .grader import Grader
from .progress import JsonProgressStore, ProgressRecord
from .project import Project, load_project
from .quiz import public_questions
from .session import Engine, SubmitOutcome, UnknownStudent
from .stages import STAGE_NAMES

PROJECTS_ROOT = REPO_ROOT / "projects"
STRONG, STEADY, STRUGGLED = "strong", "steady", "struggled"
REVISION, NEXT_TOPIC, NEW_THEME, ALL_DONE = "revision", "next_topic", "new_theme", "all_done"


# Catalog ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    project: str
    concepts: List[str]
    themeable: bool = False


@dataclass
class Catalog:
    concepts: Dict[str, str]
    topics: List[Topic]
    revision: Dict[str, str]
    thresholds: dict
    diagnostic: dict = field(default_factory=lambda: {"min_confidence": 0.8, "use_borderline": False, "min_correct_answers": 2})
    intervention: dict = field(default_factory=lambda: {"struggle_after": None})

    def topic(self, topic_id: str) -> Optional[Topic]:
        return next((t for t in self.topics if t.id == topic_id), None)

    def name(self, concept: str) -> str:
        return self.concepts.get(concept, concept.replace("_", " ").title())


def load_catalog(projects_root: Path = PROJECTS_ROOT) -> Catalog:
    data = yaml.safe_load((Path(projects_root) / "catalog.yaml").read_text())
    topics = [Topic(t["id"], t["title"], t["project"], list(t["concepts"]), bool(t.get("themeable")))
              for t in data["topics"]]
    diagnostic = {"min_confidence": 0.8, "use_borderline": False, "min_correct_answers": 2}
    diagnostic.update(data.get("diagnostic") or {})
    intervention = {"struggle_after": None}
    intervention.update(data.get("intervention") or {})
    return Catalog(dict(data["concepts"]), topics, dict(data.get("revision") or {}), dict(data["thresholds"]),
                   diagnostic, intervention)


def seed_from_placement(placement: dict, rules: dict, correct: Optional[Dict[str, int]] = None) -> Dict[str, dict]:
    """Decide which diagnostic stages to use. Returns {concept: {"stage", "confidence", "used", "reason"}}.

    `correct` is the number of correct answers per concept. A stage above 0 needs at least
    rules["min_correct_answers"] of them: one lucky guess must not skip a student past practice.
    """
    decisions = {}
    need = int(rules.get("min_correct_answers", 0) or 0)
    for concept, p in (placement.get("concepts") or {}).items():
        stage, confidence, borderline = int(p.get("stage", 0)), float(p.get("confidence", 0.0)), bool(p.get("borderline"))
        got = None if correct is None else int(correct.get(concept, 0))
        if stage > 0 and got is not None and got < need:
            reason, used = f"stage {stage} rests on {got} correct answer(s); {need} are needed", False
        elif confidence < float(rules["min_confidence"]):
            reason, used = f"confidence {confidence:.2f} is below {rules['min_confidence']}", False
        elif borderline and not rules.get("use_borderline"):
            reason, used = "borderline result", False
        else:
            reason, used = "confident result", True
        decisions[concept] = {"stage": max(0, min(3, stage)), "confidence": round(confidence, 3),
                              "used": used, "reason": reason}
    return decisions


# Judging a finished project ---------------------------------------------------------------

@dataclass
class ConceptEvidence:
    concept: str
    level: str
    max_attempts: int = 0
    total_hints: int = 0
    max_hints: int = 0
    practice: bool = False
    problems: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def assess(project: Project, record: ProgressRecord, thresholds: dict) -> Dict[str, ConceptEvidence]:
    strong, struggled = thresholds["strong"], thresholds["struggled"]
    assigned = {entry["selected"] for entry in record.routing_log if entry.get("reason") == "practice_assigned"}
    evidence = {}
    for concept in project.manifest.concept_ids():
        problems = [p for p in project.problems.values() if concept in p.concepts and p.id in record.attempts]
        if not problems:
            continue
        attempts = [record.attempts.get(p.id, 0) for p in problems]
        hints = [record.hints_seen.get(p.id, 0) for p in problems]
        practice = any(p.kind == "practice" and p.id in assigned for p in problems)
        if max(attempts) >= struggled["min_attempts"] or max(hints) >= struggled["min_hints"] or \
                (practice and struggled.get("practice_counts", True)):
            level = STRUGGLED
        elif max(attempts) <= strong["max_attempts"] and max(hints) <= strong["max_hints"]:
            level = STRONG
        else:
            level = STEADY
        evidence[concept] = ConceptEvidence(concept, level, max(attempts), sum(hints), max(hints), practice,
                                            len(problems))
    return evidence


# Deciding what's next ---------------------------------------------------------------------

@dataclass
class Option:
    kind: str
    label: str
    project: Optional[str] = None      # folder name under projects/, for revision and next_topic
    concept: Optional[str] = None
    topic: Optional[str] = None


@dataclass
class Recommendation:
    kind: str
    reason: str
    options: List[Option] = field(default_factory=list)   # options[0] is the recommended one
    evidence: Dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "reason": self.reason, "options": [asdict(o) for o in self.options],
                "evidence": self.evidence}


def _next_topic(catalog: Catalog, stages: Dict[str, int], completed: List[str], current: str) -> Optional[Topic]:
    candidates = [t for t in catalog.topics if t.id not in completed and t.id != current]
    if not candidates:
        return None
    order = {t.id: i for i, t in enumerate(catalog.topics)}
    return min(candidates, key=lambda t: (sum(stages.get(c, 0) for c in t.concepts) / len(t.concepts), order[t.id]))


def decide(catalog: Catalog, topic_id: str, revision_concept: Optional[str], evidence: Dict[str, ConceptEvidence],
           stages: Dict[str, int], completed_topics: List[str], ai_available: bool) -> Recommendation:
    upcoming = _next_topic(catalog, stages, completed_topics, topic_id)
    move_on = Option(NEXT_TOPIC, f"Start {upcoming.title}", upcoming.project, topic=upcoming.id) if upcoming else None
    done = Option(ALL_DONE, "You've finished every topic")
    summary = {c: e.to_dict() for c, e in evidence.items()}

    weak = [e for e in evidence.values() if e.level == STRUGGLED]
    if weak:
        worst = max(weak, key=lambda e: (e.max_attempts + 2 * e.total_hints, e.practice))
        name = catalog.name(worst.concept)
        revision = catalog.revision.get(worst.concept)
        if revision and revision_concept != worst.concept:
            options = [Option(REVISION, f"Review {name}", revision, concept=worst.concept)]
            options += [move_on] if move_on else []
            return Recommendation(REVISION, f"{name} took some extra tries, so here's a short review with a few "
                                            "questions to lock it in.", options, summary)
        if revision:   # just finished this revision and it was still hard: move on, but offer it again
            options = ([move_on] if move_on else [done]) + [Option(REVISION, f"Review {name} again", revision,
                                                                   concept=worst.concept)]
            return Recommendation(options[0].kind, f"You kept going on {name}. Let's keep building with new "
                                                   "problems, and you can review again anytime. If it still feels "
                                                   "hard, ask your teacher for help.", options, summary)

    topic = catalog.topic(topic_id)
    all_strong = bool(evidence) and all(e.level == STRONG for e in evidence.values())
    if revision_concept is None and not all_strong and topic and topic.themeable and ai_available:
        options = [Option(NEW_THEME, "Practice the same skills in a new theme", topic=topic.id)]
        options += [move_on] if move_on else []
        reason = "Nice work! Practice these skills once more in a theme you pick"
        reason += f", or move on to {upcoming.title}." if upcoming else "."
        return Recommendation(NEW_THEME, reason, options, summary)

    if move_on is None:
        return Recommendation(ALL_DONE, "You've finished every topic so far. Amazing work!", [done], summary)
    stage_note = ", ".join(f"{catalog.name(c)} {STAGE_NAMES[stages.get(c, 0)]}" for c in upcoming.concepts)
    if revision_concept:
        reason = f"Review done! Next up: {upcoming.title} ({stage_note})."
    elif all_strong:
        reason = f"You aced every level! Next up: {upcoming.title}, where you have the most to learn ({stage_note})."
    else:
        reason = f"Nice work! Next up: {upcoming.title} ({stage_note})."
    return Recommendation(NEXT_TOPIC, reason, [move_on], summary)


# The Course -------------------------------------------------------------------------------

class CourseError(Exception):
    pass


class Course:
    def __init__(self, data_dir, projects_root: Path = PROJECTS_ROOT, provider: Optional[ModelProvider] = None,
                 adaptive: bool = True, grader: Optional[Grader] = None, router=None):
        self.data_dir = Path(data_dir)
        self.projects_root = Path(projects_root)
        self.catalog = load_catalog(self.projects_root)
        self.store = JsonProgressStore(self.data_dir)
        self.events = EventLog(self.data_dir)
        self.provider = provider
        self.adaptive = adaptive
        self.grader = grader or Grader()
        self.router = router
        self._projects: Dict[str, Project] = {}

    # Projects and engines ---------------------------------------------------------------
    def _project(self, folder) -> Project:
        key = str(Path(folder).resolve())
        if key not in self._projects:
            self._projects[key] = load_project(key)
        return self._projects[key]

    def default_project(self) -> Project:
        return self._project(self.projects_root / self.catalog.topics[0].project)

    def project_for(self, student_id: str) -> Project:
        folder = self.store.active_project(student_id)
        if folder and Path(folder).is_dir():
            return self._project(folder)
        return self.default_project()

    def stages(self, student_id: str) -> Dict[str, int]:
        return {c: int(s) for c, s in (self.store.profile(student_id).get("concepts") or {}).items()}

    def engine(self, student_id: str, project: Optional[Project] = None) -> Engine:
        kwargs = {"router": self.router} if self.router else {}
        project = project or self.project_for(student_id)
        planned = (self.store.profile(student_id).get("planned_practice") or {}) if student_id else {}
        return Engine(project, self.store, self.events, grader=self.grader,
                      adaptive=self.adaptive, hint_provider=self.provider,
                      initial_stages=self.stages(student_id),
                      planned_practice=planned.get("problems") if planned.get("project") == project.id else None,
                      struggle_after=self.catalog.intervention.get("struggle_after"),
                      **kwargs)

    def _require(self, student_id: str) -> None:
        if not self.store.student_exists(student_id):
            raise UnknownStudent(f"no student with id {student_id}")

    # Students -----------------------------------------------------------------------------
    def new_student(self) -> str:
        engine = self.engine("", self.default_project())
        student_id = engine.new_student()
        profile = self.store.profile(student_id)
        profile.update(active_project=str(self.default_project().root), concepts={}, completed=[], next_step=None)
        self.store.save_profile(student_id, profile)
        return student_id

    # Working on a project -----------------------------------------------------------------
    def submit(self, student_id: str, submission_path) -> SubmitOutcome:
        self._require(student_id)
        engine = self.engine(student_id)
        return self._after(student_id, engine, engine.submit(student_id, submission_path))

    def answer(self, student_id: str, answers: Dict[str, object]) -> SubmitOutcome:
        self._require(student_id)
        engine = self.engine(student_id)
        return self._after(student_id, engine, engine.answer(student_id, answers))

    def _after(self, student_id: str, engine: Engine, outcome: SubmitOutcome) -> SubmitOutcome:
        record, _ = engine.open(student_id)
        profile = self.store.profile(student_id)
        concepts = dict(profile.get("concepts") or {})
        for cid, state in record.concepts.items():
            concepts[cid] = max(int(concepts.get(cid, 0)), state.stage)
        profile["concepts"] = concepts
        if outcome.passed and outcome.complete and outcome.status != "complete":
            recommendation = self._recommend(engine.project, record, profile)
            profile.setdefault("completed", []).append({
                "project_id": engine.project.id, "topic": engine.project.topic,
                "revision_concept": engine.project.manifest.parameters.get("revision_concept"),
                "evidence": recommendation.evidence,
                "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
            profile["next_step"] = recommendation.to_dict()
            outcome.next_step = profile["next_step"]
            self.events.write("next_step", student_id=student_id, project_id=engine.project.id,
                              selected=recommendation.options[0].project if recommendation.options else None,
                              reason=recommendation.kind, stages=concepts)
        self.store.save_profile(student_id, profile)
        return outcome

    def _recommend(self, project: Project, record: ProgressRecord, profile: dict) -> Recommendation:
        evidence = assess(project, record, self.catalog.thresholds)
        completed = [c["topic"] for c in profile.get("completed") or [] if c.get("topic") != "revision"]
        if project.topic != "revision":
            completed.append(project.topic)
        topic = project.topic if project.topic != "revision" else None
        return decide(self.catalog, topic or "", project.manifest.parameters.get("revision_concept"), evidence,
                      {c: int(s) for c, s in profile.get("concepts", {}).items()}, completed,
                      ai_available=self.provider is not None)

    # What's next --------------------------------------------------------------------------
    def next_step(self, student_id: str) -> Optional[dict]:
        self._require(student_id)
        record, _ = self.engine(student_id).open(student_id)
        return self.store.profile(student_id).get("next_step") if record.complete else None

    def start(self, student_id: str, option_index: int = 0, theme_request: Optional[str] = None) -> dict:
        """Start one of the options from next_step. Returns {"message", "project", "state"}."""
        step = self.next_step(student_id)
        if not step:
            raise CourseError("Finish your current project first.")
        options = step["options"]
        if not 0 <= option_index < len(options):
            raise CourseError(f"Pick an option from 1 to {len(options)}.")
        option = options[option_index]
        if option["kind"] == ALL_DONE:
            raise CourseError("You've finished every topic so far.")
        if option["kind"] == NEW_THEME:
            if not theme_request:
                raise CourseError("Tell us what theme you'd like, for example \"pokemon\".")
            return self.build_theme(student_id, theme_request)
        project = self._project(self.projects_root / option["project"])
        return self._switch(student_id, project, f"Starting {project.title}.")

    def _switch(self, student_id: str, project: Project, message: str) -> dict:
        engine = self.engine(student_id, project)
        self.store.save(engine._fresh_record(student_id))     # a fresh start, even if done before
        profile = self.store.profile(student_id)
        profile.update(active_project=str(project.root), next_step=None)
        self.store.save_profile(student_id, profile)
        self.events.write("start_project", student_id=student_id, project_id=project.id)
        return {"message": message, "project": project.id, "state": self.state(student_id)}

    def build_theme(self, student_id: str, request: str) -> dict:
        self._require(student_id)
        if self.provider is None:
            raise CourseError("Themes need the AI features to be on.")
        from .themes.builder import BUILT, ThemeBuilder
        result = ThemeBuilder(self.provider, self.data_dir / "themes").build(request)
        self.events.write("theme", student_id=student_id, source=result.status, category=result.category,
                          model_id=self.provider.model_id)
        if result.status != BUILT:
            return {"message": result.message, "project": None, "state": self.state(student_id), "built": False}
        out = self._switch(student_id, self._project(result.project_path), result.message)
        out["built"] = True
        return out

    def reset_theme(self, student_id: str) -> dict:
        self._require(student_id)
        self.store.set_active_project(student_id, str(self.default_project().root))
        return self.state(student_id)

    # Readiness diagnostic (diagnostic/) -------------------------------------------------------
    # The quest creates the student. When it's finished, its confident stages seed the profile
    # and its placement picks the first problem. Students who skip it use new_student().
    def diagnostic(self):
        if not hasattr(self, "_diagnostic"):
            from diagnostic.engine import DiagnosticEngine
            self._diagnostic = DiagnosticEngine.from_paths(project=self.default_project().root, data=self.data_dir,
                                                           provider=self.provider, adaptive=self.adaptive)
        return self._diagnostic

    def diagnostic_options(self) -> dict:
        return self.diagnostic().options()

    def diagnostic_start(self, buddy: Optional[str] = None, goal: Optional[str] = None,
                         goal_text: Optional[str] = None) -> dict:
        """Create a student and start their quest. The response includes "student_id"."""
        started = self.diagnostic().start(buddy, goal, goal_text)
        profile = self.store.profile(started["student_id"])
        profile.update(active_project=str(self.default_project().root), concepts={}, completed=[], next_step=None)
        self.store.save_profile(started["student_id"], profile)
        return started

    def diagnostic_next(self, student_id: str) -> dict:
        step = self.diagnostic().next(student_id)
        if step.get("done"):
            self.apply_diagnostic(student_id)
        return step

    def diagnostic_answer(self, student_id: str, response, elapsed_ms: Optional[int] = None) -> dict:
        return self.diagnostic().answer(student_id, response, elapsed_ms)

    def diagnostic_finish(self, student_id: str) -> dict:
        """End the quest early or on time, then apply its result."""
        result = self.diagnostic().finish(student_id)
        self.apply_diagnostic(student_id)
        return result

    def apply_diagnostic(self, student_id: str) -> dict:
        """Seed the profile with confident diagnostic stages and start the lesson at its placement.

        Safe to call more than once. A lesson that has already started keeps its place; only the
        profile (and so later projects) gets the seeded stages.
        """
        self._require(student_id)
        from diagnostic.store import DiagnosticStore
        state = DiagnosticStore(self.data_dir).load(student_id)
        if state is None or not state.placement:
            raise CourseError("The readiness quest isn't finished yet.")
        profile = self.store.profile(student_id)
        if profile.get("diagnostic", {}).get("applied"):
            return profile["diagnostic"]

        correct: Dict[str, int] = {}
        for r in state.results:
            if r.passed:
                correct[r.concept] = correct.get(r.concept, 0) + 1
        decisions = seed_from_placement(state.placement, self.catalog.diagnostic, correct)
        concepts = dict(profile.get("concepts") or {})
        for concept, d in decisions.items():
            if d["used"]:
                concepts[concept] = max(int(concepts.get(concept, 0)), d["stage"])
        profile["concepts"] = concepts

        project = self.default_project()
        # Plan a practice problem before the level of every concept the diagnostic is confident is a gap.
        planned = []
        for concept, d in decisions.items():
            if d["used"] and d["stage"] == 0:
                practice = next((p for p in project.manifest.practice_problems
                                 if p.concept == concept and p.target_stage == 1), None)
                if practice is not None:
                    planned.append(practice.id)
        profile["planned_practice"] = {"project": project.id, "problems": planned}
        start = state.placement.get("route", {}).get("next_task_id")
        engine = self.engine(student_id, project)
        try:
            existing = self.store.load(student_id, project.id)
        except Exception:
            existing = None
        started = existing is not None and bool(existing.attempts or existing.passed_problems)
        placed_at = existing.current_problem if started else None
        if not started:
            engine.initial_stages = {c: int(s) for c, s in concepts.items()}
            record = engine._fresh_record(student_id)
            if start and project.manifest.has_problem(start):
                record.current_problem = start
                practice = project.manifest.practice(start)
                if practice is not None:
                    record.origin_level = next((lvl.id for lvl in project.manifest.levels_in_order()
                                                if practice.concept in lvl.concepts), project.manifest.fallback_path[0])
                record.routing_log.append({"selected": start, "reason": "diagnostic_placement", "policy": "diagnostic",
                                           "stages": record.stages(),
                                           "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
            self.store.save(record)
            placed_at = record.current_problem
        summary = {"applied": True, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                   "seeded": {c: d["stage"] for c, d in decisions.items() if d["used"]},
                   "decisions": decisions, "start_problem": placed_at, "lesson_already_started": started}
        profile["diagnostic"] = summary
        profile.setdefault("active_project", str(project.root))
        self.store.save_profile(student_id, profile)
        self.events.write("diagnostic_applied", student_id=student_id, project_id=project.id, selected=placed_at,
                          stages=summary["seeded"], reason="lesson_already_started" if started else "placed")
        return summary

    def diagnostic_status(self, student_id: str) -> str:
        """none, in_progress, finished (not applied yet), or applied."""
        if self.store.profile(student_id).get("diagnostic", {}).get("applied"):
            return "applied"
        try:
            from diagnostic.store import DiagnosticStore, check_student_id
            check_student_id(student_id)
            state = DiagnosticStore(self.data_dir).load(student_id)
        except Exception:
            return "none"
        if state is None:
            return "none"
        return "finished" if state.placement else "in_progress"

    # Views --------------------------------------------------------------------------------
    def state(self, student_id: str) -> dict:
        """Everything a UI needs to draw the current screen."""
        self._require(student_id)
        engine = self.engine(student_id)
        record, notices = engine.open(student_id)
        project = engine.project
        problem = None if record.complete else project.problem(record.current_problem)
        profile = self.store.profile(student_id)
        stages = {c: max(int(profile.get("concepts", {}).get(c, 0)), record.concepts[c].stage)
                  if c in record.concepts else int(profile.get("concepts", {}).get(c, 0))
                  for c in self.catalog.concepts}
        return {
            "studentId": student_id,
            "project": {"id": project.id, "title": project.title, "topic": project.topic},
            "complete": record.complete,
            "notices": notices,
            "problem": None if problem is None else {
                "id": problem.id, "kind": problem.kind, "format": problem.format, "title": problem.title,
                "label": problem.label, "instructions": problem.instructions,
                "questions": public_questions(problem.questions) if problem.is_quiz else None},
            "concepts": [{"id": c, "name": name, "stage": stages[c], "stageName": STAGE_NAMES[stages[c]],
                          "inProject": c in record.concepts} for c, name in self.catalog.concepts.items()],
            "nextStep": profile.get("next_step") if record.complete else None,
            "diagnostic": self.diagnostic_status(student_id),
        }
