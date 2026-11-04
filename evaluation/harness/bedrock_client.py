"""Thin model abstraction over Amazon Bedrock Converse.

Model IDs are passed in, never hard-coded at call sites, so the harness can
swap models for the drift test (E11) without touching scoring or routing code.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import boto3
from botocore.config import Config

ALLOWED_REGIONS = ("us-west-2", "us-east-1")

# Model under evaluation (the grader) and the model used to write synthetic
# students. They differ on purpose: a grader scoring text written by the same
# model tends to agree with it more than it would with real students.
GRADER_MODEL = "us.anthropic.claude-sonnet-4-6"
GENERATOR_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
# Second grader for the drift test (E11). Not the generator model.
DRIFT_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# USD per 1M tokens (input, output), on-demand, geographic ("us.") inference
# profiles, which are priced about 10% above global profiles.
# Sources checked 2026-11-04: requesty.ai provider-rate page for Bedrock
# claude-sonnet-4-6 ($3.30 / $16.50) and typingmind Bedrock calculator (same).
# The Haiku and Sonnet 4.5 rows apply the same 10% regional uplift to
# Anthropic list prices. VERIFY against https://aws.amazon.com/bedrock/pricing/
# before reporting E09 outside the team.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "us.anthropic.claude-sonnet-4-6": (3.30, 16.50),
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": (3.30, 16.50),
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": (1.10, 5.50),
}


def cost_usd(model_id: str, tokens_in: int, tokens_out: int) -> float | None:
    price = PRICES_PER_MTOK.get(model_id)
    if not price:
        return None
    return round(tokens_in / 1e6 * price[0] + tokens_out / 1e6 * price[1], 6)


@dataclass
class ModelReply:
    text: str
    model_id: str
    tokens_in: int
    tokens_out: int
    latency_ms: int

    @property
    def cost_usd(self) -> float | None:
        return cost_usd(self.model_id, self.tokens_in, self.tokens_out)


def region() -> str:
    r = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "us-west-2"
    if r not in ALLOWED_REGIONS:
        raise ValueError(f"Region {r!r} not allowed; use one of {ALLOWED_REGIONS}")
    return r


_clients: dict[str, object] = {}


def client(service: str):
    if service not in _clients:
        _clients[service] = boto3.client(
            service, region_name=region(),
            config=Config(retries={"max_attempts": 6, "mode": "adaptive"}, read_timeout=120),
        )
    return _clients[service]


def converse(
    user_text: str,
    model_id: str,
    system: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> ModelReply:
    """One Converse call. maxTokens is always explicit to avoid quota over-reservation."""
    kwargs = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": user_text}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
    }
    if system:
        kwargs["system"] = [{"text": system}]
    start = time.time()
    resp = client("bedrock-runtime").converse(**kwargs)
    latency = int((time.time() - start) * 1000)
    text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"])
    usage = resp.get("usage", {})
    return ModelReply(text=text, model_id=model_id, tokens_in=usage.get("inputTokens", 0),
                      tokens_out=usage.get("outputTokens", 0), latency_ms=latency)


def apply_guardrail(guardrail_id: str, version: str, text: str, source: str = "INPUT") -> dict:
    """Run Bedrock Guardrails on text without a model call (ApplyGuardrail API)."""
    start = time.time()
    resp = client("bedrock-runtime").apply_guardrail(
        guardrailIdentifier=guardrail_id, guardrailVersion=version, source=source,
        content=[{"text": {"text": text}}],
    )
    return {"action": resp.get("action"), "latency_ms": int((time.time() - start) * 1000),
            "assessments": resp.get("assessments", []), "usage": resp.get("usage", {})}
