"""Model access behind one small interface, so the model or provider can be swapped.

BedrockProvider calls Amazon Bedrock's Converse API. ScriptedProvider returns
canned replies for tests and offline demos.
"""
from __future__ import annotations

import os
import time
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Union

DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_REGION = "us-west-2"

# boto3 warns that Python 3.9 support is ending. Keep it out of student-facing output.
warnings.filterwarnings("ignore", message="Boto3 will no longer support Python")


class ModelError(Exception):
    """The model call failed or returned something unusable. Callers fall back."""


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: dict


@dataclass
class ModelReply:
    text: str = ""
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    model_id: str = ""
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class ModelProvider(ABC):
    model_id: str = ""

    @abstractmethod
    def complete(self, system: str, prompt: str, max_tokens: int,
                 tools: Optional[List[ToolSpec]] = None, require_tool: bool = False) -> ModelReply:
        """One request. With require_tool, the reply must be a call to one of the tools."""


class BedrockProvider(ModelProvider):
    def __init__(self, model_id: Optional[str] = None, region: Optional[str] = None, timeout_s: float = 30.0):
        import boto3
        from botocore.config import Config

        self.model_id = model_id or os.environ.get("CODEAI_MODEL_ID", DEFAULT_MODEL_ID)
        self.region = region or os.environ.get("CODEAI_AWS_REGION", DEFAULT_REGION)
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=self.region,
            config=Config(retries={"max_attempts": 3, "mode": "adaptive"},
                          connect_timeout=5, read_timeout=timeout_s),
        )

    def complete(self, system, prompt, max_tokens, tools=None, require_tool=False) -> ModelReply:
        from botocore.exceptions import BotoCoreError, ClientError

        request = {
            "modelId": self.model_id,
            "system": [{"text": system}],
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            # Always set maxTokens. No temperature: newer Claude models reject it.
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if tools:
            request["toolConfig"] = {
                "tools": [{"toolSpec": {"name": t.name, "description": t.description,
                                        "inputSchema": {"json": t.schema}}} for t in tools],
                "toolChoice": {"any": {}} if require_tool else {"auto": {}},
            }
        started = time.monotonic()
        try:
            response = self.client.converse(**request)
        except (ClientError, BotoCoreError) as exc:
            raise ModelError(f"Bedrock call failed: {exc}") from None

        reply = ModelReply(model_id=self.model_id, latency_ms=int((time.monotonic() - started) * 1000))
        usage = response.get("usage", {})
        reply.input_tokens, reply.output_tokens = usage.get("inputTokens", 0), usage.get("outputTokens", 0)
        for block in response.get("output", {}).get("message", {}).get("content", []):
            if "text" in block:
                reply.text += block["text"]
            elif "toolUse" in block and reply.tool_name is None:
                reply.tool_name = block["toolUse"].get("name")
                reply.tool_input = block["toolUse"].get("input")
        if require_tool and reply.tool_name is None:
            raise ModelError("the model did not return the required structured answer")
        return reply


Script = Union[ModelReply, Exception, Callable[[str, str], ModelReply]]


@dataclass
class ScriptedProvider(ModelProvider):
    """Returns queued replies in order. Records every request for inspection."""

    replies: List[Script] = field(default_factory=list)
    model_id: str = "scripted"
    requests: List[dict] = field(default_factory=list)

    def complete(self, system, prompt, max_tokens, tools=None, require_tool=False) -> ModelReply:
        self.requests.append({"system": system, "prompt": prompt, "max_tokens": max_tokens,
                              "tools": [t.name for t in tools or []]})
        if not self.replies:
            raise ModelError("no scripted reply left")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            reply = reply(system, prompt)
        if require_tool and reply.tool_name is None:
            raise ModelError("the model did not return the required structured answer")
        reply.model_id = reply.model_id or self.model_id
        return reply


def provider_from_env(mode: str = "bedrock") -> Optional[ModelProvider]:
    """Return a provider for mode 'bedrock', or None for 'off'."""
    if mode == "off":
        return None
    if mode == "bedrock":
        return BedrockProvider()
    raise ValueError(f"unknown AI mode {mode!r}")
