"""Independent computation of the Level 4 report, using SQL instead of Python loops."""

WHERE = "WHERE genre = ? AND shelf_number BETWEEN ? AND ?"


def compute(conn, group, start, end):
    params = (group, start, end)
    count_a, count_b, count_normal, total, highest = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN pages >= 400.0 THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN checkouts >= 30.0 THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN pages < 400.0 AND checkouts < 30.0 THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(checkouts), 0.0), MAX(pages) FROM library_books " + WHERE, params).fetchone()
    flagged = [row[0] for row in conn.execute(
        "SELECT shelf_number FROM library_books " + WHERE +
        " AND (pages >= 400.0 OR checkouts >= 30.0) ORDER BY shelf_number", params)]
    return {
        "long_count": int(count_a),
        "popular_count": int(count_b),
        "regular_count": int(count_normal),
        "total_checkouts": round(float(total), 1),
        "max_pages": highest,
        "flagged_shelf_numbers": flagged,
    }
