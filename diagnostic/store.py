"""Where a student's quest is saved.

Uses the lesson engine's student registry (engine.progress.JsonProgressStore), so one
student id works in both the diagnostic and `python -m engine.cli`. Each quest is
one JSON file, written atomically, next to the lesson progress:

    <data dir>/progress/<student id>/diagnostic.json

Student ids come from outside (API calls), so every id is checked before it touches a path.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from engine import s3_storage
from engine.progress import JsonProgressStore

from .paths import PathLike
from .state import DiagnosticState

# One student id across the diagnostic, the lesson engine and the student web API: 32 hex characters,
# the same shape engine.session and webapi use. Older quests saved with "STU-" + hex still load.
STUDENT_ID = re.compile(r"^(?:[0-9a-f]{32}|STU-[0-9a-f]{16,32})$")
FILE_NAME = "diagnostic.json"


class StateLoadError(Exception):
    pass


class InvalidStudentId(ValueError):
    pass


def check_student_id(student_id: str) -> str:
    if not isinstance(student_id, str) or not STUDENT_ID.match(student_id):
        raise InvalidStudentId("student ids are 32 letters and digits (a-f, 0-9)")
    return student_id


class DiagnosticStore:
    def __init__(self, root: PathLike):
        self.root = Path(root)
        self.registry = JsonProgressStore(self.root)

    def _path(self, student_id: str) -> Path:
        return self.registry.root / check_student_id(student_id) / FILE_NAME

    def new_student(self) -> str:
        while True:
            student_id = uuid.uuid4().hex
            if not self.registry.student_exists(student_id):
                break
        self.registry.register_student(student_id)
        return student_id

    def exists(self, student_id: str) -> bool:
        return self.registry.student_exists(check_student_id(student_id))

    def load(self, student_id: str) -> Optional[DiagnosticState]:
        path = self._path(student_id)
        if not path.exists():
            return None
        try:
            return DiagnosticState.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise StateLoadError(str(exc)) from None

    def save(self, state: DiagnosticState) -> None:
        path = self._path(state.student_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".diagnostic-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state.to_dict(), handle, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        s3_storage.changed(path)

    def quarantine(self, student_id: str) -> None:
        path = self._path(student_id)
        if path.exists():
            kept = path.with_name(f"diagnostic.corrupt-{time.strftime('%Y%m%d-%H%M%S')}.json")
            path.rename(kept)
            s3_storage.moved(path, kept)
