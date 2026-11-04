"""Independent computation of the Level 4 report, using SQL instead of Python loops."""

WHERE = "WHERE zone = ? AND monster_number BETWEEN ? AND ?"


def compute(conn, group, start, end):
    params = (group, start, end)
    count_a, count_b, count_normal, total, highest = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN power >= 70.0 THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN speed >= 60.0 THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN power < 70.0 AND speed < 60.0 THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(speed), 0.0), MAX(power) FROM monsters " + WHERE, params).fetchone()
    flagged = [row[0] for row in conn.execute(
        "SELECT monster_number FROM monsters " + WHERE +
        " AND (power >= 70.0 OR speed >= 60.0) ORDER BY monster_number", params)]
    return {
        "strong_count": int(count_a),
        "fast_count": int(count_b),
        "balanced_count": int(count_normal),
        "total_speed": round(float(total), 1),
        "max_power": highest,
        "flagged_monster_numbers": flagged,
    }
