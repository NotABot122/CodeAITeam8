"""Themed practice problems. Each project stub imports the matching block."""
from .common import INJECTION, db_rows, describe, expect, make_row, name_of, reference, spec_of, student


# Database retrieval practice: count rows in one group --------------------------------------
def check_count_each_group(ctx):
    """Each group has the right number of rows."""
    s = spec_of(ctx)
    conn = ctx.connect()
    try:
        for group in s.groups:
            value = student(ctx, "count")(conn, group)
            wanted = len(s.names[group])
            expect(value == wanted, f"{group} has {wanted} rows, but {name_of(ctx, 'count')} returned {describe(value)}.")
        value = student(ctx, "count")(conn, "Nowhere")
        expect(value == 0, f"a group with no rows should count 0, but was {describe(value)}.")
        try:
            value = student(ctx, "count")(conn, INJECTION)
        except Exception as exc:
            raise AssertionError(f"a group name containing a quote (') caused {type(exc).__name__}. "
                                 "Use a ? placeholder.") from None
        expect(value == 0, "a group name containing a quote should count 0 rows. Use a ? placeholder.")
    finally:
        conn.close()


# Conditionals practice: three bands for metric_a -------------------------------------------
def check_bands(ctx):
    """Each value gets the right band, including the edges."""
    s = spec_of(ctx)
    a, cut = s.metric_a, s.band_cutoff
    cases = [(a.threshold, "high"), (a.maximum, "high"), (round(a.threshold - 0.1, 1), "medium"),
             (cut, "medium"), (round(cut - 0.1, 1), "low"), (a.minimum, "low")]
    for value, wanted in cases:
        result = student(ctx, "band")(value)
        expect(result == wanted, f"a {a.column} of {value:g} should be \"{wanted}\", but was {describe(result)}.")


# Loops practice: count rows labeled with metric_b -------------------------------------------
def check_count_label(ctx):
    """Count rows at or over the metric_b threshold, in a short list, an empty list, and a whole group."""
    s = spec_of(ctx)
    b = s.metric_b
    rows = [make_row(ctx, 1, s.metric_a.minimum, b.threshold), make_row(ctx, 2, s.metric_a.minimum, b.minimum),
            make_row(ctx, 3, s.metric_a.minimum, b.maximum), make_row(ctx, 4, s.metric_a.minimum,
                                                                     round(b.threshold - 0.1, 1))]
    func = student(ctx, "count_label")
    value = func(rows)
    expect(value == 2, f"2 of these 4 rows have {b.column} of {b.threshold:g} or more, "
                       f"but {name_of(ctx, 'count_label')} returned {describe(value)}.")
    expect(func([]) == 0, f"an empty list should give 0, but {name_of(ctx, 'count_label')} returned {describe(func([]))}.")
    group = s.groups[2]
    whole = db_rows(ctx, group, 1, len(s.names[group]))
    wanted = reference(ctx, "count_label")(whole)
    value = func(whole)
    expect(value == wanted, f"{group} has {wanted} such rows, but {name_of(ctx, 'count_label')} returned {describe(value)}.")
