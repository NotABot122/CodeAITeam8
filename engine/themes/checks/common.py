"""Helpers for themed checks."""
from __future__ import annotations

import sqlite3

from ...checklib import describe, expect  # noqa: F401  (re-exported for check modules)
from ..spec import theme_from_dict

INJECTION = "' OR '1'='1"
_CACHE = {}


def spec_of(ctx):
    key = id(ctx.params.get("theme"))
    if key not in _CACHE:
        _CACHE[key] = theme_from_dict(ctx.params["theme"])
    return _CACHE[key]


def student(ctx, role: str):
    return getattr(ctx.module, spec_of(ctx).functions[role])


def reference(ctx, role: str):
    return getattr(ctx.reference, spec_of(ctx).functions[role])


def name_of(ctx, role: str) -> str:
    return spec_of(ctx).functions[role]


def db_rows(ctx, group=None, start=None, end=None):
    """Ground-truth rows, read directly by the engine."""
    s = spec_of(ctx)
    g, n = s.group_column, s.number_column
    sql = f"SELECT {', '.join(s.columns)} FROM {s.table}"
    params = ()
    if group is not None:
        sql += f" WHERE {g} = ? AND {n} BETWEEN ? AND ?"
        params = (group, start, end)
    sql += f" ORDER BY {g}, {n}"
    conn = sqlite3.connect(ctx.db_path)
    try:
        return [dict(zip(s.columns, values)) for values in conn.execute(sql, params)]
    finally:
        conn.close()


def row_count(ctx) -> int:
    conn = sqlite3.connect(ctx.db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {spec_of(ctx).table}").fetchone()[0]
    finally:
        conn.close()


def make_row(ctx, number: int, a: float, b: float, group: str = "Test Group", name: str = "Test Entry") -> dict:
    s = spec_of(ctx)
    return {s.group_column: group, s.number_column: number, s.name_column: name,
            s.metric_a.column: a, s.metric_b.column: b}


def low(metric, fraction: float = 0.3) -> float:
    return round(metric.minimum + (metric.threshold - metric.minimum) * fraction, 1)
