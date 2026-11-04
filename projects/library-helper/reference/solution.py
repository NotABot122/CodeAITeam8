"""Reference solution for Library Helper. Used only to check the tests. Never shown to students."""


def get_books(conn, genre, start_number, end_number):
    cursor = conn.execute(
        "SELECT genre, shelf_number, title, pages, checkouts FROM library_books "
        "WHERE genre = ? AND shelf_number >= ? AND shelf_number <= ? ORDER BY shelf_number",
        (genre, start_number, end_number),
    )
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]


def classify_book(entry):
    labels = []
    if entry["pages"] >= 400.0:
        labels.append("long")
    if entry["checkouts"] >= 30.0:
        labels.append("popular")
    if not labels:
        labels.append("regular")
    return labels


def summarize_books(entries):
    count_a = 0
    count_b = 0
    count_normal = 0
    total = 0.0
    highest = None
    flagged = []
    for entry, labels in entries:
        if "long" in labels:
            count_a += 1
        if "popular" in labels:
            count_b += 1
        if "regular" in labels:
            count_normal += 1
        else:
            flagged.append(entry["shelf_number"])
        total += entry["checkouts"]
        if highest is None or entry["pages"] > highest:
            highest = entry["pages"]
    flagged.sort()
    return {
        "long_count": count_a,
        "popular_count": count_b,
        "regular_count": count_normal,
        "total_checkouts": round(total, 1),
        "max_pages": highest,
        "flagged_shelf_numbers": flagged,
    }


def build_book_report(conn, genre, start_number, end_number):
    rows = get_books(conn, genre, start_number, end_number)
    entries = []
    for row in rows:
        entries.append((row, classify_book(row)))
    return summarize_books(entries)


def count_books(conn, genre):
    return conn.execute("SELECT COUNT(*) FROM library_books WHERE genre = ?", (genre,)).fetchone()[0]


def pages_band(value):
    if value >= 400.0:
        return "high"
    elif value >= 230.0:
        return "medium"
    else:
        return "low"


def count_popular(rows):
    count = 0
    for row in rows:
        if row["checkouts"] >= 30.0:
            count += 1
    return count
