"""Review checks: average_high and station_average."""
from engine.checklib import describe, expect, make_row

REQUIRED = {"get_readings": 4, "average_high": 1, "station_average": 4}


def check_average_high(ctx):
    """Averages and rounds, and gives None for no rows."""
    rows = [make_row("2026-01-01", 30.0, 0.0), make_row("2026-01-02", 31.0, 0.0), make_row("2026-01-03", 33.5, 0.0)]
    value = ctx.module.average_high(rows)
    expect(value == 31.5, f"the average of 30.0, 31.0, and 33.5 is 31.5, but you returned {describe(value)}.")
    value = ctx.module.average_high([])
    expect(value is None, f"no rows should give None, but gave {describe(value)}.")


def check_station_average(ctx):
    """station_average gives the right answer and uses get_readings and average_high."""
    module = ctx.module
    calls = []
    originals = {name: getattr(module, name) for name in ("get_readings", "average_high")}

    def wrap(name):
        def wrapper(*args, **kwargs):
            calls.append(name)
            return originals[name](*args, **kwargs)
        return wrapper

    conn = ctx.connect()
    try:
        for name in originals:
            setattr(module, name, wrap(name))
        value = module.station_average(conn, "ST-B", "2026-07-01", "2026-07-31")
    finally:
        for name, func in originals.items():
            setattr(module, name, func)
        conn.close()
    wanted = ctx.reference.average_high(ctx.db_rows("ST-B", "2026-07-01", "2026-07-31"))
    expect(value == wanted, f"ST-B's average high in July 2026 is {wanted}, but you returned {describe(value)}.")
    expect("get_readings" in calls and "average_high" in calls,
           "station_average should call get_readings and then your average_high.")
