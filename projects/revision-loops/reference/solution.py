"""Reference solution for the loops review."""


def wettest_day(rows):
    most_rain = None
    wettest = None
    for row in rows:
        if most_rain is None or row["rain_mm"] > most_rain:
            most_rain = row["rain_mm"]
            wettest = row["date"]
    return wettest
