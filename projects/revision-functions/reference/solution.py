"""Reference solution for the functions review."""


def get_readings(conn, station_id, start_date, end_date):
    cursor = conn.execute(
        "SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
        "WHERE station_id = ? AND date >= ? AND date <= ? ORDER BY date",
        (station_id, start_date, end_date),
    )
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]


def average_high(rows):
    if not rows:
        return None
    total = 0.0
    count = 0
    for row in rows:
        total += row["temp_high_c"]
        count += 1
    return round(total / count, 1)


def station_average(conn, station_id, start_date, end_date):
    rows = get_readings(conn, station_id, start_date, end_date)
    return average_high(rows)
