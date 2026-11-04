"""Reference solution for Wildlife Watch. Used only to check the tests. Never shown to students."""


def get_animals(conn, park, start_number, end_number):
    cursor = conn.execute(
        "SELECT park, tag_number, species, weight_kg, daily_km FROM tagged_animals "
        "WHERE park = ? AND tag_number >= ? AND tag_number <= ? ORDER BY tag_number",
        (park, start_number, end_number),
    )
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]


def classify_animal(entry):
    labels = []
    if entry["weight_kg"] >= 100.0:
        labels.append("heavy")
    if entry["daily_km"] >= 15.0:
        labels.append("roamer")
    if not labels:
        labels.append("typical")
    return labels


def summarize_animals(entries):
    count_a = 0
    count_b = 0
    count_normal = 0
    total = 0.0
    highest = None
    flagged = []
    for entry, labels in entries:
        if "heavy" in labels:
            count_a += 1
        if "roamer" in labels:
            count_b += 1
        if "typical" in labels:
            count_normal += 1
        else:
            flagged.append(entry["tag_number"])
        total += entry["daily_km"]
        if highest is None or entry["weight_kg"] > highest:
            highest = entry["weight_kg"]
    flagged.sort()
    return {
        "heavy_count": count_a,
        "roamer_count": count_b,
        "typical_count": count_normal,
        "total_daily_km": round(total, 1),
        "max_weight_kg": highest,
        "flagged_tag_numbers": flagged,
    }


def build_animal_report(conn, park, start_number, end_number):
    rows = get_animals(conn, park, start_number, end_number)
    entries = []
    for row in rows:
        entries.append((row, classify_animal(row)))
    return summarize_animals(entries)


def count_animals(conn, park):
    return conn.execute("SELECT COUNT(*) FROM tagged_animals WHERE park = ?", (park,)).fetchone()[0]


def weight_kg_band(value):
    if value >= 100.0:
        return "high"
    elif value >= 50.5:
        return "medium"
    else:
        return "low"


def count_roamer(rows):
    count = 0
    for row in rows:
        if row["daily_km"] >= 15.0:
            count += 1
    return count
