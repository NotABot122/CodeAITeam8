"""Append-only event log (JSON lines). Students appear only by Student_Id."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import List

ALLOWED_FIELDS = {"event", "student_id", "project_id", "problem_id", "reason", "selected", "stages", "timestamp",
                  "source", "model_id", "latency_ms", "category", "direction"}


class EventLog:
    def __init__(self, root):
        self.path = Path(root) / "logs" / "events.jsonl"

    def write(self, event: str, **fields) -> dict:
        unknown = set(fields) - ALLOWED_FIELDS
        if unknown:
            # Guard against personal data slipping into logs through new fields.
            raise ValueError(f"event field(s) not allowed in logs: {', '.join(sorted(unknown))}")
        entry = {"event": event, **fields,
                 "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as handle:
            handle.write(json.dumps(entry) + "\n")
        return entry

    def read(self) -> List[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
