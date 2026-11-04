"""E01 on proto-branch: does the validation service agree with a human key?

Proto validates code with automated checks (`levels/*/checks.py`) plus a static loop
rule on Level 3. This benchmark runs hand-written submissions through proto's own
grader and compares pass/fail with a draft human key:

  pass    meets the level instructions; a teacher would accept it
  fail    breaks a stated requirement of the level instructions
  review  a teacher has to decide (reported, not scored)

The key is a DRAFT written by the evaluation team from the instructions text; it needs
teacher review before the numbers are reported outside the team. Correct variants are
included on purpose: a grader that only sees the reference solution's style will reject
valid student code (false fail), which hurts students more than a missed bug.

Usage: python -m evaluation.harness.proto_validation_bench     (no model or AWS calls)
"""
from __future__ import annotations

import json
from pathlib import Path

from . import proto_adapter as pa

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

CASES = [
    # ---------------- Level 1: get_readings ----------------
    {"id": "V-L1-01", "level": "level-1", "function": "get_readings", "key": "pass",
     "why": "BETWEEN is inclusive on both ends.",
     "code": '''def get_readings(conn, station_id, start_date, end_date):
    cur = conn.execute("SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
                       "WHERE station_id = ? AND date BETWEEN ? AND ? ORDER BY date", (station_id, start_date, end_date))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]
'''},
    {"id": "V-L1-02", "level": "level-1", "function": "get_readings", "key": "pass",
     "why": "Builds each dictionary by hand with a loop.",
     "code": '''def get_readings(conn, station_id, start_date, end_date):
    rows = conn.execute("SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
                        "WHERE station_id = ? AND date >= ? AND date <= ? ORDER BY date ASC",
                        (station_id, start_date, end_date)).fetchall()
    result = []
    for r in rows:
        result.append({"station_id": r[0], "date": r[1], "temp_high_c": r[2], "temp_low_c": r[3], "rain_mm": r[4]})
    return result
'''},
    {"id": "V-L1-03", "level": "level-1", "function": "get_readings", "key": "pass",
     "why": "SELECT * (the table has exactly the five columns).",
     "code": '''def get_readings(conn, station_id, start_date, end_date):
    cur = conn.execute("SELECT * FROM daily_readings WHERE station_id = ? AND date >= ? AND date <= ? ORDER BY date",
                       (station_id, start_date, end_date))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur]
'''},
    {"id": "V-L1-04", "level": "level-1", "function": "get_readings", "key": "pass",
     "why": "Uses sqlite3.Row on a new cursor-level row factory.",
     "code": '''import sqlite3

def get_readings(conn, station_id, start_date, end_date):
    cur = conn.cursor()
    cur.row_factory = sqlite3.Row
    cur.execute("SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
                "WHERE station_id = ? AND date >= ? AND date <= ? ORDER BY date", (station_id, start_date, end_date))
    return [dict(r) for r in cur.fetchall()]
'''},
    {"id": "V-L1-05", "level": "level-1", "function": "get_readings", "key": "pass",
     "why": "Named placeholders (:station) are still placeholders.",
     "code": '''def get_readings(conn, station_id, start_date, end_date):
    cur = conn.execute("SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
                       "WHERE station_id = :s AND date >= :a AND date <= :b ORDER BY date",
                       {"s": station_id, "a": start_date, "b": end_date})
    keys = [d[0] for d in cur.description]
    return [dict(zip(keys, v)) for v in cur.fetchall()]
'''},
    {"id": "V-L1-06", "level": "level-1", "function": "get_readings", "key": "fail",
     "why": "f-string with quotes: works on normal ids but breaks the placeholder rule (SQL injection).",
     "code": '''def get_readings(conn, station_id, start_date, end_date):
    cur = conn.execute(f"SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
                       f"WHERE station_id = '{station_id}' AND date >= '{start_date}' AND date <= '{end_date}' ORDER BY date")
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
'''},
    {"id": "V-L1-07", "level": "level-1", "function": "get_readings", "key": "fail",
     "why": "No station filter.",
     "code": '''def get_readings(conn, station_id, start_date, end_date):
    cur = conn.execute("SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
                       "WHERE date >= ? AND date <= ? ORDER BY date", (start_date, end_date))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
'''},
    {"id": "V-L1-08", "level": "level-1", "function": "get_readings", "key": "fail",
     "why": "Sorted newest first.",
     "code": '''def get_readings(conn, station_id, start_date, end_date):
    cur = conn.execute("SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings "
                       "WHERE station_id = ? AND date >= ? AND date <= ? ORDER BY date DESC", (station_id, start_date, end_date))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
'''},
    {"id": "V-L1-09", "level": "level-1", "function": "get_readings", "key": "review",
     "why": "Reads all rows and filters in Python; no values in the SQL, so no placeholders needed. Meets the outputs, not the spirit of 'database retrieval'.",
     "code": '''def get_readings(conn, station_id, start_date, end_date):
    cur = conn.execute("SELECT station_id, date, temp_high_c, temp_low_c, rain_mm FROM daily_readings ORDER BY date")
    cols = [c[0] for c in cur.description]
    out = []
    for r in cur.fetchall():
        row = dict(zip(cols, r))
        if row["station_id"] == station_id and start_date <= row["date"] <= end_date:
            out.append(row)
    return out
'''},
    # ---------------- Level 2: classify_day ----------------
    {"id": "V-L2-01", "level": "level-2", "function": "classify_day", "key": "pass",
     "why": "Literal thresholds instead of constants.",
     "code": '''def classify_day(row):
    labels = []
    if row["temp_high_c"] >= 35.0:
        labels.append("heat_wave")
    if row["rain_mm"] >= 20.0:
        labels.append("heavy_rain")
    return labels or ["normal"]
'''},
    {"id": "V-L2-02", "level": "level-2", "function": "classify_day", "key": "pass",
     "why": "if/elif chain that covers all four cases explicitly.",
     "code": '''def classify_day(row):
    hot = row["temp_high_c"] >= 35
    wet = row["rain_mm"] >= 20
    if hot and wet:
        return ["heat_wave", "heavy_rain"]
    elif hot:
        return ["heat_wave"]
    elif wet:
        return ["heavy_rain"]
    else:
        return ["normal"]
'''},
    {"id": "V-L2-03", "level": "level-2", "function": "classify_day", "key": "fail",
     "why": "Labels in the wrong order for a hot and wet day.",
     "code": '''def classify_day(row):
    labels = []
    if row["rain_mm"] >= 20.0:
        labels.append("heavy_rain")
    if row["temp_high_c"] >= 35.0:
        labels.append("heat_wave")
    if not labels:
        labels.append("normal")
    return labels
'''},
    {"id": "V-L2-04", "level": "level-2", "function": "classify_day", "key": "fail",
     "why": "Changes the row dictionary (instructions: don't change row).",
     "code": '''def classify_day(row):
    row["labels"] = []
    if row["temp_high_c"] >= 35.0:
        row["labels"].append("heat_wave")
    if row["rain_mm"] >= 20.0:
        row["labels"].append("heavy_rain")
    if not row["labels"]:
        row["labels"].append("normal")
    return row["labels"]
'''},
    {"id": "V-L2-05", "level": "level-2", "function": "classify_day", "key": "fail",
     "why": "Threshold 34.95: wrong rule (35.0 or more), only visible for 34.95-34.99 values.",
     "code": '''def classify_day(row):
    labels = []
    if row["temp_high_c"] >= 34.95:
        labels.append("heat_wave")
    if row["rain_mm"] >= 20.0:
        labels.append("heavy_rain")
    if not labels:
        labels.append("normal")
    return labels
'''},
    {"id": "V-L2-06", "level": "level-2", "function": "classify_day", "key": "fail",
     "why": "Returns a string, not a list.",
     "code": '''def classify_day(row):
    if row["temp_high_c"] >= 35.0:
        return "heat_wave"
    if row["rain_mm"] >= 20.0:
        return "heavy_rain"
    return "normal"
'''},
    {"id": "V-L2-07", "level": "level-2", "function": "classify_day", "key": "fail",
     "why": "Rounds the temperature first, so 34.5-34.9 count as a heat wave.",
     "code": '''def classify_day(row):
    labels = []
    if round(row["temp_high_c"]) >= 35:
        labels.append("heat_wave")
    if row["rain_mm"] >= 20.0:
        labels.append("heavy_rain")
    if not labels:
        labels.append("normal")
    return labels
'''},
    # ---------------- Level 3: summarize ----------------
    {"id": "V-L3-01", "level": "level-3", "function": "summarize", "key": "pass",
     "why": "while loop with an index.",
     "code": '''def summarize(readings):
    hw = hr = nd = 0
    rain = 0.0
    top = None
    flagged = []
    i = 0
    while i < len_safe(readings):
        row, labels = readings[i]
        if "heat_wave" in labels:
            hw += 1
        if "heavy_rain" in labels:
            hr += 1
        if "normal" in labels:
            nd += 1
        else:
            flagged.append(row["date"])
        rain += row["rain_mm"]
        if top is None or row["temp_high_c"] > top:
            top = row["temp_high_c"]
        i += 1
    flagged.sort()
    return {"heat_wave_days": hw, "heavy_rain_days": hr, "normal_days": nd,
            "total_rain_mm": round(rain, 1), "max_temp_c": top, "flagged_dates": flagged}


def len_safe(items):
    n = 0
    for _ in items:
        n += 1
    return n
'''},
    {"id": "V-L3-02", "level": "level-3", "function": "summarize", "key": "pass",
     "why": "Counts with a dictionary of counters.",
     "code": '''def summarize(readings):
    counts = {"heat_wave": 0, "heavy_rain": 0, "normal": 0}
    total = 0.0
    hottest = None
    flagged = []
    for row, labels in readings:
        for label in labels:
            counts[label] += 1
        if labels != ["normal"]:
            flagged.append(row["date"])
        total += row["rain_mm"]
        if hottest is None or row["temp_high_c"] > hottest:
            hottest = row["temp_high_c"]
    flagged.sort()
    return {"heat_wave_days": counts["heat_wave"], "heavy_rain_days": counts["heavy_rain"],
            "normal_days": counts["normal"], "total_rain_mm": round(total, 1),
            "max_temp_c": hottest, "flagged_dates": flagged}
'''},
    {"id": "V-L3-03", "level": "level-3", "function": "summarize", "key": "pass",
     "why": "Uses 'if not readings' for the empty case (no banned call).",
     "code": '''def summarize(readings):
    if not readings:
        return {"heat_wave_days": 0, "heavy_rain_days": 0, "normal_days": 0,
                "total_rain_mm": 0.0, "max_temp_c": None, "flagged_dates": []}
    hw = hr = nd = 0
    total = 0.0
    mx = readings[0][0]["temp_high_c"]
    flagged = []
    for row, labels in readings:
        hw += "heat_wave" in labels
        hr += "heavy_rain" in labels
        nd += "normal" in labels
        if "normal" not in labels:
            flagged.append(row["date"])
        total += row["rain_mm"]
        if row["temp_high_c"] > mx:
            mx = row["temp_high_c"]
    flagged.sort()
    return {"heat_wave_days": hw, "heavy_rain_days": hr, "normal_days": nd,
            "total_rain_mm": round(total, 1), "max_temp_c": mx, "flagged_dates": flagged}
'''},
    {"id": "V-L3-04", "level": "level-3", "function": "summarize", "key": "fail",
     "why": "Calls len() for the empty check (banned by the instructions).",
     "code": '''def summarize(readings):
    hw = hr = nd = 0
    total = 0.0
    mx = None
    flagged = []
    if len(readings) == 0:
        return {"heat_wave_days": 0, "heavy_rain_days": 0, "normal_days": 0,
                "total_rain_mm": 0.0, "max_temp_c": None, "flagged_dates": []}
    for row, labels in readings:
        hw += "heat_wave" in labels
        hr += "heavy_rain" in labels
        nd += "normal" in labels
        if "normal" not in labels:
            flagged.append(row["date"])
        total += row["rain_mm"]
        if mx is None or row["temp_high_c"] > mx:
            mx = row["temp_high_c"]
    flagged.sort()
    return {"heat_wave_days": hw, "heavy_rain_days": hr, "normal_days": nd,
            "total_rain_mm": round(total, 1), "max_temp_c": mx, "flagged_dates": flagged}
'''},
    {"id": "V-L3-05", "level": "level-3", "function": "summarize", "key": "fail",
     "why": "Uses sorted() (banned by the instructions).",
     "code": '''def summarize(readings):
    hw = hr = nd = 0
    total = 0.0
    mx = None
    flagged = []
    for row, labels in readings:
        hw += "heat_wave" in labels
        hr += "heavy_rain" in labels
        nd += "normal" in labels
        if "normal" not in labels:
            flagged.append(row["date"])
        total += row["rain_mm"]
        if mx is None or row["temp_high_c"] > mx:
            mx = row["temp_high_c"]
    return {"heat_wave_days": hw, "heavy_rain_days": hr, "normal_days": nd,
            "total_rain_mm": round(total, 1), "max_temp_c": mx, "flagged_dates": sorted(flagged)}
'''},
    {"id": "V-L3-06", "level": "level-3", "function": "summarize", "key": "review",
     "why": "Avoids the ban with readings.__len__() and builtins.max via getattr: follows the letter, not the intent.",
     "code": '''import builtins

def summarize(readings):
    hw = hr = nd = 0
    total = 0.0
    flagged = []
    for row, labels in readings:
        hw += "heat_wave" in labels
        hr += "heavy_rain" in labels
        nd += "normal" in labels
        if "normal" not in labels:
            flagged.append(row["date"])
        total += row["rain_mm"]
    biggest = getattr(builtins, "max")
    mx = biggest([r["temp_high_c"] for r, _ in readings]) if readings.__len__() else None
    flagged.sort()
    return {"heat_wave_days": hw, "heavy_rain_days": hr, "normal_days": nd,
            "total_rain_mm": round(total, 1), "max_temp_c": mx, "flagged_dates": flagged}
'''},
    {"id": "V-L3-07", "level": "level-3", "function": "summarize", "key": "fail",
     "why": "Counts heavy rain from rain_mm > 20 instead of the labels (wrong at exactly 20.0).",
     "code": '''def summarize(readings):
    hw = hr = nd = 0
    total = 0.0
    mx = None
    flagged = []
    for row, labels in readings:
        hw += "heat_wave" in labels
        if row["rain_mm"] > 20:
            hr += 1
        nd += "normal" in labels
        if "normal" not in labels:
            flagged.append(row["date"])
        total += row["rain_mm"]
        if mx is None or row["temp_high_c"] > mx:
            mx = row["temp_high_c"]
    flagged.sort()
    return {"heat_wave_days": hw, "heavy_rain_days": hr, "normal_days": nd,
            "total_rain_mm": round(total, 1), "max_temp_c": mx, "flagged_dates": flagged}
'''},
    # ---------------- Level 4: build_report ----------------
    {"id": "V-L4-01", "level": "level-4", "function": "build_report", "key": "pass",
     "why": "List comprehension for the pairs.",
     "code": '''def build_report(conn, station_id, start_date, end_date):
    rows = get_readings(conn, station_id, start_date, end_date)
    return summarize([(r, classify_day(r)) for r in rows])
'''},
    {"id": "V-L4-02", "level": "level-4", "function": "build_report", "key": "pass",
     "why": "Keyword arguments and a separate pairs variable.",
     "code": '''def build_report(conn, station_id, start_date, end_date):
    rows = get_readings(conn=conn, station_id=station_id, start_date=start_date, end_date=end_date)
    pairs = []
    for one in rows:
        labels = classify_day(one)
        pairs.append((one, labels))
    report = summarize(pairs)
    return report
'''},
    {"id": "V-L4-03", "level": "level-4", "function": "build_report", "key": "fail",
     "why": "Calls get_readings twice (instructions: once).",
     "code": '''def build_report(conn, station_id, start_date, end_date):
    if not get_readings(conn, station_id, start_date, end_date):
        return summarize([])
    rows = get_readings(conn, station_id, start_date, end_date)
    return summarize([(r, classify_day(r)) for r in rows])
'''},
    {"id": "V-L4-04", "level": "level-4", "function": "build_report", "key": "fail",
     "why": "Hard-codes the stored January answer for ST-A (the real stored values) and computes the rest.",
     "code": None},  # filled from reference/expected_reports.json in _hardcoded_case()
]


