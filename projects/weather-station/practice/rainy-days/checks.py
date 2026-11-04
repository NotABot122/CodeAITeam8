"""Practice checks: count_rainy_days. The loop rules are checked separately by the engine."""
from engine.checklib import describe, expect, make_row

REQUIRED = {"count_rainy_days": 1}


def check_small_list(ctx):
    """Count days with rain above 0 in a short list."""
    rows = [make_row("2026-04-01", 20.0, 0.0), make_row("2026-04-02", 20.0, 0.1),
            make_row("2026-04-03", 20.0, 12.5), make_row("2026-04-04", 20.0, 0.0)]
    value = ctx.module.count_rainy_days(rows)
    expect(value == 2, f"2 of these 4 days had rain, but count_rainy_days returned {describe(value)}.")


def check_empty_list(ctx):
    """An empty list has 0 rainy days."""
    value = ctx.module.count_rainy_days([])
    expect(value == 0, f"an empty list should give 0, but count_rainy_days returned {describe(value)}.")


def check_whole_station(ctx):
    """Count rainy days for a whole year at one station."""
    rows = ctx.db_rows("ST-C", "2026-01-01", "2026-12-31")
    wanted = ctx.reference.count_rainy_days(rows)
    value = ctx.module.count_rainy_days(rows)
    expect(value == wanted, f"ST-C had {wanted} rainy days in 2026, but count_rainy_days returned {describe(value)}.")
