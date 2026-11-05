"""Grade a code submission in a separate process against a fresh database copy.

Student code is untrusted. The run gets a temporary folder holding copies of everything it needs (the submission,
the checks, the reference solution, the database), so it never needs to read the data directory where other
students' work is kept, and an environment without the server's settings or credentials. On a production server
(deploy/production/) the run also happens as a separate OS user with no network access: set CODEAI_SANDBOX_COMMAND
to the root-owned wrapper and CODEAI_SANDBOX_USER to that user, and the grader runs
`sudo -n -u <user> <wrapper> <job.json>` instead of Python directly.
"""
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
# The only settings a run inherits from the server. Nothing else (AWS credentials, tokens, bucket names) reaches it.
_ENV_KEEP = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "SYSTEMROOT", "TZ")

PASSED = "passed"
FAILED = "failed"
TIMEOUT = "timeout"
SYNTAX_ERROR = "syntax_error"
IMPORT_ERROR = "import_error"
UNGRADED = "ungraded"
RUNNER_STATUSES = {PASSED, FAILED, SYNTAX_ERROR, IMPORT_ERROR, UNGRADED}


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

        sandbox_cmd = os.environ.get("CODEAI_SANDBOX_COMMAND")
        sandbox_user = os.environ.get("CODEAI_SANDBOX_USER", "codeai-sandbox")
        with tempfile.TemporaryDirectory(prefix="codeai-grade-") as tmp:
            tmp_dir = Path(tmp)
            try:
                student_dir, engine_dir = tmp_dir / "student", tmp_dir / "engine_files"
                student_dir.mkdir()
                engine_dir.mkdir()
                submission_copy = student_dir / submission_path.name
                shutil.copyfile(submission_path, submission_copy)
                checks_copy = engine_dir / "checks.py"
                shutil.copyfile(problem.checks_path, checks_copy)
                reference_copy = engine_dir / "reference.py"
                shutil.copyfile(project.reference_path, reference_copy)
                db_copy = tmp_dir / "weather.db"
                shutil.copyfile(project.ensure_dataset(), db_copy)
                job_path = tmp_dir / "job.json"
                result_path = tmp_dir / "result.json"
                job_path.write_text(json.dumps({
                    "submission": str(submission_copy),
                    "checks": str(checks_copy),
                    "reference": str(reference_copy),
                    "db": str(db_copy),
                    "params": project.manifest.parameters,
                    "expected_reports": project.read_expected_reports().get("reports", []),
                    "result": str(result_path),
                }))
                if sandbox_cmd:
                    _open_to_sandbox(tmp_dir, result_path)
            except (OSError, ValueError) as exc:
                return GradeResult(UNGRADED, error_message=f"could not prepare grading: {exc}", timeout_s=self.timeout_s)

            env = {k: v for k, v in os.environ.items() if k in _ENV_KEEP}
            env.update(PYTHONPATH=str(REPO_ROOT), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                       HOME=str(tmp_dir), TMPDIR=str(tmp_dir))
            cmd = (["sudo", "-n", "-u", sandbox_user, sandbox_cmd, str(job_path)] if sandbox_cmd
                   else [sys.executable, "-m", "engine._runner", str(job_path)])
            try:
                proc = subprocess.run(cmd, cwd=str(tmp_dir), env=env, capture_output=True, timeout=self.timeout_s)
            except subprocess.TimeoutExpired:
                return GradeResult(TIMEOUT, timeout_s=self.timeout_s)
            except OSError as exc:
                return GradeResult(UNGRADED, error_message=f"could not start grading: {exc}", timeout_s=self.timeout_s)

            if not result_path.exists() or result_path.stat().st_size == 0:
                detail = proc.stderr.decode(errors="replace").strip().splitlines()[-1:] or ["no error output"]
                return GradeResult(FAILED, failures=[{
                    "test": "process",
                    "message": f"your program stopped before the checks finished ({detail[0]}).",
                }], timeout_s=self.timeout_s)
            try:
                data = json.loads(result_path.read_text())
                if not isinstance(data, dict) or data.get("status") not in RUNNER_STATUSES:
                    raise ValueError("unexpected result")
            except (OSError, ValueError):
                return GradeResult(FAILED, failures=[{
                    "test": "process", "message": "your program stopped before the checks finished.",
                }], timeout_s=self.timeout_s)

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


def _open_to_sandbox(tmp_dir: Path, result_path: Path) -> None:
    """Let the sandbox user read the copies and write the result. The folder can't be listed by others, and
    nothing in it is from the data directory except this one submission."""
    result_path.write_text("")
    for path in tmp_dir.rglob("*"):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(result_path, 0o666)
    os.chmod(tmp_dir, 0o711)
