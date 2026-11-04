"""Scripted demo: three students take different paths through the same project.

  python -m engine.demo

- Strong student: passes every level on the first try and goes straight through.
- Struggling student: needs four tries on Level 1, gets a practice problem,
  then trips the Level 3 loop rule once before finishing.
- Router-failure student: routing breaks after Level 1, so the engine falls
  back to the fixed level order and the student still finishes.

All three end on the same final objective (Level 4). Data goes to a temporary
folder and is deleted afterward.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import REPO_ROOT
from .events import EventLog
from .progress import JsonProgressStore
from .project import load_project
from .session import Engine
from .stages import STAGE_NAMES

GET_GOOD = '''
def get_readings(conn, station_id, start_date, end_date):
    cursor = conn.execute(
        "SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
        "WHERE station_id = ? AND date >= ? AND date <= ? ORDER BY date",
        (station_id, start_date, end_date))
    names = [c[0] for c in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]
'''

# Common mistakes for the struggling student, in the order they make them.
GET_STRING_FORMAT = '''
def get_readings(conn, station_id, start_date, end_date):
    sql = ("SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
           f"WHERE station_id = '{station_id}' AND date >= '{start_date}' AND date <= '{end_date}' ORDER BY date")
    cursor = conn.execute(sql)
    names = [c[0] for c in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]
'''

GET_EXCLUSIVE = '''
def get_readings(conn, station_id, start_date, end_date):
    cursor = conn.execute(
        "SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
        "WHERE station_id = ? AND date > ? AND date < ? ORDER BY date",
        (station_id, start_date, end_date))
    names = [c[0] for c in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]
'''

GET_UNSORTED_TUPLES = '''
def get_readings(conn, station_id, start_date, end_date):
    return conn.execute(
        "SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
        "WHERE station_id = ? AND date >= ? AND date <= ?",
        (station_id, start_date, end_date)).fetchall()
'''

COUNT_GOOD = '''
def count_readings(conn, station_id):
    return conn.execute("SELECT COUNT(*) FROM daily_readings WHERE station_id = ?", (station_id,)).fetchone()[0]
'''

CLASSIFY_GOOD = '''
def classify_day(row):
    labels = []
    if row["temp_high_c"] >= 35.0:
        labels.append("heat_wave")
    if row["rain_mm"] >= 20.0:
        labels.append("heavy_rain")
    if not labels:
        labels.append("normal")
    return labels
'''

SUMMARIZE_GOOD = '''
def summarize(readings):
    heat = rain_days = normal = 0
    total = 0.0
    hottest = None
    flagged = []
    for row, labels in readings:
        if "heat_wave" in labels:
            heat += 1
        if "heavy_rain" in labels:
            rain_days += 1
        if "normal" in labels:
            normal += 1
        else:
            flagged.append(row["date"])
        total += row["rain_mm"]
        if hottest is None or row["temp_high_c"] > hottest:
            hottest = row["temp_high_c"]
    flagged.sort()
    return {"heat_wave_days": heat, "heavy_rain_days": rain_days, "normal_days": normal,
            "total_rain_mm": round(total, 1), "max_temp_c": hottest, "flagged_dates": flagged}
'''

SUMMARIZE_SHORTCUT = '''
def summarize(readings):
    flagged = sorted(row["date"] for row, labels in readings if "normal" not in labels)
    temps = [row["temp_high_c"] for row, labels in readings]
    return {
        "heat_wave_days": sum(1 for _, labels in readings if "heat_wave" in labels),
        "heavy_rain_days": sum(1 for _, labels in readings if "heavy_rain" in labels),
        "normal_days": sum(1 for _, labels in readings if "normal" in labels),
        "total_rain_mm": round(sum(row["rain_mm"] for row, _ in readings), 1),
        "max_temp_c": max(temps) if temps else None,
        "flagged_dates": flagged,
    }
'''

BUILD_GOOD = '''
def build_report(conn, station_id, start_date, end_date):
    rows = get_readings(conn, station_id, start_date, end_date)
    readings = []
    for row in rows:
        readings.append((row, classify_day(row)))
    return summarize(readings)
'''

STRONG = [GET_GOOD, GET_GOOD + CLASSIFY_GOOD, GET_GOOD + CLASSIFY_GOOD + SUMMARIZE_GOOD,
          GET_GOOD + CLASSIFY_GOOD + SUMMARIZE_GOOD + BUILD_GOOD]

STRUGGLING = [
    GET_UNSORTED_TUPLES,
    GET_STRING_FORMAT,
    GET_EXCLUSIVE,
    GET_GOOD,                                              # Level 1 passed on try 4
    GET_GOOD + COUNT_GOOD,                                 # practice problem
    GET_GOOD + COUNT_GOOD + CLASSIFY_GOOD,                 # Level 2
    GET_GOOD + COUNT_GOOD + CLASSIFY_GOOD + SUMMARIZE_SHORTCUT,   # Level 3, breaks the loop rule
    GET_GOOD + COUNT_GOOD + CLASSIFY_GOOD + SUMMARIZE_GOOD,
    GET_GOOD + COUNT_GOOD + CLASSIFY_GOOD + SUMMARIZE_GOOD + BUILD_GOOD,
]


class BrokenAfterFirstLevel:
    """A router that fails after the first decision, to show the fallback path."""

    def __init__(self, real):
        self.real, self.calls = real, 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("simulated routing outage")
        return self.real(*args, **kwargs)


def run_student(engine: Engine, name: str, submissions, workdir: Path) -> None:
    student_id = engine.new_student()
    print(f"\n{'#' * 72}\n# {name}  (student id {student_id[:8]}...)\n{'#' * 72}")
    for number, source in enumerate(submissions, start=1):
        problem, _ = engine.current_problem(student_id)
        if problem is None:
            break
        path = workdir / f"{student_id}-{number}.py"
        path.write_text(source)
        outcome = engine.submit(student_id, path)
        print(f"\nSubmission {number} for {problem.title}:")
        for notice in outcome.notices:
            print(f"   [note] {notice}")
        for message in outcome.messages:
            print(("   PASS  " if outcome.passed else "   FAIL  ") + message)
        if outcome.hint:
            print(f"   Hint: {outcome.hint}")
        for change in outcome.stage_changes:
            print(f"   Stage up: {change.concept} {change.old_stage} -> {change.new_stage}")
        if outcome.passed:
            print("   Next: " + ("project complete" if outcome.complete else outcome.next_problem.title))

    record, _ = engine.open(student_id)
    path_taken = [entry["selected"] or "complete" for entry in record.routing_log]
    print("\nPath taken: level-1 -> " + " -> ".join(path_taken))
    print("Final stages: " + ", ".join(
        f"{c.name} {record.concepts[c.id].stage} ({STAGE_NAMES[record.concepts[c.id].stage]})"
        for c in engine.manifest.concepts))
    print("Attempts: " + ", ".join(f"{pid} x{n}" for pid, n in record.attempts.items()))


def main() -> int:
    project = load_project(REPO_ROOT / "projects" / "weather-station")
    with tempfile.TemporaryDirectory(prefix="codeai-demo-") as tmp:
        tmp_path = Path(tmp)
        store, events = JsonProgressStore(tmp_path), EventLog(tmp_path)
        engine = Engine(project, store, events)
        run_student(engine, "Strong student", STRONG, tmp_path)
        run_student(engine, "Struggling student", STRUGGLING, tmp_path)

        broken = Engine(project, store, events, router=BrokenAfterFirstLevel(engine.router))
        run_student(broken, "Router-failure student", STRONG, tmp_path)

        fallbacks = [e for e in events.read() if e["event"] == "fallback"]
        print(f"\nFallback events logged: {len(fallbacks)} "
              + ", ".join(f"({e['reason']} at {e['problem_id']})" for e in fallbacks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
