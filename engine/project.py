"""Load a project folder into a Project definition."""
from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .manifest import Manifest, ManifestError, parse_manifest
from .quiz import QuizError, validate_questions

# A project's data can live in its own dataset/ folder or be shared from another project
# (manifest dataset paths such as ../weather-station/dataset/...). The generator check below covers both.
REQUIRED_ITEMS = ("manifest.yaml", "levels", "reference")
PROBLEM_FILES = ("instructions.md", "hints.yaml", "checks.py")
QUIZ_FILES = ("instructions.md", "hints.yaml", "questions.yaml")
REFERENCE_SOLUTION = "reference/solution.py"
INDEPENDENT_CHECKER = "reference/independent_checker.py"
EXPECTED_REPORTS = "reference/expected_reports.json"


class ProjectLoadError(Exception):
    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass
class Problem:
    id: str
    kind: str                  # "level" or "practice"
    title: str
    folder: Path
    concepts: List[str]
    instructions: str
    hints: List[str]
    checks_path: Path
    number: Optional[int] = None
    advance_at_stage: Optional[int] = None
    target_stage: Optional[int] = None
    loop_check: Optional[str] = None
    format: str = "code"
    questions: List[dict] = field(default_factory=list)

    @property
    def is_quiz(self) -> bool:
        return self.format == "quiz"

    @property
    def label(self) -> str:
        """Prefix used in feedback messages."""
        return f"Level {self.number}" if self.kind == "level" else self.title


@dataclass
class Project:
    id: str
    root: Path
    manifest: Manifest
    problems: Dict[str, Problem] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.manifest.title

    @property
    def topic(self) -> str:
        """Catalog topic id, from manifest parameters (themed projects inherit data-logic)."""
        return self.manifest.parameters.get("topic", "data-logic")

    @property
    def database_path(self) -> Path:
        return self.root / self.manifest.dataset["database"]

    @property
    def generator_path(self) -> Path:
        return self.root / self.manifest.dataset["generator"]

    @property
    def reference_path(self) -> Path:
        return self.root / REFERENCE_SOLUTION

    @property
    def independent_checker_path(self) -> Path:
        return self.root / INDEPENDENT_CHECKER

    @property
    def expected_reports_path(self) -> Path:
        return self.root / EXPECTED_REPORTS

    @property
    def starter_path(self) -> Path:
        return self.root / "starter.py"

    def problem(self, problem_id: str) -> Problem:
        return self.problems[problem_id]

    def first_level(self) -> Problem:
        return self.problems[self.manifest.fallback_path[0]]

    def ensure_dataset(self) -> Path:
        """Build the database with the project's generator if it doesn't exist yet."""
        if not self.database_path.exists():
            generator = load_module(self.generator_path, f"_dataset_{self.id.replace('-', '_')}")
            generator.generate(self.database_path)
        return self.database_path

    def read_expected_reports(self) -> dict:
        if not self.expected_reports_path.exists():
            return {"seed": None, "teacher_reviewed": False, "reports": []}
        return json.loads(self.expected_reports_path.read_text())


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_hints(path: Path, label: str, errors: List[str]) -> List[str]:
    try:
        hints = yaml.safe_load(path.read_text()) or []
    except yaml.YAMLError as exc:
        errors.append(f"{label}: hints.yaml could not be read: {exc}")
        return []
    if not isinstance(hints, list) or not all(isinstance(h, str) and h.strip() for h in hints):
        errors.append(f"{label}: hints.yaml must be a list of hint text")
        return []
    return [h.strip() for h in hints]


def load_project(path) -> Project:
    """Load a project, or raise ProjectLoadError listing every problem found."""
    root = Path(path).resolve()
    if not root.is_dir():
        raise ProjectLoadError([f"project folder not found: {root}"])

    missing = [item for item in REQUIRED_ITEMS if not (root / item).exists()]
    if missing:
        raise ProjectLoadError([f"project folder is missing: {', '.join(missing)}"])

    try:
        manifest = parse_manifest((root / "manifest.yaml").read_text())
    except ManifestError as exc:
        raise ProjectLoadError([f"manifest.yaml: {e}" for e in exc.errors]) from None

    errors: List[str] = []
    problems: Dict[str, Problem] = {}

    entries = [("level", lvl) for lvl in manifest.levels] + [("practice", p) for p in manifest.practice_problems]
    for kind, entry in entries:
        folder = root / entry.folder
        label = f"{'Level' if kind == 'level' else 'practice problem'} {entry.id}"
        if not folder.is_dir():
            errors.append(f"{label}: folder {entry.folder} does not exist")
            continue
        problem_format = getattr(entry, "format", "code")
        needed = QUIZ_FILES if problem_format == "quiz" else PROBLEM_FILES
        absent = [name for name in needed if not (folder / name).is_file()]
        if absent:
            errors.append(f"{label}: folder {entry.folder} is missing {', '.join(absent)}")
            continue
        hints = _read_hints(folder / "hints.yaml", label, errors)
        questions: List[dict] = []
        if problem_format == "quiz":
            try:
                questions = validate_questions(yaml.safe_load((folder / "questions.yaml").read_text()), label)
            except (QuizError, yaml.YAMLError) as exc:
                errors.append(str(exc))
                continue
        problems[entry.id] = Problem(
            id=entry.id,
            kind=kind,
            title=entry.title,
            folder=folder,
            concepts=list(entry.concepts) if kind == "level" else [entry.concept],
            instructions=(folder / "instructions.md").read_text(),
            hints=hints,
            checks_path=folder / "checks.py",
            number=entry.number if kind == "level" else None,
            advance_at_stage=entry.advance_at_stage if kind == "level" else None,
            target_stage=entry.target_stage if kind == "practice" else None,
            loop_check=entry.loop_check,
            format=problem_format,
            questions=questions,
        )

    if not (root / REFERENCE_SOLUTION).is_file():
        errors.append(f"reference folder is missing {Path(REFERENCE_SOLUTION).name}")
    if not (root / manifest.dataset["generator"]).is_file():
        errors.append(f"dataset generator not found: {manifest.dataset['generator']}")

    if errors:
        raise ProjectLoadError(errors)

    return Project(id=root.name, root=root, manifest=manifest, problems=problems)
