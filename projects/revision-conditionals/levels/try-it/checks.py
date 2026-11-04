"""Review checks: rain_level."""
from engine.checklib import describe, expect

REQUIRED = {"rain_level": 1}
CASES = [(0.0, "none"), (0.1, "light"), (4.9, "light"), (5.0, "moderate"), (19.9, "moderate"),
         (20.0, "heavy"), (62.4, "heavy")]


def check_levels(ctx):
    """Each amount gets the right level, including every edge."""
    for rain, wanted in CASES:
        value = ctx.module.rain_level(rain)
        expect(value == wanted, f"{rain} mm should be \"{wanted}\", but was {describe(value)}.")
