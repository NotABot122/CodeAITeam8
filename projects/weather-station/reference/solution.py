"""Reference solution for the Weather Station Project.

Used only to check the tests and expected values. Never shown to students.
"""

HEAT_WAVE_C = 35.0
HEAVY_RAIN_MM = 20.0


# Level 1
def get_readings(conn, station_id, start_date, end_date):
    cursor = conn.execute(
        "SELECT station_id, date, temp_high_c, temp_low_c, rain_mm "
        "FROM daily_readings "
        "WHERE station_id = ? AND date >= ? AND date <= ? "
        "ORDER BY date",
        (station_id, start_date, end_date),
    )
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, values)) for values in cursor.fetchall()]


# Level 2
def classify_day(row):
    labels = []
    if row["temp_high_c"] >= HEAT_WAVE_C:
        labels.append("heat_wave")
    if row["rain_mm"] >= HEAVY_RAIN_MM:
        labels.append("heavy_rain")
    if not labels:
        labels.append("normal")
    return labels


# Level 3
def summarize(readings):
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
            flagged_dates.append(row["date"])
        total_rain += row["rain_mm"]
        if max_temp is None or row["temp_high_c"] > max_temp:
            max_temp = row["temp_high_c"]
    flagged_dates.sort()
    return {
        "heat_wave_days": heat_wave_days,
        "heavy_rain_days": heavy_rain_days,
        "normal_days": normal_days,
        "total_rain_mm": round(total_rain, 1),
        "max_temp_c": max_temp,
        "flagged_dates": flagged_dates,
    }


# Level 4
def build_report(conn, station_id, start_date, end_date):
    rows = get_readings(conn, station_id, start_date, end_date)
    readings = []
    for row in rows:
        readings.append((row, classify_day(row)))
    return summarize(readings)


# Practice: Database Retrieval
def count_readings(conn, station_id):
    cursor = conn.execute("SELECT COUNT(*) FROM daily_readings WHERE station_id = ?", (station_id,))
    return cursor.fetchone()[0]


# Practice: Conditionals
def temp_band(temp_high_c):
    if temp_high_c >= 35.0:
        return "hot"
    elif temp_high_c >= 20.0:
        return "warm"
    else:
        return "cool"


# Practice: Loops
def count_rainy_days(rows):
    count = 0
    for row in rows:
        if row["rain_mm"] > 0:
            count += 1
    return count
