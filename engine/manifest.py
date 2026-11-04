"""Parse, validate, and print a project's manifest.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

DEFAULT_STREAK_LENGTH = 3
MIN_STREAK_LENGTH = 1
MAX_STREAK_LENGTH = 10
STAGES = (1, 2, 3)
PROBLEM_FORMATS = ("code", "quiz")
REQUIRED_FIELDS = ("title", "concepts", "levels", "stage_criteria", "fallback_path")
DEFAULT_DATASET = {"generator": "dataset/generate.py", "database": "dataset/data.db"}


class ManifestError(ValueError):
    """Raised when a manifest can't be parsed. `errors` lists every problem found."""

    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class ConceptDef:
    id: str
    name: str


@dataclass(frozen=True)
class StageCriterion:
    max_attempts: Optional[int] = None
    max_hints: Optional[int] = None

    def is_met(self, attempts: int, hints_used: int) -> bool:
        if self.max_attempts is not None and attempts > self.max_attempts:
            return False
        if self.max_hints is not None and hints_used > self.max_hints:
            return False
        return True


@dataclass(frozen=True)
class LevelDef:
    id: str
    number: int
    title: str
    folder: str
    concepts: List[str]
    advance_at_stage: Optional[int] = None
    loop_check: Optional[str] = None
    format: str = "code"        # "code" (graded by checks.py) or "quiz" (questions.yaml)


@dataclass(frozen=True)
class PracticeDef:
    id: str
    title: str
    folder: str
    concept: str
    target_stage: int
    loop_check: Optional[str] = None


@dataclass
class Manifest:
    title: str
    concepts: List[ConceptDef]
    stage_criteria: Dict[int, StageCriterion]
    levels: List[LevelDef]
    fallback_path: List[str]
    streak_length: int = DEFAULT_STREAK_LENGTH
    practice_problems: List[PracticeDef] = field(default_factory=list)
    dataset: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_DATASET))
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Lookups -------------------------------------------------------------
    def concept_ids(self) -> List[str]:
        return [c.id for c in self.concepts]

    def level(self, problem_id: str) -> Optional[LevelDef]:
        for level in self.levels:
            if level.id == problem_id:
                return level
        return None

    def practice(self, problem_id: str) -> Optional[PracticeDef]:
        for practice in self.practice_problems:
            if practice.id == problem_id:
                return practice
        return None

    def has_problem(self, problem_id: str) -> bool:
        return self.level(problem_id) is not None or self.practice(problem_id) is not None

    def levels_in_order(self) -> List[LevelDef]:
        return sorted(self.levels, key=lambda lvl: lvl.number)

    def next_level(self, level_id: str) -> Optional[LevelDef]:
        ordered = self.levels_in_order()
        for index, level in enumerate(ordered):
            if level.id == level_id:
                return ordered[index + 1] if index + 1 < len(ordered) else None
        return None


# Parsing -----------------------------------------------------------------

def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _opt_int(value: Any, where: str, errors: List[str], low: int = 0, high: Optional[int] = None) -> Optional[int]:
    if value is None:
        return None
    if not _is_int(value) or value < low or (high is not None and value > high):
        bound = f"{low} to {high}" if high is not None else f"{low} or more"
        errors.append(f"{where}: expected a whole number from {bound} or null, got {value!r}")
        return None
    return value


