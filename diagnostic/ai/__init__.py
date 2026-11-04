"""Model-facing code: prompts, output validation, readers, and offline stand-ins.

Providers come from engine.ai (BedrockProvider, ScriptedProvider). This package only
builds requests and validates replies, so the model or vendor can be swapped without
touching scoring or placement.
"""
from engine.ai import ModelError, ModelProvider, ModelReply  # noqa: F401  (re-exported for convenience)

from .advisor import AdviceResult, advise  # noqa: F401
from .cache import CachingProvider  # noqa: F401
from .mock import FailingProvider, RuleBasedProvider  # noqa: F401
from .reader import ExplainReading, read_explanation  # noqa: F401
