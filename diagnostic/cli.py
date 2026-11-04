"""Command line for the Weather Station readiness quest.

  python3 -m diagnostic.cli play                       play the quest yourself
  python3 -m diagnostic.cli play --profile mixed       watch a simulated child play
  python3 -m diagnostic.cli report   --student ID      teacher report (JSON)
  python3 -m diagnostic.cli handoff  --student ID      show (or --apply) the lesson start for this student
  python3 -m diagnostic.cli check-content              validate the item bank, tree and config
  python3 -m diagnostic.cli tree                       print the skill tree
  python3 -m diagnostic.cli show-item ID               render one question
  python3 -m diagnostic.cli export-rubric              write the evaluation rubric from the content

Options for every command: --project DIR, --data-dir DIR (or $CODEAI_PROJECT / $CODEAI_DATA_DIR),
--ai off|mock|bedrock (or $CODEAI_AI; default off = no model).
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence

from engine.project import ProjectLoadError, load_project

from . import paths
from .ai.factory import MODES, ProviderUnavailable, default_mode, make_provider
from .content import ContentError, check_content, load_content
from .contract import rubric_document
from .engine import DiagnosticEngine, NotFinished, UnknownQuest
from .handoff import apply_placement
from .models import InvalidResponse
from .render import parse_input, render_step
from .simulation import PROFILES, play, profile_student
from .store import InvalidStudentId

RUBRIC_PATH = paths.EVAL_ROOT / "rubrics" / "weather_diag_rubric.json"


def _engine(args: argparse.Namespace) -> DiagnosticEngine:
    try:
        provider = make_provider(args.ai)
    except ProviderUnavailable as exc:
        print(f"[note] running without a model: {exc}", file=sys.stderr)
        provider = None
    return DiagnosticEngine.from_paths(args.project, args.data_dir, provider=provider)


def run_quest(engine: DiagnosticEngine, ask: Callable[[str], str], say: Callable[[str], None],
              buddy: str = "cloud", goal: Optional[str] = None) -> str:
    """Play a quest in the terminal. `ask` and `say` are injected so tests can drive it."""
    options = engine.options()
    say(f"\n{options['title']}\n{options['message']}")
    goal_ids = [g["id"] for g in options["goals"]]
    if goal is None:
        say("\nWhat do you want to make?")
        for number, g in enumerate(options["goals"], start=1):
            say(f"  {number}) {g['label']}")
        pick = ask("Type a number (or press Enter): ").strip()
        goal = goal_ids[int(pick) - 1] if pick.isdigit() and 1 <= int(pick) <= len(goal_ids) else None
    started = engine.start(buddy=buddy, goal=goal)
    student_id = started["student_id"]
    for notice in started["notices"]:
        say(f"[note] {notice}")
    step = started["first"]
    while not step.get("done"):
        view = step["step"]
        say("\n" + render_step(view))
        while True:
            try:
                response = parse_input(view, ask("> "))
                feedback = engine.answer(student_id, response)["feedback"]
                break
            except (ValueError, InvalidResponse) as exc:
                say(f"  ({exc})")
        say("  " + feedback["message"] + (f" {feedback['tip']}" if feedback.get("tip") else ""))
        for badge in feedback.get("new_badges", []):
            say(f"  New badge: {badge['name']}!")
        if feedback.get("zone_cleared"):
            say("  " + feedback["zone_cleared"]["message"])
        step = engine.next(student_id)
    say("\n" + step["message"])
    say(step["goal_connection"])
    say(f"Rank: {step['game']['rank']}   Badges: {', '.join(b['name'] for b in step['game']['badges'])}")
    return student_id


def cmd_play(args: argparse.Namespace) -> int:
    engine = _engine(args)
    if args.profile:
        result = play(engine, profile_student(args.profile, args.seed))
        view = result["student_view"]
        print(f"Simulated child: {args.profile}   student id: {result['student_id']}   steps: {result['steps']}")
        print(view["message"])
        print(f"Rank: {view['game']['rank']}   Badges: {', '.join(b['name'] for b in view['game']['badges'])}")
        if args.teacher:
            print(json.dumps(result["report"], indent=2))
        return 0
    student_id = run_quest(engine, input, print, goal=args.goal)
    print(f"\nYour student id: {student_id}")
    if args.teacher:
        print(json.dumps(engine.teacher_report(student_id), indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    print(json.dumps(_engine(args).teacher_report(args.student), indent=2))
    return 0


def lesson_command(data_dir: Path, student_id: str) -> str:
    """The lesson-engine command for this student. engine.cli does not read $CODEAI_DATA_DIR,
    so a non-default data directory is passed explicitly."""
    flag = "" if data_dir == paths.DEFAULT_DATA_DIR.resolve() else f" --data-dir {shlex.quote(str(data_dir))}"
    return f"python3 -m engine.cli{flag} show --student {student_id}"


def cmd_handoff(args: argparse.Namespace) -> int:
    engine = _engine(args)
    report = engine.teacher_report(args.student)
    problem_id = report["placement"]["next_task_id"]
    print(f"Placement: start at {problem_id}. {report['placement']['reason']}")
    if report["placement"]["practice_ahead"]:
        print("Practice likely needed later: " + ", ".join(report["placement"]["practice_ahead"]))
    if args.apply:
        result = apply_placement(engine.project, paths.data_dir(args.data_dir), args.student, problem_id)
        print(("Applied: " if result.applied else "Not applied: ") + result.message)
        if result.applied:
            print("Next: " + lesson_command(paths.data_dir(args.data_dir), args.student))
        return 0 if result.applied else 1
    print("Add --apply to set this as the student's current lesson problem.")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    result = check_content(paths.project_dir(args.project))
    print("Diagnostic content check PASSED" if result.passed else "Diagnostic content check FAILED")
    for line in result.problems:
        print(f"  - {line}")
    for line in result.notices:
        print(f"  note: {line}")
    return 0 if result.passed else 1


def cmd_tree(args: argparse.Namespace) -> int:
    root = paths.project_dir(args.project)
    content = load_content(root, load_project(root).manifest.concept_ids())
    for zone in content.zones:
        print(f"{zone.name} ({zone.concept})")
        for node in content.tree.concept_nodes(zone.concept):
            parents = ", ".join(node.parents) or "start"
            print(f"  tier {node.tier}  {node.id:<16} {node.name}   needs: {parents}")
    print("\nMulti-parent nodes: " + ", ".join(content.tree.multi_parent_nodes()))
    return 0


def cmd_show_item(args: argparse.Namespace) -> int:
    root = paths.project_dir(args.project)
    content = load_content(root, load_project(root).manifest.concept_ids())
    item = content.items.get(args.item) or next((b for b in content.boosters if b.id == args.item), None)
    if item is None:
        print(f"no question named {args.item}", file=sys.stderr)
        return 2
    import random

    print(render_step(item.public(random.Random(0))))
    if args.answer:
        print(f"\nAnswer key: {item.answer}   (guess chance {item.guess_chance:.2f})")
    return 0


def cmd_export_rubric(args: argparse.Namespace) -> int:
    root = paths.project_dir(args.project)
    content = load_content(root, load_project(root).manifest.concept_ids())
    text = json.dumps(rubric_document(content), indent=2, ensure_ascii=False) + "\n"
    out = Path(args.out) if args.out else RUBRIC_PATH
    if args.check:
        same = out.exists() and out.read_text(encoding="utf-8") == text
        print("Rubric file is up to date." if same else f"Rubric file is out of date: run export-rubric ({out})")
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m diagnostic.cli", description=__doc__.split("\n")[0])
    parser.add_argument("--project", default=None, help="project folder (default: $CODEAI_PROJECT or the Weather Station project)")
    parser.add_argument("--data-dir", default=None, help="where progress and logs live (default: $CODEAI_DATA_DIR or .codeai-data)")
    parser.add_argument("--ai", choices=MODES, default=default_mode(), help="off (default), mock, or bedrock")
    sub = parser.add_subparsers(dest="command", required=True)

    play_cmd = sub.add_parser("play", help="play the quest, or watch a simulated child")
    play_cmd.add_argument("--profile", choices=sorted(PROFILES), help="simulate a child instead of typing")
    play_cmd.add_argument("--goal", default=None, help="goal id, to skip the goal question")
    play_cmd.add_argument("--seed", type=int, default=7)
    play_cmd.add_argument("--teacher", action="store_true", help="also print the teacher report")
    play_cmd.set_defaults(run=cmd_play)

    report = sub.add_parser("report", help="teacher report for a student")
    report.add_argument("--student", required=True)
    report.set_defaults(run=cmd_report)

    handoff = sub.add_parser("handoff", help="where the lesson should start for a student")
    handoff.add_argument("--student", required=True)
    handoff.add_argument("--apply", action="store_true")
    handoff.set_defaults(run=cmd_handoff)

    sub.add_parser("check-content", help="validate the content").set_defaults(run=cmd_check)
    sub.add_parser("tree", help="print the skill tree").set_defaults(run=cmd_tree)

    show = sub.add_parser("show-item", help="render one question")
    show.add_argument("item")
    show.add_argument("--answer", action="store_true", help="also print the answer key (authors only)")
    show.set_defaults(run=cmd_show_item)

    export = sub.add_parser("export-rubric", help="write evaluation/rubrics/weather_diag_rubric.json from the content")
    export.add_argument("--out", default=None)
    export.add_argument("--check", action="store_true", help="only check that the file is up to date")
    export.set_defaults(run=cmd_export_rubric)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except ProjectLoadError as exc:
        print("The project could not be loaded:", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
    except ContentError as exc:
        print("The diagnostic content has problems:", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
    except (UnknownQuest, NotFinished, InvalidStudentId) as exc:
        print(str(exc), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
