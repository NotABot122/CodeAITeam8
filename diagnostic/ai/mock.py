"""Offline stand-ins for a model. No network, no cost, fully repeatable.

RuleBasedProvider reads the same prompts a real model would and answers through the
same forced tool calls, using the keyword rules and the game's own estimates.
It lets the whole pipeline (prompts -> parsing -> bounded merge -> logging) run in
tests and in the evaluation harness before AWS access exists. It is NOT evidence
about how a real model scores; the harness reports it as a mock.

FailingProvider always raises, to exercise fallback paths.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.ai import ModelError, ModelProvider, ModelReply, ToolSpec

from ..models import ExplainPrompt, KeyIdea
from ..stance import choose_stance
from ..textmatch import keyword_stage
from . import prompts
from .tools import ADVISE_TOOL, GRADE_TOOL

MOCK_MODEL_ID = "mock-rules-v1"


class RuleBasedProvider(ModelProvider):
    model_id = MOCK_MODEL_ID

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system: str, prompt: str, max_tokens: int, tools: Optional[List[ToolSpec]] = None,
                 require_tool: bool = False) -> ModelReply:
        self.calls += 1
        names = [t.name for t in tools or []]
        if GRADE_TOOL.name in names:
            return ModelReply(tool_name=GRADE_TOOL.name, tool_input=self._grade(prompt), model_id=self.model_id)
        if ADVISE_TOOL.name in names:
            return ModelReply(tool_name=ADVISE_TOOL.name, tool_input=self._advise(prompt), model_id=self.model_id)
        raise ModelError("the mock model does not know this request")

    # One explanation ------------------------------------------------------------
    def _grade(self, prompt: str) -> Dict[str, Any]:
        task = prompts.extract_tagged_json(prompt, "task") or {}
        ideas = tuple(KeyIdea(f"idea{i}", int(k["level"]), tuple(k["words"]), k["label"])
                      for i, k in enumerate(task.get("key_ideas", [])))
        stage, quotes = keyword_stage(ExplainPrompt(task.get("prompt_id", "x"), "", (), "", ideas),
                                      prompts.extract_submission(prompt))
        return {"stage": stage, "confidence": 0.7 if stage == 0 else 0.62,
                "rationale": f"Found {stage} step(s) of the rubric in the student's own words.",
                "evidence_quotes": quotes}

    # Placement ----------------------------------------------------------------------
    def _advise(self, prompt: str) -> Dict[str, Any]:
        packet = prompts.extract_tagged_json(prompt, "evidence") or {}
        concepts = packet.get("concepts", [])
        emphasis = packet.get("goal", {}).get("emphasis", {})
        out: List[Dict[str, Any]] = []
        for c in concepts:
            stage = int(c["game_stage"])
            confidence = float(c["game_confidence"])
            quotes: List[str] = []
            explain = c.get("explain", {})
            reader = explain.get("reader_stage")
            if explain.get("text") and reader is not None and explain.get("reader_quotes"):
                if reader >= stage + 1 and stage < 3:
                    stage, quotes = stage + 1, list(explain["reader_quotes"])
                elif reader <= stage - 2:
                    stage, quotes = stage - 1, list(explain["reader_quotes"])
                if quotes:
                    confidence = min(confidence, 0.7)
            out.append({"concept": c["concept"], "stage": stage, "confidence": round(confidence, 3),
                        "rationale": "Based on the answers and the student's own words.", "evidence_quotes": quotes})
        order = sorted(concepts, key=lambda c: (next(o["stage"] for o in out if o["concept"] == c["concept"]),
                                                -float(emphasis.get(c["concept"], 0.5))))
        stages = {o["concept"]: o["stage"] for o in out}
        confident = {c["concept"]: not c.get("borderline") for c in concepts}
        zone = order[0]["zone"] if order else "the first zone"
        label = packet.get("goal", {}).get("label", "your goal")
        return {
            "concepts": out,
            "focus_order": [c["concept"] for c in order],
            "stance": choose_stance(stages, confident),
            "goal_connection": f"Your goal is: {label}. These steps lead there.",
            "student_message": f"You worked hard today. Your goal is: {label}. Let's start with {zone}.",
            "teacher_note": "Placement written by the offline mock model from the game's evidence.",
        }


class FailingProvider(ModelProvider):
    model_id = "failing"

    def complete(self, *args: Any, **kwargs: Any) -> ModelReply:
        raise ModelError("the model is unavailable (test)")
