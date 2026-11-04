"""Choose a model provider by name. One place, so the CLI, API and harness agree.

  off      no model: deterministic scoring and keyword reading only (the default)
  mock     the offline rule-based stand-in (tests, demos, harness runs without AWS)
  bedrock  Amazon Bedrock through engine.ai.BedrockProvider (needs boto3 and AWS credentials)
"""
from __future__ import annotations

import os
from typing import Optional

from engine.ai import ModelError, ModelProvider, provider_from_env

from .cache import CachingProvider
from .mock import RuleBasedProvider

MODES = ("off", "mock", "bedrock")
ENV_MODE = "CODEAI_AI"


class ProviderUnavailable(RuntimeError):
    """The requested provider could not be set up (for example, boto3 is not installed)."""


def default_mode() -> str:
    mode = os.environ.get(ENV_MODE, "off")
    return mode if mode in MODES else "off"


def make_provider(mode: Optional[str] = None, cache: bool = True) -> Optional[ModelProvider]:
    mode = mode or default_mode()
    if mode == "off":
        return None
    if mode == "mock":
        return RuleBasedProvider()
    if mode == "bedrock":
        try:
            provider = provider_from_env("bedrock")
        except (ImportError, ModelError, ValueError) as exc:
            raise ProviderUnavailable(f"Bedrock is not available: {exc}") from None
        return CachingProvider(provider) if cache and provider is not None else provider
    raise ValueError(f"unknown AI mode {mode!r}; choose one of {', '.join(MODES)}")
