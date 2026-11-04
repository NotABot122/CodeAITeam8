"""Review checks: wettest_day. The loop rule is checked by the engine."""
from engine.checklib import describe, expect, make_row

REQUIRED = {"wettest_day": 1}


def check_small_list(ctx):
    """Finds the wettest day in the middle of a list, and keeps the first one in a tie."""
    rows = [make_row("2026-04-01", 20.0, 3.0), make_row("2026-04-02", 20.0, 12.5), make_row("2026-04-03", 20.0, 1.0)]
    value = ctx.module.wettest_day(rows)
    expect(value == "2026-04-02", f"the wettest day is 2026-04-02 (12.5 mm), but you returned {describe(value)}.")
    tie = [make_row("2026-04-05", 20.0, 8.0), make_row("2026-04-06", 20.0, 8.0)]
    value = ctx.module.wettest_day(tie)
    expect(value == "2026-04-05", f"in a tie, keep the first day (2026-04-05), but you returned {describe(value)}.")


def check_empty(ctx):
    """No rows gives None."""
    value = ctx.module.wettest_day([])
    expect(value is None, f"no rows should give None, but gave {describe(value)}.")


def check_whole_year(ctx):
    """Works for a full year at one station."""
    rows = ctx.db_rows("ST-C", "2026-01-01", "2026-12-31")
    wanted = ctx.reference.wettest_day(rows)
    value = ctx.module.wettest_day(rows)
    expect(value == wanted, f"ST-C's wettest day of the year is {wanted}, but you returned {describe(value)}.")
