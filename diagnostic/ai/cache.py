"""Cache identical model requests so repeated runs do not spend budget twice.

Keys cover everything that shapes the answer. Only successful replies are kept.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

from engine.ai import ModelProvider, ModelReply, ToolSpec


class CachingProvider(ModelProvider):
    def __init__(self, inner: ModelProvider, max_entries: int = 512):
        self.inner = inner
        self.model_id = inner.model_id
        self.max_entries = max_entries
        self.hits = 0
        self.misses = 0
        self._store: Dict[str, ModelReply] = {}

    def _key(self, system: str, prompt: str, max_tokens: int, tools: Optional[List[ToolSpec]]) -> str:
        blob = json.dumps({"m": self.inner.model_id, "s": system, "p": prompt, "t": max_tokens,
                           "tools": [t.name for t in tools or []]}, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def complete(self, system: str, prompt: str, max_tokens: int, tools: Optional[List[ToolSpec]] = None,
                 require_tool: bool = False) -> ModelReply:
        key = self._key(system, prompt, max_tokens, tools)
        if key in self._store:
            self.hits += 1
            return self._store[key]
        self.misses += 1
        reply = self.inner.complete(system, prompt, max_tokens, tools=tools, require_tool=require_tool)
        if len(self._store) < self.max_entries:
            self._store[key] = reply
        return reply
