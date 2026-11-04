"""Level 2 checks: classify_day."""
import random

from engine.checklib import describe, expect, make_row

REQUIRED = {"classify_day": 1}

LABELS = ("heat_wave", "heavy_rain", "normal")


def _labels(ctx, temp, rain):
    return ctx.module.classify_day(make_row("2026-07-01", temp, rain))


def check_returns_list_of_labels(ctx):
    """classify_day should return a list of label strings."""
    result = _labels(ctx, 20.0, 0.0)
    expect(isinstance(result, list), f"classify_day should return a list, but it returned {describe(result)}.")
    expect(all(label in LABELS for label in result),
           f"labels must be \"heat_wave\", \"heavy_rain\", or \"normal\", but got {describe(result)}.")
    expect(len(result) == len(set(result)), f"each label should appear only once, but got {describe(result)}.")


def check_heat_wave_boundary(ctx):
    """35.0 is a heat wave and 34.9 is not."""
    result = _labels(ctx, 35.0, 0.0)
    expect(result == ["heat_wave"], f"a temperature of 35.0 should count as a heat wave (got {describe(result)}).")
    result = _labels(ctx, 34.9, 0.0)
    expect(result == ["normal"], f"a temperature of 34.9 is not a heat wave, so it should be normal (got {describe(result)}).")


def check_heavy_rain_boundary(ctx):
    """20.0 mm is heavy rain and 19.9 mm is not."""
    result = _labels(ctx, 20.0, 20.0)
    expect(result == ["heavy_rain"], f"rainfall of 20.0 mm should count as heavy rain (got {describe(result)}).")
    result = _labels(ctx, 20.0, 19.9)
    expect(result == ["normal"], f"rainfall of 19.9 mm is not heavy rain, so it should be normal (got {describe(result)}).")


def check_both_labels(ctx):
    """A day that meets both thresholds gets both labels, heat wave first."""
    for temp, rain in ((35.0, 20.0), (41.3, 55.0)):
        result = _labels(ctx, temp, rain)
        expect(result == ["heat_wave", "heavy_rain"],
               f"{temp} °C with {rain} mm should return [\"heat_wave\", \"heavy_rain\"] (got {describe(result)}).")


def check_normal_day(ctx):
    """A day under both thresholds is normal."""
    for temp, rain in ((12.0, 0.0), (-5.0, 3.2), (34.9, 19.9)):
        result = _labels(ctx, temp, rain)
        expect(result == ["normal"], f"{temp} °C with {rain} mm should return [\"normal\"] (got {describe(result)}).")


def check_does_not_change_row(ctx):
    """classify_day should not change the row it is given."""
    row = make_row("2026-07-01", 36.0, 25.0)
    before = dict(row)
    ctx.module.classify_day(row)
    expect(row == before, "classify_day should not change the row dictionary it is given.")


def check_matches_every_day(ctx):
    """classify_day should label every day in the database correctly."""
    rng = random.Random(7)
    rows = ctx.db_rows()
    rows += [make_row("2026-08-01", round(rng.uniform(-30.0, 50.0), 1), round(rng.uniform(0.0, 100.0), 1))
             for _ in range(150)]
    for row in rows:
        temp, rain = row["temp_high_c"], row["rain_mm"]
        try:
            result = ctx.module.classify_day(dict(row))
        except Exception as exc:
            raise AssertionError(f"{temp} °C with {rain} mm raised {type(exc).__name__}: {exc}") from None
        expect(isinstance(result, list), f"{temp} °C with {rain} mm returned {describe(result)}, not a list.")
        wanted = ctx.reference.classify_day(dict(row))
        expect(result == wanted, f"{temp} °C with {rain} mm should return {wanted}, but returned {describe(result)}.")
