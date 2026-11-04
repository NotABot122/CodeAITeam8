"""Part 2, Level 3 checks: days_by_month."""
import random

from engine.checklib import describe, expect, make_row

REQUIRED = {"days_by_month": 1}


def check_example(ctx):
    """The example from the instructions works."""
    rows = [make_row("2026-02-03", 20.0, 0.0), make_row("2026-01-31", 20.0, 0.0), make_row("2026-02-01", 20.0, 0.0)]
    value = ctx.module.days_by_month(rows)
    wanted = {"2026-01": ["2026-01-31"], "2026-02": ["2026-02-01", "2026-02-03"]}
    expect(isinstance(value, dict), f"days_by_month should return a dictionary, but it returned {describe(value)}.")
    expect(value == wanted, f"the example should give {wanted}, but gave {describe(value, 90)}.")


def check_empty(ctx):
    """No rows gives an empty dictionary."""
    value = ctx.module.days_by_month([])
    expect(value == {}, f"no rows should give {{}}, but gave {describe(value)}.")


def check_whole_station(ctx):
    """A full shuffled year at one station has 12 months, each sorted."""
    rows = ctx.db_rows("ST-B", "2026-01-01", "2026-12-31")
    random.Random(5).shuffle(rows)
    value = ctx.module.days_by_month(rows)
    wanted = ctx.reference.days_by_month(rows)
    expect(isinstance(value, dict) and sorted(value) == sorted(wanted),
           f"a full year should have the 12 months {sorted(wanted)[0]} to {sorted(wanted)[-1]} as keys.")
    for month in wanted:
        expect(value[month] == wanted[month], f"the list for {month} should have its {len(wanted[month])} dates, "
                                              f"oldest first.")
