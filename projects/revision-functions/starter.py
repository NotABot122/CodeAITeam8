"""Review: Functions

Step 1 is a short quiz. Step 2: write average_high and station_average below, then submit.
get_readings is done for you.
"""


def get_readings(conn, station_id, start_date, end_date):
    cursor = conn.execute(
        "SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
        "WHERE station_id = ? AND date >= ? AND date <= ? ORDER BY date",
        (station_id, start_date, end_date),
    )
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]


def average_high(rows):
    # Return the average temp_high_c, rounded to 1 decimal place, or None for no rows.
    pass


def station_average(conn, station_id, start_date, end_date):
    # Call get_readings, then your average_high, and return the result.
    pass
