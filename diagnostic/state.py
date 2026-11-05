"""The saved state of one student's quest. Plain data, JSON round-trippable."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .models import ItemResult

# What the student is being asked right now
KIND_ITEM, KIND_EXPLAIN, KIND_BOOSTER = "item", "explain", "booster"

PLAYING, COMPLETE = "playing", "complete"

# Explain-it records
EXPLAIN_ANSWERED, EXPLAIN_SKIPPED, EXPLAIN_FLAGGED = "answered", "skipped", "flagged"

SCHEMA_VERSION = 1


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


@dataclass
class Pending:
    kind: str
    id: str
    role: str = "first"

    def to_dict(self) -> dict:
        return {"kind": self.kind, "id": self.id, "role": self.role}

    @classmethod
    def from_dict(cls, data: dict) -> "Pending":
        return cls(kind=str(data["kind"]), id=str(data["id"]), role=str(data.get("role", "first")))


@dataclass
class ExplainRecord:
    """What the student told the guide for one zone, and how it was read."""
    concept: str
    status: str
    text: Optional[str] = None
    flags: List[str] = field(default_factory=list)
    stage: Optional[int] = None              # from the reader (model or keyword rules); None if unscorable
    confidence: float = 0.0
    rationale: str = ""
    quotes: List[str] = field(default_factory=list)
    keyword_stage: Optional[int] = None
    model_id: str = ""
    fallback: bool = False

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict) -> "ExplainRecord":
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class DiagnosticState:
    student_id: str
    quest_id: str
    goal_id: str
    buddy: Optional[str] = None
    goal_text: Optional[str] = None
    results: List[ItemResult] = field(default_factory=list)
    boosters_served: List[str] = field(default_factory=list)
    explain: Dict[str, ExplainRecord] = field(default_factory=dict)
    served: List[str] = field(default_factory=list)
    pending: Optional[Pending] = None
    consecutive_misses: int = 0
    streak: int = 0
    best_streak: int = 0
    xp: int = 0
    badges: List[str] = field(default_factory=list)
    zones_done: List[str] = field(default_factory=list)
    phase: str = PLAYING
    on_fallback: bool = False
    fallback_reason: Optional[str] = None
    fixed_queue: Optional[List[str]] = None
    placement: Optional[Dict[str, Any]] = None
    started_at: str = field(default_factory=now_iso)
    finished_at: Optional[str] = None
    elapsed_ms_total: int = 0
    # Set when the result came from an earlier lesson instead of this quest (diagnostic/importer.py):
    # {"source", "at", "concepts": {concept: {"stage", "correct", "answered"}}}. Results is then empty.
    imported: Optional[Dict[str, Any]] = None
    schema_version: int = SCHEMA_VERSION

    def answer_counts(self) -> Dict[str, Dict[str, int]]:
        """{concept: {"correct", "answered"}} from this quest's answers, or from the imported lesson."""
        if self.imported:
            return {c: {"correct": int(v.get("correct", 0)), "answered": int(v.get("answered", 0))}
                    for c, v in (self.imported.get("concepts") or {}).items()}
        counts: Dict[str, Dict[str, int]] = {}
        for r in self.results:
            entry = counts.setdefault(r.concept, {"correct": 0, "answered": 0})
            entry["answered"] += 1
            entry["correct"] += int(r.passed)
        return counts

    def to_dict(self) -> dict:
        data = dict(self.__dict__)
        data["results"] = [r.to_dict() for r in self.results]
        data["explain"] = {c: e.to_dict() for c, e in self.explain.items()}
        data["pending"] = self.pending.to_dict() if self.pending else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "DiagnosticState":
        required = ("student_id", "quest_id", "goal_id", "results", "served", "phase")
        missing = [name for name in required if name not in data]
        if missing:
            raise ValueError(f"diagnostic record is missing {', '.join(missing)}")
        if data.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ValueError(f"unsupported diagnostic record version {data.get('schema_version')!r}")
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        known["results"] = [ItemResult.from_dict(r) for r in data["results"]]
        known["explain"] = {c: ExplainRecord.from_dict(e) for c, e in data.get("explain", {}).items()}
        known["pending"] = Pending.from_dict(data["pending"]) if data.get("pending") else None
        return cls(**known)
