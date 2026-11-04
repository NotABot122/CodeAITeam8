"""Read-only adapter between the proto-branch engine and this harness.

Imports `engine` from the repo root (the layout after proto-branch and
evaluation-plan are merged into main). Nothing here changes engine code or
project content. Override the location with CODEAI_PROTO_ROOT.
"""
from __future__ import annotations

import ast
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

CONTRACT_VERSION = "0.2"
PROTO_ROOT = Path(os.environ.get("CODEAI_PROTO_ROOT", Path(__file__).resolve().parents[2]))
if not (PROTO_ROOT / "engine" / "__init__.py").exists():
    raise SystemExit(f"proto engine not found under {PROTO_ROOT}; set CODEAI_PROTO_ROOT")
if str(PROTO_ROOT) not in sys.path:
    sys.path.insert(0, str(PROTO_ROOT))

from engine.feedback import messages_for, next_hint  # noqa: E402
from engine.grader import Grader  # noqa: E402
from engine.project import load_project  # noqa: E402

from .proto_bugs import LEVEL_FUNCTIONS  # noqa: E402

PROJECT_DIR = PROTO_ROOT / "projects" / "weather-station"
_project = None


def project():
    global _project
    if _project is None:
        _project = load_project(PROJECT_DIR)
        _project.ensure_dataset()
    return _project


def reference_source() -> str:
    return project().reference_path.read_text()


def student_file(level: str, function: str, buggy_code: str) -> str:
    """Reference constants + functions up to `level`, with `function` replaced by the bug.

    The reference module docstring and later-level functions are left out so the
    hint model sees only what a student at this level would have written.
    """
    src = reference_source()
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    wanted = LEVEL_FUNCTIONS[level]
    parts = []
    for node in tree.body:
        seg = "".join(lines[node.lineno - 1: node.end_lineno])
        if isinstance(node, ast.Assign):
            parts.append(seg)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted:
            parts.append(buggy_code if node.name == function else seg)
    return "\n\n".join(p.rstrip() + "\n" for p in parts)


def grade_source(level: str, source: str, timeout_s: float = 10.0):
    """Grade `source` on `level` with the proto grader. Returns (GradeResult, messages)."""
    prj = project()
    problem = prj.problem(level)
    with tempfile.TemporaryDirectory(prefix="codeai-eval-") as tmp:
        path = Path(tmp) / "solution.py"
        path.write_text(source)
        result = Grader(timeout_s=timeout_s).grade(prj, problem, path)
    return result, messages_for(problem, result)


def authored_hint(level: str, attempt: int) -> str | None:
    """The teacher-written hint the engine would show on this attempt."""
    hint, _ = next_hint(project().problem(level), max(0, attempt - 1))
    return hint


def input_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def event_row(*, run_id: str, student_id: str, task_id: str, attempt_no: int, tool: str, payload: dict,
              output: dict, model_id: str, latency_ms: int, filter_result: list[str], fallback: bool,
              tokens_in: int | None = None, tokens_out: int | None = None, cost_usd: float | None = None,
              error: str | None = None) -> dict:
    """One row in the event_log v0.2 shape. `tool` is outside the v0.2 enum on purpose
    (hint and theme are not in the contract yet); see the report for the proposal."""
    row = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "contract_version": CONTRACT_VERSION, "run_id": run_id, "student_id": student_id,
        "lesson_id": "weather-station", "task_id": task_id, "rubric_id": None, "attempt_no": attempt_no,
        "tool": tool, "input_hash": input_hash(payload), "output": output, "model_id": model_id,
        "latency_ms": latency_ms, "filter_result": filter_result, "fallback_triggered": fallback, "error": error,
    }
    if tokens_in is not None:
        row.update(tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd)
    return row


def proto_events_to_rows(events_path: Path, run_id: str) -> list[dict]:
    """Convert proto's .codeai-data/logs/events.jsonl into event_log-shaped rows (best effort)."""
    rows = []
    for line in Path(events_path).read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        rows.append({
            "timestamp": e.get("timestamp"), "contract_version": CONTRACT_VERSION, "run_id": run_id,
            "student_id": "STU-" + str(e.get("student_id", ""))[:12], "lesson_id": e.get("project_id"),
            "task_id": e.get("problem_id"), "tool": f"proto.{e.get('event')}",
            "input_hash": input_hash(e), "output": {k: e[k] for k in ("reason", "selected", "stages", "source")
                                                   if k in e},
            "model_id": e.get("model_id", "none"), "latency_ms": e.get("latency_ms", 0),
            "filter_result": [e["category"]] if e.get("category") else [],
            "fallback_triggered": e.get("event") == "fallback" or e.get("source") == "authored",
        })
    return rows
