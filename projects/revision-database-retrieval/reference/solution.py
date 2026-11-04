"""Reference solution for the database retrieval review."""


def rainy_dates(conn, station_id, min_rain):
    rows = conn.execute(
        "SELECT date FROM daily_readings WHERE station_id = ? AND rain_mm >= ? ORDER BY date",
        (station_id, min_rain),
    ).fetchall()
    dates = []
    for row in rows:
        dates.append(row[0])
    return dates
