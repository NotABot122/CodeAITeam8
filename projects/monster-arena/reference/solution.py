"""Reference solution for Monster Arena. Used only to check the tests. Never shown to students."""


def get_monsters(conn, zone, start_number, end_number):
    cursor = conn.execute(
        "SELECT zone, monster_number, name, power, speed FROM monsters "
        "WHERE zone = ? AND monster_number >= ? AND monster_number <= ? ORDER BY monster_number",
        (zone, start_number, end_number),
    )
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]


def classify_monster(entry):
    labels = []
    if entry["power"] >= 70.0:
        labels.append("strong")
    if entry["speed"] >= 60.0:
        labels.append("fast")
    if not labels:
        labels.append("balanced")
    return labels


def summarize_monsters(entries):
    count_a = 0
    count_b = 0
    count_normal = 0
    total = 0.0
    highest = None
    flagged = []
    for entry, labels in entries:
        if "strong" in labels:
            count_a += 1
        if "fast" in labels:
            count_b += 1
        if "balanced" in labels:
            count_normal += 1
        else:
            flagged.append(entry["monster_number"])
        total += entry["speed"]
        if highest is None or entry["power"] > highest:
            highest = entry["power"]
    flagged.sort()
    return {
        "strong_count": count_a,
        "fast_count": count_b,
        "balanced_count": count_normal,
        "total_speed": round(total, 1),
        "max_power": highest,
        "flagged_monster_numbers": flagged,
    }


def build_monster_report(conn, zone, start_number, end_number):
    rows = get_monsters(conn, zone, start_number, end_number)
    entries = []
    for row in rows:
        entries.append((row, classify_monster(row)))
    return summarize_monsters(entries)


def count_monsters(conn, zone):
    return conn.execute("SELECT COUNT(*) FROM monsters WHERE zone = ?", (zone,)).fetchone()[0]


def power_band(value):
    if value >= 70.0:
        return "high"
    elif value >= 37.5:
        return "medium"
    else:
        return "low"


def count_fast(rows):
    count = 0
    for row in rows:
        if row["speed"] >= 60.0:
            count += 1
    return count
