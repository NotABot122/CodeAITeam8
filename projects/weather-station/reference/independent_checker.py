"""Independent computation of the Level 4 report.

Written separately from reference/solution.py. It uses SQL aggregation
instead of Python loops, so a bug in the reference solution won't be
repeated here.
"""

REPORT_SQL = """
SELECT
    COALESCE(SUM(CASE WHEN temp_high_c >= 35.0 THEN 1 ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN rain_mm >= 20.0 THEN 1 ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN temp_high_c < 35.0 AND rain_mm < 20.0 THEN 1 ELSE 0 END), 0),
    COALESCE(SUM(rain_mm), 0.0),
    MAX(temp_high_c)
FROM daily_readings
WHERE station_id = ? AND date BETWEEN ? AND ?
"""

FLAGGED_SQL = """
SELECT date FROM daily_readings
WHERE station_id = ? AND date BETWEEN ? AND ?
  AND (temp_high_c >= 35.0 OR rain_mm >= 20.0)
ORDER BY date
"""


def compute(conn, station_id, start_date, end_date):
    params = (station_id, start_date, end_date)
    heat, heavy, normal, rain, max_temp = conn.execute(REPORT_SQL, params).fetchone()
    flagged = [row[0] for row in conn.execute(FLAGGED_SQL, params)]
    return {
        "heat_wave_days": int(heat),
        "heavy_rain_days": int(heavy),
        "normal_days": int(normal),
        "total_rain_mm": round(float(rain), 1),
        "max_temp_c": max_temp,
        "flagged_dates": flagged,
    }
