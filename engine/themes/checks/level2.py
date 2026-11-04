"""Themed Level 2: label one row with conditionals."""
import random

from .common import db_rows, describe, expect, low, make_row, name_of, reference, spec_of, student


def _labels(ctx, a, b):
    return student(ctx, "classify")(make_row(ctx, 1, a, b))


def check_returns_list_of_labels(ctx):
    """The function should return a list of label strings."""
    s = spec_of(ctx)
    allowed = (s.metric_a.label, s.metric_b.label, s.normal_label)
    result = _labels(ctx, low(s.metric_a), low(s.metric_b))
    expect(isinstance(result, list), f"{name_of(ctx, 'classify')} should return a list, but it returned {describe(result)}.")
    expect(all(label in allowed for label in result),
           f"labels must be one of {', '.join(repr(x) for x in allowed)}, but got {describe(result)}.")
    expect(len(result) == len(set(result)), f"each label should appear only once, but got {describe(result)}.")


def check_metric_a_boundary(ctx):
    """Exactly the threshold counts, and 0.1 below it doesn't."""
    s = spec_of(ctx)
    a, la, nl = s.metric_a, s.metric_a.label, s.normal_label
    result = _labels(ctx, a.threshold, low(s.metric_b))
    expect(result == [la], f"{a.column} of {a.threshold:g} should count as {la!r} (got {describe(result)}).")
    under = round(a.threshold - 0.1, 1)
    result = _labels(ctx, under, low(s.metric_b))
    expect(result == [nl], f"{a.column} of {under:g} is under {a.threshold:g}, so it should be {nl!r} "
                           f"(got {describe(result)}).")


def check_metric_b_boundary(ctx):
    """Exactly the threshold counts, and 0.1 below it doesn't."""
    s = spec_of(ctx)
    b, lb, nl = s.metric_b, s.metric_b.label, s.normal_label
    result = _labels(ctx, low(s.metric_a), b.threshold)
    expect(result == [lb], f"{b.column} of {b.threshold:g} should count as {lb!r} (got {describe(result)}).")
    under = round(b.threshold - 0.1, 1)
    result = _labels(ctx, low(s.metric_a), under)
    expect(result == [nl], f"{b.column} of {under:g} is under {b.threshold:g}, so it should be {nl!r} "
                           f"(got {describe(result)}).")


def check_both_labels(ctx):
    """A row over both thresholds gets both labels, in order."""
    s = spec_of(ctx)
    wanted = [s.metric_a.label, s.metric_b.label]
    for a, b in ((s.metric_a.threshold, s.metric_b.threshold), (s.metric_a.maximum, s.metric_b.maximum)):
        result = _labels(ctx, a, b)
        expect(result == wanted, f"{s.metric_a.column} {a:g} with {s.metric_b.column} {b:g} should return "
                                 f"{wanted} (got {describe(result)}).")


def check_normal_row(ctx):
    """A row under both thresholds gets only the normal label."""
    s = spec_of(ctx)
    for a, b in ((s.metric_a.minimum, s.metric_b.minimum), (low(s.metric_a, 0.7), low(s.metric_b, 0.5))):
        result = _labels(ctx, a, b)
        expect(result == [s.normal_label], f"{s.metric_a.column} {a:g} with {s.metric_b.column} {b:g} should return "
                                           f"[{s.normal_label!r}] (got {describe(result)}).")


def check_does_not_change_row(ctx):
    """The function should not change the row it is given."""
    s = spec_of(ctx)
    row = make_row(ctx, 1, s.metric_a.maximum, s.metric_b.maximum)
    before = dict(row)
    student(ctx, "classify")(row)
    expect(row == before, f"{name_of(ctx, 'classify')} should not change the row dictionary it is given.")


def check_matches_every_row(ctx):
    """Every row in the database, plus random rows, gets the right labels."""
    s = spec_of(ctx)
    rng = random.Random(7)
    rows = db_rows(ctx)
    rows += [make_row(ctx, 1, round(rng.uniform(s.metric_a.minimum, s.metric_a.maximum), 1),
                      round(rng.uniform(s.metric_b.minimum, s.metric_b.maximum), 1)) for _ in range(150)]
    for row in rows:
        a, b = row[s.metric_a.column], row[s.metric_b.column]
        try:
            result = student(ctx, "classify")(dict(row))
        except Exception as exc:
            raise AssertionError(f"{s.metric_a.column} {a:g} with {s.metric_b.column} {b:g} raised "
                                 f"{type(exc).__name__}: {exc}") from None
        wanted = reference(ctx, "classify")(dict(row))
        expect(result == wanted, f"{s.metric_a.column} {a:g} with {s.metric_b.column} {b:g} should return {wanted}, "
                                 f"but returned {describe(result)}.")
