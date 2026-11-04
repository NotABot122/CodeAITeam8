"""Student progress records and where they are saved."""
from __future__ import annotations

import json
import os
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .stages import ConceptState

FIELDS = ("student_id", "project_id", "concepts", "current_problem", "origin_level", "attempts",
          "hints_seen", "passed_problems", "on_fallback", "complete", "routing_log")


class ProgressLoadError(Exception):
    pass


@dataclass
class ProgressRecord:
    student_id: str
    project_id: str
    concepts: Dict[str, ConceptState]
    current_problem: Optional[str]
    origin_level: Optional[str] = None
    attempts: Dict[str, int] = field(default_factory=dict)
    hints_seen: Dict[str, int] = field(default_factory=dict)
    passed_problems: List[str] = field(default_factory=list)
    on_fallback: bool = False
    complete: bool = False
    routing_log: List[dict] = field(default_factory=list)

    def stages(self) -> Dict[str, int]:
        return {cid: state.stage for cid, state in self.concepts.items()}

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "project_id": self.project_id,
            "concepts": {cid: state.to_dict() for cid, state in self.concepts.items()},
            "current_problem": self.current_problem,
            "origin_level": self.origin_level,
            "attempts": dict(self.attempts),
            "hints_seen": dict(self.hints_seen),
            "passed_problems": list(self.passed_problems),
            "on_fallback": self.on_fallback,
            "complete": self.complete,
            "routing_log": list(self.routing_log),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProgressRecord":
        missing = [name for name in FIELDS if name not in data]
        if missing:
            raise ValueError(f"progress record is missing {', '.join(missing)}")
        return cls(
            student_id=data["student_id"],
            project_id=data["project_id"],
            concepts={cid: ConceptState.from_dict(s) for cid, s in data["concepts"].items()},
            current_problem=data["current_problem"],
            origin_level=data["origin_level"],
            attempts={k: int(v) for k, v in data["attempts"].items()},
            hints_seen={k: int(v) for k, v in data["hints_seen"].items()},
            passed_problems=list(data["passed_problems"]),
            on_fallback=bool(data["on_fallback"]),
            complete=bool(data["complete"]),
            routing_log=list(data["routing_log"]),
        )


class ProgressStore(ABC):
    """Swap this for an Aurora-backed store without touching the engine."""

    @abstractmethod
    def load(self, student_id: str, project_id: str) -> Optional[ProgressRecord]:
        """Return the record, None if there isn't one, or raise ProgressLoadError."""

    @abstractmethod
    def save(self, record: ProgressRecord) -> None:
        ...

    @abstractmethod
    def student_exists(self, student_id: str) -> bool:
        ...

    @abstractmethod
    def register_student(self, student_id: str) -> None:
        ...

    @abstractmethod
    def quarantine(self, student_id: str, project_id: str) -> None:
        """Keep an unreadable record aside so it isn't overwritten."""


class JsonProgressStore(ProgressStore):
    """One JSON file per student and project, under root/progress/."""

    def __init__(self, root):
        self.root = Path(root) / "progress"

    def _path(self, student_id: str, project_id: str) -> Path:
        return self.root / student_id / f"{project_id}.json"

    def student_exists(self, student_id: str) -> bool:
        return (self.root / student_id).exists()

    def register_student(self, student_id: str) -> None:
        (self.root / student_id).mkdir(parents=True, exist_ok=False)

    def load(self, student_id: str, project_id: str) -> Optional[ProgressRecord]:
        path = self._path(student_id, project_id)
        if not path.exists():
            return None
        try:
            return ProgressRecord.from_dict(json.loads(path.read_text()))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ProgressLoadError(str(exc)) from None

    def save(self, record: ProgressRecord) -> None:
        path = self._path(record.student_id, record.project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".progress-", suffix=".json")
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(record.to_dict(), handle, indent=2)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def quarantine(self, student_id: str, project_id: str) -> None:
        path = self._path(student_id, project_id)
        if path.exists():
            path.rename(path.with_name(f"{project_id}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}.json"))
