"""Themed Level 3: summarize classified rows with a loop. The loop rule is checked by the engine."""
import random

from .common import db_rows, describe, expect, low, make_row, name_of, reference, spec_of, student


def _hand(ctx):
    """Seven rows with known answers. Numbers are out of order; the highest metric_a is in the middle."""
    s = spec_of(ctx)
    a, b = s.metric_a, s.metric_b
    lo_a, lo_b = low(a), low(b)
    raw = [
        (5, a.threshold, lo_b),                                     # metric_a label
        (1, lo_a, b.threshold),                                     # metric_b label
        (3, round(a.threshold + 1, 1), round(b.threshold + 1, 1)),  # both
        (2, lo_a, lo_b),                                            # normal
        (4, a.maximum, low(b, 0.1)),                                # metric_a label, highest
        (7, round(a.threshold - 0.1, 1), round(b.threshold - 0.1, 1)),  # normal, just under both
        (6, low(a, 0.6), low(b, 0.6)),                              # normal
    ]
    rows = [make_row(ctx, n, va, vb) for n, va, vb in raw]
    k = s.summary_keys
    expected = {k["count_a"]: 3, k["count_b"]: 2, k["count_normal"]: 3,
                k["total_b"]: round(sum(r[b.column] for r in rows), 1), k["max_a"]: a.maximum,
                k["flagged"]: [1, 3, 4, 5]}
    return [(row, reference(ctx, "classify")(row)) for row in rows], expected


def _summary(ctx, readings):
    result = student(ctx, "summarize")(readings)
    expect(isinstance(result, dict), f"{name_of(ctx, 'summarize')} should return a dictionary, "
                                     f"but it returned {describe(result)}.")
    return result


def check_keys(ctx):
    """The summary should have exactly the six keys."""
    readings, expected = _hand(ctx)
    result = _summary(ctx, readings)
    missing = sorted(set(expected) - set(result))
    extra = sorted(set(map(str, result)) - set(expected))
    expect(not missing, f"the summary is missing {', '.join(missing)}.")
    expect(not extra, f"the summary has extra keys: {', '.join(extra)}.")


def check_counts(ctx):
    """Counts should match a hand-checked list of 7 rows."""
    s = spec_of(ctx)
    readings, expected = _hand(ctx)
    result = _summary(ctx, readings)
    for role in ("count_a", "count_b", "count_normal"):
        key = s.summary_keys[role]
        expect(result.get(key) == expected[key],
               f"for 7 test rows, {key} should be {expected[key]}, but was {describe(result.get(key))}.")


def check_total(ctx):
    """The total should add up every value, rounded to 1 decimal place."""
    key = spec_of(ctx).summary_keys["total_b"]
    readings, expected = _hand(ctx)
    value = _summary(ctx, readings).get(key)
    expect(isinstance(value, (int, float)) and value == expected[key],
           f"{key} for 7 test rows should be {expected[key]} (rounded to 1 decimal place), but was {describe(value)}.")


def check_max(ctx):
    """The maximum should be found even when it is in the middle of the list."""
    key = spec_of(ctx).summary_keys["max_a"]
    readings, expected = _hand(ctx)
    value = _summary(ctx, readings).get(key)
    expect(value == expected[key],
           f"{key} should be {expected[key]:g}, the highest value in the middle of the list, but was {describe(value)}.")


def check_flagged(ctx):
    """Flagged numbers: every non-normal row once, smallest first."""
    key = spec_of(ctx).summary_keys["flagged"]
    readings, expected = _hand(ctx)
    value = _summary(ctx, readings).get(key)
    expect(value == expected[key], f"{key} should be {expected[key]} (smallest first), but was {describe(value)}.")


def check_empty_input(ctx):
    """An empty list gives zeros, no flagged numbers, and None for the maximum."""
    s = spec_of(ctx)
    result = _summary(ctx, [])
    k = s.summary_keys
    for role in ("count_a", "count_b", "count_normal", "total_b"):
        expect(result.get(k[role]) == 0, f"with no rows, {k[role]} should be 0, but was {describe(result.get(k[role]))}.")
    expect(result.get(k["flagged"]) == [], f"with no rows, {k['flagged']} should be [].")
    expect(k["max_a"] in result and result[k["max_a"]] is None,
           f"with no rows, {k['max_a']} should be None, but was {describe(result.get(k['max_a']))}.")


def check_matches_many_lists(ctx):
    """The summary is right for many random sets of rows."""
    s = spec_of(ctx)
    rng = random.Random(11)
    rows = db_rows(ctx)
    k = s.summary_keys
    for _ in range(100):
        sample = rng.sample(rows, rng.randint(0, len(rows)))
        readings = [(row, reference(ctx, "classify")(row)) for row in sample]
        result = _summary(ctx, readings)
        wanted = reference(ctx, "summarize")(readings)
        both = 0
        for _row, labels in readings:
            if s.metric_a.label in labels and s.metric_b.label in labels:
                both += 1
        counted = (result.get(k["count_a"]) or 0) + (result.get(k["count_b"]) or 0) - both \
            + (result.get(k["count_normal"]) or 0)
        expect(counted == len(readings), f"for {len(readings)} random rows, the counts don't add up to the number of rows.")
        for key, value in wanted.items():
            expect(result.get(key) == value, f"for {len(readings)} random rows, {key} should be {describe(value)}, "
                                             f"but was {describe(result.get(key))}.")
