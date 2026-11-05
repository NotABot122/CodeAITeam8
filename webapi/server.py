"""HTTP front for webapi.service. Standard library only.

    python -m webapi.server [--port 8080] [--data-dir DIR] [--ai off|bedrock] [--no-adaptive]

Routes (JSON):
    GET  /api/health
    POST /api/students                      -> new student + state (skips the readiness quest)
    GET  /api/quest/options                 -> buddies, goals, zones
    POST /api/quest                         {"buddy", "goal"} -> {student_id, welcome, first}
    GET  /api/quest/<id>/next               -> next step, or {done: true, ...} (result is applied)
    POST /api/quest/<id>/answer             {"response", "elapsedMs"} -> feedback
    POST /api/quest/<id>/finish             -> end early (result is applied)
    GET  /api/students/<id>                 -> state
    GET  /api/students/<id>/course          -> the whole course: topics, finished work, ideas, what's next
    POST /api/students/<id>/submit          {"code": "..."} -> {outcome, state}
    GET  /api/students/<id>/projects        -> {choices: [{project, title, pitch, suggested, current}], locked, topic}
    POST /api/students/<id>/project         {"project": "monster-arena"} -> {state, choices, locked} (before it's started)
    POST /api/students/<id>/pathway         {"grade": 9-12} -> {pathway, state} (Strands Decider 2B; once per student)
    POST /api/students/<id>/hint            {"code": "..."} -> {outcome, state} (next hint; not a submission)
    POST /api/students/<id>/answer          {"answers": {"q1": 1, "q3": "text"}} -> {outcome, state}
    GET  /api/students/<id>/next            -> {nextStep}
    POST /api/students/<id>/next            {"option": 0, "theme": "..."} -> {message, built, state}
    POST /api/students/<id>/theme           {"request": "pokemon"} -> {built, message, state}
    POST /api/students/<id>/theme/reset     -> state
    GET  /api/dev/ai, /api/dev/ai/calls/after/<n>, POST /api/dev/ai/clear   (only with --dev: the AI inspector)
    POST /api/blocks                        {"code": "..."} -> {ok, workspace, blockCount} or {ok: false, reason, message, line}
Teacher routes (GET, need header X-Teacher-Token = $CODEAI_TEACHER_TOKEN; off if unset):
    /api/teacher/overview, /api/teacher/students/<id>, /api/teacher/content-check
Anything else is served from frontend/dist if it has been built.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from engine.ai import DEFAULT_THEME_MODEL_ID, BedrockProvider, FallbackProvider, ModelError, provider_from_env
from engine.ai_trace import FEATURES, TraceLog, TracingProvider, current_student
from engine.cli import DEFAULT_DATA, DEFAULT_PROJECT

from .service import ApiError, Service
from .teacher import Teacher, token_ok

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
MAX_BODY = 64 * 1024
ID = r"([^/]+)"
ROUTES = [
    ("GET", re.compile(r"^/api/health$"), lambda s, m, b: s.health()),
    ("POST", re.compile(r"^/api/students$"), lambda s, m, b: s.new_student()),
    ("GET", re.compile(r"^/api/quest/options$"), lambda s, m, b: s.quest_options()),
    ("POST", re.compile(r"^/api/quest$"), lambda s, m, b: s.quest_start(b.get("buddy"), b.get("goal"))),
    ("GET", re.compile(rf"^/api/quest/{ID}/next$"), lambda s, m, b: s.quest_next(m[1])),
    ("POST", re.compile(rf"^/api/quest/{ID}/answer$"), lambda s, m, b: s.quest_answer(m[1], b.get("response"), b.get("elapsedMs"))),
    ("POST", re.compile(rf"^/api/quest/{ID}/finish$"), lambda s, m, b: s.quest_finish(m[1])),
    ("GET", re.compile(rf"^/api/students/{ID}$"), lambda s, m, b: s.state(m[1])),
    ("GET", re.compile(rf"^/api/students/{ID}/course$"), lambda s, m, b: s.course_view(m[1])),
    ("POST", re.compile(rf"^/api/students/{ID}/submit$"), lambda s, m, b: s.submit(m[1], b.get("code"))),
    ("GET", re.compile(rf"^/api/students/{ID}/projects$"), lambda s, m, b: s.project_choices(m[1])),
    ("POST", re.compile(rf"^/api/students/{ID}/project$"), lambda s, m, b: s.choose_project(m[1], b.get("project"))),
    ("POST", re.compile(rf"^/api/students/{ID}/pathway$"), lambda s, m, b: s.pathway(m[1], b.get("grade"))),
    ("POST", re.compile(rf"^/api/students/{ID}/hint$"), lambda s, m, b: s.hint(m[1], b.get("code"))),
    ("POST", re.compile(rf"^/api/students/{ID}/answer$"), lambda s, m, b: s.answer(m[1], b.get("answers"))),
    ("GET", re.compile(rf"^/api/students/{ID}/next$"), lambda s, m, b: {"nextStep": s.next_step(m[1])}),
    ("POST", re.compile(rf"^/api/students/{ID}/next$"), lambda s, m, b: s.start_next(m[1], b.get("option"), b.get("theme"))),
    ("POST", re.compile(rf"^/api/students/{ID}/theme$"), lambda s, m, b: s.build_theme(m[1], b.get("request"))),
    ("POST", re.compile(rf"^/api/students/{ID}/theme/reset$"), lambda s, m, b: s.reset_theme(m[1])),
    # Dev-only AI inspector (server started with --dev); 404 otherwise.
    ("GET", re.compile(r"^/api/dev/ai$"), lambda s, m, b: s.dev_info()),
    ("GET", re.compile(r"^/api/dev/ai/calls/after/(\d+)$"), lambda s, m, b: s.dev_calls(int(m[1]))),
    ("POST", re.compile(r"^/api/dev/ai/clear$"), lambda s, m, b: s.dev_clear()),
    ("POST", re.compile(r"^/api/blocks$"), lambda s, m, b: s.to_blocks(b.get("code"))),
]


def make_handler(service: Service, teacher_token=None):
    teacher = Teacher(service)
    teacher_routes = {
        "/api/teacher/overview": lambda: teacher.overview(),
        "/api/teacher/content-check": lambda: teacher.content_check(),
    }
    class Handler(BaseHTTPRequestHandler):
        server_version = "CodeAI"

        def log_message(self, fmt, *args):  # keep student ids out of logs
            pass

        def _send(self, status: int, payload, content_type="application/json", extra=None):
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ApiError(413, "too_large", "That request is too big.")
            if not length:
                return {}
            try:
                data = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError):
                raise ApiError(400, "bad_request", "The request wasn't valid JSON.") from None
            if not isinstance(data, dict):
                raise ApiError(400, "bad_request", "The request must be a JSON object.")
            return data

        def _api(self, method: str, path: str):
            try:
                if path.startswith("/api/teacher/"):
                    token_ok(teacher_token, self.headers.get("X-Teacher-Token"))
                    if method != "GET":
                        raise ApiError(405, "method_not_allowed", "Wrong method.")
                    if path in teacher_routes:
                        return self._send(200, teacher_routes[path]())
                    m = re.match(r"^/api/teacher/students/([^/]+)$", path)
                    if m:
                        return self._send(200, teacher.student(m.group(1)))
                    raise ApiError(404, "not_found", "No such endpoint.")
                wrong_method = False
                for verb, pattern, fn in ROUTES:
                    match = pattern.match(path)
                    if not match:
                        continue
                    if verb != method:
                        wrong_method = True
                        continue
                    body = self._body() if method == "POST" else {}
                    # Tag model calls made during this request with its student (for the dev AI inspector).
                    who = re.match(r"^/api/(?:students|quest)/([^/]+)", path)
                    token = current_student.set(who.group(1) if who else None)
                    try:
                        return self._send(200, fn(service, match, body))
                    finally:
                        current_student.reset(token)
                if wrong_method:
                    raise ApiError(405, "method_not_allowed", "Wrong method.")
                raise ApiError(404, "not_found", "No such endpoint.")
            except ApiError as err:
                self._send(err.status, {"error": {"code": err.code, "message": err.message}})
            except Exception:  # never leak internals to students
                traceback.print_exc(file=sys.stderr)
                self._send(500, {"error": {"code": "server_error", "message": "Something went wrong on our side. Try again."}})

        def _static(self, path: str):
            if not DIST.is_dir():
                return self._send(404, {"error": {"code": "not_found", "message": "Frontend not built."}})
            target = (DIST / path.lstrip("/")).resolve()
            if not target.is_file() or DIST.resolve() not in target.parents:
                target = DIST / "index.html"  # single-page app fallback
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self._send(200, target.read_bytes(), ctype)

        def do_GET(self):
            path = urlparse(self.path).path
            self._api("GET", path) if path.startswith("/api/") else self._static(path)

        def do_POST(self):
            path = urlparse(self.path).path
            if path.startswith("/api/"):
                self._api("POST", path)
            else:
                self._send(405, {"error": {"code": "method_not_allowed", "message": "Wrong method."}})

    return Handler


def build_service(data_dir, ai="bedrock", adaptive=True, project=DEFAULT_PROJECT, dev=False, guardrail=True) -> Service:
    provider, reason = None, "turned off"
    if ai != "off":
        try:
            provider = provider_from_env(ai)
        except (ImportError, ModelError, ValueError) as exc:
            reason = str(exc)
    trace = TraceLog() if dev else None
    # "Make it yours" project generation: its own model (GPT-5.6 Terra by default), the team model as backup.
    theme_provider = None
    if provider is not None and ai == "bedrock":
        try:
            theme_provider = BedrockProvider(model_id=os.environ.get("CODEAI_THEME_MODEL_ID", DEFAULT_THEME_MODEL_ID),
                                             timeout_s=120)
        except (ImportError, ModelError, ValueError) as exc:
            print(f"Theme model not available ({exc}); themes use the team model.", file=sys.stderr)
    if trace is not None and provider is not None:
        provider = TracingProvider(provider, trace)       # records every call for the AI inspector
        if theme_provider is not None:
            theme_provider = TracingProvider(theme_provider, trace)
    if theme_provider is not None:
        theme_provider = FallbackProvider(theme_provider, provider)
    service = Service(Path(data_dir), Path(project), provider=provider, ai_reason=reason, adaptive=adaptive,
                      theme_provider=theme_provider)
    service.trace = trace
    # Safety: the Bedrock Guardrail made from our local rules (engine/guardrail.py), when AI is on and it has been
    # synced. Otherwise, or if a check fails, the local rules decide.
    service.guardrail = None
    if guardrail and provider is not None:
        from engine import safety
        from engine.guardrail import BedrockGuardrail, load_config
        cfg = load_config()
        if cfg:
            try:
                service.guardrail = BedrockGuardrail(cfg["id"], cfg["version"], cfg.get("region", "us-west-2"), trace=trace)
                safety.configure_guardrail(service.guardrail)
            except Exception as exc:          # boto3 missing or misconfigured: keep the local rules
                print(f"Bedrock Guardrail not used ({exc}); local safety rules only.", file=sys.stderr)
    return service


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m webapi.server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA))
    parser.add_argument("--ai", choices=["bedrock", "off"], default="bedrock")
    parser.add_argument("--no-adaptive", action="store_true")
    parser.add_argument("--no-guardrail", action="store_true",
                        help="use only the local safety rules, not the Bedrock Guardrail (engine/guardrail.py)")
    parser.add_argument("--dev", action="store_true",
                        help="dev/demo only: record every AI call and show the AI inspector panel in the UI")
    args = parser.parse_args(argv)
    service = build_service(args.data_dir, args.ai, not args.no_adaptive, dev=args.dev, guardrail=not args.no_guardrail)
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(service, os.environ.get("CODEAI_TEACHER_TOKEN") or None))
    g = service.guardrail
    print(f"CodeAI student UI on http://{args.host}:{args.port}  (AI {'on' if service.provider else 'off'}; "
          f"themes: {getattr(service.theme_provider, 'model_id', None) or 'team model'}; "
          f"safety: {g.label if g else 'local rules'})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
