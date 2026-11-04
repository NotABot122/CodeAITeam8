"""Practice checks: count_labels."""
from engine.checklib import describe, expect

REQUIRED = {"count_labels": 1}


def check_counts(ctx):
    """Counts each label across all lists."""
    value = ctx.module.count_labels([["heat_wave"], ["normal"], ["heat_wave", "heavy_rain"]])
    wanted = {"heat_wave": 2, "normal": 1, "heavy_rain": 1}
    expect(value == wanted, f"the example should give {wanted}, but gave {describe(value)}.")
    expect(ctx.module.count_labels([]) == {}, "no lists should give {}.")
    many = [["normal"]] * 40 + [["heavy_rain"]] * 3
    value = ctx.module.count_labels(many)
    expect(value == {"normal": 40, "heavy_rain": 3}, f"40 normal and 3 heavy_rain lists gave {describe(value)}.")
