"""Load and validate a project's diagnostic content (config, skill tree, item bank).

The loader reports every problem it finds in one pass, like engine.manifest does,
so an author can fix a whole file without re-running it for each mistake.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from .models import (CODE_LANGS, DEFAULT_OPTION_FORMAT, DISPLAYS, CHOICE, CHOICE_LIKE, DEFAULT_FACET, FACETS, ITEM_TYPES,
                     OPTION_FORMATS, ORDER, SORT, SPOT, TIERS, Bucket, Card, ExplainPrompt, Goal, Item, KeyIdea, Node, Option,
                     ScoringRules, Table, Zone)
from .paths import PathLike, content_dir
from .readability import readability_problems
from .safety import authored_text_problem
from .tree import SkillTree

CONFIG_FILE = "diagnostic.yaml"
TREE_FILE = "tree.yaml"
BOOSTERS_FILE = "boosters.yaml"
ITEMS_FOLDER = "items"
MIN_ITEMS_PER_TIER = 2          # a first question and a twin
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Code blocks and tables must fit a phone screen without sideways scrolling.
MAX_CODE_LINES = 12
MAX_CODE_LINE_CHARS = 60
MAX_TABLE_COLUMNS = 6
MAX_TABLE_ROWS = 8
# A prompt that reads like code belongs in `code`, not in the sentence. Checked after removing `backtick`
# spans: an assignment or comparison between names, a block header (if/for/while/def ... :), or a SQL clause.
_BACKTICKS = re.compile(r"`[^`]*`")
_CODE_IN_PROMPT = re.compile(r"\b[a-z_][a-z0-9_]*\s*(=|\+=|>=|<=|==)\s*\S"
                             r"|\b(if|for|while|def)\b[^.?]*:(\s|$)"
                             r"|\b(SELECT|WHERE|FROM)\b\s+\S")


def _code_in_sentence(prompt: str) -> bool:
    return bool(_CODE_IN_PROMPT.search(_BACKTICKS.sub("", prompt)))


class ContentError(ValueError):
    """Raised when content can't be loaded. `errors` lists every problem found."""

    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


# Config -------------------------------------------------------------------

@dataclass(frozen=True)
class Limits:
    max_scored_items: int
    max_items_per_zone: int
    max_bonus_items: int
    bonus_min_stage: int
    bonus_confidence_target: float
    max_explain_prompts: int
    explain_below_confidence: float
    max_boosters: int
    misses_before_booster: int
    seconds_per_item: int
    seconds_per_explain: int
    target_minutes: int


@dataclass(frozen=True)
class Thresholds:
    unlock: float
    master: float


@dataclass(frozen=True)
class ReadingRules:
    max_sentence_words: int
    max_word_length: int


@dataclass(frozen=True)
class TextRules:
    min_words: int
    max_chars: int
    max_goal_chars: int


@dataclass(frozen=True)
class Config:
    id: str
    title: str
    grade_band: str
    version: int
    limits: Limits
    pass_credit: Dict[str, float]
    thresholds: Thresholds
    scoring: ScoringRules
    reading: ReadingRules
    text: TextRules
    game: Dict[str, Any]
    banned_student_words: Tuple[str, ...]
    buddies: Tuple[Tuple[str, str], ...]


@dataclass
class Content:
    config: Config
    tree: SkillTree
    zones: List[Zone]
    goals: Dict[str, Goal]
    items: Dict[str, Item]
    boosters: List[Item]
    explain: Dict[str, ExplainPrompt]
    notices: List[str] = field(default_factory=list)

    def concepts(self) -> List[str]:
        return [z.concept for z in self.zones]

    def zone_for(self, concept: str) -> Zone:
        return next(z for z in self.zones if z.concept == concept)

    def items_for(self, concept: str, tier: int) -> List[Item]:
        return [i for i in self.items.values() if i.concept == concept and i.tier == tier]

    def default_goal(self) -> Goal:
        return self.goals.get("not_sure") or next(iter(self.goals.values()))

    def explain_for(self, concept: str) -> Optional[ExplainPrompt]:
        return self.explain.get(concept)


# Small validation helpers --------------------------------------------------

def _card_text(value: Any, where: str, errors: "_Errors") -> str:
    """Card text keeps its leading spaces: an order card can be an indented line of code."""
    return value.rstrip() if errors.text(value, where, "text") else ""


