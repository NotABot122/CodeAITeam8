"""Diagnostic -> lesson, end to end: does any student start where they should and then learn?

Goal (product owner): any student can take the readiness diagnostic and start the adaptive
lesson at their level. This harness checks that with simulated students whose true level
per concept is known, run through the real code: the diagnostic quest (diagnostic/), its
handoff, and the lesson through engine.course.Course (what the student web API uses).

Four conditions, same students, same random draws (common random numbers):
  no_diagnostic       today's lesson without a diagnostic
  diagnostic_today    quest + Course.apply_diagnostic as shipped (confident stages seeded into the
                      profile, lesson starts at the quest's placement)
  diagnostic_proposed today's handoff plus the missing piece: each diagnosed gap gets its practice
                      problem before its level (the quest's planned practice is used)
  oracle              the proposed handoff fed with the TRUE stages: the upper bound

Learner model (an assumption, stated in the report): chance to pass an attempt depends on the
true stage of the problem's concept, rises with each attempt (feedback, hints), and practice is
easier. Passing a practice problem, or a level after struggling, lifts a true stage 0 to 1.
Passing submissions are the reference solution; failing ones are a seeded bug for that concept;
proto's grader grades every one.

No engine or diagnostic code is changed. The proposed condition only uses public pieces that
exist today (the profile store, apply_placement, ProgressRecord through the lesson's own store).

Usage: python -m evaluation.harness.diag_lesson_eval [--students 40] [--seed 2026]
"""
from __future__ import annotations

import argparse
import ast
import json
import random
import re
import statistics
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from . import proto_adapter as pa
from .proto_bugs import BUGS
from engine.course import Course
from engine.grader import Grader
from engine.progress import JsonProgressStore

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
MAX_SUBMISSIONS = 40
CONDITIONS = ("no_diagnostic", "diagnostic_today", "diagnostic_proposed", "oracle")
LABELS = {
    "no_diagnostic": "No diagnostic",
    "diagnostic_today": "Diagnostic, handoff as built today",
    "diagnostic_proposed": "Diagnostic, proposed handoff",
    "oracle": "Perfect knowledge of the student (upper bound)",
}

# Learner model
BASE_PASS = {0: 0.20, 1: 0.50, 2: 0.80, 3: 0.95}
PER_ATTEMPT = 0.12
PRACTICE_BONUS = 0.15

PRACTICE_BUGS = {
    "count_readings": '''def count_readings(conn, station_id):
    return 0
''',
    "temp_band": '''def temp_band(temp_high_c):
    if temp_high_c > 35.0:
        return "hot"
    elif temp_high_c > 20.0:
        return "warm"
    else:
        return "cool"
''',
    "count_rainy_days": '''def count_rainy_days(rows):
    count = 0
    for row in rows:
        if row["rain_mm"] >= 0:
            count += 1
    return count
''',
}
PRACTICE_FUNCTION = {"practice-db-count": "count_readings", "practice-temp-band": "temp_band",
                     "practice-rainy-days": "count_rainy_days"}


