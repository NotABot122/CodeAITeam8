"""Reference solution for the dictionaries review."""


def days_per_station(rows):
    counts = {}
    for row in rows:
        station = row["station_id"]
        counts[station] = counts.get(station, 0) + 1
    return counts
