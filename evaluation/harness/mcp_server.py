"""Draft MCP server exposing the evaluation contract v0.2 (stdio transport).

Tools:
  - validate_submission : reference grader (harness/validator.py)
  - get_rubric          : returns the active task rubric so clients can show it

`route_next` is defined in schemas/route_next.schema.json but is NOT served
here: routing is owned by teammates. The harness only calls it.

This draft speaks the MCP JSON-RPC methods directly (initialize, tools/list,
tools/call, ping) so it runs on Python 3.9 without the `mcp` SDK, which
requires Python 3.10+. When the team moves to 3.10+, port it to
`mcp.server.fastmcp.FastMCP` with the same tool names and schemas.

Run:  python -m evaluation.harness.mcp_server
Client config example (.kiro/settings/mcp.json or any MCP client):
  {"mcpServers": {"codeai-eval": {"command": "python",
     "args": ["-m", "evaluation.harness.mcp_server"], "cwd": "<repo root>"}}}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .validator import CONTRACT_VERSION, normalize_input, validate_submission

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "codeai-team8-evaluation", "version": "0.2.0"}

_RUBRICS = {
    json.loads(p.read_text(encoding="utf-8"))["rubric_id"]: json.loads(p.read_text(encoding="utf-8"))
    for p in (ROOT / "rubrics").glob("*.json")
}
_VS_SCHEMA = json.loads((ROOT / "schemas" / "validate_submission.schema.json").read_text(encoding="utf-8"))


def _inline_refs(node, defs):
    """MCP clients expect self-contained schemas; inline local #/$defs refs."""
    if isinstance(node, dict):
        if node.get("$ref", "").startswith("#/$defs/"):
            return _inline_refs(defs[node["$ref"].split("/")[-1]], defs)
        return {k: _inline_refs(v, defs) for k, v in node.items()}
    if isinstance(node, list):
        return [_inline_refs(v, defs) for v in node]
    return node


_IN = _inline_refs(_VS_SCHEMA["properties"]["input"], _VS_SCHEMA["$defs"])
_OUT = _inline_refs(_VS_SCHEMA["properties"]["output"], _VS_SCHEMA["$defs"])

TOOLS = [
    {
        "name": "validate_submission",
        "description": f"Score one student submission against a task rubric. Returns a stage per sub-skill "
                       f"(range from the rubric) with confidence, rationale, and evidence quotes, plus "
                       f"scorable / needs_review / filter_flags. Contract v{CONTRACT_VERSION}.",
        "inputSchema": _IN,
        "outputSchema": _OUT,
    },
    {
        "name": "get_rubric",
        "description": "Return the task rubric JSON for a rubric_id.",
        "inputSchema": {"type": "object", "required": ["rubric_id"],
                        "properties": {"rubric_id": {"type": "string"}}},
    },
]


def _call(name: str, args: dict) -> dict:
    if name == "get_rubric":
        rubric = _RUBRICS.get(args.get("rubric_id"))
        if rubric is None:
            raise ValueError(f"unknown rubric_id; available: {sorted(_RUBRICS)}")
        return rubric
    if name == "validate_submission":
        args = normalize_input(args)
        missing = [k for k in _IN["required"] if k not in args]
        if missing:
            raise ValueError(f"missing required fields: {missing}")
        rubric = _RUBRICS.get(args["rubric_id"])
        if rubric is None:
            raise ValueError(f"unknown rubric_id; available: {sorted(_RUBRICS)}")
        return validate_submission(args, rubric)
    raise ValueError(f"unknown tool: {name}")


def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification (e.g. notifications/initialized): no reply
        return None
    try:
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL_VERSION, "serverInfo": SERVER_INFO,
                      "capabilities": {"tools": {"listChanged": False}}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            p = msg.get("params", {})
            try:
                data = _call(p.get("name"), p.get("arguments") or {})
                result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
                          "structuredContent": data, "isError": False}
            except Exception as e:  # tool errors are returned to the model, not raised
                result = {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
