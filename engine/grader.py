"""Grade a code submission in a separate process against a fresh database copy."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from . import REPO_ROOT
from .loop_checker import find_loop_problems
from .project import Problem, Project

DEFAULT_TIMEOUT_S = 10.0

PASSED = "passed"
FAILED = "failed"
TIMEOUT = "timeout"
SYNTAX_ERROR = "syntax_error"
IMPORT_ERROR = "import_error"
UNGRADED = "ungraded"


@dataclass
class GradeResult:
    status: str
    failures: List[dict] = field(default_factory=list)
    error_message: Optional[str] = None
    error_line: Optional[int] = None
    timeout_s: float = DEFAULT_TIMEOUT_S
    tests_run: int = 0

    @property
    def passed(self) -> bool:
        return self.status == PASSED

    @property
    def ungraded(self) -> bool:
        return self.status == UNGRADED


class Grader:
    def __init__(self, timeout_s: float = DEFAULT_TIMEOUT_S):
        self.timeout_s = timeout_s

    def grade(self, project: Project, problem: Problem, submission_path) -> GradeResult:
        submission_path = Path(submission_path).resolve()
        if not submission_path.is_file():
            return GradeResult(SYNTAX_ERROR, error_message=f"file not found: {submission_path.name}", timeout_s=self.timeout_s)

        with tempfile.TemporaryDirectory(prefix="codeai-grade-") as tmp:
            tmp_dir = Path(tmp)
            try:
                db_copy = tmp_dir / "weather.db"
                shutil.copyfile(project.ensure_dataset(), db_copy)
                job_path = tmp_dir / "job.json"
                result_path = tmp_dir / "result.json"
                job_path.write_text(json.dumps({
                    "submission": str(submission_path),
                    "checks": str(problem.checks_path),
                    "reference": str(project.reference_path),
                    "db": str(db_copy),
                    "params": project.manifest.parameters,
                    "expected_reports": project.read_expected_reports().get("reports", []),
                    "result": str(result_path),
                }))
            except (OSError, ValueError) as exc:
                return GradeResult(UNGRADED, error_message=f"could not prepare grading: {exc}", timeout_s=self.timeout_s)

            env = dict(os.environ)
            env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "engine._runner", str(job_path)],
                    cwd=str(tmp_dir), env=env, capture_output=True, timeout=self.timeout_s,
                )
            except subprocess.TimeoutExpired:
                return GradeResult(TIMEOUT, timeout_s=self.timeout_s)
            except OSError as exc:
                return GradeResult(UNGRADED, error_message=f"could not start grading: {exc}", timeout_s=self.timeout_s)

            if not result_path.exists():
                detail = proc.stderr.decode(errors="replace").strip().splitlines()[-1:] or ["no error output"]
                return GradeResult(FAILED, failures=[{
                    "test": "process",
                    "message": f"your program stopped before the checks finished ({detail[0]}).",
                }], timeout_s=self.timeout_s)
            data = json.loads(result_path.read_text())

        result = GradeResult(
            status=data["status"],
            failures=data.get("failures", []),
            error_message=data.get("error_message"),
            error_line=data.get("error_line"),
            timeout_s=self.timeout_s,
            tests_run=data.get("tests_run", 0),
        )

        if problem.loop_check and result.status in (PASSED, FAILED):
            loop_problems = find_loop_problems(submission_path.read_text(), problem.loop_check)
            if loop_problems:
                result.failures.extend({"test": "loop_check", "message": m} for m in loop_problems)
                result.status = FAILED
        return result
