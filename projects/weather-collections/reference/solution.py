"""Reference solution for Weather Station Part 2. Used only to check the tests."""


def hot_dates(rows, threshold):
    dates = []
    for row in rows:
        if row["temp_high_c"] >= threshold:
            dates.append(row["date"])
    dates.sort()
    return dates


def rain_by_station(rows):
    totals = {}
    for row in rows:
        station = row["station_id"]
        totals[station] = totals.get(station, 0.0) + row["rain_mm"]
    for station in totals:
        totals[station] = round(totals[station], 1)
    return totals


def days_by_month(rows):
    months = {}
    for row in rows:
        month = row["date"][:7]
        if month not in months:
            months[month] = []
        months[month].append(row["date"])
    for month in months:
        months[month].sort()
    return months


def station_summary(rows):
    totals = rain_by_station(rows)
    summary = {}
    for station in totals:
        mine = []
        for row in rows:
            if row["station_id"] == station:
                mine.append(row)
        summary[station] = {
            "hot_days": len(hot_dates(mine, 35.0)),
            "total_rain": totals[station],
            "months": len(days_by_month(mine)),
        }
    return summary


def first_and_last(rows):
    if not rows:
        return []
    dates = []
    for row in rows:
        dates.append(row["date"])
    dates.sort()
    return [dates[0], dates[-1]]


def count_labels(label_lists):
    counts = {}
    for labels in label_lists:
        for label in labels:
            counts[label] = counts.get(label, 0) + 1
    return counts