def _text(value: Any, where: str, errors: List[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where}: expected non-empty text, got {value!r}")
        return ""
    return value


def parse_manifest(text: str) -> Manifest:
    try:
        data = yaml.safe_load(text)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        line = mark.line + 1 if mark is not None else "unknown"
        raise ManifestError([f"YAML syntax error at line {line}: {exc.problem or exc}"]) from None
    except yaml.YAMLError as exc:
        raise ManifestError([f"YAML syntax error: {exc}"]) from None

    if not isinstance(data, dict):
        raise ManifestError(["manifest must be a YAML mapping of fields"])

    missing = [name for name in REQUIRED_FIELDS if data.get(name) in (None, "", [], {})]
    if isinstance(data.get("title"), str) and not data["title"].strip() and "title" not in missing:
        missing.append("title")
    if missing:
        raise ManifestError([f"missing or empty required field(s): {', '.join(missing)}"])

    errors: List[str] = []
    title = _text(data["title"], "title", errors)

    # Streak length
    streak_length = data.get("streak_length", DEFAULT_STREAK_LENGTH)
    if streak_length is None:
        streak_length = DEFAULT_STREAK_LENGTH
    if not _is_int(streak_length) or not MIN_STREAK_LENGTH <= streak_length <= MAX_STREAK_LENGTH:
        errors.append(
            f"streak_length: expected a whole number from {MIN_STREAK_LENGTH} to {MAX_STREAK_LENGTH}, got {streak_length!r}"
        )
        streak_length = DEFAULT_STREAK_LENGTH

    # Concepts
    concepts: List[ConceptDef] = []
    if not isinstance(data["concepts"], list):
        errors.append("concepts: expected a list")
    else:
        for index, item in enumerate(data["concepts"]):
            where = f"concepts[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{where}: expected a mapping with id and name")
                continue
            concepts.append(ConceptDef(_text(item.get("id"), f"{where}.id", errors),
                                       _text(item.get("name"), f"{where}.name", errors)))
    concept_ids = [c.id for c in concepts]
    for cid in sorted({c for c in concept_ids if concept_ids.count(c) > 1}):
        errors.append(f"concepts: duplicate concept id {cid!r}")

    # Stage criteria
    criteria: Dict[int, StageCriterion] = {}
    raw_criteria = data["stage_criteria"]
    if not isinstance(raw_criteria, dict):
        errors.append("stage_criteria: expected a mapping of stage number to criteria")
    else:
        for key, item in raw_criteria.items():
            where = f"stage_criteria[{key!r}]"
            if not _is_int(key) or key not in STAGES:
                errors.append(f"{where}: stage must be 1, 2, or 3")
                continue
            if item is None:
                item = {}
            if not isinstance(item, dict):
                errors.append(f"{where}: expected a mapping with max_attempts and max_hints")
                continue
            criteria[key] = StageCriterion(
                max_attempts=_opt_int(item.get("max_attempts"), f"{where}.max_attempts", errors, low=1),
                max_hints=_opt_int(item.get("max_hints"), f"{where}.max_hints", errors, low=0),
            )

    # Levels
    levels: List[LevelDef] = []
    if not isinstance(data["levels"], list):
        errors.append("levels: expected a list")
    else:
        for index, item in enumerate(data["levels"]):
            where = f"levels[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{where}: expected a mapping")
                continue
            level_id = _text(item.get("id"), f"{where}.id", errors)
            where = f"level {level_id or index}"
            number = item.get("number")
            if not _is_int(number) or number < 1:
                errors.append(f"{where}.number: expected a whole number of 1 or more, got {number!r}")
                number = 0
            level_concepts = item.get("concepts")
            if not isinstance(level_concepts, list) or not level_concepts:
                errors.append(f"{where}.concepts: expected a non-empty list of concept ids")
                level_concepts = []
            for cid in level_concepts:
                if cid not in concept_ids:
                    errors.append(f"{where}.concepts: concept {cid!r} is not declared in concepts")
            loop_check = item.get("loop_check")
            if loop_check is not None:
                loop_check = _text(loop_check, f"{where}.loop_check", errors)
            problem_format = item.get("format", "code") or "code"
            if problem_format not in PROBLEM_FORMATS:
                errors.append(f"{where}.format: expected one of {', '.join(PROBLEM_FORMATS)}, got {problem_format!r}")
                problem_format = "code"
            if problem_format == "quiz" and loop_check is not None:
                errors.append(f"{where}: a quiz level can't have a loop_check")
            levels.append(LevelDef(
                id=level_id,
                number=number,
                title=_text(item.get("title"), f"{where}.title", errors),
                folder=_text(item.get("folder"), f"{where}.folder", errors),
                concepts=list(level_concepts),
                advance_at_stage=_opt_int(item.get("advance_at_stage"), f"{where}.advance_at_stage", errors, low=1, high=3),
                loop_check=loop_check,
                format=problem_format,
            ))

    # Practice problems
    practice: List[PracticeDef] = []
    raw_practice = data.get("practice_problems") or []
    if not isinstance(raw_practice, list):
        errors.append("practice_problems: expected a list")
        raw_practice = []
    for index, item in enumerate(raw_practice):
        where = f"practice_problems[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: expected a mapping")
            continue
        pid = _text(item.get("id"), f"{where}.id", errors)
        where = f"practice problem {pid or index}"
        concept = item.get("concept")
        if concept not in concept_ids:
            errors.append(f"{where}.concept: concept {concept!r} is not declared in concepts")
        target = item.get("target_stage")
        if not _is_int(target) or target not in STAGES:
            errors.append(f"{where}.target_stage: expected 1, 2, or 3, got {target!r}")
            target = 1
        loop_check = item.get("loop_check")
        if loop_check is not None:
            loop_check = _text(loop_check, f"{where}.loop_check", errors)
        practice.append(PracticeDef(
            id=pid,
            title=_text(item.get("title"), f"{where}.title", errors),
            folder=_text(item.get("folder"), f"{where}.folder", errors),
            concept=concept if isinstance(concept, str) else "",
            target_stage=target,
            loop_check=loop_check,
        ))

    all_ids = [lvl.id for lvl in levels] + [p.id for p in practice]
    for pid in sorted({p for p in all_ids if p and all_ids.count(p) > 1}):
        errors.append(f"problem id {pid!r} is used more than once")
    numbers = [lvl.number for lvl in levels if lvl.number]
    for number in sorted({n for n in numbers if numbers.count(n) > 1}):
        errors.append(f"level number {number} is used more than once")

    # Fallback path
    fallback = data["fallback_path"]
    if not isinstance(fallback, list):
        errors.append("fallback_path: expected a list of level ids")
        fallback = []
    level_ids = [lvl.id for lvl in levels]
    for lid in fallback:
        if lid not in level_ids:
            errors.append(f"fallback_path: {lid!r} is not a declared level")
    for lid in level_ids:
        if lid and lid not in fallback:
            errors.append(f"fallback_path: declared level {lid!r} is missing")
    for lid in sorted({x for x in fallback if isinstance(x, str) and fallback.count(x) > 1}):
        errors.append(f"fallback_path: level {lid!r} appears more than once")

    # Dataset and parameters
    dataset = data.get("dataset") or dict(DEFAULT_DATASET)
    if not isinstance(dataset, dict) or not all(isinstance(dataset.get(k), str) for k in ("generator", "database")):
        errors.append("dataset: expected a mapping with generator and database paths")
        dataset = dict(DEFAULT_DATASET)
    parameters = data.get("parameters") or {}
    if not isinstance(parameters, dict):
        errors.append("parameters: expected a mapping")
        parameters = {}

    if errors:
        raise ManifestError(errors)

    return Manifest(
        title=title,
        concepts=concepts,
        stage_criteria=criteria,
        levels=levels,
        fallback_path=list(fallback),
        streak_length=streak_length,
        practice_problems=practice,
        dataset={"generator": dataset["generator"], "database": dataset["database"]},
        parameters=parameters,
    )


