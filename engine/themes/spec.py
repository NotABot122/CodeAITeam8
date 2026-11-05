"""The theme spec: everything the model is allowed to choose for a themed project.

The model picks names, story text, and number ranges. The engine derives the
function names, dictionary keys, data, tests, and reference solution from
this spec, so every themed project tests the same skills the same way.

Identifiers end up in SQL and Python source, so they are checked against a
strict pattern and reserved-word lists before use.
"""
from __future__ import annotations

import builtins
import keyword
import re
from dataclasses import asdict, dataclass
from typing import Dict, List

from ..safety import screen_text

IDENT = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
SQL_RESERVED = {
    "abort", "action", "add", "all", "alter", "and", "as", "asc", "between", "by", "case", "check", "column",
    "commit", "create", "cross", "current", "date", "default", "delete", "desc", "distinct", "drop", "each",
    "else", "end", "except", "exists", "from", "full", "glob", "group", "having", "if", "in", "index", "inner",
    "insert", "into", "is", "join", "key", "left", "like", "limit", "match", "natural", "not", "null", "of",
    "offset", "on", "or", "order", "outer", "primary", "references", "replace", "right", "rowid", "select",
    "set", "table", "then", "time", "to", "union", "unique", "update", "using", "values", "view", "when",
    "where", "with",
}
RESERVED_NAMES = {"conn", "row", "rows", "labels", "readings", "result", "sqlite3", "engine", "self", "cls"}
NAME_TEXT = re.compile(r"^[^\x00-\x1f`<>{}\\$]{1,30}$")
MIN_NAMES, MAX_NAMES = 12, 40
VALUE_MIN, VALUE_MAX = 0.0, 10000.0


class ThemeError(ValueError):
    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class Metric:
    column: str
    label: str          # the label for rows at or above the threshold, e.g. "powerful"
    unit: str
    description: str
    minimum: float
    maximum: float
    threshold: float


@dataclass(frozen=True)
class ThemeSpec:
    title: str
    story: str
    entity_singular: str
    entity_plural: str
    table: str
    group_column: str
    group_description: str
    groups: List[str]
    number_column: str
    name_column: str
    metric_a: Metric
    metric_b: Metric
    normal_label: str
    names: Dict[str, List[str]]

    # Derived names --------------------------------------------------------
    @property
    def columns(self) -> List[str]:
        return [self.group_column, self.number_column, self.name_column, self.metric_a.column, self.metric_b.column]

    @property
    def functions(self) -> Dict[str, str]:
        s, p = self.entity_singular, self.entity_plural
        return {
            "get": f"get_{p}",
            "classify": f"classify_{s}",
            "summarize": f"summarize_{p}",
            "report": f"build_{s}_report",
            "count": f"count_{p}",
            "band": f"{self.metric_a.column}_band",
            "count_label": f"count_{self.metric_b.label}",
        }

    @property
    def summary_keys(self) -> Dict[str, str]:
        return {
            "count_a": f"{self.metric_a.label}_count",
            "count_b": f"{self.metric_b.label}_count",
            "count_normal": f"{self.normal_label}_count",
            "total_b": f"total_{self.metric_b.column}",
            "max_a": f"max_{self.metric_a.column}",
            "flagged": f"flagged_{self.number_column}s",
        }

    @property
    def band_cutoff(self) -> float:
        """Lower edge of the "medium" band in the conditionals practice problem."""
        return round((self.metric_a.minimum + self.metric_a.threshold) / 2, 1)

    def to_dict(self) -> dict:
        return asdict(self)


def _identifier(value, where: str, errors: List[str]) -> str:
    if not isinstance(value, str) or not IDENT.match(value):
        errors.append(f"{where}: {value!r} must be lowercase letters, digits, and underscores, starting with a letter")
        return "x"
    if value in SQL_RESERVED or keyword.iskeyword(value) or hasattr(builtins, value) or value in RESERVED_NAMES:
        errors.append(f"{where}: {value!r} is a reserved word")
    return value


def _text(value, where: str, errors: List[str], limit: int, multiline: bool = False) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        errors.append(f"{where}: expected text of 1 to {limit} characters")
        return ""
    if multiline:
        return "\n".join(" ".join(line.split()) for line in value.strip().splitlines())
    return " ".join(value.split())


