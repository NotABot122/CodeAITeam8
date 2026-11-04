"""Level 1 checks: get_readings."""
from engine.checklib import COLUMNS, date_range, describe, expect

REQUIRED = {"get_readings": 4}

INJECTION = "' OR '1'='1"


def _call(ctx, *args):
    conn = ctx.connect()
    try:
        return ctx.module.get_readings(conn, *args)
    finally:
        conn.close()


def _row_count(ctx):
    conn = ctx.connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM daily_readings").fetchone()[0]
    finally:
        conn.close()


def check_only_requested_station(ctx):
    """get_readings for ST-A should return only ST-A rows."""
    rows = _call(ctx, "ST-A", "2026-01-01", "2026-01-31")
    expect(isinstance(rows, list), f"get_readings should return a list, but it returned {describe(rows)}.")
    others = [r for r in rows if not isinstance(r, dict) or r.get("station_id") != "ST-A"]
    expect(not others, "asking for station ST-A returned rows that aren't for ST-A.")


def check_exact_date_range(ctx):
    """get_readings should return each day in the range exactly once, including both ends."""
    for station, start, end in (("ST-A", "2026-01-01", "2026-01-31"), ("ST-C", "2026-06-10", "2026-06-20")):
        rows = _call(ctx, station, start, end)
        expect(isinstance(rows, list), f"get_readings should return a list, but it returned {describe(rows)}.")
        dates = [r.get("date") if isinstance(r, dict) else None for r in rows]
        wanted = date_range(start, end)
        expect(start in dates and end in dates,
               f"{station} from {start} to {end} should include both {start} and {end}.")
        expect(sorted(d for d in dates if d) == wanted and len(dates) == len(wanted),
               f"{station} from {start} to {end} should return {len(wanted)} rows, one per day, but returned {len(dates)}.")


def check_rows_are_dictionaries(ctx):
    """Each row should be a dictionary with the five column names and the database values."""
    rows = _call(ctx, "ST-B", "2026-05-01", "2026-05-10")
    truth = {r["date"]: r for r in ctx.db_rows("ST-B", "2026-05-01", "2026-05-10")}
    for row in rows:
        expect(isinstance(row, dict), f"each row should be a dictionary, but one was {describe(row)}.")
        expect(set(row) == set(COLUMNS),
               f"each row should have exactly the keys {', '.join(COLUMNS)}, but one had {', '.join(sorted(map(str, row)))}.")
        expect(row == truth.get(row["date"]),
               f"the row for {row['date']} should have the values stored in the database.")


def check_sorted_by_date(ctx):
    """Rows should be sorted by date, oldest first."""
    rows = _call(ctx, "ST-B", "2026-03-01", "2026-03-31")
    dates = [r.get("date") for r in rows if isinstance(r, dict)]
    ascending = all(a < b for a, b in zip(dates, dates[1:]))
    expect(ascending, "rows should be sorted by date, oldest first. Try ORDER BY date.")


def check_empty_ranges(ctx):
    """A range with no matching days should return an empty list without an error."""
    rows = _call(ctx, "ST-A", "2027-01-01", "2027-01-31")
    expect(rows == [], f"a range with no data (2027) should return [], but returned {describe(rows)}.")
    rows = _call(ctx, "ST-A", "2026-02-10", "2026-02-01")
    expect(rows == [], f"a start date after the end date should return [], but returned {describe(rows)}.")


def check_uses_placeholders(ctx):
    """A station ID containing a quote should return no rows."""
    before = _row_count(ctx)
    try:
        rows = _call(ctx, INJECTION, "2026-01-01", "2026-12-31")
    except Exception as exc:
        raise AssertionError(
            f"a station ID containing a quote (') caused {type(exc).__name__}. "
            "Use ? placeholders instead of putting values into the SQL text."
        ) from None
    expect(rows == [], f"the station ID {INJECTION} should match no rows, but {len(rows) if isinstance(rows, list) else 'some'} "
                       "came back. Use ? placeholders instead of putting values into the SQL text.")
    expect(_row_count(ctx) == before, "get_readings should not change the database.")
