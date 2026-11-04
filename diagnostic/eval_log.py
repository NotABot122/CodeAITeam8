"""Event-log rows in the evaluation team's format (evaluation/schemas/event_log.schema.json).

One row per tool call (`validate_submission`, `route_next`). Every evaluation item reads
this log. Students appear only by their pseudonymous id, marked `STU-` here; the free-text goal is
never written here.

This is separate from engine.events.EventLog, which records lesson events with its own
allow-list of fields. Both live under the data directory's logs/ folder.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import PathLike

LOG_NAME = "eval_events.jsonl"
STUDENT_PREFIX = "STU-"


def log_student_id(student_id: str) -> str:
    """The id as it appears in evaluation logs: real students are marked STU-, simulated ones keep SIM-/ADV-."""
    return student_id if student_id.startswith(("STU-", "SIM-", "ADV-")) else STUDENT_PREFIX + student_id


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def new_run_id() -> str:
    return f"diag-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"


class EvalEventLog:
    def __init__(self, root: PathLike, run_id: Optional[str] = None, path: Optional[PathLike] = None):
        """`root` is the data directory (rows go to <root>/logs/eval_events.jsonl); `path` overrides the file."""
        self.path = Path(path) if path else Path(root) / "logs" / LOG_NAME
        self.run_id = run_id or new_run_id()

    def _write(self, row: Dict[str, Any]) -> Dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def _base(self, student_id: str, lesson_id: str, task_id: str, tool: str, tool_input: Any, model_id: str,
              latency_ms: int, filter_result: List[str], fallback: bool, error: Optional[str]) -> Dict[str, Any]:
        return {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "run_id": self.run_id,
            "student_id": log_student_id(student_id),
            "lesson_id": lesson_id,
            "task_id": task_id,
            "tool": tool,
            "input_hash": canonical_hash(tool_input),
            "model_id": model_id or "none",
            "latency_ms": int(latency_ms),
            "filter_result": list(filter_result),
            "fallback_triggered": bool(fallback),
            "error": error,
        }

    def write_validate(self, student_id: str, lesson_id: str, task_id: str, attempt_no: int, tool_input: Dict[str, Any],
                       output: Dict[str, Any], fallback: bool = False, error: Optional[str] = None,
                       temperature: Optional[float] = None) -> Dict[str, Any]:
        row = self._base(student_id, lesson_id, task_id, "validate_submission", tool_input,
                         output.get("model_id", ""), output.get("latency_ms", 0), output.get("filter_flags", []),
                         fallback, error)
        row["attempt_no"] = attempt_no
        row["output"] = output
        stages = {r["subskill"]: r["stage"] for r in output.get("results", [])}
        row["stages"] = stages
        for legacy in ("prompting", "evaluation", "prompt_revision"):    # v0.1 fields, when present
            if legacy in stages:
                row[f"stage_{legacy}"] = stages[legacy]
        row["tokens_in"] = int(output.get("tokens_in", 0))
        row["tokens_out"] = int(output.get("tokens_out", 0))
        if temperature is not None:
            row["temperature"] = temperature
        return self._write(row)

    def write_route(self, student_id: str, lesson_id: str, tool_input: Dict[str, Any], output: Dict[str, Any],
                    model_id: str = "", latency_ms: int = 0, tokens_in: int = 0, tokens_out: int = 0,
                    filter_result: Optional[List[str]] = None, fallback: bool = False,
                    error: Optional[str] = None, stages: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        row = self._base(student_id, lesson_id, "placement", "route_next", tool_input, model_id, latency_ms,
                         filter_result or [], fallback, error)
        row["output"] = output
        if stages is not None:
            row["stages"] = dict(stages)
        row["tokens_in"], row["tokens_out"] = int(tokens_in), int(tokens_out)
        return self._write(row)

    def read(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