class _Errors:
    def __init__(self) -> None:
        self.items: List[str] = []

    def add(self, where: str, message: str) -> None:
        self.items.append(f"{where}: {message}")

    def text(self, value: Any, where: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            self.add(where, f"{field_name} must be non-empty text")
            return ""
        return value.strip()

    def number(self, value: Any, where: str, field_name: str, low: float, high: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            self.add(where, f"{field_name} must be a number from {low} to {high}, got {value!r}")
            return float(low)
        return float(value)

    def whole(self, value: Any, where: str, field_name: str, low: int, high: int = 10 ** 6) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            self.add(where, f"{field_name} must be a whole number from {low} to {high}, got {value!r}")
            return low
        return value

    def ident(self, value: Any, where: str) -> str:
        if not isinstance(value, str) or not ID_PATTERN.match(value):
            self.add(where, f"id must be lowercase letters, digits, - or _, got {value!r}")
            return str(value)
        return value


def _read_yaml(path: Path, errors: _Errors) -> Any:
    if not path.is_file():
        errors.add(path.name, "file not found")
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        errors.add(path.name, f"YAML could not be read: {exc}")
        return None


def _mapping(value: Any, where: str, errors: _Errors) -> Dict[str, Any]:
    if not isinstance(value, dict):
        errors.add(where, "expected a mapping")
        return {}
    return value


def _sequence(value: Any, where: str, errors: _Errors) -> List[Any]:
    if not isinstance(value, list):
        errors.add(where, "expected a list")
        return []
    return value


# Config parsing -------------------------------------------------------------

def _parse_config(data: Any, errors: _Errors) -> Optional[Config]:
    where = CONFIG_FILE
    root = _mapping(data, where, errors)
    if not root:
        return None
    lim = _mapping(root.get("limits"), f"{where} limits", errors)
    lw = f"{where} limits"
    limits = Limits(
        max_scored_items=errors.whole(lim.get("max_scored_items"), lw, "max_scored_items", 4, 60),
        max_items_per_zone=errors.whole(lim.get("max_items_per_zone"), lw, "max_items_per_zone", 2, 12),
        max_bonus_items=errors.whole(lim.get("max_bonus_items"), lw, "max_bonus_items", 0, 10),
        bonus_min_stage=errors.whole(lim.get("bonus_min_stage"), lw, "bonus_min_stage", 1, 3),
        bonus_confidence_target=errors.number(lim.get("bonus_confidence_target"), lw, "bonus_confidence_target", 0, 1),
        max_explain_prompts=errors.whole(lim.get("max_explain_prompts"), lw, "max_explain_prompts", 0, 10),
        explain_below_confidence=errors.number(lim.get("explain_below_confidence"), lw, "explain_below_confidence", 0, 1),
        max_boosters=errors.whole(lim.get("max_boosters"), lw, "max_boosters", 0, 10),
        misses_before_booster=errors.whole(lim.get("misses_before_booster"), lw, "misses_before_booster", 1, 20),
        seconds_per_item=errors.whole(lim.get("seconds_per_item"), lw, "seconds_per_item", 1, 600),
        seconds_per_explain=errors.whole(lim.get("seconds_per_explain"), lw, "seconds_per_explain", 1, 900),
        target_minutes=errors.whole(lim.get("target_minutes"), lw, "target_minutes", 1, 120),
    )

    pc = _mapping(root.get("pass_credit"), f"{where} pass_credit", errors)
    pass_credit: Dict[str, float] = {}
    for item_type in ITEM_TYPES:
        if item_type not in pc:
            errors.add(f"{where} pass_credit", f"missing a value for {item_type!r}")
            continue
        pass_credit[item_type] = errors.number(pc[item_type], f"{where} pass_credit", item_type, 0.5, 1.0)

    th = _mapping(root.get("thresholds"), f"{where} thresholds", errors)
    thresholds = Thresholds(
        unlock=errors.number(th.get("unlock"), f"{where} thresholds", "unlock", 0.05, 1.0),
        master=errors.number(th.get("master"), f"{where} thresholds", "master", 0.05, 1.0),
    )
    if thresholds.unlock > thresholds.master:
        errors.add(f"{where} thresholds", "unlock must not be higher than master")

    sc = _mapping(root.get("scoring"), f"{where} scoring", errors)
    prior_raw = _sequence(sc.get("prior"), f"{where} scoring prior", errors)
    prior = tuple(errors.number(p, f"{where} scoring", "prior value", 0.01, 1.0) for p in prior_raw)
    if len(prior) != 4 or abs(sum(prior) - 1.0) > 1e-6:
        errors.add(f"{where} scoring", "prior needs four numbers that add up to 1")
        prior = (0.25, 0.25, 0.25, 0.25)
    scoring = ScoringRules(
        slip=errors.number(sc.get("slip"), f"{where} scoring", "slip", 0.0, 0.4),
        prior=prior,
        borderline_below=errors.number(sc.get("borderline_below"), f"{where} scoring", "borderline_below", 0.0, 1.0),
    )

    rd = _mapping(root.get("readability"), f"{where} readability", errors)
    reading = ReadingRules(
        max_sentence_words=errors.whole(rd.get("max_sentence_words"), f"{where} readability", "max_sentence_words", 4, 60),
        max_word_length=errors.whole(rd.get("max_word_length"), f"{where} readability", "max_word_length", 4, 40),
    )

    tx = _mapping(root.get("text"), f"{where} text", errors)
    text = TextRules(
        min_words=errors.whole(tx.get("min_words"), f"{where} text", "min_words", 1, 20),
        max_chars=errors.whole(tx.get("max_chars"), f"{where} text", "max_chars", 20, 4000),
        max_goal_chars=errors.whole(tx.get("max_goal_chars"), f"{where} text", "max_goal_chars", 10, 400),
    )

    game = _mapping(root.get("game"), f"{where} game", errors)
    _check_game(game, errors)

    banned = tuple(str(w).lower() for w in _sequence(root.get("student_text_ban"), f"{where} student_text_ban", errors))

    buddies: List[Tuple[str, str]] = []
    for index, entry in enumerate(_sequence(root.get("buddies"), f"{where} buddies", errors), start=1):
        entry = _mapping(entry, f"{where} buddy #{index}", errors)
        buddies.append((errors.ident(entry.get("id"), f"{where} buddy #{index}"),
                        errors.text(entry.get("label"), f"{where} buddy #{index}", "label")))
    if len({b[0] for b in buddies}) != len(buddies):
        errors.add(f"{where} buddies", "buddy ids must be unique")
    if not buddies:
        errors.add(f"{where} buddies", "at least one buddy is needed")

    return Config(
        id=errors.ident(root.get("id"), where), title=errors.text(root.get("title"), where, "title"),
        grade_band=errors.text(str(root.get("grade_band", "")), where, "grade_band"),
        version=errors.whole(root.get("version"), where, "version", 1),
        limits=limits, pass_credit=pass_credit, thresholds=thresholds, scoring=scoring, reading=reading, text=text,
        game=game, banned_student_words=banned, buddies=tuple(buddies),
    )


def _check_game(game: Dict[str, Any], errors: _Errors) -> None:
    where = f"{CONFIG_FILE} game"
    guide = _mapping(game.get("guide"), f"{where} guide", errors)
    errors.text(guide.get("name"), f"{where} guide", "name")
    for key in ("right", "wrong"):
        lines = _sequence(guide.get(key), f"{where} guide {key}", errors)
        if not lines or not all(isinstance(line, str) and line.strip() for line in lines):
            errors.add(f"{where} guide", f"{key} needs a list of non-empty lines")
    for key in ("welcome", "streak", "booster_intro", "explain_intro", "explain_skip", "bonus_intro",
                "flagged_text", "goal_flagged", "finish"):
        errors.text(guide.get(key), f"{where} guide", key)
    xp = _mapping(game.get("xp"), f"{where} xp", errors)
    for key in ("try", "correct", "streak_bonus", "explain", "booster"):
        errors.whole(xp.get(key), f"{where} xp", key, 0, 1000)
    ranks = _sequence(game.get("ranks"), f"{where} ranks", errors)
    last = -1
    for index, rank in enumerate(ranks):
        rank = _mapping(rank, f"{where} rank #{index + 1}", errors)
        value = errors.whole(rank.get("xp"), f"{where} rank #{index + 1}", "xp", 0)
        if (index == 0 and value != 0) or value <= last:
            errors.add(f"{where} ranks", "ranks must start at 0 XP and increase")
        last = value
        errors.text(rank.get("title"), f"{where} rank #{index + 1}", "title")
    if not ranks:
        errors.add(f"{where} ranks", "at least one rank is needed")
    badge_ids = set()
    for index, badge in enumerate(_sequence(game.get("badges"), f"{where} badges", errors), start=1):
        badge = _mapping(badge, f"{where} badge #{index}", errors)
        badge_ids.add(errors.ident(badge.get("id"), f"{where} badge #{index}"))
        errors.text(badge.get("name"), f"{where} badge #{index}", "name")
    for needed in ("first_step", "hot_streak", "bounce_back", "storyteller", "zone_clear", "quest_done"):
        if needed not in badge_ids:
            errors.add(f"{where} badges", f"missing the {needed!r} badge the game awards")


def _parse_zones(data: Any, errors: _Errors) -> List[Zone]:
    zones = []
    for index, entry in enumerate(_sequence(_mapping(data, CONFIG_FILE, errors).get("zones"), f"{CONFIG_FILE} zones", errors), start=1):
        where = f"{CONFIG_FILE} zone #{index}"
        entry = _mapping(entry, where, errors)
        zones.append(Zone(
            id=errors.ident(entry.get("id"), where), concept=errors.text(entry.get("concept"), where, "concept"),
            name=errors.text(entry.get("name"), where, "name"), story=errors.text(entry.get("story"), where, "story"),
            done_message=errors.text(entry.get("done_message"), where, "done_message"),
        ))
    if not zones:
        errors.add(f"{CONFIG_FILE} zones", "at least one zone is needed")
    if len({z.id for z in zones}) != len(zones) or len({z.concept for z in zones}) != len(zones):
        errors.add(f"{CONFIG_FILE} zones", "zone ids and concepts must each be unique")
    return zones


def _parse_goals(data: Any, concepts: Iterable[str], errors: _Errors) -> Dict[str, Goal]:
    goals: Dict[str, Goal] = {}
    known = set(concepts)
    for index, entry in enumerate(_sequence(_mapping(data, CONFIG_FILE, errors).get("goals"), f"{CONFIG_FILE} goals", errors), start=1):
        where = f"{CONFIG_FILE} goal #{index}"
        entry = _mapping(entry, where, errors)
        goal_id = errors.ident(entry.get("id"), where)
        emphasis = {}
        for concept, weight in _mapping(entry.get("emphasis"), where, errors).items():
            if concept not in known:
                errors.add(where, f"emphasis names an unknown concept {concept!r}")
            emphasis[concept] = errors.number(weight, where, f"emphasis for {concept}", 0, 1)
        if goal_id in goals:
            errors.add(where, f"duplicate goal id {goal_id!r}")
        goals[goal_id] = Goal(goal_id, errors.text(entry.get("label"), where, "label"), emphasis)
    if not goals:
        errors.add(f"{CONFIG_FILE} goals", "at least one goal is needed")
    return goals


# Tree and items ---------------------------------------------------------------

def _parse_tree(data: Any, errors: _Errors) -> Optional[SkillTree]:
    nodes: List[Node] = []
    for index, entry in enumerate(_sequence(_mapping(data, TREE_FILE, errors).get("nodes"), f"{TREE_FILE} nodes", errors), start=1):
        where = f"{TREE_FILE} node #{index}"
        entry = _mapping(entry, where, errors)
        nodes.append(Node(
            id=errors.ident(entry.get("id"), where), name=errors.text(entry.get("name"), where, "name"),
            concept=errors.text(entry.get("concept"), where, "concept"),
            tier=errors.whole(entry.get("tier"), where, "tier", 1, 3),
            parents=tuple(str(p) for p in _sequence(entry.get("parents", []), where, errors)),
            csta=tuple(str(c) for c in _sequence(entry.get("csta", []), where, errors)),
        ))
    if not nodes:
        errors.add(TREE_FILE, "at least one node is needed")
        return None
    try:
        return SkillTree(nodes)
    except ValueError as exc:
        errors.add(TREE_FILE, str(exc))
        return None


def _parse_item(entry: Any, where: str, concept: Optional[str], config: Config, tree: Optional[SkillTree],
                errors: _Errors, booster: bool = False) -> Optional[Item]:
    entry = _mapping(entry, where, errors)
    item_id = errors.ident(entry.get("id"), where)
    where = f"{where} ({item_id})"
    item_type = entry.get("type")
    if item_type not in ITEM_TYPES:
        errors.add(where, f"type must be one of {', '.join(ITEM_TYPES)}, got {item_type!r}")
        return None
    if booster and item_type != CHOICE:
        errors.add(where, "boosters must be choice questions")

    tier = 0 if booster else errors.whole(entry.get("tier"), where, "tier", 1, 3)
    nodes = tuple(str(n) for n in _sequence(entry.get("nodes", []), where, errors))
    if not booster:
        if not nodes:
            errors.add(where, "nodes must list at least one skill-tree node")
        for node_id in nodes:
            if tree is not None and node_id not in tree.nodes:
                errors.add(where, f"unknown node {node_id!r}")
        if tree is not None and nodes and nodes[0] in tree.nodes:
            primary = tree.nodes[nodes[0]]
            if primary.concept != concept:
                errors.add(where, f"primary node {primary.id!r} belongs to {primary.concept!r}, not {concept!r}")
            if primary.tier != tier:
                errors.add(where, f"primary node {primary.id!r} is tier {primary.tier} but the item is tier {tier}")
    facet = entry.get("facet", DEFAULT_FACET[item_type])
    if facet not in FACETS:
        errors.add(where, f"facet must be one of {', '.join(FACETS)}")
        facet = DEFAULT_FACET[item_type]
    prompt = errors.text(entry.get("prompt"), where, "prompt")

    options: List[Option] = []
    cards: List[Card] = []
    buckets: List[Bucket] = []
    answer: Any = None
    item_misconception = entry.get("misconception")

    if item_type in CHOICE_LIKE:
        correct = []
        for index, raw in enumerate(_sequence(entry.get("options"), f"{where} options", errors), start=1):
            raw = _mapping(raw, f"{where} option #{index}", errors)
            # A spot item's options are lines of one program, so their indentation is kept like a card's.
            text = (_card_text(raw.get("text"), f"{where} option #{index}", errors) if item_type == SPOT
                    else errors.text(raw.get("text"), f"{where} option #{index}", "text"))
            option = Option(errors.ident(raw.get("id"), f"{where} option #{index}"), text,
                            raw.get("misconception"), raw.get("why"))
            options.append(option)
            if raw.get("correct") is True:
                correct.append(option)
                if option.misconception:
                    errors.add(where, f"correct option {option.id!r} should not have a misconception")
            elif not booster and not option.misconception:
                errors.add(where, f"wrong option {option.id!r} needs a misconception tag")
        if len(options) < (2 if booster else 3):
            errors.add(where, f"needs at least {2 if booster else 3} options")
        if len({o.id for o in options}) != len(options):
            errors.add(where, "option ids must be unique")
        if len(correct) != 1:
            errors.add(where, f"exactly one option must be correct, found {len(correct)}")
        answer = correct[0].id if len(correct) == 1 else None
    else:
        for index, raw in enumerate(_sequence(entry.get("cards"), f"{where} cards", errors), start=1):
            raw = _mapping(raw, f"{where} card #{index}", errors)
            cards.append(Card(errors.ident(raw.get("id"), f"{where} card #{index}"),
                              _card_text(raw.get("text"), f"{where} card #{index}", errors), raw.get("misconception")))
        if len(cards) < 3:
            errors.add(where, "needs at least 3 cards")
        if len({c.id for c in cards}) != len(cards):
            errors.add(where, "card ids must be unique")
        if item_type == ORDER:
            answer = [c.id for c in cards]
            if not item_misconception:
                errors.add(where, "order questions need a misconception tag")
        else:
            raw_cards = _sequence(entry.get("cards"), f"{where} cards", errors)
            for index, raw in enumerate(_sequence(entry.get("buckets"), f"{where} buckets", errors), start=1):
                raw = _mapping(raw, f"{where} bucket #{index}", errors)
                buckets.append(Bucket(errors.ident(raw.get("id"), f"{where} bucket #{index}"),
                                      errors.text(raw.get("text"), f"{where} bucket #{index}", "text")))
            bucket_ids = {b.id for b in buckets}
            if len(buckets) < 2 or len(bucket_ids) != len(buckets):
                errors.add(where, "needs at least 2 buckets with unique ids")
            answer = {}
            for raw in raw_cards:
                if isinstance(raw, dict) and raw.get("bucket") in bucket_ids:
                    answer[str(raw.get("id"))] = raw["bucket"]
                else:
                    errors.add(where, f"card {raw.get('id') if isinstance(raw, dict) else raw!r} must name one of its buckets")
            if answer and set(answer.values()) != bucket_ids:
                errors.add(where, "every bucket needs at least one card")
            if not item_misconception and not any(c.misconception for c in cards):
                errors.add(where, "sort questions need a misconception tag on the item or on a card")
    display = entry.get("display")
    if display is not None and (item_type != SORT or display not in DISPLAYS):
        errors.add(where, f"display is only for sort questions and must be one of {', '.join(DISPLAYS)}")
    code, code_lang = _parse_code(entry, where, errors)
    table = _parse_table(entry.get("table"), where, errors)
    if _code_in_sentence(prompt):
        errors.add(where, "the prompt has code in its sentence; move it to `code:` (a block) or wrap names in `backticks`")
    option_format = entry.get("option_format", DEFAULT_OPTION_FORMAT[item_type])
    if option_format not in OPTION_FORMATS:
        errors.add(where, f"option_format must be one of {', '.join(OPTION_FORMATS)}")
        option_format = DEFAULT_OPTION_FORMAT[item_type]

    return Item(
        id=item_id, concept=None if booster else concept, tier=tier, type=item_type, prompt=prompt, nodes=nodes,
        facet=facet, options=tuple(options), cards=tuple(cards), buckets=tuple(buckets), answer=answer,
        misconception=item_misconception, feedback_right=entry.get("feedback_right"),
        feedback_wrong=entry.get("feedback_wrong"), pass_credit=config.pass_credit.get(item_type, 1.0),
        display=display, code=code, code_lang=code_lang, table=table, option_format=option_format,
    )


def _parse_code(entry: Dict[str, Any], where: str, errors: _Errors) -> Tuple[Optional[str], str]:
    raw = entry.get("code")
    lang = entry.get("code_lang", "python")
    if lang not in CODE_LANGS:
        errors.add(where, f"code_lang must be one of {', '.join(CODE_LANGS)}")
        lang = "python"
    if raw is None:
        return None, lang
    if not isinstance(raw, str) or not raw.strip():
        errors.add(where, "code must be a non-empty block of text")
        return None, lang
    if "\t" in raw:
        errors.add(where, "code must indent with spaces, not tabs")
    lines = raw.rstrip("\n").split("\n")
    if len(lines) > MAX_CODE_LINES:
        errors.add(where, f"code has {len(lines)} lines; keep it to {MAX_CODE_LINES}")
    for number, line in enumerate(lines, start=1):
        if len(line) > MAX_CODE_LINE_CHARS:
            errors.add(where, f"code line {number} is {len(line)} characters; keep lines to {MAX_CODE_LINE_CHARS}")
    return "\n".join(line.rstrip() for line in lines), lang


def _parse_table(raw: Any, where: str, errors: _Errors) -> Optional[Table]:
    if raw is None:
        return None
    raw = _mapping(raw, f"{where} table", errors)
    columns = tuple(str(c) for c in _sequence(raw.get("columns"), f"{where} table columns", errors))
    rows = tuple(tuple(str(cell) for cell in _sequence(row, f"{where} table row", errors))
                 for row in _sequence(raw.get("rows"), f"{where} table rows", errors))
    if not 2 <= len(columns) <= MAX_TABLE_COLUMNS:
        errors.add(where, f"a table needs 2 to {MAX_TABLE_COLUMNS} columns")
    if not 1 <= len(rows) <= MAX_TABLE_ROWS:
        errors.add(where, f"a table needs 1 to {MAX_TABLE_ROWS} rows")
    for number, row in enumerate(rows, start=1):
        if len(row) != len(columns):
            errors.add(where, f"table row {number} has {len(row)} cells but there are {len(columns)} columns")
    return Table(columns, rows)


def _parse_explain(entry: Any, concept: str, where: str, tree: Optional[SkillTree], errors: _Errors) -> Optional[ExplainPrompt]:
    entry = _mapping(entry, where, errors)
    ideas = []
    for index, raw in enumerate(_sequence(entry.get("key_ideas"), f"{where} key_ideas", errors), start=1):
        raw = _mapping(raw, f"{where} key idea #{index}", errors)
        words = tuple(str(w).lower() for w in _sequence(raw.get("words"), f"{where} key idea #{index}", errors))
        if not words:
            errors.add(f"{where} key idea #{index}", "words needs at least one word or phrase")
        ideas.append(KeyIdea(errors.ident(raw.get("id"), f"{where} key idea #{index}"),
                             errors.whole(raw.get("level"), f"{where} key idea #{index}", "level", 1, 3),
                             words, errors.text(raw.get("label"), f"{where} key idea #{index}", "label")))
    if {i.level for i in ideas} != set(TIERS):
        errors.add(where, "key_ideas must cover levels 1, 2 and 3")
    nodes = tuple(str(n) for n in _sequence(entry.get("nodes", []), where, errors))
    for node_id in nodes:
        if tree is not None and node_id not in tree.nodes:
            errors.add(where, f"unknown node {node_id!r}")
    return ExplainPrompt(errors.ident(entry.get("id"), where), concept, nodes,
                         errors.text(entry.get("prompt"), where, "prompt"), tuple(ideas))


# Student-facing text lint ----------------------------------------------------

def _student_strings(content: Content) -> List[Tuple[str, str]]:
    """(where, text) for every string a student reads."""
    strings: List[Tuple[str, str]] = []
    for item in list(content.items.values()) + content.boosters:
        label = f"item {item.id}"
        strings.append((f"{label} prompt", item.prompt))
        if item.option_format == "text":
            strings += [(f"{label} option", o.text) for o in item.options]
            strings += [(f"{label} card", c.text) for c in item.cards]
        strings += [(f"{label} why", o.why) for o in item.options if o.why]
        strings += [(f"{label} bucket", b.text) for b in item.buckets]
        strings += [(f"{label} feedback", t) for t in (item.feedback_right, item.feedback_wrong) if t]
    strings += [(f"explain {e.id} prompt", e.prompt) for e in content.explain.values()]
    for zone in content.zones:
        strings += [(f"zone {zone.id} story", zone.story), (f"zone {zone.id} done", zone.done_message)]
    guide = content.config.game["guide"]
    for key, value in guide.items():
        if key == "name":
            continue
        for line in (value if isinstance(value, list) else [value]):
            strings.append((f"guide {key}", str(line)))
    strings += [(f"goal {g.id}", g.label) for g in content.goals.values()]
    return strings


def _student_code_strings(content: Content) -> List[Tuple[str, str]]:
    """(where, text) for code and data a student reads: code blocks, table cells, code-style options and cards."""
    strings: List[Tuple[str, str]] = []
    for item in list(content.items.values()) + content.boosters:
        label = f"item {item.id}"
        if item.code:
            strings += [(f"{label} code", line) for line in item.code.split("\n") if line.strip()]
        if item.table is not None:
            strings += [(f"{label} table", cell) for cell in item.table.columns]
            strings += [(f"{label} table", cell) for row in item.table.rows for cell in row]
        if item.option_format == "code":
            strings += [(f"{label} option", o.text) for o in item.options]
            strings += [(f"{label} card", c.text) for c in item.cards]
    return strings


def _lint_student_text(content: Content, errors: _Errors) -> None:
    """Reading level for prose; for everything a student sees, no stage/score words and nothing the
    content filter blocks (profanity, slurs, violence, personal details)."""
    rules = content.config.reading
    banned = [re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE) for w in content.config.banned_student_words]
    prose = _student_strings(content)
    for where, text in prose:
        for problem in readability_problems(text, rules.max_sentence_words, rules.max_word_length):
            errors.add(where, problem)
    for where, text in prose + _student_code_strings(content):
        for pattern in banned:
            if pattern.search(text):
                errors.add(where, f"uses the word {pattern.pattern!r}, which stays out of student-facing text")
        problem = authored_text_problem(text)
        if problem:
            errors.add(where, f"the content filter blocks this text ({problem})")


def _check_coverage(content: Content, concept_ids: Optional[Sequence[str]], errors: _Errors) -> None:
    tree = content.tree
    zone_concepts = content.concepts()
    if concept_ids is not None:
        for concept in zone_concepts:
            if concept not in concept_ids:
                errors.add("zones", f"concept {concept!r} is not in the project manifest ({', '.join(concept_ids)})")
        for concept in concept_ids:
            if concept not in zone_concepts:
                errors.add("zones", f"manifest concept {concept!r} has no zone")
    for node in tree.nodes.values():
        if node.concept not in zone_concepts:
            errors.add("tree", f"node {node.id!r} belongs to {node.concept!r}, which has no zone")
    for concept in zone_concepts:
        for tier in TIERS:
            count = len(content.items_for(concept, tier))
            if count < MIN_ITEMS_PER_TIER:
                errors.add("items", f"{concept} tier {tier} has {count} questions; at least {MIN_ITEMS_PER_TIER} are needed")
        if concept not in content.explain:
            errors.add("items", f"{concept} has no explain prompt")
    primary_nodes = {i.nodes[0] for i in content.items.values() if i.nodes}
    for node_id in tree.order:
        if node_id not in primary_nodes:
            errors.add("tree", f"node {node_id!r} has no question that targets it")
    if len(content.boosters) < content.config.limits.max_boosters:
        errors.add(BOOSTERS_FILE, f"needs at least {content.config.limits.max_boosters} boosters")


# Entry points ---------------------------------------------------------------------

def load_content(project_root: PathLike, concept_ids: Optional[Sequence[str]] = None) -> Content:
    """Load the diagnostic content for a project, or raise ContentError listing every problem."""
    folder = content_dir(project_root)
    errors = _Errors()
    if not folder.is_dir():
        raise ContentError([f"no diagnostic folder at {folder}"])

    config_data = _read_yaml(folder / CONFIG_FILE, errors)
    config = _parse_config(config_data, errors)
    tree = _parse_tree(_read_yaml(folder / TREE_FILE, errors), errors)
    zones = _parse_zones(config_data, errors) if config_data else []
    goals = _parse_goals(config_data, [z.concept for z in zones], errors) if config_data else {}
    if config is None:
        raise ContentError(errors.items)

    items: Dict[str, Item] = {}
    explain: Dict[str, ExplainPrompt] = {}
    items_dir = folder / ITEMS_FOLDER
    files = sorted(items_dir.glob("*.yaml")) if items_dir.is_dir() else []
    if not files:
        errors.add(ITEMS_FOLDER, "no item files found")
    for path in files:
        data = _mapping(_read_yaml(path, errors), path.name, errors)
        concept = data.get("concept")
        if concept not in {z.concept for z in zones}:
            errors.add(path.name, f"concept {concept!r} has no zone in {CONFIG_FILE}")
            continue
        if "explain" in data:
            prompt = _parse_explain(data["explain"], concept, f"{path.name} explain", tree, errors)
            if prompt is not None:
                explain[concept] = prompt
        for index, raw in enumerate(_sequence(data.get("items"), f"{path.name} items", errors), start=1):
            item = _parse_item(raw, f"{path.name} item #{index}", concept, config, tree, errors)
            if item is not None:
                if item.id in items:
                    errors.add(path.name, f"duplicate item id {item.id!r}")
                items[item.id] = item

    boosters: List[Item] = []
    booster_data = _mapping(_read_yaml(folder / BOOSTERS_FILE, errors), BOOSTERS_FILE, errors)
    for index, raw in enumerate(_sequence(booster_data.get("boosters"), f"{BOOSTERS_FILE} boosters", errors), start=1):
        booster = _parse_item(raw, f"{BOOSTERS_FILE} booster #{index}", None, config, None, errors, booster=True)
        if booster is not None:
            boosters.append(booster)

    all_ids = list(items) + [b.id for b in boosters] + [e.id for e in explain.values()]
    for duplicate in sorted({i for i in all_ids if all_ids.count(i) > 1}):
        errors.add("ids", f"id {duplicate!r} is used more than once")

    if tree is None or errors.items:
        raise ContentError(errors.items)

    content = Content(config=config, tree=tree, zones=zones, goals=goals, items=items, boosters=boosters, explain=explain)
    _check_coverage(content, concept_ids, errors)
    _lint_student_text(content, errors)
    if errors.items:
        raise ContentError(errors.items)

    missing_csta = [n.id for n in tree.nodes.values() if not n.csta]
    if missing_csta:
        content.notices.append(f"{len(missing_csta)} of {len(tree.nodes)} skill-tree nodes have no CSTA code yet "
                               "(add codes in tree.yaml once checked against the standards workbook)")
    return content


@dataclass
class CheckResult:
    passed: bool
    problems: List[str] = field(default_factory=list)
    notices: List[str] = field(default_factory=list)


def check_content(project_root: PathLike) -> CheckResult:
    """Validate a project's diagnostic against its manifest. Never raises for bad content."""
    from engine.project import ProjectLoadError, load_project

    try:
        concept_ids = load_project(project_root).manifest.concept_ids()
    except ProjectLoadError as exc:
        return CheckResult(False, [f"project: {e}" for e in exc.errors])
    try:
        content = load_content(project_root, concept_ids)
    except ContentError as exc:
        return CheckResult(False, exc.errors)
    lim = content.config.limits
    notices = list(content.notices)
    typical = len(content.zones) * 3
    low = typical * lim.seconds_per_item + lim.max_explain_prompts * lim.seconds_per_explain
    high = (lim.max_scored_items + lim.max_boosters) * lim.seconds_per_item + lim.max_explain_prompts * lim.seconds_per_explain
    notices.append(f"{len(content.items)} questions, {len(content.boosters)} boosters, {len(content.tree.nodes)} skill-tree nodes; "
                   f"a quest asks about {typical}-{lim.max_scored_items} scored questions "
                   f"(about {low // 60}-{-(-high // 60)} minutes, target {lim.target_minutes})")
    return CheckResult(True, [], notices)
