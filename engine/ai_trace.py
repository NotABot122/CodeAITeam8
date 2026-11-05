"""Dev-only AI inspector: record every model call (what went in, what came out) for the demo panel.

TracingProvider wraps the real provider (Bedrock) and passes every call through unchanged, keeping a copy in an
in-memory ring buffer: the feature that made the call, the model, the system prompt, the input, the tools offered,
the reply (text or structured tool answer), latency, tokens, and which student it was for. Nothing is written to
disk, and the server only turns it on with --dev. Students are known by their random id only.
"""
from __future__ import annotations

import contextvars
import datetime as dt
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

from .ai import ModelError, ModelProvider, ModelReply, ToolSpec

MAX_CALLS = 300
MAX_TEXT = 20_000

# The student the current request is for (set by the web server per request).
current_student: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_student", default=None)

# (text that identifies the system prompt, feature name, what it does in the app)
FEATURES = [
    ("Strands Decider 2B", "Pathway decider (Strands Decider 2B)",
     "Picks the student's lesson pathway from the readiness check, their grade and the CSTA standards."),
    ("patient coding tutor", "AI tutor hint (Ducky)",
     "Writes one hint about the student's failing code. Level-aware; falls back to the teacher's hint."),
    ("explain Python errors", "Error explainer",
     "Explains a Python or SQL error in plain words. Falls back to the rule-based explanation."),
    ("label the most likely mistake", "Mistake labeler",
     "Picks the likely mistake from the project's allowed list when the rules can't decide."),
    ("score a high school student's short written answer", "Quiz answer scorer",
     "Scores a typed quiz answer against the teacher's rubric."),
    ("rubric reader", "Readiness check: explanation reader",
     "Reads the student's own words in the readiness check and scores them against key ideas."),
    ("place children", "Readiness check: placement advisor",
     "Suggests where to start; may move a stage by one only with the student's own words as proof."),
    ("screen requests", "Theme moderation",
     "Checks that a \"Make it yours\" theme request is fine for a classroom."),
    ("design the theme", "Theme designer (Make it yours)",
     "Designs the names, words and number ranges for a themed project; the engine builds and checks the rest."),
]


def feature_of(system: str) -> Dict[str, str]:
    for needle, name, what in FEATURES:
        if needle.lower() in system.lower():
            return {"name": name, "what": what}
    return {"name": "Other model call", "what": ""}


def _clip(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + f"\n… ({len(text) - MAX_TEXT} more characters)"


class TraceLog:
    def __init__(self, size: int = MAX_CALLS):
        self._calls: deque = deque(maxlen=size)
        self._next = 1
        self._lock = threading.Lock()

    def add(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            entry["id"] = self._next
            self._next += 1
            self._calls.append(entry)

    def after(self, call_id: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            return [c for c in self._calls if c["id"] > call_id]

    def clear(self) -> None:
        with self._lock:
            self._calls.clear()


class TracingProvider(ModelProvider):
    """Passes calls to `inner` and records each one in `log`."""

    def __init__(self, inner: ModelProvider, log: TraceLog):
        self.inner = inner
        self.log = log
        self.model_id = inner.model_id

    def complete(self, system: str, prompt: str, max_tokens: int, tools: Optional[List[ToolSpec]] = None,
                 require_tool: bool = False) -> ModelReply:
        entry: Dict[str, Any] = {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "feature": feature_of(system),
            "model": self.inner.model_id,
            "student": current_student.get(),
            "system": _clip(system),
            "input": _clip(prompt),
            "maxTokens": max_tokens,
            "tools": [{"name": t.name, "description": t.description, "schema": t.schema} for t in tools or []],
            "requireTool": require_tool,
        }
        started = time.monotonic()
        try:
            reply = self.inner.complete(system, prompt, max_tokens, tools=tools, require_tool=require_tool)
        except ModelError as exc:
            entry.update(ok=False, error=str(exc)[:1000], latencyMs=int((time.monotonic() - started) * 1000))
            self.log.add(entry)
            raise
        entry.update(ok=True, latencyMs=reply.latency_ms or int((time.monotonic() - started) * 1000),
                     outputText=_clip(reply.text) or None, toolName=reply.tool_name, toolInput=reply.tool_input,
                     inputTokens=reply.input_tokens, outputTokens=reply.output_tokens)
        self.log.add(entry)
        return reply
