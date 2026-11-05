"""Start from an earlier lesson's results instead of taking the readiness check.

A teacher (or a demo) brings a small JSON export from a previous lesson: a stage per concept, how many
questions backed it, and optionally the student's goal and interests. It becomes a finished readiness
record, so everything downstream (seeding, placement, project match, pathway) works exactly as after a
quest. The same trust rules apply: a stage is used only if the evidence behind it is strong enough
(projects/catalog.yaml `diagnostic`), so a thin export starts the student at the beginning.

Privacy and safety:
- Only the fields below are read. A file with personal details (a name, email, birthday...) is rejected
  with a message saying which field, so the person exporting can remove it. Any other unknown field is
  ignored and never stored. Any id in the file is ignored: the student gets a new random STU- id.
- Free text (`interests`, `source`) is screened like the quest's own goal text: personal details,
  filtered words or instructions to the AI mean it is dropped, with a notice.
- Nothing from the file is written to the event log except the stages.

Format (codeai-lesson-export, version 1):
    {"format": "codeai-lesson-export", "version": 1,
     "source": "Intro unit, fall",                 optional, at most 80 characters
     "goal": "build_game",                         optional, a readiness-check goal id
     "interests": "soccer and video games",        optional, at most 80 characters
     "concepts": {"loops": {"stage": 2, "correct": 5, "answered": 6}, ...}}
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import yaml

from .content import Content
from .models import CONCEPTUAL, MAX_STAGE, ConceptEstimate, NodePoints
from .safety import clean_goal_text

FORMAT, VERSION = "codeai-lesson-export", 1
FIELDS = {"format", "version", "source", "goal", "interests", "concepts"}
CONCEPT_FIELDS = {"stage", "correct", "answered"}
# Keys that hold personal details. A file with any of them is rejected, never silently cleaned.
PERSONAL_KEYS = {"name", "first_name", "last_name", "full_name", "student_name", "nickname", "email", "e_mail",
                 "phone", "address", "birthday", "birth_date", "date_of_birth", "dob", "age", "school", "teacher",
                 "parent", "guardian", "gender", "ethnicity", "photo", "ssn"}
ID_KEYS = {"id", "student_id", "user_id", "sis_id", "login"}
MAX_TEXT_CHARS = 80
MAX_ANSWERED = 100
SAMPLES_FOLDER = "samples"
SAMPLE_INDEX = "samples.yaml"
_SAMPLE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


class ImportRejected(ValueError):
    """The file can't be used. `problems` lists every reason, in plain words."""

    def __init__(self, problems: List[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class ImportRecord:
    concepts: Dict[str, Dict[str, int]]          # concept -> {stage, correct, answered}
    goal_id: Optional[str]
    interests: Optional[str]
    source: Optional[str]
    notices: List[str] = field(default_factory=list)


def _key(name: Any) -> str:
    return re.sub(r"[^a-z]+", "_", str(name).lower()).strip("_")


def _whole(value: Any, low: int, high: int) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high else None


def parse_export(data: Any, content: Content) -> ImportRecord:
    """Check an export and keep only what the course uses. Raises ImportRejected."""
    if not isinstance(data, dict):
        raise ImportRejected(["The file must be one JSON object, like the sample files."])
    personal = sorted({str(k) for k in data if _key(k) in PERSONAL_KEYS})
    concepts_raw = data.get("concepts")
    if isinstance(concepts_raw, dict):
        for entry in concepts_raw.values():
            if isinstance(entry, dict):
                personal += sorted({str(k) for k in entry if _key(k) in PERSONAL_KEYS} - set(personal))
    if personal:
        raise ImportRejected([f"The file has personal details ({', '.join(personal)}). Remove them and try again. "
                              "We only need results per idea."])
    problems: List[str] = []
    notices: List[str] = []
    if data.get("format") != FORMAT or data.get("version") != VERSION:
        problems.append(f'This isn\'t a lesson results file. It needs "format": "{FORMAT}" and "version": {VERSION}.')
    ignored = sorted(str(k) for k in data if k not in FIELDS and _key(k) not in ID_KEYS)
    if any(_key(k) in ID_KEYS for k in data):
        notices.append("The id in the file wasn't used. You get a new private id.")
    if ignored:
        notices.append("These fields aren't used and weren't kept: " + ", ".join(ignored[:6]) + ".")

    known = content.concepts()
    concepts: Dict[str, Dict[str, int]] = {}
    if not isinstance(concepts_raw, dict) or not concepts_raw:
        problems.append("The file needs a \"concepts\" object with at least one idea.")
    else:
        unknown = sorted(str(c) for c in concepts_raw if c not in known)
        if unknown:
            notices.append("These ideas aren't part of this course and weren't used: " + ", ".join(unknown[:6]) + ".")
        for concept in known:
            entry = concepts_raw.get(concept)
            if entry is None:
                continue
            if not isinstance(entry, dict):
                problems.append(f"{concept} must be an object with stage, correct and answered.")
                continue
            stage = _whole(entry.get("stage"), 0, MAX_STAGE)
            answered = _whole(entry.get("answered", 0), 0, MAX_ANSWERED)
            correct = _whole(entry.get("correct", 0), 0, MAX_ANSWERED)
            if stage is None:
                problems.append(f"{concept}: stage must be a whole number from 0 to {MAX_STAGE}.")
            if answered is None or correct is None:
                problems.append(f"{concept}: correct and answered must be whole numbers from 0 to {MAX_ANSWERED}.")
            elif correct > answered:
                problems.append(f"{concept}: correct can't be more than answered.")
            if stage is not None and answered is not None and correct is not None and correct <= answered:
                concepts[concept] = {"stage": stage, "correct": correct, "answered": answered}
            extra = sorted(set(entry) - CONCEPT_FIELDS)
            if extra:
                notices.append(f"{concept}: these fields weren't kept: {', '.join(str(e) for e in extra[:4])}.")
        if not concepts and not problems:
            problems.append("None of the ideas in the file are part of this course.")

    goal = data.get("goal")
    if goal is not None and goal not in content.goals:
        notices.append("The goal in the file isn't one of ours, so you can pick a project yourself.")
        goal = None

    def text(name: str) -> Optional[str]:
        value = data.get(name)
        if value is None:
            return None
        if not isinstance(value, str):
            problems.append(f"{name} must be text.")
            return None
        cleaned, _ = clean_goal_text(value, MAX_TEXT_CHARS)
        if value.strip() and cleaned is None:
            notices.append(f"We didn't keep the {name} text: it had personal details or words we filter out.")
        return cleaned

    interests, source = text("interests"), text("source")
    if problems:
        raise ImportRejected(problems)
    return ImportRecord(concepts, goal, interests, source, notices)


# Turning imported results into the readiness check's own evidence ---------------------------------------

def imported_confidence(stage: int, correct: int, answered: int) -> float:
    """How sure the course should be of an imported stage. More questions behind it means more sure;
    a stage the answers contradict (e.g. stage 2 on mostly wrong answers) is capped low."""
    confidence = min(0.95, 0.5 + 0.1 * answered)
    if answered and ((stage >= 2 and correct / answered < 0.5) or (stage == 0 and correct / answered >= 0.75)):
        confidence = min(confidence, 0.6)
    return round(confidence, 3)


def imported_estimates(content: Content, imported: Mapping[str, Any]) -> Dict[str, ConceptEstimate]:
    rows = imported.get("concepts") or {}
    borderline_below = content.config.scoring.borderline_below
    out: Dict[str, ConceptEstimate] = {}
    for concept in content.concepts():
        row = rows.get(concept)
        if row is None:     # no evidence: the course treats it as unknown and starts at the beginning
            out[concept] = ConceptEstimate(concept, 0, 0.25, True, 0, ())
            continue
        confidence = imported_confidence(row["stage"], row["correct"], row["answered"])
        out[concept] = ConceptEstimate(concept, row["stage"], confidence, confidence < borderline_below,
                                       row["answered"], ())
    return out


def imported_points(content: Content, imported: Mapping[str, Any]) -> Dict[str, NodePoints]:
    """Skill-tree points: a node at or below the imported stage is earned, the ones above it are not."""
    rows = imported.get("concepts") or {}
    points: Dict[str, NodePoints] = {}
    for node in content.tree.nodes.values():
        row = rows.get(node.concept)
        if row is None or not row.get("answered"):
            continue
        pts = NodePoints()
        pts.possible[CONCEPTUAL] = 1.0
        pts.earned[CONCEPTUAL] = 1.0 if node.tier <= row["stage"] else 0.0
        pts.evidence = 1
        points[node.id] = pts
    return points


# Sample files for demos ---------------------------------------------------------------------------------

def _samples_dir(content_root: Path) -> Path:
    return Path(content_root) / SAMPLES_FOLDER


def list_samples(content_root: Path) -> List[Dict[str, str]]:
    """[{id, label, about}] from <project>/diagnostic/samples/samples.yaml. Synthetic students only."""
    index = _samples_dir(content_root) / SAMPLE_INDEX
    if not index.is_file():
        return []
    rows = yaml.safe_load(index.read_text(encoding="utf-8")) or []
    return [{"id": str(r["id"]), "label": str(r["label"]), "about": str(r.get("about", ""))}
            for r in rows if isinstance(r, dict) and _SAMPLE_ID.match(str(r.get("id", "")))]


def load_sample(content_root: Path, sample_id: str) -> Dict[str, Any]:
    if not isinstance(sample_id, str) or not _SAMPLE_ID.match(sample_id) or \
            sample_id not in {s["id"] for s in list_samples(content_root)}:
        raise ImportRejected(["Pick one of the sample students in the list."])
    return json.loads((_samples_dir(content_root) / f"{sample_id}.json").read_text(encoding="utf-8"))
