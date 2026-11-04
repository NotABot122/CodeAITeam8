"""Reference solution for the lists review."""


def temps_above(rows, threshold):
    temps = []
    for row in rows:
        if row["temp_high_c"] >= threshold:
            temps.append(row["temp_high_c"])
    return temps
