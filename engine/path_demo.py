"""Demo of the adaptive path across projects.

  python -m engine.path_demo            live: Bedrock scores the quiz's written answer
  python -m engine.path_demo --offline  no network: a scripted model scores it

Two students finish the Weather Station project:
- Aced it: every level on the first try, so the Course moves them to the
  topic where they have the least mastery (Lists and Dictionaries), and
  their stages carry over.
- Struggled: four tries on Level 1 and a practice problem, so the Course
  gives a revision project: a review quiz (predict the output, explain it)
  and a scaffolded coding task. Then it moves them on.
Data goes to a temporary folder.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .ai import ModelReply, ScriptedProvider, provider_from_env
from .course import PROJECTS_ROOT, Course
from .demo import COUNT_GOOD, GET_EXCLUSIVE, GET_GOOD, GET_STRING_FORMAT, GET_UNSORTED_TUPLES, STRONG

EXPLANATION = ("If you paste a value like O'Brien into the SQL text, the quote ends the string early and breaks "
               "the query, and someone could even change what the query does. With ? the database keeps the "
               "value as data.")


class OfflineModel(ScriptedProvider):
    def complete(self, system, prompt, max_tokens, tools=None, require_tool=False):
        if tools and tools[0].name == "score_answer":
            return ModelReply(tool_name="score_answer", tool_input={
                "stage": 3, "feedback": "Great answer: you named both problems and why ? keeps values as data."},
                model_id="scripted (offline)")
        return ModelReply(text="Check which rows your query keeps, and whether the values are placeholders.",
                          model_id="scripted (offline)")


def stages_line(course: Course, student: str) -> str:
    return ", ".join(f"{c['name']} {c['stage']}" for c in course.state(student)["concepts"])


def show_step(step: dict) -> None:
    print(f"  What's next ({step['kind']}): {step['reason']}")
    for n, option in enumerate(step["options"], start=1):
        print(f"    {n}. {option['label']}")


def run(course: Course, root: Path, label: str, submissions, extra=None) -> str:
    print(f"\n{'#' * 72}\n# {label}\n{'#' * 72}")
    student = course.new_student()
    outcome = None
    for i, source in enumerate(submissions):
        path = root / f"{student}-{i}.py"
        path.write_text(source)
        problem = course.state(student)["problem"]
        outcome = course.submit(student, path)
        mark = "PASS" if outcome.passed else "FAIL"
        print(f"  {mark} {problem['title']}")
    print(f"  Stages now: {stages_line(course, student)}")
    show_step(outcome.next_step)
    return student


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Adaptive path demo")
    parser.add_argument("--offline", action="store_true", help="use a scripted model instead of Bedrock")
    args = parser.parse_args(argv)
    provider = OfflineModel() if args.offline else provider_from_env("bedrock")
    reference = lambda folder: (PROJECTS_ROOT / folder / "reference" / "solution.py").read_text()  # noqa: E731

    with tempfile.TemporaryDirectory(prefix="codeai-path-demo-") as tmp:
        root = Path(tmp)
        course = Course(root / "data", provider=provider)
        print(f"Model: {provider.model_id}")

        # 1. Aced it.
        strong = run(course, root, "Student who aced the Weather Station project", STRONG)
        result = course.start(strong, 0)
        print(f"  -> {result['message']}")
        state = course.state(strong)
        print(f"  Now on: {state['project']['title']}, {state['problem']['title']}")
        print(f"  Starting stages carry over: {stages_line(course, strong)}")

        # 2. Struggled.
        struggled = run(course, root, "Student who struggled with Level 1",
                        [GET_UNSORTED_TUPLES, GET_STRING_FORMAT, GET_EXCLUSIVE, GET_GOOD, GET_GOOD + COUNT_GOOD]
                        + [COUNT_GOOD + s for s in STRONG[1:]])
        result = course.start(struggled, 0)
        print(f"  -> {result['message']}")
        quiz = course.state(struggled)["problem"]
        print(f"\n  {quiz['title']}: {len(quiz['questions'])} questions")
        for q in quiz["questions"]:
            print(f"    - ({q['type']}) {q['prompt']}")

        first = course.answer(struggled, {"q1": 0, "q2": 1, "q3": EXPLANATION})
        print(f"\n  First try: {'PASS' if first.passed else 'FAIL'}")
        for r in first.question_results:
            if r.get("explanation"):
                print(f"    {r['id']} wrong. Why: {r['explanation']}")
        second = course.answer(struggled, {"q1": 1, "q2": 1, "q3": EXPLANATION})
        print(f"  Second try: {'PASS' if second.passed else 'FAIL'}")
        written = second.question_results[2]
        print(f"    Written answer: rubric stage {written['score']}. Feedback: {written['feedback']}")

        task = course.state(struggled)["problem"]
        print(f"\n  {task['title']} (starter has blanks to fill in)")
        path = root / "revision.py"
        path.write_text(reference("revision-database-retrieval"))
        done = course.submit(struggled, path)
        print(f"  {'PASS' if done.passed else 'FAIL'} {task['title']}")
        print(f"  Stages now: {stages_line(course, struggled)}")
        show_step(done.next_step)
    return 0


if __name__ == "__main__":
    sys.exit(main())
