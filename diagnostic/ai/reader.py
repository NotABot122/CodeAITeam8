"""Read one "tell the guide" answer: prefilter, then a model (or the keyword rules).

This is the engine behind the evaluation team's `validate_submission` contract
(see diagnostic/contract.py). It follows that contract's rules:
  - unscorable text (empty, gibberish, injection, ...) never reaches a model and
    gets no stage;
  - a model answer that does not parse gets no stage and a `parse_error` flag
    (a stage is never guessed);
  - a failed model call gets no stage and an `error`, so callers use the
    deterministic path and log the fallback.
With no model configured, the keyword rules produce the stage (model_id "rules-v1").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from engine.ai import ModelError, ModelProvider

from ..content import Config
from ..models import ExplainPrompt
from ..safety import prefilter
from ..textmatch import keyword_stage
from . import prompts
from .parse import parse_reading
from .tools import GRADE_TOOL

RULES_MODEL_ID = "rules-v1"
PARSE_ERROR = "parse_error"
MAX_TOKENS = 500


@dataclass
class ExplainReading:
    stage: Optional[int]
    confidence: float = 0.0
    rationale: str = ""
    quotes: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    model_id: str = RULES_MODEL_ID
    keyword_stage: Optional[int] = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    error: Optional[str] = None          # the model call failed: the caller falls back

    @property
    def fallback(self) -> bool:
        return self.error is not None

    @property
    def unscorable(self) -> bool:
        return self.stage is None


def read_explanation(prompt: ExplainPrompt, zone_name: str, text: Optional[str], provider: Optional[ModelProvider],
                     config: Config) -> ExplainReading:
    text = (text or "")[: config.text.max_chars]
    pre = prefilter(text, config.text.min_words)
    if pre.unscorable:
        return ExplainReading(None, 0.0, "Unscorable input: " + ", ".join(pre.flags), [], list(pre.flags))

    rule_stage, rule_quotes = keyword_stage(prompt, text)
    flags = list(pre.flags)               # a mild-insult flag stays on a scorable answer
    if provider is None:
        return ExplainReading(rule_stage, 0.5, "Keyword check of the child's own words.", rule_quotes, flags,
                              RULES_MODEL_ID, rule_stage)

    try:
        reply = provider.complete(prompts.grade_system(prompt, zone_name, config.grade_band),
                                  prompts.grade_user(text, prompt), MAX_TOKENS, tools=[GRADE_TOOL], require_tool=True)
    except ModelError as exc:
        return ExplainReading(None, 0.0, "The reader was unavailable.", [], flags, provider.model_id, rule_stage,
                              error=str(exc)[:200])
    except Exception as exc:                                   # a provider bug must not end the quest
        return ExplainReading(None, 0.0, "The reader failed.", [], flags, provider.model_id, rule_stage,
                              error=f"{type(exc).__name__}: {exc}"[:200])

    meta = dict(model_id=reply.model_id or provider.model_id, tokens_in=reply.input_tokens,
                tokens_out=reply.output_tokens, latency_ms=reply.latency_ms, keyword_stage=rule_stage)
    reading = parse_reading(reply.tool_input, text) if reply.tool_name == GRADE_TOOL.name else None
    if reading is None:
        return ExplainReading(None, 0.0, "The reader's answer could not be used.", [], flags + [PARSE_ERROR], **meta)
    quotes = list(reading.quotes) or rule_quotes      # every stage points at the child's own words
    return ExplainReading(reading.stage, reading.confidence, reading.rationale, quotes, flags, **meta)
