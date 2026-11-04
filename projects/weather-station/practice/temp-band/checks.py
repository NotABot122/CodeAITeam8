"""Practice checks: temp_band."""
from engine.checklib import describe, expect

REQUIRED = {"temp_band": 1}

CASES = [(35.0, "hot"), (48.2, "hot"), (34.9, "warm"), (20.0, "warm"), (19.9, "cool"), (-5.0, "cool")]


def check_bands(ctx):
    """Each temperature gets the right band, including the edges."""
    for temp, wanted in CASES:
        value = ctx.module.temp_band(temp)
        expect(value == wanted, f"a temperature of {temp} should be \"{wanted}\", but was {describe(value)}.")
