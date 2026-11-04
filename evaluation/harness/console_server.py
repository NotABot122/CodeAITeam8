"""Evaluation console API: live evaluation of the proto engine plus stored results.

    python -m evaluation.harness.console_server [--port 8090] [--host 127.0.0.1]

Serves the built console (evaluation/console/dist) and a JSON API:

  GET  /api/health                 AI / Guardrail / AgentCore availability
  GET  /api/overview               customer requirements -> evidence, from results/*.json
  GET  /api/results/<e01|e07|e08|e12>
  GET  /api/presets                levels, seeded bugs, sample inputs
  POST /api/live/validate          {level, code}
  POST /api/live/hint              {level, code, attempt, gap?, agentcore?}
  POST /api/live/filter            {text, direction: "input" | "output"}
  POST /api/run/<e01|e07>          re-run a suite that needs no model calls
  GET  /api/rating/items           blind E12 rating items
  POST /api/rating                 {rater, item_id, H1..H5, notes}
  GET  /api/rating/agreement       human vs. judge, per rater

Student code typed in the console is executed by proto's grader (separate process,
time limit, database copy, no security sandbox). Keep the server on 127.0.0.1.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import mimetypes
import re
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import proto_adapter as pa
from .proto_bugs import BUGS

ROOT = Path(__file__).resolve().parents[1]
RESULTS, ANNOTATION, DATA = ROOT / "results", ROOT / "annotation", ROOT / "data"
DIST = ROOT / "console" / "dist"
MAX_CODE = 20_000
MAX_TEXT = 1_000
LEVELS = ("level-1", "level-2", "level-3", "level-4")
RATER = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
RATINGS = ANNOTATION / "E12_proto_hint_ratings.jsonl"
_write_lock = threading.Lock()
_run_lock = threading.Lock()


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# --------------------------------------------------------------------------- helpers

def _load(name: str):
    p = RESULTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _jsonl(path: Path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def _str(body: dict, key: str, limit: int, required: bool = True) -> str:
    v = body.get(key)
    if v is None and not required:
        return ""
    if not isinstance(v, str) or (required and not v.strip()):
        raise ApiError(400, f"'{key}' must be non-empty text.")
    if len(v) > limit:
        raise ApiError(400, f"'{key}' is longer than {limit} characters.")
    return v


def _level(body: dict) -> str:
    lv = body.get("level")
    if lv not in LEVELS:
        raise ApiError(400, f"'level' must be one of {', '.join(LEVELS)}.")
    return lv


_ai_state = {"checked": False, "ok": False, "reason": "not checked"}


def _ai_ok() -> bool:
    if not _ai_state["checked"]:
        try:
            import boto3
            boto3.client("sts").get_caller_identity()
            _ai_state.update(ok=True, reason="ok")
        except Exception as exc:  # no credentials, expired token, no network
            _ai_state.update(ok=False, reason=type(exc).__name__)
        _ai_state["checked"] = True
    return _ai_state["ok"]


def _require_ai():
    if not _ai_ok():
        raise ApiError(503, f"AWS is not available ({_ai_state['reason']}). Set AWS credentials and restart.")


# --------------------------------------------------------------------------- overview

def _status(value, good, ok):
    if value is None:
        return "not_tested"
    return "met" if good(value) else ("partial" if ok(value) else "not_met")


def overview() -> dict:
    """Customer requirements in plain language, with the measured result. No internal test codes."""
    e01, e07, e08, e12 = (_load(f) for f in ("E01_proto_validation_summary.json", "E07_proto_fallback_summary.json",
                                              "E08_proto_safety_summary.json", "E12_proto_hint_summary.json"))
    pc = lambda x: "-" if x is None else f"{round(x * 100)}%"
    items = []

    base = next((s for s in (e07 or {}).get("scenarios", []) if s["scenario"] == "baseline adaptive"), None)
    items.append({
        "id": "lesson_end_to_end", "tab": "fallback",
        "requirement": "A student can finish one adaptive lesson, with the order of at least three tasks chosen by the engine.",
        "source": "Vision: MVP success criteria",
        "status": _status(base and base["completed"] and len(base["path"]) >= 3, bool, bool),
        "metric": f"A test student finished all {len(base['path'])} levels." if base else None,
        "evidence": "Test student run through the engine.",
        "caveat": "Tested with scripted students, not a real class.",
    })

    agree = (e01 or {}).get("agreement")
    items.append({
        "id": "validation_agreement", "tab": "validation",
        "requirement": "The grader agrees with a teacher on a small set of student answers.",
        "source": "Vision: MVP success criteria and Definition of Done",
        "status": _status(agree, lambda v: v >= 0.95 and not e01["false_pass"], lambda v: v >= 0.8),
        "metric": (f"Same decision as the teacher on {pc(agree)} of {e01['n_scored']} answers; "
                   f"{len(e01['false_pass'])} wrong answers accepted, {len(e01['false_fail'])} correct answers rejected.")
                  if e01 else None,
        "evidence": "Hand-written answers for every level.",
        "caveat": "The teacher decisions are our draft and still need a real teacher. Progress (stage) comes from the "
                  "number of tries, not from how good the code is.",
    })

    items.append({
        "id": "routing", "tab": "fallback",
        "requirement": "The engine picks the next step from what the student has shown, using content written and approved in advance.",
        "source": "Vision: MVP success criteria",
        "status": "met" if base and base["completed"] else "not_tested",
        "metric": "Students below the target level get a practice problem before moving on.",
        "evidence": "Rules in the lesson's settings file; all routed content is written by people.",
        "caveat": "The optional student-chosen themes are generated on the fly and not reviewed per student.",
    })

    if e07:
        failing = [s for s in e07["scenarios"] if not s["completed"]]
        items.append({
            "id": "fallback", "tab": "fallback",
            "requirement": "If grading or the next-step choice fails, the student continues on the standard path instead of getting stuck.",
            "source": "Vision: MVP success criteria and Definition of Done",
            "status": _status(e07["passed"] / e07["n"], lambda v: v == 1, lambda v: v >= 0.5),
            "metric": f"The student finished in {e07['passed']} of {e07['n']} failure cases.",
            "evidence": "We broke one part of the engine at a time.",
            "caveat": ("Not handled: unexpected errors in grading or in the AI tutor, and grading that stays down."
                       if failing else ""),
        })

    if e08:
        i, o = e08["input"]["proto"], e08["output"]["proto"]
        items.append({
            "id": "filtering", "tab": "safety",
            "requirement": "Content is filtered both on what students type and on what the AI writes.",
            "source": "Vision: business constraints, Must Have and Definition of Done",
            "status": _status(min(i["catch_rate"] or 0, o["catch_rate"] or 0), lambda v: v >= 0.95, lambda v: v >= 0.5),
            "metric": f"Student requests: {pc(i['catch_rate'])} of harmful ones stopped, but {pc(i['false_block_rate'])} of "
                      f"harmless ones stopped too. Tutor hints: {pc(o['catch_rate'])} of problem hints stopped.",
            "evidence": f"{len(e08['input_rows'])} student requests and {len(e08['output_rows'])} tutor hints.",
            "caveat": "Hints that give the answer in plain words, or are unkind, are not stopped.",
        })

    if e12:
        a, t = e12["ai_raw"], e12["authored"]
        items.append({
            "id": "content_signoff", "tab": "hints",
            "requirement": "The curriculum team signs off on everything students see, including hints.",
            "source": "Vision: Definition of Done",
            "status": "not_met",
            "metric": f"{pc(a['give_away_rate_H2_0'])} of AI hints and {pc(t['give_away_rate_H2_0'])} of teacher-written "
                      "hints give the answer away.",
            "evidence": f"{a['n']} AI and {t['n']} teacher-written hints, rated by an AI reviewer and AWS AgentCore.",
            "caveat": "No sign-off yet. The AI reviewer still needs checking by teachers.",
        })
        items.append({
            "id": "cost_latency", "tab": "hints",
            "requirement": "Cost and response time stay under control when many students use it at once.",
            "source": "Vision: business constraints",
            "status": "partial",
            "metric": f"An AI hint takes about {round((e12['ai_latency_p50_ms'] or 0) / 1000, 1)} s "
                      f"(slowest 5%: {round((e12['ai_latency_p95_ms'] or 0) / 1000, 1)} s) and costs about "
                      f"${e12['ai_cost_usd_per_hint']}.",
            "evidence": "Measured on real AWS Bedrock calls.",
            "caveat": "Not tested under load yet.",
        })
    dl = _load("diag_lesson_summary.json")
    if dl:
        sm, checks = dl["summary"], dl["checks"]
        low = {c: sm[c]["by_band"].get("low", {}).get("failed_on_levels") for c in ("no_diagnostic", "diagnostic", "diagnostic_intervention")}
        failing = [c for c in checks if not c["passed"]]
        items.append({
            "id": "diagnostic_handoff", "tab": "diagnostic",
            "requirement": "Any student can take the diagnostic and start the lesson at their own level.",
            "source": "Product goal; Vision: diagnostic placement (Exploratory)",
            "status": "met" if not failing else ("partial" if len(failing) < len(checks) else "not_met"),
            "metric": f"Diagnosed gaps that get practice before their level: {pc(sm['diagnostic']['gaps_practiced_first'])}. "
                      f"Students who start low fail {low['no_diagnostic']} times on levels without a diagnostic, "
                      f"{low['diagnostic']} with it, {low['diagnostic_intervention']} with in-lesson help on too.",
            "evidence": f"{dl['students']} simulated students through the real diagnostic, handoff and lesson.",
            "caveat": (f"{len(failing)} of {len(checks)} handoff checks still fail: "
                       + "; ".join(c["requirement"].rstrip(".").lower() for c in failing) + ".") if failing else "",
        })
    order = {"not_met": 0, "partial": 1, "met": 2, "not_tested": 3}
    items.sort(key=lambda i: order.get(i["status"], 9))  # problems first: that is what to talk about
    return {"items": items, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}


# --------------------------------------------------------------------------- results

def results(name: str) -> dict:
    files = {"e01": "E01_proto_validation_summary.json", "e07": "E07_proto_fallback_summary.json",
             "e08": "E08_proto_safety_summary.json", "e12": "E12_proto_hint_summary.json",
             "diag": "diag_lesson_summary.json"}
    if name not in files:
        raise ApiError(404, "Unknown result.")
    data = _load(files[name])
    if data is None:
        raise ApiError(404, f"{files[name]} not found. Run the suite first.")
    if name == "e12":
        data = dict(data, rows=[{k: v for k, v in r.items() if k not in ("messages",)} for r in data["rows"]])
    if name == "diag":
        data = {k: v for k, v in data.items() if k != "rows"}  # per-student rows are large; the page needs the summary
    return data


def presets() -> dict:
    prj = pa.project()
    levels = [{"id": lv, "title": prj.problem(lv).title, "label": prj.problem(lv).label,
               "instructions": prj.problem(lv).instructions} for lv in LEVELS]
    bugs = [{"bug_id": b["bug_id"], "level": b["level"], "gap": b["gap"],
             "code": pa.student_file(b["level"], b["function"], b["code"])} for b in BUGS]
    correct = {lv: pa.student_file(lv, "__none__", "") for lv in LEVELS}
    return {"levels": levels, "bugs": bugs, "correct": correct,
            "theme_requests": _jsonl(DATA / "proto_theme_requests.jsonl"),
            "hint_outputs": _jsonl(DATA / "proto_hint_outputs.jsonl")}


# --------------------------------------------------------------------------- live

def live_validate(body: dict) -> dict:
    level, code = _level(body), _str(body, "code", MAX_CODE)
    t = time.time()
    result, messages = pa.grade_source(level, code)
    return {"status": result.status, "passed": result.passed, "messages": messages,
            "tests_run": result.tests_run, "ms": int((time.time() - t) * 1000)}


def live_hint(body: dict) -> dict:
    from .proto_hint_eval import RecordingProvider, _judge
    from engine.hints import AIHinter
    from engine.safety import ContentFilter
    _require_ai()
    level, code = _level(body), _str(body, "code", MAX_CODE)
    attempt = body.get("attempt", 1)
    if not isinstance(attempt, int) or not 1 <= attempt <= 5:
        raise ApiError(400, "'attempt' must be 1-5.")
    gap = _str(body, "gap", 500, required=False) or "Unknown (live input): judge from the check messages and code."
    result, messages = pa.grade_source(level, code)
    if result.passed:
        return {"passed": True, "messages": messages}
    problem = pa.project().problem(level)
    provider = RecordingProvider()
    hinter = AIHinter(provider, ContentFilter(), reference_source=pa.reference_source())
    ai = hinter.hint(problem, messages, code, attempt)
    raw = provider.last
    authored = pa.authored_hint(level, attempt)
    bug = {"level": level, "gap": gap}
    out = {"passed": False, "messages": messages, "attempt": attempt,
           "ai": {"raw": " ".join(raw.text.split()) if raw else None, "served": ai is not None,
                  "rejected": hinter.last_rejection, "latency_ms": raw.latency_ms if raw else None,
                  "tokens_in": raw.input_tokens if raw else None, "tokens_out": raw.output_tokens if raw else None,
                  "model_id": raw.model_id if raw else None},
           "authored": {"text": authored}}
    # All scoring calls are independent: run them in parallel so a live demo waits for the slowest one only.
    from concurrent.futures import ThreadPoolExecutor
    texts = {"ai": out["ai"]["raw"], "authored": authored}
    with ThreadPoolExecutor(max_workers=6) as pool:
        judges = {k: pool.submit(_judge, bug, code, messages, attempt, t) for k, t in texts.items() if t}
        ac_jobs = {}
        if body.get("agentcore") and out["ai"]["raw"]:
            from . import agentcore_eval as ace
            from .proto_hint_eval import JUDGE_MODEL
            ev = ace.find_or_create_hint_evaluator(JUDGE_MODEL)
            user = (f"Attempt {attempt} on {problem.label}. Task: {problem.instructions.strip()[:1200]}\n"
                    f"My code:\n{code}\nChecks that failed:\n" + "\n".join(messages) + "\nCan I have a hint?")
            for key, text in texts.items():
                if text:
                    _, tids, spans = ace.build_session([(user, text)])
                    ac_jobs[key] = (tids[0], pool.submit(ace.evaluate, ev, spans, tids),
                                    pool.submit(ace.evaluate, "Builtin.Harmfulness", spans, tids))
        for key, fut in judges.items():
            out["ai" if key == "ai" else "authored"]["judge"] = fut.result()[0]
        if ac_jobs:
            out["agentcore"] = {}
            for key, (tid, h2f, harmf) in ac_jobs.items():
                h2, harm = h2f.result().get(tid, {}), harmf.result().get(tid, {})
                out["agentcore"][key] = {"h2": h2.get("value"), "h2_label": h2.get("label"),
                                         "h2_explanation": h2.get("explanation"), "harmfulness": harm.get("value"),
                                         "harmfulness_label": harm.get("label")}
    return out


def live_filter(body: dict) -> dict:
    from engine.hints import check_hint
    from engine.safety import ContentFilter, screen_text
    text = _str(body, "text", MAX_TEXT)
    direction = body.get("direction", "input")
    if direction not in ("input", "output"):
        raise ApiError(400, "'direction' must be input or output.")
    layers = []
    t = time.time()
    local = screen_text(text)
    layers.append({"layer": "Word list", "blocked": local.blocked, "detail": local.category,
                   "ms": int((time.time() - t) * 1000)})
    if direction == "output":
        reason = check_hint(text, pa.reference_source())
        layers.append({"layer": "Hint check (code, copied answer, length)", "blocked": reason is not None,
                       "detail": reason or "ok", "ms": 0})
    ai = _ai_ok()
    if direction == "input":
        if ai:
            from engine.ai import BedrockProvider
            t = time.time()
            res = ContentFilter(BedrockProvider()).screen_request(text)
            layers.append({"layer": "Word list, then AI moderation (engine default)", "blocked": res.blocked,
                           "detail": res.category, "ms": int((time.time() - t) * 1000),
                           "note": "The AI moderation step is skipped when the word list already blocks." if local.blocked else None})
        else:
            layers.append({"layer": "Word list, then AI moderation (engine default)", "blocked": None,
                           "detail": "live AI is off", "ms": None})
    if ai:
        from .proto_safety_eval import _guardrail, _guardrail_id
        gid = _guardrail_id()
        if gid:
            blocked, hits, ms = _guardrail(gid, text, "INPUT" if direction == "input" else "OUTPUT")
            layers.append({"layer": "AWS Bedrock Guardrails (for comparison)", "blocked": blocked,
                           "detail": ", ".join(hits) or "ok", "ms": ms})
    proto_layers = [l for l in layers if l["layer"] in ("Word list", "Hint check (code, copied answer, length)") and l["blocked"] is not None]
    if direction == "input":
        default = next((l for l in layers if l["layer"].startswith("Word list, then")), None)
        blocked = default["blocked"] if default and default["blocked"] is not None else local.blocked
        student_sees = "a message that the request is blocked" if blocked else "the project they asked for"
    else:
        student_sees = "the teacher-written hint (AI hint not shown)" if any(l["blocked"] for l in proto_layers) else "the AI hint"
    return {"direction": direction, "layers": layers, "proto_outcome": student_sees}


def run_suite(name: str) -> dict:
    if not _run_lock.acquire(blocking=False):
        raise ApiError(409, "Another suite is running. Try again in a moment.")
    try:
        if name == "e01":
            from . import proto_validation_bench as m
        elif name == "e07":
            from . import proto_fallback_eval as m
        elif name == "diag":
            from . import diag_lesson_eval as m
            t = time.time()
            m.main(["--students", "40"])  # same size as the published run, so numbers stay comparable
            return {"suite": name, "seconds": round(time.time() - t, 1), "result": results(name)}
        else:
            raise ApiError(400, "Only the grading, failure and diagnostic tests can be re-run here. "
                                "The filter and hint tests call AI models; run them from the command line.")
        t = time.time()
        m.main([])
        return {"suite": name, "seconds": round(time.time() - t, 1), "result": results(name)}
    finally:
        _run_lock.release()


# --------------------------------------------------------------------------- human rating (E12)

def rating_items() -> dict:
    sheet = ANNOTATION / "E12_proto_hint_rating_sheet.csv"
    if not sheet.exists():
        raise ApiError(404, "No rating sheet. Run proto_hint_eval first.")
    with sheet.open(encoding="utf-8") as fh:
        items = [{k: r[k] for k in ("item_id", "level", "attempt", "check_messages", "student_mistake", "hint")}
                 for r in csv.DictReader(fh)]
    done = {}
    for r in _jsonl(RATINGS):
        done.setdefault(r["rater"], set()).add(r["item_id"])
    return {"items": items, "rated": {k: sorted(v) for k, v in done.items()}}


def save_rating(body: dict) -> dict:
    rater = body.get("rater")
    if not isinstance(rater, str) or not RATER.match(rater):
        raise ApiError(400, "'rater' must be 1-32 letters, digits, - or _.")
    item_id = body.get("item_id")
    valid_ids = {i["item_id"] for i in rating_items()["items"]}
    if item_id not in valid_ids:
        raise ApiError(400, "Unknown item_id.")
    scales = {"H1": (0, 1), "H2": (0, 2), "H3": (0, 2), "H4": (0, 1), "H5": (0, 1)}
    row = {"rater": rater, "item_id": item_id,
           "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    for k, (lo, hi) in scales.items():
        v = body.get(k)
        if not isinstance(v, int) or not lo <= v <= hi:
            raise ApiError(400, f"'{k}' must be an integer {lo}-{hi}.")
        row[k] = v
    row["notes"] = _str(body, "notes", 500, required=False)
    with _write_lock:
        ANNOTATION.mkdir(exist_ok=True)
        with RATINGS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"saved": True}


def rating_agreement() -> dict:
    key = {k["item_id"]: k for k in json.loads((ANNOTATION / "E12_proto_hint_key.json").read_text())} \
        if (ANNOTATION / "E12_proto_hint_key.json").exists() else {}
    e12 = _load("E12_proto_hint_summary.json") or {"rows": []}
    sheet = ANNOTATION / "E12_proto_hint_rating_sheet.csv"
    judge_by_item = {}
    if sheet.exists():
        with sheet.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                k = key.get(r["item_id"], {})
                src = "ai_raw" if k.get("source") == "ai_raw" else "authored"
                match = next((x for x in e12["rows"] if x["source"] == src and x["hint"] == r["hint"]
                              and str(x["attempt"]) == r["attempt"]), None)
                if match and "H2" in match.get("judge", {}):
                    judge_by_item[r["item_id"]] = match["judge"]
    latest = {}
    for r in _jsonl(RATINGS):
        latest[(r["rater"], r["item_id"])] = r
    per_rater = {}
    for (rater, item), r in latest.items():
        per_rater.setdefault(rater, []).append((r, judge_by_item.get(item), key.get(item, {}).get("source")))
    out = []
    for rater, rows in sorted(per_rater.items()):
        pairs = [(r["H2"], j["H2"]) for r, j, _ in rows if j]
        exact = round(sum(a == b for a, b in pairs) / len(pairs), 3) if pairs else None
        give = {s: [r["H2"] == 0 for r, _, src in rows if src == s] for s in ("ai_raw", "authored")}
        out.append({"rater": rater, "n": len(rows), "h2_exact_vs_judge": exact,
                    "give_away_ai": round(sum(give["ai_raw"]) / len(give["ai_raw"]), 3) if give["ai_raw"] else None,
                    "give_away_teacher": round(sum(give["authored"]) / len(give["authored"]), 3) if give["authored"] else None})
    raters = sorted(per_rater)
    between = None
    if len(raters) >= 2:
        a = {i: r["H2"] for (rt, i), r in latest.items() if rt == raters[0]}
        b = {i: r["H2"] for (rt, i), r in latest.items() if rt == raters[1]}
        common = sorted(set(a) & set(b))
        if common:
            between = {"raters": raters[:2], "n": len(common),
                       "h2_exact": round(sum(a[i] == b[i] for i in common) / len(common), 3)}
    return {"raters": out, "between_raters": between}


# --------------------------------------------------------------------------- HTTP

ROUTES = [
    ("GET", re.compile(r"^/api/health$"), lambda m, b: {"ai": _ai_ok(), "ai_reason": _ai_state["reason"],
                                                         "proto_root": str(pa.PROTO_ROOT)}),
    ("GET", re.compile(r"^/api/overview$"), lambda m, b: overview()),
    ("GET", re.compile(r"^/api/results/(e01|e07|e08|e12|diag)$"), lambda m, b: results(m[1])),
    ("GET", re.compile(r"^/api/presets$"), lambda m, b: presets()),
    ("POST", re.compile(r"^/api/live/validate$"), lambda m, b: live_validate(b)),
    ("POST", re.compile(r"^/api/live/hint$"), lambda m, b: live_hint(b)),
    ("POST", re.compile(r"^/api/live/filter$"), lambda m, b: live_filter(b)),
    ("POST", re.compile(r"^/api/run/(e01|e07|e08|e12|diag)$"), lambda m, b: run_suite(m[1])),
    ("GET", re.compile(r"^/api/rating/items$"), lambda m, b: rating_items()),
    ("POST", re.compile(r"^/api/rating$"), lambda m, b: save_rating(b)),
    ("GET", re.compile(r"^/api/rating/agreement$"), lambda m, b: rating_agreement()),
]


class Handler(BaseHTTPRequestHandler):
    server_version = "CodeAIEvalConsole/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, urlparse(self.path).path))

    def _send(self, status, payload, ctype="application/json"):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("application/json", "text/")) else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_CODE * 2:
            raise ApiError(413, "Request too large.")
        if not n:
            return {}
        try:
            data = json.loads(self.rfile.read(n))
        except json.JSONDecodeError:
            raise ApiError(400, "Body must be JSON.") from None
        if not isinstance(data, dict):
            raise ApiError(400, "Body must be a JSON object.")
        return data

    def _api(self, method):
        path = urlparse(self.path).path
        try:
            for verb, pat, fn in ROUTES:
                m = pat.match(path)
                if m:
                    if verb != method:
                        raise ApiError(405, "Wrong method.")
                    return self._send(200, fn(m, self._body() if method == "POST" else {}))
            raise ApiError(404, "No such endpoint.")
        except ApiError as e:
            self._send(e.status, {"error": e.message})
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            self._send(500, {"error": f"Server error: {type(exc).__name__}. See the server log."})

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return self._api("GET")
        if not DIST.is_dir():
            return self._send(404, {"error": "Console not built. Run: cd evaluation/console && npm run build"})
        target = (DIST / path.lstrip("/")).resolve()
        if not target.is_file() or DIST.resolve() not in target.parents:
            target = DIST / "index.html"
        self._send(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")

    def do_POST(self):
        if urlparse(self.path).path.startswith("/api/"):
            return self._api("POST")
        self._send(405, {"error": "Wrong method."})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evaluation.harness.console_server")
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("warning: the console runs submitted code; keep it on localhost.", file=sys.stderr)
    pa.project()  # fail fast if proto is missing
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Evaluation console on http://{args.host}:{args.port}  (AI {'on' if _ai_ok() else 'off: ' + _ai_state['reason']})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
