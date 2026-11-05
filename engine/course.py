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
from typing import Dict, List, Optional, Tuple

import yaml

from . import REPO_ROOT
from .ai import ModelProvider
from .events import EventLog
from .grader import Grader
from .progress import JsonProgressStore, ProgressRecord
from .project import Project, load_project
from .quiz import public_questions
from .session import Engine, SubmitOutcome, UnknownStudent
from .support import SupportPolicy
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
    # Projects with the same skills and different stories: [{"project", "goals", "pitch"}]. The student picks one.
    choices: List[dict] = field(default_factory=list)


@dataclass
class Catalog:
    concepts: Dict[str, str]
    topics: List[Topic]
    revision: Dict[str, str]
    thresholds: dict
    diagnostic: dict = field(default_factory=lambda: {"min_confidence": 0.8, "use_borderline": False, "min_correct_answers": 2})
    intervention: dict = field(default_factory=lambda: {"struggle_after": None})
    support: dict = field(default_factory=dict)       # adaptive support policy (engine/support.py)

    def topic(self, topic_id: str) -> Optional[Topic]:
        return next((t for t in self.topics if t.id == topic_id), None)

    def name(self, concept: str) -> str:
        return self.concepts.get(concept, concept.replace("_", " ").title())


def load_catalog(projects_root: Path = PROJECTS_ROOT) -> Catalog:
    data = yaml.safe_load((Path(projects_root) / "catalog.yaml").read_text())
    topics = [Topic(t["id"], t["title"], t["project"], list(t["concepts"]), bool(t.get("themeable")),
                    [dict(c) for c in t.get("choices") or []])
              for t in data["topics"]]
    diagnostic = {"min_confidence": 0.8, "use_borderline": False, "min_correct_answers": 2}
    diagnostic.update(data.get("diagnostic") or {})
    intervention = {"struggle_after": None}
    intervention.update(data.get("intervention") or {})
    return Catalog(dict(data["concepts"]), topics, dict(data.get("revision") or {}), dict(data["thresholds"]),
                   diagnostic, intervention, dict(data.get("support") or {}))


