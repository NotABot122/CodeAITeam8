"""Command-line interface for students and curriculum authors.

  python -m engine.cli new                              start a new (anonymous) student
  python -m engine.cli show     --student ID            show the current problem
  python -m engine.cli submit   --student ID            grade your solution file
  python -m engine.cli answer   --student ID            answer a quiz (asks each question)
  python -m engine.cli next     --student ID [--choose N] [--theme "..."]
                                                        after a project: see and start what's next
  python -m engine.cli progress --student ID            stages for every concept, and position
  python -m engine.cli theme    --student ID "pokemon"  build this project in your own theme (Bedrock)
  python -m engine.cli theme    --student ID --reset    go back to the standard project
  python -m engine.cli placement --student ID      after the readiness quest: set starting stages and problem
  python -m engine.cli check-content [--project DIR]    check a project's tests, answers, and quizzes
  python -m engine.cli generate-data                    rebuild the dataset from its seed
  python -m engine.cli generate-expected                recompute expected reports (marks them unreviewed)

AI features (tutor hints, quiz feedback, themes) use Amazon Bedrock. Turn them off with --ai off.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import REPO_ROOT
from .ai import ModelError, provider_from_env
from .content import check_content, generate_expected
from .course import Course, CourseError
from .project import ProjectLoadError, load_module, load_project
from .session import SubmitOutcome, UnknownStudent
from .stages import STAGE_NAMES

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


def print_problem(problem: dict) -> None:
    print("=" * 72)
    print(problem["instructions"].strip())
    if problem.get("questions"):
        print("\nThis step is a quiz. Run: python -m engine.cli answer --student ID")
    print("=" * 72)


def print_next_step(step: dict) -> None:
    print(f"\nWhat's next: {step['reason']}")
    for number, option in enumerate(step["options"], start=1):
        star = " (recommended)" if number == 1 else ""
        print(f"  {number}. {option['label']}{star}")
    if step["options"] and step["options"][0]["kind"] != "all_done":
        print("Start one with: python -m engine.cli next --student ID --choose 1")


def print_outcome(outcome: SubmitOutcome) -> None:
    for notice in outcome.notices:
        print(f"[note] {notice}")
    for message in outcome.messages:
        print(("  PASS " if outcome.passed else "  FAIL ") + message)
    for number, result in enumerate(outcome.question_results, start=1):
        line = f"  Q{number}: {result['message']}"
        if result.get("score") is not None:
            line += f" Rubric stage {result['score']} ({STAGE_NAMES[result['score']]})."
        print(line)
        if result.get("explanation"):
            print(f"      Why: {result['explanation']}")
        if result.get("feedback"):
            print(f"      Feedback: {result['feedback']}")
    if outcome.hint:
        label = "Hint (AI tutor)" if outcome.hint_source == "ai" else "Hint"
        print(f"\n{label}: {outcome.hint}")
    for change in outcome.stage_changes:
        print(f"\nStage up: {change.concept} {change.old_stage} -> {change.new_stage}")
    if outcome.passed and outcome.complete:
        print("\nProject complete!")
        if outcome.next_step:
            print_next_step(outcome.next_step)
    elif outcome.passed and outcome.next_problem:
        print(f"\nNext: {outcome.next_problem.title}\n")
        print_problem({"instructions": outcome.next_problem.instructions,
                       "questions": outcome.next_problem.questions})


def ask_quiz(questions) -> dict:
    answers = {}
    for number, q in enumerate(questions, start=1):
        print(f"\nQuestion {number}: {q['prompt']}")
        if q["type"] == "predict":
            print("\n    " + q["code"].rstrip().replace("\n", "\n    ") + "\n")
            for index, choice in enumerate(q["choices"], start=1):
                print(f"  {index}) {choice.replace(chr(10), ' / ')}")
            while True:
                raw = input("Your answer (number): ").strip()
                if raw.isdigit() and 1 <= int(raw) <= len(q["choices"]):
                    answers[q["id"]] = int(raw) - 1
                    break
                print(f"Type a number from 1 to {len(q['choices'])}.")
        else:
            answers[q["id"]] = input("Your answer: ").strip()
    return answers


def make_provider(mode: str):
    if mode == "off":
        return None
    try:
        return provider_from_env(mode)
    except (ImportError, ModelError, ValueError) as exc:
        print(f"[note] AI features are off: {exc}", file=sys.stderr)
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.cli", description="CodeAI Adaptive Engine prototype")
    parser.add_argument("--project", default=None, help="project folder, for the author commands")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA), help="where progress, logs, and workspaces live")
    parser.add_argument("--no-adaptive", action="store_true", help="turn off adaptive routing (fixed level order)")
    parser.add_argument("--ai", choices=("bedrock", "off"), default=os.environ.get("CODEAI_AI", "bedrock"),
                        help="AI tutor hints, quiz feedback, and themes (default: bedrock)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("new")
    for name in ("show", "progress"):
        sub.add_parser(name).add_argument("--student", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--student", required=True)
    submit.add_argument("--file", help="solution file (default: your workspace file for this project)")
    answer = sub.add_parser("answer")
    answer.add_argument("--student", required=True)
    answer.add_argument("--answers", help='JSON, e.g. {"q1": 0, "q3": "my explanation"} (default: ask)')
    nxt = sub.add_parser("next")
    nxt.add_argument("--student", required=True)
    nxt.add_argument("--choose", type=int, help="start option N")
    nxt.add_argument("--theme", help="theme for a 'new theme' option")
    theme = sub.add_parser("theme")
    theme.add_argument("--student", required=True)
    theme.add_argument("request", nargs="*", help='what you want your project to be about, e.g. "pokemon"')
    theme.add_argument("--reset", action="store_true", help="go back to the standard project")
    placement = sub.add_parser("placement", help="use a finished readiness quest (python -m diagnostic.cli play)")
    placement.add_argument("--student", required=True)
    sub.add_parser("check-content")
    sub.add_parser("generate-data")
    sub.add_parser("generate-expected")
    args = parser.parse_args(argv)
    data_dir = Path(args.data_dir)

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

        course = Course(data_dir, provider=make_provider(args.ai), adaptive=not args.no_adaptive)

        if args.command == "new":
            student_id = course.new_student()
            path = start_workspace(data_dir, student_id, course.project_for(student_id))
            print(f"Your student id: {student_id}")
            print(f"Write your code in: {path}")
            print('Want a different theme? Run: python -m engine.cli theme --student ID "your idea"\n')
            print_problem(course.state(student_id)["problem"])
            return 0

        student = args.student

        if args.command == "theme":
            if args.reset:
                course.reset_theme(student)
                print("You're back on the standard project.")
                return 0
            print("Building your project. This takes about half a minute...")
            result = course.build_theme(student, " ".join(args.request))
            print(result["message"])
            if not result.get("built"):
                return 1
            return show_start(course, data_dir, student)

        if args.command == "placement":
            summary = course.apply_diagnostic(student)
            for concept, d in summary["decisions"].items():
                used = "starts at Stage %d" % d["stage"] if d["used"] else "not used (%s)" % d["reason"]
                print(f"  {course.catalog.name(concept):<20} {used}")
            note = " (your lesson had already started, so it keeps its place)" if summary["lesson_already_started"] else ""
            print(f"First problem: {summary['start_problem']}{note}")
            return show_start(course, data_dir, student)

        if args.command == "next":
            step = course.next_step(student)
            if step is None:
                print("Finish your current project first. Run `show` to see where you are.")
                return 1
            if args.choose is None:
                print_next_step(step)
                return 0
            result = course.start(student, args.choose - 1, theme_request=args.theme)
            print(result["message"])
            if result.get("built") is False:
                return 1
            return show_start(course, data_dir, student)

        if args.command == "show":
            state = course.state(student)
            for notice in state["notices"]:
                print(f"[note] {notice}")
            project = course.project_for(student)
            print(f"Project: {project.title}   File: {workspace_file(data_dir, student, project)}")
            if state["complete"]:
                print("You've finished this project.")
                if state["nextStep"]:
                    print_next_step(state["nextStep"])
            else:
                print_problem(state["problem"])
            return 0

        if args.command == "progress":
            state = course.state(student)
            print(course.engine(student).progress_view(student))
            print("\nAll concepts:")
            for c in state["concepts"]:
                print(f"  {c['name']:<20} Stage {c['stage']} ({c['stageName']})")
            return 0

        if args.command == "submit":
            project = course.project_for(student)
            path = Path(args.file) if args.file else start_workspace(data_dir, student, project)
            print_outcome(course.submit(student, path))
            return 0

        if args.command == "answer":
            state = course.state(student)
            problem = state["problem"]
            if not problem or not problem.get("questions"):
                print("Your current step isn't a quiz. Use `submit` for code.")
                return 1
            answers = json.loads(args.answers) if args.answers else ask_quiz(problem["questions"])
            print_outcome(course.answer(student, answers))
            return 0
    except ProjectLoadError as exc:
        print("The project couldn't be loaded:", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    except UnknownStudent as exc:
        print(f"{exc}. Run `new` to start.", file=sys.stderr)
        return 2
    except CourseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 1


def show_start(course: Course, data_dir: Path, student: str) -> int:
    project = course.project_for(student)
    path = start_workspace(data_dir, student, project)
    print(f"Write your code in: {path}\n")
    print_problem(course.state(student)["problem"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