def _replace_function(source: str, name: str, code: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return "".join(lines[:node.lineno - 1]) + code + "".join(lines[node.end_lineno:])


class Files:
    """One correct file and one failing file per problem, written once."""

    def __init__(self, root: Path):
        ref = pa.reference_source()
        self.correct = root / "correct.py"
        self.correct.write_text(ref)
        self.wrong = {}
        first_bug = {}
        for b in BUGS:
            first_bug.setdefault(b["level"], b)
        for level, b in first_bug.items():
            p = root / f"wrong-{level}.py"
            p.write_text(_replace_function(ref, b["function"], b["code"]))
            self.wrong[level] = p
        for pid, fn in PRACTICE_FUNCTION.items():
            p = root / f"wrong-{pid}.py"
            p.write_text(_replace_function(ref, fn, PRACTICE_BUGS[fn]))
            self.wrong[pid] = p


# --------------------------------------------------------------------------- diagnostic side

def _diagnostic(root: Path, run_id: str):
    from diagnostic.content import load_content
    from diagnostic.engine import DiagnosticEngine
    from diagnostic.eval_log import EvalEventLog
    from diagnostic.store import DiagnosticStore
    from engine.events import EventLog
    project = pa.project()
    content = load_content(project.root, project.manifest.concept_ids())
    return DiagnosticEngine(project, content, DiagnosticStore(root), EventLog(root), EvalEventLog(root, run_id), None)


def _quest(diag, sim_student):
    from diagnostic import simulation as sim
    out = sim.play(diag, sim_student)
    rep = out["report"]
    stages = {c["concept"]: c["stage"] for c in rep["concepts"]}
    next_stop = out["student_view"].get("next_stop") or {}
    zone_name = next_stop.get("zone")
    # The zone named in "next stop" is the first concept of the placement's focus order.
    focus = rep["placement"].get("focus_order") or []
    zone_concept = focus[0] if focus else None
    return {"student_id": out["student_id"], "stages": stages, "next_task": rep["placement"]["next_task_id"],
            "practice_ahead": list(rep["placement"].get("practice_ahead") or []),
            "next_stop_zone": zone_name, "next_stop_concept": zone_concept}


# --------------------------------------------------------------------------- lesson side

def _practice_for(concept: str):
    return next((p for p in pa.project().manifest.practice_problems if p.concept == concept and p.target_stage == 1), None)


def _set_current(store: JsonProgressStore, sid: str, problem_id: str, origin: str | None):
    rec = store.load(sid, pa.project().id)
    rec.current_problem, rec.origin_level = problem_id, origin
    store.save(rec)


def _run_lesson(course: Course, sid: str, latent: dict, files: Files, rng_seed: str, gaps_ahead: set[str]):
    """Drive one student through the lesson. Returns metrics. `gaps_ahead`: concepts whose practice
    is inserted before their level (the proposed handoff); empty for today's behaviour."""
    prj = pa.project()
    store = course.store
    latent = dict(latent)
    true_gaps = {c for c, s in latent.items() if s == 0}
    attempts = Counter()
    path, fails_on_levels, fails_total, subs = [], 0, 0, 0
    practiced_before_level = set()
    practice_done = set()
    practice_unneeded = 0
    first_problem = None
    while subs < MAX_SUBMISSIONS:
        engine = course.engine(sid)
        rec, _ = engine.open(sid)
        if rec.complete or rec.current_problem is None:
            break
        pid = rec.current_problem
        prob = prj.problem(pid)
        concept = prob.concepts[0]
        # Proposed handoff: before a level whose concept was diagnosed as a gap, do its practice first.
        if prob.kind == "level" and concept in gaps_ahead and concept not in practice_done and pid not in rec.passed_problems:
            pr = _practice_for(concept)
            if pr is not None and pr.id not in rec.passed_problems:
                _set_current(store, sid, pr.id, pid)
                continue
        if first_problem is None:
            first_problem = pid
        path.append(pid)
        attempts[pid] += 1
        p = BASE_PASS[latent[concept]] + PER_ATTEMPT * (attempts[pid] - 1)
        if prob.kind == "practice":
            p += PRACTICE_BONUS
        passed = random.Random(f"{rng_seed}:{pid}:{attempts[pid]}").random() < min(p, 0.97)
        out = course.submit(sid, files.correct if passed else files.wrong[pid])
        subs += 1
        if not out.passed:
            fails_total += 1
            if prob.kind == "level":
                fails_on_levels += 1
            continue
        if prob.kind == "practice":
            practice_done.add(concept)
            if not any(lv in path[:-1] for lv in (l.id for l in prj.manifest.levels_in_order() if concept in l.concepts)):
                practiced_before_level.add(concept)
            if latent[concept] >= 2:
                practice_unneeded += 1
            latent[concept] = max(latent[concept], 1)
        elif latent[concept] == 0:
            latent[concept] = 1  # learned it the hard way
    rec, _ = course.engine(sid).open(sid)
    return {
        "completed": bool(rec.complete), "submissions": subs, "failed_on_levels": fails_on_levels,
        "failed_total": fails_total, "path": path, "first_problem": first_problem,
        "true_gaps": sorted(true_gaps), "gaps_practiced_first": sorted(true_gaps & practiced_before_level),
        "practice_unneeded": practice_unneeded, "final_engine_stages": rec.stages(),
    }


def run(n_students: int, seed: int) -> dict:
    from diagnostic import simulation as sim
    from diagnostic.handoff import apply_placement
    tmp = Path(tempfile.mkdtemp(prefix="codeai-diag-lesson-"))
    files = Files(tmp)
    grader = Grader(timeout_s=10)
    content_probe = _diagnostic(tmp / "probe", "probe").content
    cohort = sim.make_cohort(content_probe, n_students, seed=seed)
    rows = []
    for i, st in enumerate(cohort):
        latent = dict(st.latent)
        rng_seed = f"{seed}:{st.sim_id}"
        for cond in CONDITIONS:
            root = tmp / f"{i:03d}-{cond}"
            course = Course(root, grader=grader)
            row = {"student": st.sim_id, "condition": cond, "true": latent,
                   "band": "low" if statistics.mean(latent.values()) < 1 else ("high" if statistics.mean(latent.values()) >= 2 else "middle")}
            if cond == "no_diagnostic":
                sid = course.new_student()
                gaps_ahead = set()
            else:
                q = _quest(course.diagnostic(), st)
                sid = q["student_id"]
                row.update(diag_stages=q["stages"], diag_next=q["next_task"], diag_practice_ahead=q["practice_ahead"],
                           next_stop_zone=q["next_stop_zone"], next_stop_concept=q["next_stop_concept"])
                stages = q["stages"] if cond != "oracle" else latent
                if cond in ("diagnostic_today", "diagnostic_proposed"):
                    profile = course.store.profile(sid)
                    profile.update(active_project=str(pa.project().root), concepts={}, completed=[], next_step=None)
                    course.store.save_profile(sid, profile)
                    applied = course.apply_diagnostic(sid)
                    row["stages_used"] = sum(d["used"] for d in applied["decisions"].values())
                    row["stages_found"] = len(applied["decisions"])
                    gaps_ahead = set() if cond == "diagnostic_today" else {c for c, s in q["stages"].items() if s == 0}
                else:
                    profile = course.store.profile(sid)
                    profile.update(active_project=str(pa.project().root), concepts=dict(stages), completed=[], next_step=None)
                    course.store.save_profile(sid, profile)
                    course.engine(sid).open(sid)  # fresh record now carries the stages (Engine.initial_stages)
                    gaps_ahead = {c for c, s in stages.items() if s == 0}
                    order = [l.concepts[0] for l in pa.project().manifest.levels_in_order()]
                    first_gap = next((c for c in order if c in gaps_ahead), None)
                    start = (_practice_for(first_gap).id if first_gap == order[0] and _practice_for(first_gap) else "level-1")
                    origin = "level-1" if start != "level-1" else None
                    _set_current(course.store, sid, start, origin)
                row["lesson_start_stages"] = course.engine(sid).open(sid)[0].stages()
            row.update(_run_lesson(course, sid, latent, files, rng_seed, gaps_ahead))
            rows.append(row)
        print(f"  student {i + 1}/{len(cohort)} done", flush=True)
    return {"rows": rows, "checks": integration_checks(tmp)}


# --------------------------------------------------------------------------- integration checks

def integration_checks(tmp: Path) -> list[dict]:
    """The handoff standard as pass/fail checks on the code as it is today."""
    from diagnostic import simulation as sim
    from diagnostic.handoff import apply_placement
    checks = []
    root = tmp / "checks"
    q = _quest(Course(root).diagnostic(), sim.profile_student("mixed"))
    sid = q["student_id"]

    try:
        from webapi.service import STUDENT_ID as WEB_ID
        ok = bool(WEB_ID.match(sid))
        detail = f"diagnostic id {sid[:8]}… vs student app rule {WEB_ID.pattern}"
    except Exception as exc:
        ok, detail = False, f"student web API not importable: {exc}"
    checks.append({"id": "same_student", "requirement": "The student app opens the student who took the diagnostic.",
                   "passed": ok, "detail": detail})

    course0 = Course(root)
    summary0 = course0.apply_diagnostic(sid)
    rec = JsonProgressStore(root).load(sid, pa.project().id)
    confident = summary0.get("seeded", {})
    carried = rec is not None and all(rec.stages().get(c) == s for c, s in confident.items())
    checks.append({"id": "stages_carried", "requirement": "What the diagnostic found (stage per concept) reaches the lesson.",
                   "passed": carried,
                   "detail": f"diagnostic {q['stages']}; confident and used {confident}; lesson starts with {rec.stages() if rec else None}"})

    checks.append({"id": "practice_carried", "requirement": "Every gap the diagnostic found is planned in the lesson, not only the first one.",
                   "passed": not q["practice_ahead"],
                   "detail": f"practice the diagnostic planned but the lesson never receives: {q['practice_ahead'] or 'none'}"})

    first = pa.project().problem(q["next_task"])
    consistent = q["next_stop_concept"] is None or q["next_stop_concept"] in first.concepts
    checks.append({"id": "message_matches", "requirement": "What the student is told comes next is what the lesson starts with.",
                   "passed": consistent,
                   "detail": f"told: {q['next_stop_zone']}; lesson starts with {first.title} ({', '.join(first.concepts)})"})

    band = None
    cfg = Path(pa.PROTO_ROOT) / "projects" / "weather-station" / "diagnostic" / "diagnostic.yaml"
    if cfg.exists():
        m = re.search(r'grade_band:\s*"?([0-9K]+-[0-9]+)"?', cfg.read_text())
        band = m.group(1) if m else None
    hints_src = (Path(pa.PROTO_ROOT) / "engine" / "hints.py").read_text()
    lesson_hs = "high school" in hints_src
    checks.append({"id": "same_grade", "requirement": "The diagnostic and the lesson are written for the same grades.",
                   "passed": not (band and band.startswith(("3", "4", "5", "K")) and lesson_hs),
                   "detail": f"diagnostic grade band {band}; lesson tutor and filters are written for high school"})

    r2 = tmp / "checks-fail"
    diag2 = _diagnostic(r2, "checks2")
    q2 = _quest(diag2, sim.profile_student("middle"))
    res = apply_placement(pa.project(), r2, q2["student_id"], "no-such-problem")
    course = Course(r2)
    start = course.engine(q2["student_id"]).open(q2["student_id"])[0].current_problem
    checks.append({"id": "fails_safe", "requirement": "If the handoff fails, the lesson still starts normally.",
                   "passed": (not res.applied) and start == "level-1", "detail": f"handoff applied={res.applied}; lesson starts at {start}"})

    files = Files(tmp)
    course.submit(q2["student_id"], files.wrong["level-1"])
    res2 = apply_placement(pa.project(), r2, q2["student_id"], "practice-db-count")
    checks.append({"id": "no_overwrite", "requirement": "A diagnostic never resets a lesson the student has already started.",
                   "passed": not res2.applied, "detail": res2.message})
    return checks


# --------------------------------------------------------------------------- report

def summarize(rows: list[dict]) -> dict:
    out = {}
    for cond in CONDITIONS:
        rs = [r for r in rows if r["condition"] == cond]
        per_band = {}
        for band in ("low", "middle", "high"):
            b = [r for r in rs if r["band"] == band]
            if b:
                per_band[band] = {"n": len(b), "completed": round(sum(r["completed"] for r in b) / len(b), 3),
                                  "failed_on_levels": round(statistics.mean(r["failed_on_levels"] for r in b), 2),
                                  "submissions": round(statistics.mean(r["submissions"] for r in b), 2)}
        gaps = sum(len(r["true_gaps"]) for r in rs)
        out[cond] = {
            "n": len(rs),
            "completed": round(sum(r["completed"] for r in rs) / len(rs), 3),
            "submissions": round(statistics.mean(r["submissions"] for r in rs), 2),
            "failed_on_levels": round(statistics.mean(r["failed_on_levels"] for r in rs), 2),
            "gaps": gaps,
            "gaps_practiced_first": round(sum(len(r["gaps_practiced_first"]) for r in rs) / gaps, 3) if gaps else None,
            "practice_unneeded": sum(r["practice_unneeded"] for r in rs),
            "start_counts": dict(Counter(r["first_problem"] for r in rs)),
            "by_band": per_band,
        }
    diag_rows = [r for r in rows if r["condition"] == "diagnostic_today"]
    if diag_rows:
        pairs = [(r["true"][c], r["diag_stages"][c]) for r in diag_rows for c in r["true"]]
        out["diagnostic_accuracy"] = {"n": len(pairs), "exact": round(sum(a == b for a, b in pairs) / len(pairs), 3),
                                      "within_one": round(sum(abs(a - b) <= 1 for a, b in pairs) / len(pairs), 3),
                                      "gap_found": round(sum(b == 0 for a, b in pairs if a == 0) / max(1, sum(a == 0 for a, _ in pairs)), 3)}
        out["lesson_start_stage_zero"] = round(sum(all(v == 0 for v in r["lesson_start_stages"].values()) for r in diag_rows) / len(diag_rows), 3)
        used = sum(r.get("stages_used", 0) for r in diag_rows)
        found = sum(r.get("stages_found", 0) for r in diag_rows)
        out["stages_used_share"] = round(used / found, 3) if found else None
    return out


def report(summary: dict, checks: list[dict], n: int, seed: int) -> str:
    f = lambda x: "-" if x is None else (f"{round(x * 100)}%" if isinstance(x, float) and x <= 1 else str(x))
    L = ["# Diagnostic to lesson, end to end", "",
         f"{n} simulated students (diagnosis branch cohort generator, seed {seed}) with a known true stage per concept. "
         "Each student runs the real diagnostic quest, its handoff, and the lesson through `engine.course.Course` "
         "(what the student web API uses), in four conditions with the same random draws. No engine or diagnostic "
         "code is changed.", "",
         "## The handoff standard, checked on today's code", "",
         "| Check | Requirement | Result | Detail |", "|---|---|---|---|"]
    for c in checks:
        L.append(f"| {c['id']} | {c['requirement']} | {'pass' if c['passed'] else '**fail**'} | {c['detail']} |")
    L += ["", "## What happens in the lesson", "",
          "| | " + " | ".join(LABELS[c] for c in CONDITIONS) + " |", "|---|" + "---|" * len(CONDITIONS)]
    rowsdef = [("Finished the lesson", "completed"), ("Failed attempts on levels (mean)", "failed_on_levels"),
               ("Submissions to finish (mean)", "submissions"),
               ("Gaps that got practice before their level", "gaps_practiced_first"),
               ("Practice given where it was not needed", "practice_unneeded")]
    for label, k in rowsdef:
        L.append(f"| {label} | " + " | ".join(f(summary[c][k]) for c in CONDITIONS) + " |")
    L += ["", "Failed attempts on levels, by the student's true level:", "",
          "| Student level | " + " | ".join(LABELS[c] for c in CONDITIONS) + " |", "|---|" + "---|" * len(CONDITIONS)]
    for band in ("low", "middle", "high"):
        cells = [f"{summary[c]['by_band'][band]['failed_on_levels']} (n={summary[c]['by_band'][band]['n']})"
                 if band in summary[c]["by_band"] else "-" for c in CONDITIONS]
        L.append(f"| {band} | " + " | ".join(cells) + " |")
    if "diagnostic_accuracy" in summary:
        a = summary["diagnostic_accuracy"]
        L += ["", f"Diagnostic vs. true stage: exact {f(a['exact'])}, within one stage {f(a['within_one'])}, "
              f"true gaps (stage 0) found {f(a['gap_found'])}. Today's handoff uses {f(summary.get('stages_used_share'))} "
              f"of the diagnosed stages (only confident, non-borderline ones); the lesson starts every concept at "
              f"stage 0 for {f(summary['lesson_start_stage_zero'])} of students."]
    L += ["", "## Assumptions", "",
          f"- Learner model: pass chance per attempt {BASE_PASS} by true stage, +{PER_ATTEMPT} per extra attempt, "
          f"+{PRACTICE_BONUS} on practice problems; passing practice (or a level after struggling) lifts stage 0 to 1. "
          "Real students will differ; the comparison between conditions is the point, not the absolute numbers.",
          "- The proposed handoff uses only what exists: the student profile's `concepts` (read by `Course` as initial "
          "stages), `apply_placement` for the start problem, and the lesson's own progress record for practice before "
          "a level. The engine and diagnostic owners decide how to build it for real.",
          "- The diagnostic quest uses rules only (no model); the simulated children come from `diagnostic/simulation.py`.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--students", type=int, default=40)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args(argv)
    res = run(args.students, args.seed)
    summary = summarize(res["rows"])
    # Two checks are about the whole class, not one student: recompute them from the cohort.
    today = [r for r in res["rows"] if r["condition"] == "diagnostic_today"]
    lost = [r for r in today if r.get("diag_practice_ahead")]
    told = [r for r in today if r.get("next_stop_concept")]
    mismatch = [r for r in told if r["next_stop_concept"] not in pa.project().problem(r["first_problem"]).concepts]
    for c in res["checks"]:
        if c["id"] == "practice_carried":
            c["passed"] = not lost
            c["detail"] = (f"{len(lost)} of {len(today)} students had practice planned by the diagnostic "
                           f"({sum(len(r['diag_practice_ahead']) for r in lost)} problems) that the lesson never receives")
        if c["id"] == "message_matches":
            c["passed"] = not mismatch
            c["detail"] = (f"{len(mismatch)} of {len(told)} students are told a different first stop than the "
                           "lesson starts with")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "diag_lesson_summary.json").write_text(json.dumps(
        {"students": args.students, "seed": args.seed, "summary": summary, "checks": res["checks"],
         "labels": LABELS, "rows": res["rows"]}, indent=2), encoding="utf-8")
    (RESULTS / "diag_lesson_report.md").write_text(report(summary, res["checks"], args.students, args.seed), encoding="utf-8")
    print("wrote results/diag_lesson_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
