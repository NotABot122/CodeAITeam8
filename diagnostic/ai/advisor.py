"""The contextualising call: give the model the evidence, the goal and the tree.

It returns advice (stage reads, a focus order, a stance, short messages). Nothing in
the advice is trusted yet: diagnostic/placement.py applies it within strict bounds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional

from engine.ai import ModelError, ModelProvider

from ..content import Content
from ..models import ConceptEstimate, NodeState
from ..state import EXPLAIN_ANSWERED, DiagnosticState
from . import prompts
from .parse import Advice, parse_advice
from .tools import ADVISE_TOOL

MAX_TOKENS = 900
PARSE_ERROR = "parse_error"


@dataclass
class AdviceResult:
    advice: Optional[Advice]
    model_id: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    error: Optional[str] = None
    parse_error: bool = False
    skipped: bool = False              # no model configured


def advise(content: Content, state: DiagnosticState, estimates: Mapping[str, ConceptEstimate],
           node_states: Mapping[str, NodeState], provider: Optional[ModelProvider]) -> AdviceResult:
    if provider is None:
        return AdviceResult(None, skipped=True)
    packet = prompts.build_packet(content, state, estimates, node_states)
    texts: Dict[str, str] = {c: r.text for c, r in state.explain.items() if r.status == EXPLAIN_ANSWERED and r.text}
    try:
        reply = provider.complete(prompts.advise_system(content), prompts.advise_user(packet), MAX_TOKENS,
                                  tools=[ADVISE_TOOL], require_tool=True)
    except ModelError as exc:
        return AdviceResult(None, provider.model_id, error=str(exc)[:200])
    except Exception as exc:                                   # a provider bug must not end the quest
        return AdviceResult(None, provider.model_id, error=f"{type(exc).__name__}: {exc}"[:200])

    meta = dict(model_id=reply.model_id or provider.model_id, tokens_in=reply.input_tokens,
                tokens_out=reply.output_tokens, latency_ms=reply.latency_ms)
    advice = parse_advice(reply.tool_input, content.concepts(), texts) if reply.tool_name == ADVISE_TOOL.name else None
    if advice is None:
        return AdviceResult(None, parse_error=True, error="the model's placement answer could not be used", **meta)
    return AdviceResult(advice, **meta)
