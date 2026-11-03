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
# students. They are different on purpose: a grader scoring text written by
# the same model tends to agree with it more than it would with real students.
GRADER_MODEL = "us.anthropic.claude-sonnet-4-6"
GENERATOR_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# USD per 1M tokens (input, output). Fill these in from the Bedrock pricing
# page for us-west-2 before reporting E09; unknown models report no cost.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {}


@dataclass
class ModelReply:
    text: str
    model_id: str
    tokens_in: int
    tokens_out: int
    latency_ms: int

    @property
    def cost_usd(self) -> float | None:
        price = PRICES_PER_MTOK.get(self.model_id)
        if not price:
            return None
        return round(self.tokens_in / 1e6 * price[0] + self.tokens_out / 1e6 * price[1], 6)


def _region() -> str:
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "us-west-2"
    if region not in ALLOWED_REGIONS:
        raise ValueError(f"Region {region!r} not allowed; use one of {ALLOWED_REGIONS}")
    return region


_client = None


def _runtime():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            region_name=_region(),
            config=Config(retries={"max_attempts": 6, "mode": "adaptive"}, read_timeout=120),
        )
    return _client


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
    resp = _runtime().converse(**kwargs)
    latency = int((time.time() - start) * 1000)
    text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"])
    usage = resp.get("usage", {})
    return ModelReply(
        text=text,
        model_id=model_id,
        tokens_in=usage.get("inputTokens", 0),
        tokens_out=usage.get("outputTokens", 0),
        latency_ms=latency,
    )
