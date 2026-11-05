"""Plain data types shared across the diagnostic. No behavior beyond small helpers."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Item types ---------------------------------------------------------------
CHOICE = "choice"          # tap one option
SPOT = "spot"              # tap the step that is wrong (a choice over steps)
TRACE = "trace"            # follow a routine and tap what it makes (a choice over results)
ORDER = "order"            # drag cards into the right order
SORT = "sort"              # drag cards into buckets
CHOICE_LIKE = (CHOICE, SPOT, TRACE)
ITEM_TYPES = CHOICE_LIKE + (ORDER, SORT)
# How a sort item is drawn. The answer model is the same: every card goes in one bucket.
DISPLAYS = ("rows", "belt", "chips")   # tap table rows | sorting belt | word chips into boxes

# How a question shows code. Code never goes inside the prompt sentence: it goes in `code` (a block,
# shown under the prompt) or `table` (rows of data). Short names inside sentences use `backticks`.
CODE_LANGS = ("python", "sql")
OPTION_FORMATS = ("text", "code")      # code: every option or card is drawn in the code font
DEFAULT_OPTION_FORMAT = {CHOICE: "text", SORT: "text", SPOT: "code", TRACE: "code", ORDER: "code"}

# The point vector from the project spec (P_node). Every item feeds one facet.
CONCEPTUAL, SYNTAX, PROBLEM_SOLVING = "conceptual", "syntax", "problem_solving"
FACETS = (CONCEPTUAL, SYNTAX, PROBLEM_SOLVING)
DEFAULT_FACET = {CHOICE: CONCEPTUAL, SORT: CONCEPTUAL, SPOT: SYNTAX, TRACE: PROBLEM_SOLVING, ORDER: PROBLEM_SOLVING}

TIERS = (1, 2, 3)          # tier N is the evidence for Stage N
MAX_STAGE = 3

# Skill tree node status (project spec section 4.2)
LOCKED, AVAILABLE, MASTERED = "LOCKED", "AVAILABLE", "MASTERED"

# Roles an item can play in a concept's ladder
ROLE_FIRST, ROLE_TWIN, ROLE_BONUS = "first", "twin", "bonus"


class InvalidResponse(ValueError):
    """The student's answer does not fit the question (wrong shape or unknown ids)."""


@dataclass(frozen=True)
class Option:
    id: str
    text: str
    misconception: Optional[str] = None   # what a student who picks this likely thinks
    why: Optional[str] = None             # one kind sentence shown after a wrong pick


@dataclass(frozen=True)
class Card:
    id: str
    text: str
    misconception: Optional[str] = None   # sort items: the idea behind putting this card in the wrong bucket


@dataclass(frozen=True)
class Bucket:
    id: str
    text: str


@dataclass(frozen=True)
class Table:
    columns: Tuple[str, ...]
    rows: Tuple[Tuple[str, ...], ...]

    def public(self) -> Dict[str, Any]:
        return {"columns": list(self.columns), "rows": [list(r) for r in self.rows]}


