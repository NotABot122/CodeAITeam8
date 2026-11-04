"""Validate what a model returned. Anything that does not fit is rejected, never guessed.

The model's claims are checked before they are trusted:
  - stage must be a whole number 0-3, confidence a number (clamped to 0-1);
  - evidence quotes must really appear in the student's own words;
  - the concept list must be complete and use only known concepts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..textmatch import quote_in_text
from .prompts import escape
from .tools import STANCES

MAX_RATIONALE_CHARS = 300
MAX_QUOTES = 5
MAX_QUOTE_CHARS = 200


@dataclass(frozen=True)
class Reading:
    stage: int
    confidence: float
    rationale: str
    quotes: Tuple[str, ...]


@dataclass
class Advice:
    reads: Dict[str, Reading]
    focus_order: List[str]
    stance: Optional[str]
    goal_connection: str = ""
    student_message: str = ""
    teacher_note: str = ""


def _stage(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and 0 <= value <= 3:
        return value
    return None


def _confidence(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(min(max(float(value), 0.0), 1.0), 3)


def verified_quotes(raw_quotes: Any, text: str) -> Tuple[str, ...]:
    """Keep only quotes that appear in the student's text. Drops the rest silently."""
    if not isinstance(raw_quotes, list) or not text:
        return ()
    kept: List[str] = []
    escaped = escape(text)
    for quote in raw_quotes:
        if not isinstance(quote, str):
            continue
        quote = quote.strip()[:MAX_QUOTE_CHARS]
        if quote and (quote_in_text(quote, text) or quote_in_text(quote, escaped)) and quote not in kept:
            kept.append(quote)
    return tuple(kept[:MAX_QUOTES])


def parse_reading(raw: Any, text: str) -> Optional[Reading]:
    """One stage reading, or None when the model's answer is unusable."""
    if not isinstance(raw, dict):
        return None
    stage = _stage(raw.get("stage"))
    confidence = _confidence(raw.get("confidence"))
    if stage is None or confidence is None:
        return None
    rationale = raw.get("rationale")
    rationale = " ".join(rationale.split())[:MAX_RATIONALE_CHARS] if isinstance(rationale, str) else ""
    return Reading(stage, confidence, rationale, verified_quotes(raw.get("evidence_quotes"), text))


def parse_advice(raw: Any, concepts: Sequence[str], texts: Mapping[str, str]) -> Optional[Advice]:
    """The placement advice, or None when it is incomplete or malformed."""
    if not isinstance(raw, dict) or not isinstance(raw.get("concepts"), list):
        return None
    reads: Dict[str, Reading] = {}
    for entry in raw["concepts"]:
        if not isinstance(entry, dict):
            return None
        concept = entry.get("concept")
        if concept not in concepts or concept in reads:
            return None
        reading = parse_reading(entry, texts.get(concept, ""))
        if reading is None:
            return None
        reads[concept] = reading
    if set(reads) != set(concepts):
        return None

    focus: List[str] = []
    for concept in raw.get("focus_order") or []:
        if concept in concepts and concept not in focus:
            focus.append(concept)
    focus += [c for c in concepts if c not in focus]

    stance = raw.get("stance") if raw.get("stance") in STANCES else None

    def text_field(name: str) -> str:
        value = raw.get(name)
        return " ".join(value.split()) if isinstance(value, str) else ""

    return Advice(reads, focus, stance, text_field("goal_connection"), text_field("student_message"),
                  text_field("teacher_note"))
