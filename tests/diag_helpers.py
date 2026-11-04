"""Shared helpers for the diagnostic tests."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yaml

from engine.ai import ModelProvider
from engine.events import EventLog
from engine.project import load_project

from diagnostic.content import Content, load_content
from diagnostic.engine import DiagnosticEngine
from diagnostic.eval_log import EvalEventLog
from diagnostic.models import ItemResult
from diagnostic.paths import DEFAULT_PROJECT
from diagnostic.store import DiagnosticStore

_PROJECT = None
_CONTENT = None


def project():
    global _PROJECT
    if _PROJECT is None:
        _PROJECT = load_project(DEFAULT_PROJECT)
    return _PROJECT


def content() -> Content:
    """The real Weather Station diagnostic content (loaded once; treat as read-only)."""
    global _CONTENT
    if _CONTENT is None:
        _CONTENT = load_content(project().root, project().manifest.concept_ids())
    return _CONTENT


def make_result(item_id: str, passed: bool = True, role: str = "first", credit: Optional[float] = None) -> ItemResult:
    item = content().items[item_id]
    return ItemResult(item.id, item.concept, item.tier, role, credit if credit is not None else (1.0 if passed else 0.0),
                      passed, item.guess_chance, None if passed else "test_mistake")


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="codeai-diag-test-")
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def engine(self, provider: Optional[ModelProvider] = None, adaptive: bool = True) -> DiagnosticEngine:
        root = self.tmp / "data"
        return DiagnosticEngine(project(), content(), DiagnosticStore(root), EventLog(root), EvalEventLog(root, "test-run"),
                                provider, adaptive)

    def copy_project(self) -> Path:
        """A throwaway copy of the diagnostic content that a test can break on purpose."""
        root = self.tmp / "project"
        shutil.copytree(DEFAULT_PROJECT, root, ignore=shutil.ignore_patterns("*.db", "__pycache__"))
        return root


def edit_yaml(path: Path, change: Callable[[Dict[str, Any]], None]) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
