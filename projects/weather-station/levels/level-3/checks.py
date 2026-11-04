"""Level 3 checks: summarize. The loop rules are checked separately by the engine."""
import random

from engine.checklib import describe, expect, make_row

REQUIRED = {"summarize": 1}

KEYS = {"heat_wave_days", "heavy_rain_days", "normal_days", "total_rain_mm", "max_temp_c", "flagged_dates"}

# Hand-checked input. Dates are out of order on purpose, and the highest
# temperature (37.9) is neither first nor last.
HAND_ROWS = [
    ("2026-03-05", 35.0, 0.0),    # heat wave (boundary)
    ("2026-03-01", 22.0, 20.0),   # heavy rain (boundary)
    ("2026-03-03", 36.5, 25.2),   # both
    ("2026-03-02", 18.0, 3.1),    # normal
    ("2026-03-04", 37.9, 0.4),    # heat wave, highest
    ("2026-03-07", 34.9, 19.9),   # normal (just under both)
    ("2026-03-06", 21.0, 0.0),    # normal
]
HAND_EXPECTED = {
    "heat_wave_days": 3,
    "heavy_rain_days": 2,
    "normal_days": 3,
    "total_rain_mm": 68.6,
    "max_temp_c": 37.9,
    "flagged_dates": ["2026-03-01", "2026-03-03", "2026-03-04", "2026-03-05"],
}


def _classified(ctx, rows):
    return [(row, ctx.reference.classify_day(row)) for row in rows]


def _hand_input(ctx):
    return _classified(ctx, [make_row(d, t, r) for d, t, r in HAND_ROWS])


def _summary(ctx, readings):
    result = ctx.module.summarize(readings)
    expect(isinstance(result, dict), f"summarize should return a dictionary, but it returned {describe(result)}.")
    return result


def check_keys(ctx):
    """summarize should return a dictionary with exactly the six keys."""
    result = _summary(ctx, _hand_input(ctx))
    missing = sorted(KEYS - set(result))
    extra = sorted(set(map(str, result)) - KEYS)
    expect(not missing, f"the summary is missing {', '.join(missing)}.")
    expect(not extra, f"the summary has extra keys: {', '.join(extra)}.")


def check_counts(ctx):
    """Counts should match a hand-checked list of 7 days."""
    result = _summary(ctx, _hand_input(ctx))
    for key in ("heat_wave_days", "heavy_rain_days", "normal_days"):
        expect(result.get(key) == HAND_EXPECTED[key],
               f"for 7 test days, {key} should be {HAND_EXPECTED[key]}, but was {describe(result.get(key))}.")


def check_total_rain(ctx):
    """total_rain_mm should be all rainfall added up, rounded to 1 decimal place."""
    value = _summary(ctx, _hand_input(ctx)).get("total_rain_mm")
    expect(isinstance(value, (int, float)) and round(value, 1) == HAND_EXPECTED["total_rain_mm"] and value == round(value, 1),
           f"total_rain_mm for 7 test days should be {HAND_EXPECTED['total_rain_mm']} (rounded to 1 decimal place), "
           f"but was {describe(value)}.")


def check_max_temp(ctx):
    """max_temp_c should be the highest temperature, even when it is in the middle of the list."""
    value = _summary(ctx, _hand_input(ctx)).get("max_temp_c")
    expect(value == HAND_EXPECTED["max_temp_c"],
           f"max_temp_c should be 37.9, the highest temperature in the middle of the list, but was {describe(value)}.")


def check_flagged_dates(ctx):
    """flagged_dates should list every non-normal date once, oldest first."""
    value = _summary(ctx, _hand_input(ctx)).get("flagged_dates")
    expect(value == HAND_EXPECTED["flagged_dates"],
           f"flagged_dates should be {HAND_EXPECTED['flagged_dates']} (oldest first), but was {describe(value, 90)}.")


def check_empty_input(ctx):
    """An empty list should give zeros, no flagged dates, and the empty max temperature."""
    result = _summary(ctx, [])
    empty_max = ctx.params.get("empty_max_temp_c")
    for key in ("heat_wave_days", "heavy_rain_days", "normal_days", "total_rain_mm"):
        expect(result.get(key) == 0, f"with no readings, {key} should be 0, but was {describe(result.get(key))}.")
    expect(result.get("flagged_dates") == [], "with no readings, flagged_dates should be [].")
    expect(result.get("max_temp_c") == empty_max and "max_temp_c" in result,
           f"with no readings, max_temp_c should be {empty_max!r}, but was {describe(result.get('max_temp_c'))}.")


def check_matches_many_ranges(ctx):
    """summarize should give the right answer for many random sets of days."""
    rng = random.Random(11)
    rows = ctx.db_rows()
    for trial in range(100):
        sample = rng.sample(rows, rng.randint(0, 365))
        readings = _classified(ctx, sample)
        result = _summary(ctx, readings)
        wanted = ctx.reference.summarize(readings)
        both = 0
        for _, labels in readings:
            if "heat_wave" in labels and "heavy_rain" in labels:
                both += 1
        counted = (result.get("heat_wave_days", 0) or 0) + (result.get("heavy_rain_days", 0) or 0) \
            - both + (result.get("normal_days", 0) or 0)
        expect(counted == len(readings),
               f"for {len(readings)} random days, the day counts don't add up to the number of days.")
        for key, value in wanted.items():
            expect(result.get(key) == value,
                   f"for {len(readings)} random days, {key} should be {describe(value)}, "
                   f"but was {describe(result.get(key))}.")
