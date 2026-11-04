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
    POST /api/students/<id>/submit          {"code": "..."} -> {outcome, state}
    POST /api/students/<id>/answer          {"answers": {"q1": 1, "q3": "text"}} -> {outcome, state}
    GET  /api/students/<id>/next            -> {nextStep}
    POST /api/students/<id>/next            {"option": 0, "theme": "..."} -> {message, built, state}
    POST /api/students/<id>/theme           {"request": "pokemon"} -> {built, message, state}
    POST /api/students/<id>/theme/reset     -> state
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

from engine.ai import ModelError, provider_from_env
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
    ("POST", re.compile(rf"^/api/students/{ID}/submit$"), lambda s, m, b: s.submit(m[1], b.get("code"))),
    ("POST", re.compile(rf"^/api/students/{ID}/answer$"), lambda s, m, b: s.answer(m[1], b.get("answers"))),
    ("GET", re.compile(rf"^/api/students/{ID}/next$"), lambda s, m, b: {"nextStep": s.next_step(m[1])}),
    ("POST", re.compile(rf"^/api/students/{ID}/next$"), lambda s, m, b: s.start_next(m[1], b.get("option"), b.get("theme"))),
    ("POST", re.compile(rf"^/api/students/{ID}/theme$"), lambda s, m, b: s.build_theme(m[1], b.get("request"))),
    ("POST", re.compile(rf"^/api/students/{ID}/theme/reset$"), lambda s, m, b: s.reset_theme(m[1])),
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
                    return self._send(200, fn(service, match, body))
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


def build_service(data_dir, ai="bedrock", adaptive=True, project=DEFAULT_PROJECT) -> Service:
    provider, reason = None, "turned off"
    if ai != "off":
        try:
            provider = provider_from_env(ai)
        except (ImportError, ModelError, ValueError) as exc:
            reason = str(exc)
    return Service(Path(data_dir), Path(project), provider=provider, ai_reason=reason, adaptive=adaptive)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m webapi.server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA))
    parser.add_argument("--ai", choices=["bedrock", "off"], default="bedrock")
    parser.add_argument("--no-adaptive", action="store_true")
    args = parser.parse_args(argv)
    service = build_service(args.data_dir, args.ai, not args.no_adaptive)
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(service, os.environ.get("CODEAI_TEACHER_TOKEN") or None))
    print(f"CodeAI student UI on http://{args.host}:{args.port}  (AI {'on' if service.provider else 'off'})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
