"""Practice checks: first_and_last."""
import random

from engine.checklib import describe, expect, make_row

REQUIRED = {"first_and_last": 1}


def check_first_and_last(ctx):
    """Earliest and latest date, for unordered rows, one row, and no rows."""
    rows = [make_row("2026-03-05", 20.0, 0.0), make_row("2026-03-01", 20.0, 0.0), make_row("2026-03-09", 20.0, 0.0)]
    value = ctx.module.first_and_last(rows)
    expect(value == ["2026-03-01", "2026-03-09"], f"these rows should give ['2026-03-01', '2026-03-09'], "
                                                  f"but gave {describe(value)}.")
    one = ctx.module.first_and_last([make_row("2026-05-05", 20.0, 0.0)])
    expect(one == ["2026-05-05", "2026-05-05"], f"one row is both first and last, but you returned {describe(one)}.")
    expect(ctx.module.first_and_last([]) == [], "no rows should give [].")
    year = ctx.db_rows("ST-A", "2026-01-01", "2026-12-31")
    random.Random(2).shuffle(year)
    value = ctx.module.first_and_last(year)
    expect(value == ["2026-01-01", "2026-12-31"], f"a shuffled full year should give ['2026-01-01', '2026-12-31'], "
                                                  f"but gave {describe(value)}.")
