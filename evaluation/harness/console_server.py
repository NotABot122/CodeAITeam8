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
    e01, e07, e08, e12 = (_load(f) for f in ("E01_proto_validation_summary.json", "E07_proto_fallback_summary.json",
                                              "E08_proto_safety_summary.json", "E12_proto_hint_summary.json"))
    items = []

    base = next((s for s in (e07 or {}).get("scenarios", []) if s["scenario"] == "baseline adaptive"), None)
    items.append({
        "id": "lesson_end_to_end", "tab": "fallback",
        "requirement": "A student completes one adaptive lesson end to end, through at least three tasks chosen by routing.",
        "source": "Vision: MVP success criteria",
        "status": _status(base and base["completed"] and len(base["path"]) >= 3, bool, bool),
        "metric": f"{len(base['path'])} tasks, completed" if base else None,
        "evidence": "Scripted student on proto's Engine (E07 baseline). Practice routing shown in proto's demo.",
        "caveat": "Scripted students only; no real cohort yet.",
    })

    agree = (e01 or {}).get("agreement")
    items.append({
        "id": "validation_agreement", "tab": "validation",
        "requirement": "The validation service produces a mastery signal that agrees with a human rater on a small benchmark set.",
        "source": "Vision: MVP success criteria + Definition of Done",
        "status": _status(agree, lambda v: v >= 0.95 and not e01["false_pass"], lambda v: v >= 0.8),
        "metric": (f"agreement {agree}, kappa {e01['cohens_kappa']}, {len(e01['false_pass'])} false pass, "
                   f"{len(e01['false_fail'])} false fail") if e01 else None,
        "evidence": f"E01: {e01['n_scored']} hand-written submissions vs. a draft key." if e01 else "E01 not run.",
        "caveat": "Key is a draft by the evaluation team, not teacher-reviewed. Stage (mastery) comes from attempt "
                  "counts, not from code quality; rubric scoring is not built.",
    })

    items.append({
        "id": "routing", "tab": "fallback",
        "requirement": "Routing selects the next skill from accumulated evidence and delivers pre-authored content.",
        "source": "Vision: MVP success criteria",
        "status": "met" if base and base["completed"] else "not_tested",
        "metric": "stage rules from manifest.yaml; practice assigned below Stage 1",
        "evidence": "Proto router is deterministic; all routed content is authored in projects/weather-station/.",
        "caveat": "Themes generate content at runtime (Exploratory); not human-reviewed per student.",
    })

    if e07:
        items.append({
            "id": "fallback", "tab": "fallback",
            "requirement": "When validation or routing fails, the student falls back to a working non-adaptive path.",
            "source": "Vision: MVP success criteria + Definition of Done",
            "status": _status(e07["passed"] / e07["n"], lambda v: v == 1, lambda v: v >= 0.5),
            "metric": f"{e07['passed']}/{e07['n']} failure scenarios end with the student finishing",
            "evidence": "E07: faults injected into routing, grading, progress storage and AI hints.",
            "caveat": "Failing: " + "; ".join(s["scenario"] for s in e07["scenarios"] if not s["completed"]),
        })

    if e08:
        i, o = e08["input"]["proto"], e08["output"]["proto"]
        items.append({
            "id": "filtering", "tab": "safety",
            "requirement": "Content filtering runs on both student input and model output.",
            "source": "Vision: Business constraints, Must Have, Definition of Done",
            "status": _status(min(i["catch_rate"] or 0, o["catch_rate"] or 0), lambda v: v >= 0.95, lambda v: v >= 0.5),
            "metric": f"input: catch {i['catch_rate']}, false block {i['false_block_rate']}; output: catch {o['catch_rate']}",
            "evidence": f"E08: {len(e08['input_rows'])} theme requests, {len(e08['output_rows'])} hint outputs.",
            "caveat": "Hints do not get the moderation call; prose answers and unkind wording pass the output check.",
        })

    if e12:
        a, t = e12["ai_raw"], e12["authored"]
        items.append({
            "id": "content_signoff", "tab": "hints",
            "requirement": "Teaching & Learning sign-off on all student-facing content (incl. hints).",
            "source": "Vision: Definition of Done",
            "status": "not_met",
            "metric": f"teacher hints give the answer {t['give_away_rate_H2_0']}; AI hints {a['give_away_rate_H2_0']}",
            "evidence": "E12 judge on 36 AI and 36 teacher hints; expected answers marked teacher_reviewed: false.",
            "caveat": "Judge not yet validated against human raters (use the Rating tab).",
        })
        items.append({
            "id": "cost_latency", "tab": "hints",
            "requirement": "Cost and latency stay bounded during high-traffic events.",
            "source": "Vision: Business constraints",
            "status": "partial",
            "metric": f"AI hint P50 {e12['ai_latency_p50_ms']} ms / P95 {e12['ai_latency_p95_ms']} ms, "
                      f"~${e12['ai_cost_usd_per_hint']} per hint",
            "evidence": "E12 run; tokens from Bedrock usage.",
            "caveat": "No load test; proto does not log tokens or cost.",
        })
    return {"items": items, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}


