"""Build a themed project's SQLite database from its spec and a seed.

Names come from the theme. All numbers are made up for practice: they are
random within the theme's ranges, plus forced rows at each threshold and just
below it, and one row over both thresholds, in every group.
"""
from __future__ import annotations

import os
import random
import sqlite3
import tempfile
from pathlib import Path

from .spec import theme_from_dict

# number -> (metric_a, metric_b), where "low" means a random value under the threshold.
FORCED = {2: ("at", "low"), 3: ("below", "low"), 5: ("low", "at"), 6: ("low", "below"), 8: ("over", "over")}


def _value(rng: random.Random, metric, mode: str) -> float:
    if mode == "at":
        return metric.threshold
    if mode == "below":
        return round(metric.threshold - 0.1, 1)
    if mode == "low":
        return round(rng.uniform(metric.minimum, metric.threshold - 0.2), 1)
    if mode == "over":
        return round(rng.uniform(metric.threshold, metric.maximum), 1)
    return round(rng.uniform(metric.minimum, metric.maximum), 1)


def build_rows(spec, seed: int):
    rng = random.Random(seed)
    rows = []
    for group in spec.groups:
        for number, name in enumerate(spec.names[group], start=1):
            mode_a, mode_b = FORCED.get(number, ("any", "any"))
            rows.append((group, number, name, _value(rng, spec.metric_a, mode_a), _value(rng, spec.metric_b, mode_b)))
    return rows


def build(out_path, spec_data: dict, seed: int) -> Path:
    spec = theme_from_dict(spec_data)
    out_path = Path(out_path)
    g, n, nm, a, b = spec.columns
    fd, tmp = tempfile.mkstemp(prefix=".data-", suffix=".db", dir=str(out_path.parent))
    os.close(fd)
    try:
        conn = sqlite3.connect(tmp)
        try:
            # Identifiers were validated by parse_theme, so they're safe to place in DDL.
            conn.execute(
                f"CREATE TABLE {spec.table} ({g} TEXT NOT NULL, {n} INTEGER NOT NULL, {nm} TEXT NOT NULL, "
                f"{a} REAL NOT NULL, {b} REAL NOT NULL, PRIMARY KEY ({g}, {n}))")
            conn.executemany(f"INSERT INTO {spec.table} VALUES (?, ?, ?, ?, ?)", build_rows(spec, seed))
            conn.commit()
        finally:
            conn.close()
        os.replace(tmp, out_path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return out_path
