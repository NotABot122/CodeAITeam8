"""Review checks: temps_above."""
from engine.checklib import describe, expect, make_row

REQUIRED = {"temps_above": 2}


def check_small_list(ctx):
    """Keeps values at or above the threshold, in order."""
    rows = [make_row("2026-07-01", 36.0, 0.0), make_row("2026-07-02", 30.0, 0.0), make_row("2026-07-03", 35.0, 0.0)]
    value = ctx.module.temps_above(rows, 35.0)
    expect(value == [36.0, 35.0], f"with 35.0, the result should be [36.0, 35.0] (35.0 counts, same order), "
                                  f"but was {describe(value)}.")
    expect(ctx.module.temps_above(rows, 50.0) == [], "nothing reaches 50.0, so the result should be [].")
    expect(ctx.module.temps_above([], 10.0) == [], "no rows should give [].")


def check_whole_year(ctx):
    """Works for a full year at one station."""
    rows = ctx.db_rows("ST-A", "2026-01-01", "2026-12-31")
    wanted = ctx.reference.temps_above(rows, 38.0)
    value = ctx.module.temps_above(rows, 38.0)
    expect(value == wanted, f"ST-A had {len(wanted)} days at 38.0 or more, but you returned "
                            f"{len(value) if isinstance(value, list) else describe(value)} values.")