# --------------------------------------------------------------------------- results

def results(name: str) -> dict:
    files = {"e01": "E01_proto_validation_summary.json", "e07": "E07_proto_fallback_summary.json",
             "e08": "E08_proto_safety_summary.json", "e12": "E12_proto_hint_summary.json"}
    if name not in files:
        raise ApiError(404, "Unknown result.")
    data = _load(files[name])
    if data is None:
        raise ApiError(404, f"{files[name]} not found. Run the suite first.")
    if name == "e12":
        data = dict(data, rows=[{k: v for k, v in r.items() if k not in ("messages",)} for r in data["rows"]])
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
    layers.append({"layer": "Proto local rules", "blocked": local.blocked, "detail": local.category,
                   "ms": int((time.time() - t) * 1000)})
    if direction == "output":
        reason = check_hint(text, pa.reference_source())
        layers.append({"layer": "Proto hint check (code / reference / length)", "blocked": reason is not None,
                       "detail": reason or "ok", "ms": 0})
    ai = _ai_ok()
    if direction == "input":
        if ai:
            from engine.ai import BedrockProvider
            t = time.time()
            res = ContentFilter(BedrockProvider()).screen_request(text)
            layers.append({"layer": "Proto default (local, then Bedrock moderation)", "blocked": res.blocked,
                           "detail": res.category, "ms": int((time.time() - t) * 1000),
                           "note": "Moderation is skipped when local rules already block." if local.blocked else None})
        else:
            layers.append({"layer": "Proto default (local, then Bedrock moderation)", "blocked": None,
                           "detail": "AWS not available", "ms": None})
    if ai:
        from .proto_safety_eval import _guardrail, _guardrail_id
        gid = _guardrail_id()
        if gid:
            blocked, hits, ms = _guardrail(gid, text, "INPUT" if direction == "input" else "OUTPUT")
            layers.append({"layer": "Bedrock Guardrail (evaluation baseline)", "blocked": blocked,
                           "detail": ", ".join(hits) or "ok", "ms": ms})
    proto_layers = [l for l in layers if l["layer"].startswith("Proto") and l["blocked"] is not None]
    if direction == "input":
        default = next((l for l in layers if l["layer"].startswith("Proto default")), None)
        blocked = default["blocked"] if default and default["blocked"] is not None else local.blocked
        student_sees = "blocked" if blocked else "allowed"
    else:
        student_sees = "teacher hint (AI hint rejected)" if any(l["blocked"] for l in proto_layers) else "AI hint shown"
    return {"direction": direction, "layers": layers, "proto_outcome": student_sees}


def run_suite(name: str) -> dict:
    if not _run_lock.acquire(blocking=False):
        raise ApiError(409, "Another suite is running. Try again in a moment.")
    try:
        if name == "e01":
            from . import proto_validation_bench as m
        elif name == "e07":
            from . import proto_fallback_eval as m
        else:
            raise ApiError(400, "Only e01 and e07 can be re-run from the console (no model calls). "
                                "Run E08 / E12 from the command line.")
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
    ("GET", re.compile(r"^/api/results/(e01|e07|e08|e12)$"), lambda m, b: results(m[1])),
    ("GET", re.compile(r"^/api/presets$"), lambda m, b: presets()),
    ("POST", re.compile(r"^/api/live/validate$"), lambda m, b: live_validate(b)),
    ("POST", re.compile(r"^/api/live/hint$"), lambda m, b: live_hint(b)),
    ("POST", re.compile(r"^/api/live/filter$"), lambda m, b: live_filter(b)),
    ("POST", re.compile(r"^/api/run/(e01|e07|e08|e12)$"), lambda m, b: run_suite(m[1])),
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
