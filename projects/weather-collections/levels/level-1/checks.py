"""Part 2, Level 1 checks: hot_dates."""
import random

from engine.checklib import describe, expect, make_row

REQUIRED = {"hot_dates": 2}


def check_small_list(ctx):
    """Return the hot dates from a short list, oldest first."""
    rows = [make_row("2026-07-03", 36.0, 0.0), make_row("2026-07-01", 35.0, 0.0),
            make_row("2026-07-02", 34.9, 0.0), make_row("2026-07-04", 20.0, 0.0)]
    value = ctx.module.hot_dates(rows, 35.0)
    expect(isinstance(value, list), f"hot_dates should return a list, but it returned {describe(value)}.")
    expect(value == ["2026-07-01", "2026-07-03"],
           f"with a threshold of 35.0, the hot dates are ['2026-07-01', '2026-07-03'] (oldest first, "
           f"35.0 counts), but you returned {describe(value)}.")


def check_empty(ctx):
    """No hot days, or no rows, gives an empty list."""
    expect(ctx.module.hot_dates([], 30.0) == [], "an empty list of rows should give [].")
    rows = [make_row("2026-01-01", 10.0, 0.0)]
    value = ctx.module.hot_dates(rows, 30.0)
    expect(value == [], f"no day reaches 30.0, so the result should be [], but was {describe(value)}.")


def check_does_not_change_rows(ctx):
    """hot_dates should not change the list it is given."""
    rows = [make_row("2026-07-02", 36.0, 0.0), make_row("2026-07-01", 37.0, 0.0)]
    before = [dict(r) for r in rows]
    ctx.module.hot_dates(rows, 35.0)
    expect(rows == before, "hot_dates should not change or reorder the rows it is given.")


def check_whole_year(ctx):
    """Works on a full year of data for different thresholds."""
    rng = random.Random(3)
    rows = ctx.db_rows()
    rng.shuffle(rows)
    for threshold in (30.0, 35.0, 40.0):
        wanted = ctx.reference.hot_dates(rows, threshold)
        value = ctx.module.hot_dates(rows, threshold)
        expect(value == wanted, f"with a threshold of {threshold}, a full year has {len(wanted)} hot dates, "
                                f"but you returned {len(value) if isinstance(value, list) else describe(value)}.")
