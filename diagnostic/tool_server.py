"""The diagnostic as a tool server function, for evaluation/harness/mcp_server.py.

The MCP server routes any rubric marked `"provider": "diagnostic"` here. Content comes
from the default project (or $CODEAI_PROJECT); the model comes from $CODEAI_AI
(off | mock | bedrock, default off, which uses the keyword rules).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from engine.project import load_project

from .ai.factory import make_provider
from .content import Content, load_content
from .contract import validate_submission
from .paths import project_dir


@lru_cache(maxsize=1)
def _content() -> Content:
    project = load_project(project_dir())
    return load_content(project.root, project.manifest.concept_ids())


@lru_cache(maxsize=1)
def _provider():
    return make_provider()


def validate_submission_tool(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    return validate_submission(tool_input, _content(), _provider())
