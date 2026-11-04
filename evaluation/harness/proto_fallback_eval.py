"""E07 on proto-branch: does every failure leave the student on a working path?

Customer requirement (Vision, MVP success criteria): "When validation or routing fails,
the student falls back to a working non-adaptive path rather than a broken one."

Each scenario injects one fault into proto's `Engine` (through its public constructor
arguments and its own progress files; no engine code is changed), then drives a
scripted student who submits a correct file up to MAX_SUBMISSIONS times.
A scenario passes when the student finishes the project without an unhandled error.

Usage: python -m evaluation.harness.proto_fallback_eval     (no model or AWS calls)
"""
from __future__ import annotations

import json
import tempfile
import traceback
from pathlib import Path

from . import proto_adapter as pa
from .proto_bugs import BUGS
from engine import grader as g
from engine.ai import ModelError, ScriptedProvider
from engine.events import EventLog
from engine.progress import JsonProgressStore
from engine.router import next_problem
from engine.session import Engine

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
MAX_SUBMISSIONS = 12


class _Router:
    """Wraps proto's router; fails in a chosen way on the n-th call."""

    def __init__(self, mode: str, fail_on: int = 1):
        self.mode, self.fail_on, self.calls = mode, fail_on, 0

    def __call__(self, *a, **k):
        self.calls += 1
        if self.calls >= self.fail_on:
            if self.mode == "raise":
                raise RuntimeError("router crashed")
            if self.mode == "unknown_problem":
                d = next_problem(*a, **k)
                return type(d)("level-99", d.reason, d.origin_level)
        return next_problem(*a, **k)


class _Grader(g.Grader):
    """Proto's grader, with injected outages."""

    def __init__(self, mode: str, n: int):
        super().__init__(timeout_s=10)
        self.mode, self.n, self.calls = mode, n, 0

    def grade(self, project, problem, path):
        self.calls += 1
        if self.calls <= self.n:
            if self.mode == "ungraded":
                return g.GradeResult(g.UNGRADED, error_message="grading service unavailable")
            if self.mode == "raise":
                raise RuntimeError("grader crashed")
            if self.mode == "timeout":
                return g.GradeResult(g.TIMEOUT, timeout_s=self.timeout_s)
        return super().grade(project, problem, path)


class _FailingStore(JsonProgressStore):
    def __init__(self, root, fail_saves: int):
        super().__init__(root)
        self.fail_saves = fail_saves

    def save(self, record):
        if self.fail_saves > 0:
            self.fail_saves -= 1
            raise OSError("disk full")
        super().save(record)


def _drive(engine: Engine, tmp: Path, student_id: str, correct: Path, first_wrong: Path | None = None) -> dict:
    path, submissions, crashed, notices, hint_sources = [], 0, None, [], []
    try:
        prob, n = engine.current_problem(student_id)
        notices += n
        while prob is not None and submissions < MAX_SUBMISSIONS:
            path.append(prob.id)
            src = first_wrong if (first_wrong is not None and submissions == 0) else correct
            out = engine.submit(student_id, src)
            submissions += 1
            notices += out.notices
            if out.hint_source:
                hint_sources.append(out.hint_source)
            if out.complete:
                prob = None
                break
            prob = out.next_problem
    except Exception as exc:
        crashed = f"{type(exc).__name__}: {exc}"
        tb = traceback.format_exc().strip().splitlines()
        where = next((l.strip() for l in reversed(tb) if "engine/session.py" in l), "")
        crashed += " (escapes Engine: " + where.split("engine/")[-1].replace('"', "") + ")" if where else ""
    events = EventLog(tmp).read()
    return {"completed": crashed is None and prob is None, "submissions": submissions, "crashed": crashed,
            "path": path, "notices": sorted(set(notices)), "hint_sources": hint_sources,
            "fallback_events": [e.get("reason") for e in events if e["event"] == "fallback"],
            "ungraded_events": sum(e["event"] == "ungraded" for e in events)}


