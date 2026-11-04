"""Practice checks: count_readings."""
from engine.checklib import describe, expect

REQUIRED = {"count_readings": 2}


def _count(ctx, station_id):
    conn = ctx.connect()
    try:
        return ctx.module.count_readings(conn, station_id)
    finally:
        conn.close()


def check_full_year(ctx):
    """Each station has 365 readings."""
    for station in ("ST-A", "ST-C"):
        value = _count(ctx, station)
        expect(value == 365, f"{station} has 365 readings, but count_readings returned {describe(value)}.")


def check_unknown_station(ctx):
    """A station with no rows returns 0."""
    value = _count(ctx, "ST-Z")
    expect(value == 0, f"station ST-Z has no readings, so the count should be 0, but was {describe(value)}.")


def check_uses_placeholders(ctx):
    """A station ID containing a quote should count 0 rows."""
    try:
        value = _count(ctx, "' OR '1'='1")
    except Exception as exc:
        raise AssertionError(f"a station ID containing a quote (') caused {type(exc).__name__}. Use a ? placeholder.") from None
    expect(value == 0, "a station ID containing a quote should count 0 rows. Use a ? placeholder.")
