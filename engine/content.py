"""Expected values and the content check for a project."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import List

from .grader import Grader
from .loop_checker import find_loop_problems
from .project import Project, load_module
from .quiz import run_predict_code


@dataclass
class ContentCheckResult:
    passed: bool
    problems: List[str] = field(default_factory=list)
    notices: List[str] = field(default_factory=list)


def _dataset_seed(project: Project) -> int:
    generator = load_module(project.generator_path, f"_seed_{project.id.replace('-', '_')}")
    return generator.read_default_seed()


def generate_expected(project: Project) -> dict:
    """Recompute expected reports with the independent checker and mark them unreviewed."""
    checker = load_module(project.independent_checker_path, "_independent_checker")
    conn = sqlite3.connect(str(project.ensure_dataset()))
    try:
        reports = [{"args": dict(args), "report": checker.compute(conn, **args)}
                   for args in project.manifest.parameters.get("expected_report_args", [])]
    finally:
        conn.close()
    data = {
        "seed": _dataset_seed(project),
        "teacher_reviewed": False,
        "generated_by": "independent_checker",
        "reports": reports,
    }
    project.expected_reports_path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def check_content(project: Project, grader: Grader = None) -> ContentCheckResult:
    grader = grader or Grader()
    problems: List[str] = []
    notices: List[str] = []

    # 1. Stored expected values: seed and independent recomputation (projects that have them).
    has_reports = bool(project.manifest.parameters.get("expected_report_args"))
    stored = project.read_expected_reports()
    if has_reports:
        seed = _dataset_seed(project)
        if stored.get("seed") != seed:
            problems.append(f"expected reports were made with seed {stored.get('seed')!r}, "
                            f"but the dataset seed is {seed}. Regenerate the expected reports.")
        checker = load_module(project.independent_checker_path, "_independent_checker")
        conn = sqlite3.connect(str(project.ensure_dataset()))
        try:
            for entry in stored.get("reports", []):
                computed = checker.compute(conn, **entry["args"])
                for key in sorted(set(computed) | set(entry["report"])):
                    if computed.get(key) != entry["report"].get(key):
                        where = " ".join(str(v) for v in entry["args"].values())
                        problems.append(f"expected report {where}: {key} is stored as {entry['report'].get(key)!r} "
                                        f"but computes to {computed.get(key)!r}")
        finally:
            conn.close()

    # 2. The reference solution must pass every code problem, including loop checks.
    #    Every quiz "predict" answer must match what its code really prints.
    for problem in project.problems.values():
        if problem.is_quiz:
            for q in problem.questions:
                if q["type"] != "predict":
                    continue
                try:
                    output = run_predict_code(q["code"])
                except Exception as exc:
                    problems.append(f"{problem.label} question {q['id']}: code raised {type(exc).__name__}: {exc}")
                    continue
                if output != q["choices"][q["answer"]].strip():
                    problems.append(f"{problem.label} question {q['id']}: the code prints {output!r}, "
                                    f"but the marked answer is {q['choices'][q['answer']]!r}")
                if sum(1 for c in q["choices"] if c.strip() == output) != 1:
                    problems.append(f"{problem.label} question {q['id']}: exactly one choice must match the output")
            continue
        result = grader.grade(project, problem, project.reference_path)
        if not result.passed:
            details = [f["test"] for f in result.failures] or [result.status, result.error_message or ""]
            problems.append(f"reference solution fails {problem.label}: {', '.join(d for d in details if d)}")
        if problem.loop_check:
            for message in find_loop_problems(project.reference_path.read_text(), problem.loop_check):
                problems.append(f"reference solution fails the loop check for {problem.label}: {message}")

    if has_reports and not stored.get("teacher_reviewed", False):
        notices.append("Expected values are unreviewed: a teacher has not checked them yet.")

    return ContentCheckResult(passed=not problems, problems=problems, notices=notices)