def translate_problem(source: Project, target: Project, problem_id: Optional[str]) -> Optional[str]:
    """The same place in another project with the same structure: a level keeps its id; a practice problem
    becomes the target's practice for the same concept and stage."""
    if not problem_id:
        return problem_id
    if target.manifest.has_problem(problem_id) and target.manifest.practice(problem_id) is None:
        return problem_id
    practice = source.manifest.practice(problem_id) if source.manifest.has_problem(problem_id) else None
    if practice is not None:
        match = next((p for p in target.manifest.practice_problems
                      if p.concept == practice.concept and p.target_stage == practice.target_stage), None)
        if match is not None:
            return match.id
    return problem_id if target.manifest.has_problem(problem_id) else None


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
                      support=SupportPolicy.from_dict(self.catalog.support),
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

    def request_hint(self, student_id: str, submission_path=None) -> SubmitOutcome:
        """Next hint for the current problem, on request. Changes no stage, so no profile update."""
        self._require(student_id)
        return self.engine(student_id).request_hint(student_id, submission_path)

    def _after(self, student_id: str, engine: Engine, outcome: SubmitOutcome) -> SubmitOutcome:
        record, _ = engine.open(student_id)
        profile = self.store.profile(student_id)
        concepts = dict(profile.get("concepts") or {})
        for cid, state in record.concepts.items():
            concepts[cid] = max(int(concepts.get(cid, 0)), state.stage)
        profile["concepts"] = concepts
        if outcome.passed and outcome.complete and outcome.status != "complete":
            recommendation = self._recommend(engine.project, record, profile)
            self._continue_pathway(profile, engine.project, recommendation)
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
        project = self._project(result.project_path)
        when = self.theme_target(student_id)
        if when == "later":
            # On a review (or another step) first: the themed project waits for the pathway's core step.
            self._set_core(student_id, str(project.root))
            return {"message": f"{result.message}. You'll start it after your current project.", "project": project.id,
                    "state": self.state(student_id), "built": True}
        if self.store.profile(student_id).get("pathway") or self.catalog.topics[0].choices:
            self._set_core(student_id, str(project.root))
        out = self._switch(student_id, project, result.message)
        out["built"] = True
        return out

    def reset_theme(self, student_id: str) -> dict:
        """Back to a ready-made project: the student's catalog choice (or the goal's suggestion)."""
        self._require(student_id)
        profile = self.store.profile(student_id)
        if profile.get("core_project") and profile["core_project"] not in self.core_choices():
            profile.pop("core_project")
            self.store.save_profile(student_id, profile)
        folder = self.core_project_for(student_id)
        self._set_core(student_id, folder, keep_choice=False)
        if self._is_core(self.project_for(student_id)):
            self.store.set_active_project(student_id, str(self._project(self.projects_root / folder).root))
        return self.state(student_id)

    def _is_core(self, project: Project) -> bool:
        return project.topic == self.catalog.topics[0].id

    def _set_core(self, student_id: str, folder: str, keep_choice: bool = True) -> None:
        """Make `folder` (a catalog choice, or a themed project's path) the student's first-topic project,
        including the pathway steps that haven't been reached yet."""
        profile = self.store.profile(student_id)
        if keep_choice:
            profile["core_project"] = folder
        pathway = profile.get("pathway")
        if pathway:
            new_title = self._project(self.projects_root / folder).title
            for i, step in enumerate(pathway.get("steps") or []):
                if i < pathway.get("current", 0):
                    continue
                if self._is_core(self._project(self.projects_root / step["project"])):
                    old_title = step["title"]
                    step["project"], step["title"] = folder, new_title
                    if old_title != new_title and old_title in (pathway.get("student_message") or ""):
                        pathway["student_message"] = pathway["student_message"].replace(old_title, new_title)
        self.store.save_profile(student_id, profile)

    def theme_target(self, student_id: str) -> Optional[str]:
        """When a theme the student builds would be used: "now" (they're on the first topic and haven't
        finished it), "later" (a pathway step on the first topic is still ahead), or None."""
        try:
            record, _ = self.engine(student_id).open(student_id)
        except Exception:
            return None
        if self._is_core(self.project_for(student_id)):
            return "now"
        pathway = self.store.profile(student_id).get("pathway") or {}
        steps = pathway.get("steps") or []
        for step in steps[pathway.get("current", 0):]:
            if self._is_core(self._project(self.projects_root / step["project"])):
                return "later"
        return None

    # Project choice: same skills, different stories (catalog topics[0].choices) ---------------
    def core_choices(self) -> List[str]:
        topic = self.catalog.topics[0]
        folders = [c["project"] for c in topic.choices if (self.projects_root / c["project"]).is_dir()]
        return folders or [topic.project]

    def _goal(self, student_id: str) -> Optional[str]:
        from diagnostic.store import DiagnosticStore
        try:
            state = DiagnosticStore(self.data_dir).load(student_id)
        except Exception:
            return None
        return state.goal_id if state is not None else None

    def _interests(self, student_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """(goal id, goal label, the student's own screened words) from the readiness check or an import."""
        from diagnostic.store import DiagnosticStore
        try:
            state = DiagnosticStore(self.data_dir).load(student_id)
        except Exception:
            return None, None, None
        if state is None:
            return None, None, None
        goal = self.diagnostic().content.goals.get(state.goal_id)
        return state.goal_id, goal.label if goal else None, state.goal_text

    def _story_match(self, student_id: str):
        from .matching import match_story
        goal, label, words = self._interests(student_id)
        available = [c for c in self.catalog.topics[0].choices if c["project"] in self.core_choices()]
        return match_story(available, goal, label, words, self.catalog.topics[0].project)

    def suggested_project(self, student_id: str) -> str:
        """The ready-made story that best fits the student's interests (engine/matching.py)."""
        if not self._goal(student_id):
            return self.catalog.topics[0].project
        return self._story_match(student_id).project

    def project_match(self, student_id: str) -> Optional[dict]:
        """Why the suggested project fits this student: their interests (the story) and what the readiness
        check is confident about (where they start). None for students who skipped the check."""
        from .matching import match_view, skill_fit
        if not self._goal(student_id):
            return None
        story = self._story_match(student_id)
        profile = self.store.profile(student_id)
        decisions = (profile.get("diagnostic") or {}).get("decisions")
        skills = None
        if decisions is not None:
            # Warm-ups are the planned practice problems; the student sees their concepts, not problem ids.
            project = self._project(self.projects_root / self.core_project_for(student_id))
            planned = [project.manifest.practice(p) for p in (profile.get("planned_practice") or {}).get("problems") or []
                       if project.manifest.has_problem(p)]
            skills = skill_fit(decisions, self.catalog.concepts, {p.concept for p in planned if p is not None})
        title = self._project(self.projects_root / story.project).title
        pitch = next((c.get("pitch", "") for c in self.catalog.topics[0].choices if c["project"] == story.project), "")
        return match_view(story, skills, title, pitch)

    def core_project_for(self, student_id: str) -> str:
        """The student's first-topic project: their choice, a theme they built, or the story that fits their interests."""
        chosen = self.store.profile(student_id).get("core_project") if student_id else None
        if chosen in self.core_choices():
            return chosen
        if chosen and Path(chosen).is_absolute() and (Path(chosen) / "manifest.yaml").is_file():
            return chosen
        return self.suggested_project(student_id)

    def _core_started(self, student_id: str, folder: str) -> bool:
        try:
            record = self.store.load(student_id, self._project(self.projects_root / folder).id)
        except Exception:
            return False
        return record is not None and bool(record.attempts or record.passed_problems)

    def project_choices(self, student_id: str) -> dict:
        self._require(student_id)
        current = self.core_project_for(student_id)
        # Only a readiness check (or an import) suggests a project; students who skipped it get no "best match" tag.
        suggested = self.suggested_project(student_id) if self._goal(student_id) else None
        out = []
        if current not in self.core_choices():         # a theme the student built
            project = self._project(self.projects_root / current)
            out.append({"project": "custom", "title": project.title, "pitch": "Your own theme, built by your AI guide.",
                        "suggested": False, "current": True, "custom": True})
        for choice in self.catalog.topics[0].choices:
            folder = choice["project"]
            if folder not in self.core_choices():
                continue
            project = self._project(self.projects_root / folder)
            out.append({"project": folder, "title": project.title, "pitch": choice.get("pitch", ""),
                        "suggested": folder == suggested, "current": folder == current, "custom": False})
        return {"choices": out, "locked": self._core_started(student_id, current),
                "topic": self.catalog.topics[0].title, "match": self.project_match(student_id)}

    def choose_project(self, student_id: str, folder: str) -> dict:
        """Pick which story to learn the first topic's skills in. Allowed until that project is started."""
        self._require(student_id)
        current = self.core_project_for(student_id)
        if folder == "custom" and current not in self.core_choices():
            return self.state(student_id)               # already on their own theme
        if folder not in self.core_choices():
            raise CourseError("Pick one of the projects in the list.")
        if folder != current and self._core_started(student_id, current):
            title = self._project(self.projects_root / current).title
            raise CourseError(f"You've already started {title}. Finish it first.")
        self._set_core(student_id, folder)
        profile = self.store.profile(student_id)
        pathway = profile.get("pathway")
        if (profile.get("diagnostic") or {}).get("applied"):
            profile["diagnostic"]["applied"] = False        # place the student again, in the chosen project
            self.store.save_profile(student_id, profile)
        self.events.write("choose_project", student_id=student_id, project_id=folder, selected=folder)
        on_core = self._is_core(self.project_for(student_id))
        if on_core:
            self.store.set_active_project(student_id, str(self._project(self.projects_root / folder).root))
        if (profile.get("diagnostic") or {}).get("decisions") is not None:
            self.apply_diagnostic(student_id)
            if pathway:
                steps = pathway.get("steps") or []
                step = steps[pathway.get("current", 0)] if pathway.get("current", 0) < len(steps) else None
                if step and step["project"] == folder:
                    self._start_step(student_id, step)
        elif on_core:
            project = self._project(self.projects_root / folder)
            self._switch(student_id, project, f"Starting {project.title}.")
        return self.state(student_id)

    # Lesson pathway (Strands Decider 2B, engine/decider.py) -----------------------------------
    # After the readiness check, the decider picks a pathway: rules decide which ones the student can get,
    # Bedrock picks one using the evidence, grade and CSTA standards, and the rules' pick is the fallback.
    def _readiness(self, student_id: str) -> Dict[str, "Readiness"]:
        from diagnostic.store import DiagnosticStore
        from .decider import Readiness
        state = DiagnosticStore(self.data_dir).load(student_id)
        if state is None or not state.placement:
            raise CourseError("Finish the readiness check first.")
        decisions = (self.store.profile(student_id).get("diagnostic") or {}).get("decisions") or {}
        tree = self.diagnostic().content.tree
        out: Dict[str, Readiness] = {}
        counts = state.answer_counts()
        for concept, est in state.placement.get("concepts", {}).items():
            answers = [r for r in state.results if r.concept == concept]
            times = sorted(r.elapsed_ms / 1000 for r in answers if r.elapsed_ms)
            count = counts.get(concept) or {"correct": 0, "answered": 0}
            d = decisions.get(concept) or {}
            codes: List[str] = []
            for node in tree.nodes.values():
                if node.concept == concept:
                    codes += [c for c in node.csta if c not in codes]
            out[concept] = Readiness(
                concept=concept, name=self.catalog.name(concept), stage=int(est.get("stage", 0)),
                confident_stage=int(d["stage"]) if d.get("used") else None,
                confidence=float(est.get("confidence", 0.0)), borderline=bool(est.get("borderline")),
                correct=count["correct"], answered=count["answered"],
                misconceptions=list(est.get("misconceptions") or []),
                median_seconds=round(times[len(times) // 2], 1) if times else None, standards=codes)
        return out

    def decide_pathway(self, student_id: str, grade: int) -> dict:
        """Pick and start the student's pathway. Safe to call again: the first decision is kept."""
        from .curriculum import CurriculumError, load_curriculum
        from .decider import GRADES, StrandsDecider, load_pathways
        self._require(student_id)
        if grade not in GRADES:
            raise CourseError(f"Pick a grade from {GRADES[0]} to {GRADES[-1]}.")
        profile = self.store.profile(student_id)
        if profile.get("pathway"):
            return profile["pathway"]
        if not (profile.get("diagnostic") or {}).get("applied"):
            self.apply_diagnostic(student_id)
            profile = self.store.profile(student_id)
        readiness = self._readiness(student_id)
        try:
            curriculum = load_curriculum()
        except CurriculumError:
            curriculum = None
        from diagnostic.store import DiagnosticStore
        state = DiagnosticStore(self.data_dir).load(student_id)
        goal = self.diagnostic().content.goals.get(state.goal_id) if state.goal_id else None
        pathways = load_pathways(self.projects_root / "catalog.yaml")
        weakest = (state.placement.get("focus_order") or list(readiness))[0]

        def resolve(pathway) -> List[dict]:
            out = []
            for step in pathway.steps:
                folder = (self.catalog.revision.get(weakest) if step.project == "revision"
                          else self.core_project_for(student_id) if step.project in self.core_choices() else step.project)
                if folder and (self.projects_root / folder).is_dir():
                    out.append({"project": folder, "title": self._project(self.projects_root / folder).title,
                                "start": step.start})
            return out

        decider = StrandsDecider(pathways, self.provider, curriculum)
        decision = decider.decide(readiness, grade, goal.label if goal else "",
                                  {p.id: [s["title"] for s in resolve(p)] for p in pathways})
        steps = resolve(decision.pathway)
        standards = [s.brief() for s in curriculum.lookup(decision.standards)] if curriculum else \
            [{"id": c, "skill": c, "must_do": "", "skill_area": ""} for c in decision.standards]
        record = {
            "id": decision.pathway.id, "title": decision.pathway.title, "summary": decision.pathway.summary,
            "stance": decision.stance, "student_message": decision.student_message,
            "teacher_note": decision.teacher_note, "standards": standards, "steps": steps, "current": 0,
            "grade": grade, "decided_by": decision.decided_by, "model_id": decision.model_id,
            "latency_ms": decision.latency_ms, "fallback_reason": decision.fallback_reason,
            "eligible": decision.eligible, "rules_pick": decision.rules_pick, "notes": decision.notes,
            "decider": "Strands Decider 2B",
            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
        profile["grade"] = grade
        profile["pathway"] = record
        self.store.save_profile(student_id, profile)
        self.events.write("pathway", student_id=student_id, selected=decision.pathway.id, reason=decision.stance,
                          source=decision.decided_by, model_id=decision.model_id or None,
                          latency_ms=decision.latency_ms or None, category="strands_decider_2b")
        if decision.fallback_reason and self.provider is not None:
            self.events.write("fallback", student_id=student_id, selected=decision.pathway.id,
                              reason=f"pathway decider: {decision.fallback_reason}"[:300], category="strands_decider_2b")
        if steps:
            self._start_step(student_id, steps[0])
        return record

    def _start_step(self, student_id: str, step: dict) -> None:
        project = self._project(self.projects_root / step["project"])
        if not self._is_core(project) or project.root.name not in self.core_choices():
            self._switch(student_id, project, f"Starting {project.title}.")     # reviews, later topics, own themes
            return
        self.store.set_active_project(student_id, str(project.root))
        start = step.get("start")
        if start in (None, "readiness") or not project.manifest.has_problem(start):
            return      # the readiness check's placement (apply_diagnostic) already set the first problem
        engine = self.engine(student_id, project)
        try:
            record = self.store.load(student_id, project.id)
        except Exception:
            return      # unreadable progress: leave it to the engine's own recovery
        if record is not None and (record.attempts or record.passed_problems):
            return      # never move a lesson the student has already started
        record = record or engine._fresh_record(student_id)
        record.current_problem, record.origin_level, record.return_to = start, None, None
        record.routing_log.append({"selected": start, "reason": "pathway_start", "policy": "pathway",
                                   "stages": record.stages(),
                                   "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
        self.store.save(record)
        self.store.set_active_project(student_id, str(project.root))

    def _continue_pathway(self, profile: dict, finished: Project, recommendation: "Recommendation") -> None:
        """When a pathway project is finished, offer the pathway's next project first.
        A review the course recommends after a struggle still comes first."""
        pathway = profile.get("pathway")
        if not pathway:
            return
        steps = pathway.get("steps") or []
        i = pathway.get("current", 0)
        if i < len(steps) and Path(steps[i]["project"]).name == finished.root.name:
            pathway["current"] = i = i + 1
        if i >= len(steps):
            return
        folder = steps[i]["project"]
        option = Option(REVISION if folder in self.catalog.revision.values() else NEXT_TOPIC,
                        f"Next on your pathway: {steps[i]['title']}", folder)
        rest = [o for o in recommendation.options if o.project != folder and o.kind != ALL_DONE]
        if recommendation.kind == REVISION and rest:
            recommendation.options = [rest[0], option] + rest[1:]
        else:
            if not recommendation.options or recommendation.options[0].project != folder:
                recommendation.reason = f"Nice work! Next on your pathway ({pathway['title']}): {steps[i]['title']}."
            recommendation.options = [option] + rest
            recommendation.kind = option.kind

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
            self._name_first_stop(step, self.apply_diagnostic(student_id), student_id)
        return step

    def _name_first_stop(self, result: dict, summary: dict, student_id: str) -> None:
        """The quest names a Weather Station problem; say the one the student will really open."""
        placed = summary.get("start_problem")
        stop = result.get("next_stop")
        if placed and isinstance(stop, dict):
            project = self._project(self.projects_root / self.core_project_for(student_id))
            if project.manifest.has_problem(placed):
                stop["activity"] = {"id": placed, "title": project.problem(placed).title}
                stop["project"] = project.title
            if project.root != self.default_project().root:
                # The quest's own sentence is about Weather Station; describe the student's project instead.
                pitch = next((c.get("pitch", "") for c in self.catalog.topics[0].choices
                              if c["project"] == project.root.name), "")
                result["goal_connection"] = f"Your project: {project.title}. {pitch}".strip()
        result["match"] = self.project_match(student_id)

    def import_previous(self, data: Optional[dict] = None, sample: Optional[str] = None) -> dict:
        """Skip the readiness check with an earlier lesson's results (a file's JSON, or a sample student's id).
        Creates the student, applies the result like a finished check, and returns the closing screen
        (with "student_id", "notices" and the project match). Raises diagnostic.importer.ImportRejected."""
        diagnostic = self.diagnostic()
        result = diagnostic.import_previous(diagnostic.load_sample(sample) if sample is not None else data)
        student_id = result["student_id"]
        profile = self.store.profile(student_id)
        profile.update(active_project=str(self.default_project().root), concepts={}, completed=[], next_step=None)
        self.store.save_profile(student_id, profile)
        self._name_first_stop(result, self.apply_diagnostic(student_id), student_id)
        return result

    def import_samples(self) -> List[dict]:
        return self.diagnostic().import_samples()

    def diagnostic_answer(self, student_id: str, response, elapsed_ms: Optional[int] = None) -> dict:
        return self.diagnostic().answer(student_id, response, elapsed_ms)

    def diagnostic_finish(self, student_id: str) -> dict:
        """End the quest early or on time, then apply its result."""
        result = self.diagnostic().finish(student_id)
        self._name_first_stop(result, self.apply_diagnostic(student_id), student_id)
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

        correct = {c: n["correct"] for c, n in state.answer_counts().items()}
        decisions = seed_from_placement(state.placement, self.catalog.diagnostic, correct)
        concepts = dict(profile.get("concepts") or {})
        for concept, d in decisions.items():
            if d["used"]:
                concepts[concept] = max(int(concepts.get(concept, 0)), d["stage"])
        profile["concepts"] = concepts

        project = self._project(self.projects_root / self.core_project_for(student_id))
        # Plan a practice problem before the level of every concept the diagnostic is confident is a gap.
        planned = []
        for concept, d in decisions.items():
            if d["used"] and d["stage"] == 0:
                practice = next((p for p in project.manifest.practice_problems
                                 if p.concept == concept and p.target_stage == 1), None)
                if practice is not None:
                    planned.append(practice.id)
        profile["planned_practice"] = {"project": project.id, "problems": planned}
        # The readiness check places students in Weather Station's problems; other choices share its structure.
        start = translate_problem(self.default_project(), project, state.placement.get("route", {}).get("next_task_id"))
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
        profile["core_project"] = project.root.name
        if not profile.get("active_project") or Path(profile["active_project"]).name in self.core_choices():
            profile["active_project"] = str(project.root)
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
