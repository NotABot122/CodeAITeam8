from __future__ import annotations

import tempfile
from pathlib import Path

from engine import REPO_ROOT
from engine.events import EventLog
from engine.grader import Grader
from engine.progress import JsonProgressStore
from engine.project import load_project
from engine.session import Engine

PROJECT_DIR = REPO_ROOT / "projects" / "weather-station"
_PROJECT = None


def project():
    global _PROJECT
    if _PROJECT is None:
        _PROJECT = load_project(PROJECT_DIR)
        _PROJECT.ensure_dataset()
    return _PROJECT


class TempDirMixin:
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="codeai-test-")
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, source: str) -> Path:
        path = self.tmp / name
        path.write_text(source)
        return path

    def engine(self, **kwargs) -> Engine:
        return Engine(project(), JsonProgressStore(self.tmp), EventLog(self.tmp),
                      grader=kwargs.pop("grader", Grader(timeout_s=5)), **kwargs)
