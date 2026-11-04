"""Independent computation of the Level 4 report, using SQL instead of Python loops."""

WHERE = "WHERE park = ? AND tag_number BETWEEN ? AND ?"


def compute(conn, group, start, end):
    params = (group, start, end)
    count_a, count_b, count_normal, total, highest = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN weight_kg >= 100.0 THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN daily_km >= 15.0 THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN weight_kg < 100.0 AND daily_km < 15.0 THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(daily_km), 0.0), MAX(weight_kg) FROM tagged_animals " + WHERE, params).fetchone()
    flagged = [row[0] for row in conn.execute(
        "SELECT tag_number FROM tagged_animals " + WHERE +
        " AND (weight_kg >= 100.0 OR daily_km >= 15.0) ORDER BY tag_number", params)]
    return {
        "heavy_count": int(count_a),
        "roamer_count": int(count_b),
        "typical_count": int(count_normal),
        "total_daily_km": round(float(total), 1),
        "max_weight_kg": highest,
        "flagged_tag_numbers": flagged,
    }
