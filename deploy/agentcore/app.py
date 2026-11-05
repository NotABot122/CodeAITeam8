"""AgentCore Runtime entry point: the readiness diagnostic's `validate_submission` tool over HTTP.

Implements the AgentCore Runtime HTTP protocol contract (port 8080):

    GET  /ping          -> {"status": "Healthy"}
    POST /invocations   validate_submission input (evaluation/schemas/validate_submission.schema.json)
                        -> 200 with the tool output, 400 for bad input, 503 when the model call fails

Authentication is not handled here. The runtime is created with an inbound JWT authorizer
(AgentCore Identity), so AgentCore rejects requests without a valid token before they reach
this process. Standard library only; the deployment package adds PyYAML for the engine.

Run locally:  PORT=8091 python3 -m deploy.agentcore.app   (then POST to http://localhost:8091/invocations)
"""
from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from diagnostic.contract import ToolError
from diagnostic.tool_server import validate_submission_tool

PORT = int(os.environ.get("PORT", "8080"))   # AgentCore expects 8080; override only for local runs
MAX_BODY = 64 * 1024

log = logging.getLogger("codeai.agentcore")


class Handler(BaseHTTPRequestHandler):
    server_version = "CodeAI"

    def log_message(self, fmt, *args):  # request lines are logged by _send without payloads
        pass

    def _send(self, status: int, payload: dict, started: float) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        # Student text and ids stay out of the logs (they go to CloudWatch).
        log.info("%s %s -> %d in %d ms", self.command, self.path, status, (time.monotonic() - started) * 1000)

    def do_GET(self) -> None:
        started = time.monotonic()
        if self.path == "/ping":
            self._send(200, {"status": "Healthy", "time_of_last_update": int(time.time())}, started)
        else:
            self._send(404, {"error": "not found"}, started)

    def do_POST(self) -> None:
        started = time.monotonic()
        if self.path.split("?", 1)[0] != "/invocations":
            self._send(404, {"error": "not found"}, started)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._send(413, {"error": f"body larger than {MAX_BODY} bytes"}, started)
            return
        try:
            tool_input = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(tool_input, dict):
                raise ValueError("the body must be a JSON object")
            self._send(200, validate_submission_tool(tool_input), started)
        except ValueError as exc:  # includes json.JSONDecodeError
            self._send(400, {"error": str(exc)}, started)
        except ToolError as exc:
            self._send(503, {"error": "grader unavailable, use the fallback path", "detail": str(exc)}, started)
        except Exception:
            log.exception("unexpected error")
            self._send(500, {"error": "internal error"}, started)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    # AgentCore sends SIGTERM before stopping a session; shut down cleanly.
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start())
    log.info("listening on port %d", PORT)
    server.serve_forever()
    server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
