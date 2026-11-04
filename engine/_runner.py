"""Run one problem's checks against a submission. Executed in a separate process.

Usage: python -m engine._runner JOB.json

The job file names the submission, checks module, reference solution,
database copy, manifest parameters, expected reports, and the result file.
The result is written to the result file, not stdout, so a student's print()
calls can't corrupt it.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sqlite3
import sys
import traceback
from pathlib import Path

from engine import checklib


class Context:
    def __init__(self, module, reference, db_path, params, expected_reports):
        self.module = module
        self.reference = reference
        self.db_path = db_path
        self.params = params
        self.expected_reports = expected_reports

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def db_rows(self, station_id=None, start=None, end=None):
        return checklib.read_rows(self.db_path, station_id, start, end)


def _load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _line_in(tb, filename: str):
    line = None
    for frame in traceback.extract_tb(tb):
        if Path(frame.filename).resolve() == Path(filename).resolve():
            line = frame.lineno
    return line


def _positional_count(func) -> int:
    params = inspect.signature(func).parameters.values()
    return len([p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])


def run(job: dict) -> dict:
    submission = job["submission"]

    # 1. Syntax
    try:
        source = Path(submission).read_text()
        compile(source, submission, "exec")
    except SyntaxError as exc:
        return {"status": "syntax_error", "error_message": exc.msg, "error_line": exc.lineno}

    # 2. Import
    try:
        module = _load(submission, "student_solution")
    except BaseException as exc:  # includes SystemExit from student code
        return {
            "status": "import_error",
            "error_message": f"{type(exc).__name__}: {exc}",
            "error_line": _line_in(exc.__traceback__, submission),
        }

    # 3. Engine-side modules. A failure here is not the student's fault.
    try:
        reference = _load(job["reference"], "reference_solution")
        checks = _load(job["checks"], "problem_checks")
    except BaseException as exc:
        return {"status": "ungraded", "error_message": f"could not load checks: {exc}"}

    # 4. Required functions
    failures = []
    for name, count in getattr(checks, "REQUIRED", {}).items():
        func = getattr(module, name, None)
        if not callable(func):
            failures.append({"test": "required_functions",
                             "message": f"define a function named {name} with {count} parameter(s)."})
        elif _positional_count(func) != count:
            failures.append({"test": "required_functions",
                             "message": f"{name} should take {count} parameter(s), but it takes {_positional_count(func)}."})
    if failures:
        return {"status": "failed", "failures": failures, "tests_run": 0}

    # 5. Checks, in definition order
    ctx = Context(module, reference, job["db"], job.get("params", {}), job.get("expected_reports", []))
    tests = [(name, obj) for name, obj in vars(checks).items() if name.startswith("check_") and callable(obj)]
    for name, check in tests:
        try:
            check(ctx)
        except AssertionError as exc:
            failures.append({"test": name, "message": str(exc) or name})
        except BaseException as exc:
            summary = (check.__doc__ or name).strip().splitlines()[0]
            failures.append({"test": name,
                             "message": f"{summary} Your code raised {type(exc).__name__}: {exc}"})
    return {"status": "failed" if failures else "passed", "failures": failures, "tests_run": len(tests)}


def main() -> int:
    job = json.loads(Path(sys.argv[1]).read_text())
    result = run(job)
    Path(job["result"]).write_text(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