# Printing ----------------------------------------------------------------

def manifest_to_dict(manifest: Manifest) -> Dict[str, Any]:
    return {
        "title": manifest.title,
        "streak_length": manifest.streak_length,
        "concepts": [{"id": c.id, "name": c.name} for c in manifest.concepts],
        "stage_criteria": {
            stage: {"max_attempts": c.max_attempts, "max_hints": c.max_hints}
            for stage, c in sorted(manifest.stage_criteria.items())
        },
        "levels": [
            {
                "id": lvl.id,
                "number": lvl.number,
                "title": lvl.title,
                "folder": lvl.folder,
                "concepts": list(lvl.concepts),
                "advance_at_stage": lvl.advance_at_stage,
                "loop_check": lvl.loop_check,
                "format": lvl.format,
            }
            for lvl in manifest.levels
        ],
        "practice_problems": [
            {
                "id": p.id,
                "title": p.title,
                "folder": p.folder,
                "concept": p.concept,
                "target_stage": p.target_stage,
                "loop_check": p.loop_check,
            }
            for p in manifest.practice_problems
        ],
        "fallback_path": list(manifest.fallback_path),
        "dataset": dict(manifest.dataset),
        "parameters": manifest.parameters,
    }


def print_manifest(manifest: Manifest) -> str:
    return yaml.safe_dump(manifest_to_dict(manifest), sort_keys=False, allow_unicode=True)
