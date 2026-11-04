"""Level 4 checks: build_report."""
import inspect

from engine.checklib import describe, expect, read_rows

REQUIRED = {"get_readings": 4, "classify_day": 1, "summarize": 1, "build_report": 4}

HELPERS = ("get_readings", "classify_day", "summarize")


def _expected(ctx, station_id, start_date, end_date):
    for entry in ctx.expected_reports:
        args = entry["args"]
        if (args["station_id"], args["start_date"], args["end_date"]) == (station_id, start_date, end_date):
            return entry["report"]
    raise AssertionError(f"no stored expected report for {station_id} {start_date} to {end_date} (content problem).")


def _report(ctx, station_id, start_date, end_date):
    conn = ctx.connect()
    try:
        return ctx.module.build_report(conn, station_id, start_date, end_date)
    finally:
        conn.close()


def _compare(ctx, station_id, start_date, end_date):
    result = _report(ctx, station_id, start_date, end_date)
    expect(isinstance(result, dict), f"build_report should return a dictionary, but it returned {describe(result)}.")
    wanted = _expected(ctx, station_id, start_date, end_date)
    wrong = [key for key in wanted if result.get(key) != wanted[key]]
    extra = [str(key) for key in result if key not in wanted]
    expect(not wrong and not extra,
           f"the report for {station_id} from {start_date} to {end_date} has wrong values for "
           f"{', '.join(wrong + extra)}.")


def check_january_report(ctx):
    """The ST-A report for January 2026 should match the stored answer."""
    _compare(ctx, "ST-A", "2026-01-01", "2026-01-31")


def check_second_report(ctx):
    """The ST-B report for July 1 to 14 should match the stored answer."""
    _compare(ctx, "ST-B", "2026-07-01", "2026-07-14")


def check_empty_report(ctx):
    """A range with no data should give the empty summary without an error."""
    result = _report(ctx, "ST-A", "2027-01-01", "2027-01-31")
    wanted = {"heat_wave_days": 0, "heavy_rain_days": 0, "normal_days": 0, "total_rain_mm": 0,
              "max_temp_c": ctx.params.get("empty_max_temp_c"), "flagged_dates": []}
    expect(isinstance(result, dict) and all(result.get(k) == v for k, v in wanted.items()),
           f"a range with no data (2027) should give zero counts and max_temp_c {wanted['max_temp_c']!r}, "
           f"but gave {describe(result, 90)}.")


def check_database_unchanged(ctx):
    """build_report should not change the database."""
    before = read_rows(ctx.db_path)
    _report(ctx, "ST-C", "2026-03-01", "2026-03-31")
    expect(read_rows(ctx.db_path) == before, "build_report should not change the database.")


def check_same_result_twice(ctx):
    """Two calls with the same arguments should return the same report."""
    first = _report(ctx, "ST-A", "2026-02-01", "2026-02-28")
    second = _report(ctx, "ST-A", "2026-02-01", "2026-02-28")
    expect(first == second, "calling build_report twice with the same arguments gave different reports.")


def check_uses_your_functions(ctx):
    """build_report should call get_readings once, classify_day for each row, then summarize once."""
    module = ctx.module
    originals = {name: getattr(module, name) for name in HELPERS}
    calls = []

    def wrap(name):
        func = originals[name]

        def wrapper(*args, **kwargs):
            calls.append((name, inspect.signature(func).bind(*args, **kwargs).arguments))
            return func(*args, **kwargs)
        return wrapper

    conn = ctx.connect()
    try:
        for name in HELPERS:
            setattr(module, name, wrap(name))
        module.build_report(conn, "ST-A", "2026-01-01", "2026-01-07")
    finally:
        for name, func in originals.items():
            setattr(module, name, func)
        conn.close()

    names = [name for name, _ in calls]
    not_called = [name for name in HELPERS if name not in names]
    expect(not not_called, f"build_report should call your {', '.join(not_called)} function(s).")
    expect(names.count("get_readings") == 1, "build_report should call get_readings exactly once.")
    args = list(calls[names.index("get_readings")][1].values())
    expect(args[0] is conn and args[1:] == ["ST-A", "2026-01-01", "2026-01-07"],
           "build_report should pass its conn, station_id, start_date, and end_date to get_readings.")
    expect(names.count("classify_day") == 7,
           f"for 7 days, build_report should call classify_day 7 times, but called it {names.count('classify_day')} times.")
    expect(names.count("summarize") == 1, "build_report should call summarize exactly once.")
    expect(names[0] == "get_readings" and names[-1] == "summarize",
           "build_report should call get_readings first and summarize last.")
