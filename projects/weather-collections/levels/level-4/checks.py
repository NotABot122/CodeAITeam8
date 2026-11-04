"""Part 2, Level 4 checks: station_summary."""
from engine.checklib import describe, expect

REQUIRED = {"hot_dates": 2, "rain_by_station": 1, "days_by_month": 1, "station_summary": 1}
HELPERS = ("hot_dates", "rain_by_station", "days_by_month")


def check_january(ctx):
    """The summary for January at all three stations is right."""
    rows = [r for r in ctx.db_rows() if r["date"].startswith("2026-01")]
    wanted = ctx.reference.station_summary(rows)
    value = ctx.module.station_summary(rows)
    expect(isinstance(value, dict), f"station_summary should return a dictionary, but it returned {describe(value)}.")
    expect(sorted(value) == sorted(wanted), f"the summary should have the stations {sorted(wanted)} as keys.")
    for station in wanted:
        expect(value[station] == wanted[station],
               f"for {station} in January the summary should be {wanted[station]}, but was {describe(value[station], 90)}.")


def check_whole_year(ctx):
    """The summary for the whole year is right."""
    rows = ctx.db_rows()
    expect(ctx.module.station_summary(rows) == ctx.reference.station_summary(rows),
           "the summary for the whole year doesn't match.")


def check_empty(ctx):
    """No rows gives an empty dictionary."""
    value = ctx.module.station_summary([])
    expect(value == {}, f"no rows should give {{}}, but gave {describe(value)}.")


def check_uses_your_functions(ctx):
    """station_summary should call rain_by_station once, and hot_dates and days_by_month once per station."""
    module = ctx.module
    originals = {name: getattr(module, name) for name in HELPERS}
    calls = []

    def wrap(name):
        def wrapper(*args, **kwargs):
            calls.append(name)
            return originals[name](*args, **kwargs)
        return wrapper

    rows = [r for r in ctx.db_rows() if r["date"].startswith("2026-03")]
    try:
        for name in HELPERS:
            setattr(module, name, wrap(name))
        module.station_summary(rows)
    finally:
        for name, func in originals.items():
            setattr(module, name, func)
    missing = [name for name in HELPERS if name not in calls]
    expect(not missing, f"station_summary should call your {', '.join(missing)} function(s).")
    expect(calls.count("rain_by_station") == 1, "station_summary should call rain_by_station exactly once.")
    expect(calls.count("hot_dates") == 3 and calls.count("days_by_month") == 3,
           "with 3 stations, station_summary should call hot_dates and days_by_month once per station.")
