"""Review checks: days_per_station."""
from engine.checklib import describe, expect, make_row

REQUIRED = {"days_per_station": 1}


def check_counts(ctx):
    """Counts rows per station, gives {} for no rows, and works for a full year."""
    rows = [make_row("2026-01-01", 20.0, 0.0, "ST-A"), make_row("2026-01-02", 20.0, 0.0, "ST-A"),
            make_row("2026-01-01", 20.0, 0.0, "ST-C")]
    value = ctx.module.days_per_station(rows)
    expect(value == {"ST-A": 2, "ST-C": 1}, f"these rows should give {{'ST-A': 2, 'ST-C': 1}}, but gave {describe(value)}.")
    expect(ctx.module.days_per_station([]) == {}, "no rows should give {}.")
    value = ctx.module.days_per_station(ctx.db_rows())
    expect(value == {"ST-A": 365, "ST-B": 365, "ST-C": 365},
           f"a full year has 365 days at each station, but you returned {describe(value)}.")
