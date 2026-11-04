"""Command-line interface for students and curriculum authors.

  python -m engine.cli new                       start a new (anonymous) student
  python -m engine.cli show     --student ID     show the current problem
  python -m engine.cli submit   --student ID     grade your solution file
  python -m engine.cli progress --student ID     show stages and position
  python -m engine.cli check-content             check the project's tests and expected values
  python -m engine.cli generate-data             rebuild the dataset from its seed
  python -m engine.cli generate-expected         recompute expected reports (marks them unreviewed)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import REPO_ROOT
from .content import check_content, generate_expected
from .events import EventLog
from .progress import JsonProgressStore
from .project import ProjectLoadError, load_module, load_project
from .session import Engine, SubmitOutcome, UnknownStudent

DEFAULT_PROJECT = REPO_ROOT / "projects" / "weather-station"
DEFAULT_DATA = REPO_ROOT / ".codeai-data"


def workspace_file(data_dir: Path, student_id: str) -> Path:
    return data_dir / "workspace" / student_id / "solution.py"


def print_problem(problem) -> None:
    print("=" * 72)
    print(problem.instructions.strip())
    print("=" * 72)


def print_outcome(outcome: SubmitOutcome) -> None:
    for notice in outcome.notices:
        print(f"[note] {notice}")
    for message in outcome.messages:
        print(("  PASS " if outcome.passed else "  FAIL ") + message)
    if outcome.hint:
        print(f"\nHint: {outcome.hint}")
    for change in outcome.stage_changes:
        print(f"\nStage up: {change.concept} {change.old_stage} -> {change.new_stage}")
    if outcome.passed and outcome.complete:
        print("\nProject complete! Run `progress` to see your stages.")
    elif outcome.passed and outcome.next_problem:
        print(f"\nNext: {outcome.next_problem.title}\n")
        print_problem(outcome.next_problem)


def build_engine(args) -> Engine:
    project = load_project(args.project)
    data_dir = Path(args.data_dir)
    return Engine(project, JsonProgressStore(data_dir), EventLog(data_dir), adaptive=not args.no_adaptive)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.cli", description="CodeAI Adaptive Engine prototype")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT), help="project folder")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA), help="where progress, logs, and workspaces live")
    parser.add_argument("--no-adaptive", action="store_true", help="turn off adaptive routing (fixed level order)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("new")
    for name in ("show", "progress"):
        sub.add_parser(name).add_argument("--student", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--student", required=True)
    submit.add_argument("--file", help="solution file (default: your workspace solution.py)")
    sub.add_parser("check-content")
    sub.add_parser("generate-data")
    sub.add_parser("generate-expected")
    args = parser.parse_args(argv)

    try:
        if args.command == "generate-data":
            project = load_project(args.project)
            load_module(project.generator_path, "_generator").generate(project.database_path)
            print(f"Wrote {project.database_path}")
            return 0
        if args.command == "generate-expected":
            data = generate_expected(load_project(args.project))
            print(f"Wrote {len(data['reports'])} expected reports (seed {data['seed']}, teacher_reviewed: false).")
            return 0
        if args.command == "check-content":
            result = check_content(load_project(args.project))
            print("Content check PASSED" if result.passed else "Content check FAILED")
            for line in result.problems:
                print(f"  - {line}")
            for line in result.notices:
                print(f"  note: {line}")
            return 0 if result.passed else 1

        engine = build_engine(args)
        data_dir = Path(args.data_dir)

        if args.command == "new":
            student_id = engine.new_student()
            path = workspace_file(data_dir, student_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            if engine.project.starter_path.exists():
                shutil.copyfile(engine.project.starter_path, path)
            else:
                path.touch()
            print(f"Your student id: {student_id}")
            print(f"Write your code in: {path}\n")
            problem, _ = engine.current_problem(student_id)
            print_problem(problem)
            return 0

        if args.command == "show":
            problem, notices = engine.current_problem(args.student)
            for notice in notices:
                print(f"[note] {notice}")
            if problem is None:
                print("You've finished the project.")
            else:
                print_problem(problem)
            return 0

        if args.command == "progress":
            print(engine.progress_view(args.student))
            return 0

        if args.command == "submit":
            path = Path(args.file) if args.file else workspace_file(data_dir, args.student)
            print_outcome(engine.submit(args.student, path))
            return 0
    except ProjectLoadError as exc:
        print("The project couldn't be loaded:", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    except UnknownStudent as exc:
        print(f"{exc}. Run `new` to start.", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
