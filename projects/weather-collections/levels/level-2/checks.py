"""Part 2, Level 2 checks: rain_by_station."""
from engine.checklib import describe, expect, make_row

REQUIRED = {"rain_by_station": 1}


def check_example(ctx):
    """The example from the instructions works."""
    rows = [make_row("2026-01-01", 20.0, 2.5, "ST-A"), make_row("2026-01-02", 20.0, 1.0, "ST-A"),
            make_row("2026-01-01", 20.0, 4.0, "ST-B")]
    value = ctx.module.rain_by_station(rows)
    expect(isinstance(value, dict), f"rain_by_station should return a dictionary, but it returned {describe(value)}.")
    expect(value == {"ST-A": 3.5, "ST-B": 4.0},
           f"the example should give {{'ST-A': 3.5, 'ST-B': 4.0}}, but gave {describe(value)}.")


def check_empty(ctx):
    """No rows gives an empty dictionary."""
    value = ctx.module.rain_by_station([])
    expect(value == {}, f"no rows should give {{}}, but gave {describe(value)}.")


def check_rounding(ctx):
    """Totals are rounded to 1 decimal place."""
    rows = [make_row(f"2026-02-{d:02d}", 20.0, 0.1, "ST-C") for d in range(1, 4)]
    value = ctx.module.rain_by_station(rows)
    expect(value == {"ST-C": 0.3}, f"three days of 0.1 mm should total 0.3 (rounded), but gave {describe(value)}.")


def check_whole_year(ctx):
    """Works for a full year at all three stations."""
    rows = ctx.db_rows()
    wanted = ctx.reference.rain_by_station(rows)
    value = ctx.module.rain_by_station(rows)
    expect(value == wanted, f"for the full year, the totals should be {describe(wanted, 90)}, but were {describe(value, 90)}.")
