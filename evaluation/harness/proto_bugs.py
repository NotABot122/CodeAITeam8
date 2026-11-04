"""Seeded bugs for the proto-branch weather-station lesson (E12 hint quality).

Each bug replaces one function of the reference solution. `gap` is the ground
truth the judge uses for H1 (does the hint name the student's actual gap).
The student file only holds the functions up to the bug's level, so the hint
model never sees code from later levels or the reference docstring.
"""
from __future__ import annotations

LEVEL_FUNCTIONS = {
    "level-1": ["get_readings"],
    "level-2": ["get_readings", "classify_day"],
    "level-3": ["get_readings", "classify_day", "summarize"],
    "level-4": ["get_readings", "classify_day", "summarize", "build_report"],
}

BUGS = [
    {
        "bug_id": "L1-exclusive-range", "level": "level-1", "function": "get_readings",
        "gap": "Uses > and < on the dates, so the start and end dates are left out.",
        "code": '''def get_readings(conn, station_id, start_date, end_date):
    cursor = conn.execute(
        "SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
        "WHERE station_id = ? AND date > ? AND date < ? ORDER BY date",
        (station_id, start_date, end_date),
    )
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, values)) for values in cursor.fetchall()]
''',
    },
    {
        "bug_id": "L1-tuples", "level": "level-1", "function": "get_readings",
        "gap": "Returns the raw tuples from fetchall() instead of one dictionary per row.",
        "code": '''def get_readings(conn, station_id, start_date, end_date):
    cursor = conn.execute(
        "SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
        "WHERE station_id = ? AND date >= ? AND date <= ? ORDER BY date",
        (station_id, start_date, end_date),
    )
    return cursor.fetchall()
''',
    },
    {
        "bug_id": "L1-string-concat", "level": "level-1", "function": "get_readings",
        "gap": "Builds the SQL by string concatenation without quotes or ? placeholders, so the query breaks (and is unsafe).",
        "code": '''def get_readings(conn, station_id, start_date, end_date):
    sql = ("SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
           "WHERE station_id = " + station_id + " AND date >= " + start_date + " AND date <= " + end_date)
    cursor = conn.execute(sql)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, values)) for values in cursor.fetchall()]
''',
    },
    {
        "bug_id": "L1-no-order", "level": "level-1", "function": "get_readings",
        "gap": "Missing ORDER BY date, so rows are not guaranteed oldest first.",
        "code": '''def get_readings(conn, station_id, start_date, end_date):
    cursor = conn.execute(
        "SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
        "WHERE station_id = ? AND date >= ? AND date <= ? ORDER BY rain_mm",
        (station_id, start_date, end_date),
    )
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, values)) for values in cursor.fetchall()]
''',
    },
    {
        "bug_id": "L2-strict-threshold", "level": "level-2", "function": "classify_day",
        "gap": "Uses > 35.0 and > 20.0, so exactly 35.0 / 20.0 are not labeled.",
        "code": '''def classify_day(row):
    labels = []
    if row["temp_high_c"] > HEAT_WAVE_C:
        labels.append("heat_wave")
    if row["rain_mm"] > HEAVY_RAIN_MM:
        labels.append("heavy_rain")
    if not labels:
        labels.append("normal")
    return labels
''',
    },
    {
        "bug_id": "L2-elif", "level": "level-2", "function": "classify_day",
        "gap": "Uses elif, so a day that is both hot and rainy gets only one label.",
        "code": '''def classify_day(row):
    labels = []
    if row["temp_high_c"] >= HEAT_WAVE_C:
        labels.append("heat_wave")
    elif row["rain_mm"] >= HEAVY_RAIN_MM:
        labels.append("heavy_rain")
    else:
        labels.append("normal")
    return labels
''',
    },
    {
        "bug_id": "L2-always-normal", "level": "level-2", "function": "classify_day",
        "gap": "Always appends 'normal', even when another label was added.",
        "code": '''def classify_day(row):
    labels = []
    if row["temp_high_c"] >= HEAT_WAVE_C:
        labels.append("heat_wave")
    if row["rain_mm"] >= HEAVY_RAIN_MM:
        labels.append("heavy_rain")
    labels.append("normal")
    return labels
''',
    },
    {
        "bug_id": "L3-builtins", "level": "level-3", "function": "summarize",
        "gap": "Uses sum(), max() and len() instead of computing the values in the loop (breaks the Level 3 loop rule).",
        "code": '''def summarize(readings):
    flagged_dates = []
    for row, labels in readings:
        if "normal" not in labels:
            flagged_dates.append(row["date"])
    flagged_dates.sort()
    return {
        "heat_wave_days": len([1 for r, l in readings if "heat_wave" in l]),
        "heavy_rain_days": len([1 for r, l in readings if "heavy_rain" in l]),
        "normal_days": len([1 for r, l in readings if "normal" in l]),
        "total_rain_mm": round(sum(r["rain_mm"] for r, l in readings), 1),
        "max_temp_c": max([r["temp_high_c"] for r, l in readings]) if readings else None,
        "flagged_dates": flagged_dates,
    }
''',
    },
    {
        "bug_id": "L3-max-zero", "level": "level-3", "function": "summarize",
        "gap": "Starts max_temp at 0, so an empty list returns 0 instead of None and all-negative temperatures are wrong.",
        "code": '''def summarize(readings):
    heat_wave_days = 0
    heavy_rain_days = 0
    normal_days = 0
    total_rain = 0.0
    max_temp = 0
    flagged_dates = []
    for row, labels in readings:
        if "heat_wave" in labels:
            heat_wave_days += 1
        if "heavy_rain" in labels:
            heavy_rain_days += 1
        if "normal" in labels:
            normal_days += 1
        else:
            flagged_dates.append(row["date"])
        total_rain += row["rain_mm"]
        if row["temp_high_c"] > max_temp:
            max_temp = row["temp_high_c"]
    flagged_dates.sort()
    return {"heat_wave_days": heat_wave_days, "heavy_rain_days": heavy_rain_days, "normal_days": normal_days,
            "total_rain_mm": round(total_rain, 1), "max_temp_c": max_temp, "flagged_dates": flagged_dates}
''',
    },
    {
        "bug_id": "L3-no-round-sort", "level": "level-3", "function": "summarize",
        "gap": "Does not round total rain to 1 decimal and does not sort flagged dates.",
        "code": '''def summarize(readings):
    heat_wave_days = 0
    heavy_rain_days = 0
    normal_days = 0
    total_rain = 0.0
    max_temp = None
    flagged_dates = []
    for row, labels in readings:
        if "heat_wave" in labels:
            heat_wave_days += 1
        if "heavy_rain" in labels:
            heavy_rain_days += 1
        if "normal" in labels:
            normal_days += 1
        else:
            flagged_dates.insert(0, row["date"])
        total_rain += row["rain_mm"]
        if max_temp is None or row["temp_high_c"] > max_temp:
            max_temp = row["temp_high_c"]
    return {"heat_wave_days": heat_wave_days, "heavy_rain_days": heavy_rain_days, "normal_days": normal_days,
            "total_rain_mm": total_rain, "max_temp_c": max_temp, "flagged_dates": flagged_dates}
''',
    },
    {
        "bug_id": "L4-reimplements-sql", "level": "level-4", "function": "build_report",
        "gap": "Writes a new SQL query instead of calling get_readings, classify_day and summarize.",
        "code": '''def build_report(conn, station_id, start_date, end_date):
    rows = conn.execute(
        "SELECT temp_high_c, rain_mm FROM daily_readings WHERE station_id = ? AND date >= ? AND date <= ?",
        (station_id, start_date, end_date)).fetchall()
    return {"heat_wave_days": len([r for r in rows if r[0] >= 35.0]),
            "heavy_rain_days": len([r for r in rows if r[1] >= 20.0])}
''',
    },
    {
        "bug_id": "L4-rows-not-pairs", "level": "level-4", "function": "build_report",
        "gap": "Passes the rows straight to summarize instead of (row, labels) pairs from classify_day.",
        "code": '''def build_report(conn, station_id, start_date, end_date):
    rows = get_readings(conn, station_id, start_date, end_date)
    return summarize(rows)
''',
    },
]
