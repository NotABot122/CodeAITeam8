"""Review checks: rainy_dates."""
from engine.checklib import describe, expect

REQUIRED = {"rainy_dates": 3}


def _call(ctx, *args):
    conn = ctx.connect()
    try:
        return ctx.module.rainy_dates(conn, *args)
    finally:
        conn.close()


def _truth(ctx, station, minimum):
    return sorted(r["date"] for r in ctx.db_rows(station, "2026-01-01", "2026-12-31") if r["rain_mm"] >= minimum)


def check_matches(ctx):
    """Returns the right dates, oldest first, including the exact minimum."""
    for station, minimum in (("ST-A", 20.0), ("ST-C", 30.0)):
        value = _call(ctx, station, minimum)
        wanted = _truth(ctx, station, minimum)
        expect(value == wanted, f"{station} with at least {minimum} mm should give {len(wanted)} dates, oldest first "
                                f"(20.0 counts as 'at least 20.0'), but you returned {describe(value, 80)}.")


def check_none(ctx):
    """A minimum nobody reaches gives an empty list."""
    value = _call(ctx, "ST-B", 999.0)
    expect(value == [], f"no day has 999 mm of rain, so the result should be [], but was {describe(value)}.")


def check_placeholders(ctx):
    """A station ID with a quote finds nothing."""
    try:
        value = _call(ctx, "' OR '1'='1", 0.0)
    except Exception as exc:
        raise AssertionError(f"a station ID with a quote caused {type(exc).__name__}. Use ? placeholders.") from None
    expect(value == [], "a station ID with a quote should find nothing. Use ? placeholders.")