def _scenario(name: str, requirement: str, expect: str, build, first_wrong: bool = False, prep=None) -> dict:
    with tempfile.TemporaryDirectory(prefix="codeai-e07-") as d:
        tmp = Path(d)
        correct = tmp / "correct.py"
        correct.write_text(pa.reference_source())
        wrong = None
        if first_wrong:
            b = BUGS[0]
            wrong = tmp / "wrong.py"
            wrong.write_text(pa.student_file(b["level"], b["function"], b["code"]))
        engine = build(tmp)
        sid = engine.new_student()
        if prep:
            prep(engine, tmp, sid)
        res = _drive(engine, tmp, sid, correct, wrong)
    res.update(scenario=name, requirement=requirement, expect=expect)
    return res


def _corrupt(engine, tmp, sid):
    engine.submit(sid, tmp / "correct.py")  # pass level 1 so there is saved progress
    for p in (tmp / "progress").rglob("*.json"):
        if sid in str(p) and "profile" not in p.name:
            p.write_text("{not json")


def main(argv=None) -> int:
    prj = pa.project()

    def eng(tmp, **kw):
        store = kw.pop("store", None) or JsonProgressStore(tmp)
        return Engine(prj, store, EventLog(tmp), grader=kw.pop("grader", g.Grader(timeout_s=10)), **kw)

    S = [
        _scenario("baseline adaptive", "-", "completes, no fallback", lambda t: eng(t)),
        _scenario("router raises on 2nd decision", "routing fails", "fallback to fixed order, completes",
                  lambda t: eng(t, router=_Router("raise", 2))),
        _scenario("router returns a problem not in the manifest", "routing fails",
                  "fallback to fixed order, completes", lambda t: eng(t, router=_Router("unknown_problem", 1))),
        _scenario("saved progress is corrupted", "routing state lost", "restart on fixed order, completes",
                  lambda t: eng(t), prep=_corrupt),
        _scenario("progress save fails twice", "infrastructure", "notice, completes",
                  lambda t: eng(t, store=_FailingStore(t, 2))),
        _scenario("grader unavailable for 2 submissions", "validation fails (transient)",
                  "retry, completes", lambda t: eng(t, grader=_Grader("ungraded", 2))),
        _scenario("grader unavailable for every submission", "validation fails (persistent)",
                  "falls back to a working non-adaptive path", lambda t: eng(t, grader=_Grader("ungraded", 10**6))),
        _scenario("grader raises an unexpected exception once", "validation fails (bug)",
                  "error handled, completes", lambda t: eng(t, grader=_Grader("raise", 1))),
        _scenario("grader times out once", "validation fails (timeout)", "counted as a failed attempt, completes",
                  lambda t: eng(t, grader=_Grader("timeout", 1))),
        _scenario("AI hint model returns ModelError", "AI hint fails", "teacher hint, completes",
                  lambda t: eng(t, hint_provider=ScriptedProvider([ModelError("throttled")])), first_wrong=True),
        _scenario("AI hint model raises an unexpected exception", "AI hint fails (bug)", "teacher hint, completes",
                  lambda t: eng(t, hint_provider=ScriptedProvider([RuntimeError("SDK bug")])), first_wrong=True),
        _scenario("adaptive routing turned off", "operator switch", "fixed order, completes",
                  lambda t: eng(t, adaptive=False)),
    ]
    passed = sum(s["completed"] for s in S)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "E07_proto_fallback_summary.json").write_text(json.dumps({"passed": passed, "n": len(S), "scenarios": S},
                                                                         indent=2), encoding="utf-8")
    L = ["# E07 on proto-branch: fallback under injected failures", "",
         "Requirement (Vision, MVP success criteria): when validation or routing fails, the student falls back to a "
         "working non-adaptive path rather than a broken one. Each scenario injects one fault into proto's `Engine` "
         f"(commit 745b446, unchanged) and submits a correct file up to {MAX_SUBMISSIONS} times. No model calls.", "",
         f"**{passed}/{len(S)} scenarios end with the student finishing the project.**", "",
         "| Scenario | Failure type | Expected | Finished | Submissions | Path | Fallback logged | Crash |",
         "|---|---|---|---|---|---|---|---|"]
    for s in S:
        L.append(f"| {s['scenario']} | {s['requirement']} | {s['expect']} | {'yes' if s['completed'] else '**no**'} | "
                 f"{s['submissions']} | {' → '.join(s['path'][:7])}{' …' if len(s['path']) > 7 else ''} | "
                 f"{', '.join(s['fallback_events']) or '-'} | {s['crashed'] or '-'} |")
    L.append("")
    (RESULTS / "E07_proto_fallback_report.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