def _number(value, where: str, errors: List[str]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not VALUE_MIN <= value <= VALUE_MAX:
        errors.append(f"{where}: expected a number from {VALUE_MIN:g} to {VALUE_MAX:g}, got {value!r}")
        return 0.0
    return round(float(value), 1)


def _metric(data, where: str, errors: List[str]) -> Metric:
    if not isinstance(data, dict):
        errors.append(f"{where}: expected an object")
        data = {}
    metric = Metric(
        column=_identifier(data.get("column"), f"{where}.column", errors),
        label=_identifier(data.get("label"), f"{where}.label", errors),
        unit=_text(data.get("unit", "points"), f"{where}.unit", errors, 16),
        description=_text(data.get("description"), f"{where}.description", errors, 120),
        minimum=_number(data.get("minimum"), f"{where}.minimum", errors),
        maximum=_number(data.get("maximum"), f"{where}.maximum", errors),
        threshold=_number(data.get("threshold"), f"{where}.threshold", errors),
    )
    if not metric.minimum + 2.0 <= metric.threshold <= metric.maximum - 2.0:
        errors.append(f"{where}: threshold must be at least 2 above minimum and 2 below maximum")
    return metric


def parse_theme(data: dict) -> ThemeSpec:
    if not isinstance(data, dict):
        raise ThemeError(["theme must be an object"])
    errors: List[str] = []

    groups = data.get("groups")
    if not isinstance(groups, list) or len(groups) != 3:
        errors.append("groups: expected exactly 3 group names")
        groups = []
    groups = [_text(g, f"groups[{i}]", errors, 24) for i, g in enumerate(groups)]
    if len(set(groups)) != len(groups):
        errors.append("groups: names must be different")

    raw_names = data.get("names")
    names: Dict[str, List[str]] = {}
    if not isinstance(raw_names, dict):
        errors.append("names: expected an object mapping each group to a list of names")
        raw_names = {}
    for group in groups:
        items = raw_names.get(group)
        if not isinstance(items, list) or not MIN_NAMES <= len(items) <= MAX_NAMES:
            errors.append(f"names[{group!r}]: expected {MIN_NAMES} to {MAX_NAMES} names")
            continue
        clean = []
        for item in items:
            if not isinstance(item, str) or not NAME_TEXT.match(item.strip()):
                errors.append(f"names[{group!r}]: {item!r} is not a usable name")
            else:
                clean.append(item.strip())
        if len(set(clean)) != len(clean):
            errors.append(f"names[{group!r}]: names must not repeat within a group")
        names[group] = clean
    for group in raw_names:
        if group not in groups:
            errors.append(f"names: {group!r} is not one of the groups")

    spec = ThemeSpec(
        title=_text(data.get("title"), "title", errors, 60),
        story=_text(data.get("story"), "story", errors, 700, multiline=True),
        entity_singular=_identifier(data.get("entity_singular"), "entity_singular", errors),
        entity_plural=_identifier(data.get("entity_plural"), "entity_plural", errors),
        table=_identifier(data.get("table"), "table", errors),
        group_column=_identifier(data.get("group_column"), "group_column", errors),
        group_description=_text(data.get("group_description"), "group_description", errors, 80),
        groups=groups,
        number_column=_identifier(data.get("number_column"), "number_column", errors),
        name_column=_identifier(data.get("name_column"), "name_column", errors),
        metric_a=_metric(data.get("metric_a"), "metric_a", errors),
        metric_b=_metric(data.get("metric_b"), "metric_b", errors),
        normal_label=_identifier(data.get("normal_label"), "normal_label", errors),
        names=names,
    )

    if not errors:
        if len(set(spec.columns)) != 5:
            errors.append("columns: group, number, name, and both metric columns must all be different")
        labels = [spec.metric_a.label, spec.metric_b.label, spec.normal_label]
        if len(set(labels)) != 3:
            errors.append("labels: metric_a.label, metric_b.label, and normal_label must all be different")
        derived = list(spec.functions.values()) + list(spec.summary_keys.values()) + [spec.table]
        for name in derived:
            if len(name) > 40:
                errors.append(f"derived name {name!r} is too long; use shorter words")
            elif keyword.iskeyword(name) or hasattr(builtins, name):
                errors.append(f"derived name {name!r} is a reserved word")
        if len(set(spec.functions.values())) != len(spec.functions):
            errors.append("derived function names collide; pick different words")
        if len(set(spec.summary_keys.values())) != len(spec.summary_keys):
            errors.append("derived summary keys collide; pick different words")
        if spec.table in spec.columns:
            errors.append("table must not have the same name as a column")

    # Every piece of text a student will see goes through the content filter.
    texts = [spec.title, spec.story, spec.group_description, spec.metric_a.description, spec.metric_b.description,
             spec.metric_a.unit, spec.metric_b.unit] + groups + [n for items in names.values() for n in items]
    # One check for all of it (one guardrail call instead of one per name); the model wrote these, so OUTPUT.
    verdict = screen_text("\n".join(texts), "OUTPUT")
    if verdict.blocked:
        culprit = next((t for t in texts if screen_text(t, local_only=True).blocked), None)
        where = f": {culprit[:40]!r}" if culprit else ""
        errors.append(f"content filter blocked text ({verdict.category}){where}")

    if errors:
        raise ThemeError(errors)
    return spec


def theme_from_dict(data: dict) -> ThemeSpec:
    """Rebuild a spec saved with to_dict (already validated)."""
    fields = dict(data)
    fields["metric_a"] = Metric(**data["metric_a"])
    fields["metric_b"] = Metric(**data["metric_b"])
    return ThemeSpec(**fields)