@dataclass(frozen=True)
class Item:
    id: str
    concept: Optional[str]          # None for boosters
    tier: int                       # 0 for boosters
    type: str
    prompt: str
    nodes: Tuple[str, ...]          # first is the primary node; the rest are supporting nodes
    facet: str
    options: Tuple[Option, ...] = ()
    cards: Tuple[Card, ...] = ()
    buckets: Tuple[Bucket, ...] = ()
    answer: Any = None              # option id | [card ids in order] | {card id: bucket id}
    misconception: Optional[str] = None   # for order/sort items answered wrongly
    feedback_right: Optional[str] = None
    feedback_wrong: Optional[str] = None
    pass_credit: float = 1.0
    display: Optional[str] = None   # sort items only: a game skin; never changes how it is scored
    code: Optional[str] = None      # a code block shown under the prompt
    code_lang: str = "python"
    table: Optional[Table] = None   # rows of data shown under the prompt
    option_format: str = "text"

    @property
    def guess_chance(self) -> float:
        """Chance of passing by guessing alone. Used to judge how much a pass proves."""
        if self.type in CHOICE_LIKE:
            return 1.0 / max(len(self.options), 1)
        if self.type == ORDER:
            return 1.0 / math.factorial(max(len(self.cards), 1))
        buckets = max(len(self.buckets), 1)
        # Chance of getting at least ceil(pass_credit * n) cards right by guessing.
        n = len(self.cards)
        need = math.ceil(self.pass_credit * n - 1e-9)
        p = 1.0 / buckets
        return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(need, n + 1))

    def public(self, rng: random.Random) -> Dict[str, Any]:
        """What the student's screen needs. Never includes the answer or misconception tags."""
        payload: Dict[str, Any] = {"id": self.id, "type": self.type, "prompt": self.prompt,
                                   "option_format": self.option_format}
        if self.code:
            payload["code"] = {"lang": self.code_lang, "text": self.code}
        if self.table is not None:
            payload["table"] = self.table.public()
        if self.type in CHOICE_LIKE:
            options = [{"id": o.id, "text": o.text} for o in self.options]
            if self.type != SPOT:       # a spot item's options are the lines of one program, in order
                rng.shuffle(options)
            payload["options"] = options
        else:
            cards = [{"id": c.id, "text": c.text} for c in self.cards]
            shuffled = list(cards)
            rng.shuffle(shuffled)
            if self.type == ORDER and len(cards) > 1:
                correct = [c for c in self.answer]
                for _ in range(10):  # never present the cards already solved
                    if [c["id"] for c in shuffled] != correct:
                        break
                    rng.shuffle(shuffled)
            payload["cards"] = shuffled
            if self.type == SORT:
                payload["buckets"] = [{"id": b.id, "text": b.text} for b in self.buckets]
                if self.display:
                    payload["display"] = self.display
        return payload


@dataclass(frozen=True)
class KeyIdea:
    id: str
    level: int                       # 1-3: how sophisticated the idea is
    words: Tuple[str, ...]           # any one of these (whole word or phrase) shows the idea
    label: str


@dataclass(frozen=True)
class ExplainPrompt:
    id: str
    concept: str
    nodes: Tuple[str, ...]
    prompt: str
    key_ideas: Tuple[KeyIdea, ...]


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    concept: str
    tier: int
    parents: Tuple[str, ...] = ()
    csta: Tuple[str, ...] = ()       # verified standard codes; empty until checked against the workbook


@dataclass(frozen=True)
class Goal:
    id: str
    label: str
    emphasis: Dict[str, float]       # concept id -> weight 0..1 (how much this goal needs the concept)


@dataclass(frozen=True)
class Zone:
    id: str
    concept: str
    name: str
    story: str
    done_message: str


@dataclass
class NodePoints:
    """Earned and possible points per facet for one node (the spec's P_node)."""
    earned: Dict[str, float] = field(default_factory=lambda: {f: 0.0 for f in FACETS})
    possible: Dict[str, float] = field(default_factory=lambda: {f: 0.0 for f in FACETS})
    evidence: int = 0

    @property
    def ratio(self) -> Optional[float]:
        total = sum(self.possible.values())
        return None if total == 0 else sum(self.earned.values()) / total


@dataclass(frozen=True)
class NodeState:
    status: str
    ratio: Optional[float]
    evidence: int
    facets: Dict[str, Optional[float]]


@dataclass
class ItemResult:
    """One scored answer. Serializable."""
    item_id: str
    concept: str
    tier: int
    role: str
    credit: float
    passed: bool
    guess_chance: float
    misconception: Optional[str] = None
    elapsed_ms: Optional[int] = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict) -> "ItemResult":
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass(frozen=True)
class ScoringRules:
    """Parameters of the guess-and-slip stage estimate (diagnostic.yaml `scoring`)."""
    slip: float                        # chance a student who knows the idea still misses a question
    prior: Tuple[float, ...]           # chance of true stage 0, 1, 2, 3 before any answers
    borderline_below: float            # confidence under this marks a concept as borderline


@dataclass(frozen=True)
class ConceptEstimate:
    concept: str
    stage: int
    confidence: float
    borderline: bool
    items_seen: int
    misconceptions: Tuple[str, ...] = ()


def tier_counts(results: List[ItemResult]) -> Dict[int, Tuple[int, int]]:
    """tier -> (passes, fails)."""
    counts: Dict[int, List[int]] = {t: [0, 0] for t in TIERS}
    for r in results:
        counts.setdefault(r.tier, [0, 0])[0 if r.passed else 1] += 1
    return {t: (p, f) for t, (p, f) in counts.items()}
