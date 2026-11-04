"""Live demo of student-chosen themes and AI tutor hints.

  python -m engine.theme_demo "I love pokemon"     uses Amazon Bedrock
  python -m engine.theme_demo --offline            uses a scripted model (no network)

A student asks for a theme. The engine screens the request, has the model
design the theme, builds the project, and runs its quality checks. The
student then makes a common Level 1 mistake and gets an AI hint, fixes it,
and finishes all four levels. Data goes to a temporary folder.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .ai import ModelReply, ScriptedProvider, provider_from_env
from .events import EventLog
from .progress import JsonProgressStore
from .project import load_project
from .session import Engine
from .themes.builder import BUILT, ThemeBuilder
from .themes.samples import POKEMON

OFFLINE_HINT = ("Look at the comparison signs in your WHERE clause. The task says to include both ends of the "
                "range, so which signs keep the first and last numbers?")


def offline_provider() -> ScriptedProvider:
    return ScriptedProvider([
        ModelReply(tool_name="screen_request", tool_input={"allowed": True, "category": "ok"}),
        ModelReply(tool_name="create_theme", tool_input=POKEMON),
        ModelReply(text=OFFLINE_HINT),
    ], model_id="scripted (offline)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Themes and AI hints demo")
    parser.add_argument("request", nargs="*", default=["I", "love", "pokemon,", "can", "my", "project", "be", "a",
                                                        "pokedex?"])
    parser.add_argument("--offline", action="store_true", help="use a scripted model instead of Bedrock")
    args = parser.parse_args(argv)
    request = " ".join(args.request)
    provider = offline_provider() if args.offline else provider_from_env("bedrock")

    with tempfile.TemporaryDirectory(prefix="codeai-theme-demo-") as tmp:
        root = Path(tmp)
        print(f"Student asks: \"{request}\"\nModel: {provider.model_id}\n")
        result = ThemeBuilder(provider, root / "themes").build(request)
        print(f"[{result.status}] {result.message}")
        if result.status != BUILT:
            print(f"  reason: {result.category}")
            return 1

        project = load_project(result.project_path)
        spec = result.spec
        print(f"\nStory: {spec.story}\n")
        print(f"Table `{spec.table}`: {', '.join(spec.columns)}")
        print(f"Groups: {', '.join(spec.groups)}   e.g. {', '.join(spec.names[spec.groups[0]][:5])}")
        print(f"Rules: {spec.metric_a.label} = {spec.metric_a.column} >= {spec.metric_a.threshold:g}, "
              f"{spec.metric_b.label} = {spec.metric_b.column} >= {spec.metric_b.threshold:g}")
        print("Functions to write: " + ", ".join(spec.functions[r] for r in ("get", "classify", "summarize", "report")))
        print("Quality gate: passed (reference passes every check, answers match an independent SQL check)\n")

        engine = Engine(project, JsonProgressStore(root), EventLog(root), hint_provider=provider)
        student = engine.new_student()
        reference = project.reference_path.read_text()
        n = spec.number_column
        mistake = reference.replace(f"{n} >= ? AND {n} <= ?", f"{n} > ? AND {n} < ?")

        attempts = [("Level 1, first try (leaves out both ends of the range)", mistake)] + \
                   [(f"Level {i}", reference) for i in range(1, 5)]
        for label, source in attempts:
            path = root / "solution.py"
            path.write_text(source)
            outcome = engine.submit(student, path)
            print(f"--- {label}")
            for message in outcome.messages:
                print(("  PASS " if outcome.passed else "  FAIL ") + message)
            if outcome.hint:
                print(f"  Hint ({'AI tutor' if outcome.hint_source == 'ai' else 'pre-authored'}): {outcome.hint}")
            if outcome.passed:
                print("  Next: " + ("project complete" if outcome.complete else outcome.next_problem.title))
        print("\nThe concepts, levels, and checks are the same as the weather project. Only the theme changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
