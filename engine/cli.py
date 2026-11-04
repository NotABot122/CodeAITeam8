"""Command-line interface for students and curriculum authors.

  python -m engine.cli new                              start a new (anonymous) student
  python -m engine.cli show     --student ID            show the current problem
  python -m engine.cli submit   --student ID            grade your solution file
  python -m engine.cli progress --student ID            show stages and position
  python -m engine.cli theme    --student ID "pokemon"  build a project in your own theme (Bedrock)
  python -m engine.cli theme    --student ID --reset    go back to the standard project
  python -m engine.cli check-content                    check the project's tests and expected values
  python -m engine.cli generate-data                    rebuild the dataset from its seed
  python -m engine.cli generate-expected                recompute expected reports (marks them unreviewed)

AI features (tutor hints, themes) use Amazon Bedrock. Turn them off with --ai off.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from . import REPO_ROOT
from .ai import ModelError, provider_from_env
from .content import check_content, generate_expected
from .events import EventLog
from .progress import JsonProgressStore
from .project import ProjectLoadError, load_module, load_project
from .session import Engine, SubmitOutcome, UnknownStudent

DEFAULT_PROJECT = REPO_ROOT / "projects" / "weather-station"
DEFAULT_DATA = REPO_ROOT / ".codeai-data"


def workspace_file(data_dir: Path, student_id: str, project) -> Path:
    folder = data_dir / "workspace" / student_id
    return folder / ("solution.py" if project.root == DEFAULT_PROJECT.resolve() else f"{project.id}.py")


def start_workspace(data_dir: Path, student_id: str, project) -> Path:
    path = workspace_file(data_dir, student_id, project)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        if project.starter_path.exists():
            shutil.copyfile(project.starter_path, path)
        else:
            path.touch()
    return path


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
        label = "Hint (AI tutor)" if outcome.hint_source == "ai" else "Hint"
        print(f"\n{label}: {outcome.hint}")
    for change in outcome.stage_changes:
        print(f"\nStage up: {change.concept} {change.old_stage} -> {change.new_stage}")
    if outcome.passed and outcome.complete:
        print("\nProject complete! Run `progress` to see your stages.")
    elif outcome.passed and outcome.next_problem:
        print(f"\nNext: {outcome.next_problem.title}\n")
        print_problem(outcome.next_problem)


def make_provider(args):
    if args.ai == "off":
        return None
    try:
        return provider_from_env(args.ai)
    except (ImportError, ModelError, ValueError) as exc:
        print(f"[note] AI features are off: {exc}", file=sys.stderr)
        return None


def resolve_project(args, store: JsonProgressStore):
    if args.project:
        return load_project(args.project)
    student = getattr(args, "student", None)
    folder = store.active_project(student) if student else None
    if folder and Path(folder).is_dir():
        return load_project(folder)
    return load_project(DEFAULT_PROJECT)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.cli", description="CodeAI Adaptive Engine prototype")
    parser.add_argument("--project", default=None, help="project folder (default: the student's active project)")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA), help="where progress, logs, and workspaces live")
    parser.add_argument("--no-adaptive", action="store_true", help="turn off adaptive routing (fixed level order)")
    parser.add_argument("--ai", choices=("bedrock", "off"), default=os.environ.get("CODEAI_AI", "bedrock"),
                        help="AI tutor hints and themes (default: bedrock)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("new")
    for name in ("show", "progress"):
        sub.add_parser(name).add_argument("--student", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--student", required=True)
    submit.add_argument("--file", help="solution file (default: your workspace file for this project)")
    theme = sub.add_parser("theme")
    theme.add_argument("--student", required=True)
    theme.add_argument("request", nargs="*", help='what you want your project to be about, e.g. "pokemon"')
    theme.add_argument("--reset", action="store_true", help="go back to the standard project")
    sub.add_parser("check-content")
    sub.add_parser("generate-data")
    sub.add_parser("generate-expected")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    store = JsonProgressStore(data_dir)
    events = EventLog(data_dir)

    try:
        if args.command in ("generate-data", "generate-expected", "check-content"):
            project = load_project(args.project or DEFAULT_PROJECT)
            if args.command == "generate-data":
                load_module(project.generator_path, "_generator").generate(project.database_path)
                print(f"Wrote {project.database_path}")
                return 0
            if args.command == "generate-expected":
                data = generate_expected(project)
                print(f"Wrote {len(data['reports'])} expected reports (seed {data['seed']}, teacher_reviewed: false).")
                return 0
            result = check_content(project)
            print("Content check PASSED" if result.passed else "Content check FAILED")
            for line in result.problems:
                print(f"  - {line}")
            for line in result.notices:
                print(f"  note: {line}")
            return 0 if result.passed else 1

        provider = make_provider(args)

        if args.command == "theme":
            if not store.student_exists(args.student):
                raise UnknownStudent(f"no student with id {args.student}")
            if args.reset:
                store.set_active_project(args.student, None)
                print("You're back on the standard project.")
                return 0
            if provider is None:
                print("Themes need the AI features. Run without --ai off.", file=sys.stderr)
                return 2
            from .themes.builder import BUILT, ThemeBuilder

            print("Building your project. This takes about half a minute...")
            result = ThemeBuilder(provider, data_dir / "themes").build(" ".join(args.request))
            events.write("theme", student_id=args.student, source=result.status,
                         category=result.category, model_id=provider.model_id)
            print(result.message)
            if result.status != BUILT:
                return 1
            project = load_project(result.project_path)
            store.set_active_project(args.student, str(project.root))
            engine = Engine(project, store, events, hint_provider=provider, adaptive=not args.no_adaptive)
            engine.open(args.student)
            path = start_workspace(data_dir, args.student, project)
            print(f"Write your code in: {path}\n")
            problem, _ = engine.current_problem(args.student)
            print_problem(problem)
            return 0

        if args.command == "new":
            project = load_project(args.project or DEFAULT_PROJECT)
            engine = Engine(project, store, events, hint_provider=provider, adaptive=not args.no_adaptive)
            student_id = engine.new_student()
            path = start_workspace(data_dir, student_id, project)
            print(f"Your student id: {student_id}")
            print(f"Write your code in: {path}")
            print('Want a different theme? Run: python -m engine.cli theme --student ID "your idea"\n')
            problem, _ = engine.current_problem(student_id)
            print_problem(problem)
            return 0

        project = resolve_project(args, store)
        engine = Engine(project, store, events, hint_provider=provider, adaptive=not args.no_adaptive)

        if args.command == "show":
            problem, notices = engine.current_problem(args.student)
            for notice in notices:
                print(f"[note] {notice}")
            print(f"Project: {project.title}   File: {workspace_file(data_dir, args.student, project)}")
            if problem is None:
                print("You've finished the project.")
            else:
                print_problem(problem)
            return 0

        if args.command == "progress":
            print(engine.progress_view(args.student))
            return 0

        if args.command == "submit":
            path = Path(args.file) if args.file else start_workspace(data_dir, args.student, project)
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