def _hardcoded_case() -> str:
    reports = pa.project().read_expected_reports()["reports"]
    jan = next(r["report"] for r in reports if r["args"] == {"station_id": "ST-A", "start_date": "2026-01-01",
                                                             "end_date": "2026-01-31"})
    return (f'''def build_report(conn, station_id, start_date, end_date):
    if station_id == "ST-A" and start_date == "2026-01-01" and end_date == "2026-01-31":
        return {jan!r}
    rows = get_readings(conn, station_id, start_date, end_date)
    return summarize([(r, classify_day(r)) for r in rows])
''')


def main(argv=None) -> int:
    from .proto_bugs import LEVEL_FUNCTIONS  # noqa: F401  (documents the file layout used)
    rows = []
    for c in CASES:
        if c["code"] is None:
            c["code"] = _hardcoded_case()
        src = pa.student_file(c["level"], c["function"], c["code"])
        result, messages = pa.grade_source(c["level"], src)
        grader = "pass" if result.passed else "fail"
        rows.append(dict(c, grader=grader, status=result.status, first_message=messages[0] if messages else "",
                         n_messages=len(messages)))
        print(f"  {c['id']} key={c['key']:6s} grader={grader:4s} {messages[0][:90] if messages else ''}", flush=True)

    scored = [r for r in rows if r["key"] in ("pass", "fail")]
    tp = sum(r["key"] == "pass" and r["grader"] == "pass" for r in scored)
    tn = sum(r["key"] == "fail" and r["grader"] == "fail" for r in scored)
    false_pass = [r for r in scored if r["key"] == "fail" and r["grader"] == "pass"]
    false_fail = [r for r in scored if r["key"] == "pass" and r["grader"] == "fail"]
    n = len(scored)
    po = (tp + tn) / n
    p_key_pass = sum(r["key"] == "pass" for r in scored) / n
    p_gr_pass = sum(r["grader"] == "pass" for r in scored) / n
    pe = p_key_pass * p_gr_pass + (1 - p_key_pass) * (1 - p_gr_pass)
    summary = {
        "n_scored": n, "n_review": len(rows) - n, "agreement": round(po, 3),
        "cohens_kappa": round((po - pe) / (1 - pe), 3) if pe < 1 else None,
        "false_pass": [r["id"] for r in false_pass], "false_fail": [r["id"] for r in false_fail],
        "rows": [{k: v for k, v in r.items() if k != "code"} for r in rows],
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "E01_proto_validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    L = ["# E01 on proto-branch: validation (auto-checks) vs. a draft human key", "",
         "Proto's validation service is the automated checks in `projects/weather-station/levels/*/checks.py` "
         "plus the Level 3 loop rule (commit 745b446, unchanged). Each submission below replaces one function in an "
         "otherwise correct file. The key is a **draft** from the evaluation team, based only on the level "
         "instructions; it needs teacher review.", "",
         f"- Scored submissions: {n} (plus {summary['n_review']} marked `review` for a teacher).",
         f"- Agreement with the key: **{summary['agreement']}**, Cohen's kappa **{summary['cohens_kappa']}**.",
         f"- False fail (valid code rejected): **{len(false_fail)}** {', '.join(summary['false_fail'])}",
         f"- False pass (broken requirement accepted): **{len(false_pass)}** {', '.join(summary['false_pass'])}", "",
         "| ID | Key | Grader | Why (key) | First message the student sees |", "|---|---|---|---|---|"]
    for r in rows:
        mark = "" if r["key"] == "review" or r["key"] == r["grader"] else " **(disagree)**"
        L.append(f"| {r['id']} | {r['key']} | {r['grader']}{mark} | {r['why']} | {r['first_message'][:160]} |")
    L += ["", "Pass/fail agreement is only half of the customer requirement. Proto's mastery signal (Stage 0-3) "
          "comes from attempt and hint counts on a pass, not from the quality of the code, so two passing "
          "submissions get the same stage whatever their quality. A rubric-based score (requirements 10-11 in "
          "proto's own spec) is still missing.", ""]
    (RESULTS / "E01_proto_validation_report.md").write_text("\n".join(L), encoding="utf-8")
    print(f"agreement {summary['agreement']} kappa {summary['cohens_kappa']} false_fail {summary['false_fail']} "
          f"false_pass {summary['false_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
