"""Review: Database Retrieval

Step 1 is a short quiz. Step 2: fill in the blanks (____) below, then submit.
"""


def rainy_dates(conn, station_id, min_rain):
    rows = conn.execute(
        "SELECT date FROM daily_readings WHERE ____ ORDER BY date",
        (____),
    ).fetchall()
    dates = []
    for row in rows:
        dates.append(____)
    return dates
