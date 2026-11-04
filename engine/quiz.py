"""Check-for-understanding quizzes: "predict the output" and "explain it".

questions.yaml is a list of questions:

  - id: q1
    type: predict
    prompt: What does this print?
    code: |
      total = 0
      for n in [1, 2, 3]:
          total += n
      print(total)
    choices: ["3", "6", "123"]
    answer: 1                 # index into choices
    explanation: The loop adds 1, then 2, then 3.

  - id: q3
    type: explain
    prompt: In your own words, why ...?
    rubric:                   # one descriptor per stage
      0: ...
      1: ...
      2: ...
      3: ...

A quiz passes when every predict answer is right and every explain answer is
given (1 to 2,000 characters, allowed by the content filter). The explain
score is shown to the student as feedback, but it does not change stages,
because the AI grader hasn't been benchmarked against human raters yet.
"""
from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from typing import Dict, List, Optional

MAX_EXPLAIN_CHARS = 2000


class QuizError(ValueError):
    pass


@dataclass
class QuestionResult:
    id: str
    type: str
    correct: Optional[bool] = None       # predict questions
    message: str = ""
    explanation: Optional[str] = None    # shown after a wrong predict answer
    score: Optional[int] = None          # explain questions, 0-3, None if ungraded
    feedback: Optional[str] = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class QuizResult:
    passed: bool
    results: List[QuestionResult] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)


def validate_questions(data, where: str) -> List[dict]:
    """Return the questions, or raise QuizError naming the first problem."""
    if not isinstance(data, list) or not data:
        raise QuizError(f"{where}: questions.yaml must be a non-empty list")
    ids = set()
    for index, q in enumerate(data):
        at = f"{where} question {index + 1}"
        if not isinstance(q, dict) or not isinstance(q.get("id"), str) or not isinstance(q.get("prompt"), str):
            raise QuizError(f"{at}: needs an id and a prompt")
        if q["id"] in ids:
            raise QuizError(f"{at}: id {q['id']!r} is used twice")
        ids.add(q["id"])
        if q.get("type") == "predict":
            choices = q.get("choices")
            if not isinstance(choices, list) or len(choices) < 2 or not all(isinstance(c, str) for c in choices):
                raise QuizError(f"{at}: predict questions need at least 2 text choices")
            answer = q.get("answer")
            if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < len(choices):
                raise QuizError(f"{at}: answer must be the index of the right choice")
            if not isinstance(q.get("code"), str) or not isinstance(q.get("explanation"), str):
                raise QuizError(f"{at}: predict questions need code and an explanation")
        elif q.get("type") == "explain":
            rubric = q.get("rubric")
            if not isinstance(rubric, dict) or sorted(rubric) != [0, 1, 2, 3] or \
                    not all(isinstance(v, str) and v.strip() for v in rubric.values()):
                raise QuizError(f"{at}: explain questions need a rubric with descriptors for stages 0, 1, 2, and 3")
        else:
            raise QuizError(f"{at}: type must be predict or explain")
    return data


def run_predict_code(code: str) -> str:
    """Run an authored snippet and return what it prints. Used by the content check only."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exec(compile(code, "<quiz>", "exec"), {"__name__": "__quiz__"})  # trusted, curriculum-authored code
    return buffer.getvalue().strip()


def public_questions(questions: List[dict]) -> List[dict]:
    """What a student (or the UI) may see: no answers, explanations, or rubrics."""
    out = []
    for q in questions:
        item = {"id": q["id"], "type": q["type"], "prompt": q["prompt"]}
        if q["type"] == "predict":
            item.update(code=q["code"], choices=list(q["choices"]))
        out.append(item)
    return out


def grade_quiz(label: str, questions: List[dict], answers: Dict[str, object], rubric_grader=None) -> QuizResult:
    results, messages = [], []
    passed = True
    for number, q in enumerate(questions, start=1):
        given = answers.get(q["id"])
        if q["type"] == "predict":
            if not isinstance(given, int) or isinstance(given, bool) or not 0 <= given < len(q["choices"]):
                passed = False
                results.append(QuestionResult(q["id"], "predict", False, "Pick one of the choices."))
                messages.append(f"{label}: question {number} needs an answer.")
                continue
            correct = given == q["answer"]
            passed = passed and correct
            results.append(QuestionResult(q["id"], "predict", correct, "Right!" if correct else "Not quite.",
                                          explanation=None if correct else q["explanation"]))
            if not correct:
                messages.append(f"{label}: question {number} isn't right yet. Read the explanation and try again.")
        else:
            text = given.strip() if isinstance(given, str) else ""
            if not 1 <= len(text) <= MAX_EXPLAIN_CHARS:
                passed = False
                results.append(QuestionResult(q["id"], "explain", message=f"Write 1 to {MAX_EXPLAIN_CHARS} characters."))
                messages.append(f"{label}: question {number} needs a written answer.")
                continue
            if rubric_grader is None:
                results.append(QuestionResult(q["id"], "explain", message="Thanks, your answer was saved."))
                continue
            graded = rubric_grader.grade(q["prompt"], q["rubric"], text)
            if graded.blocked:
                passed = False
                results.append(QuestionResult(q["id"], "explain", message="Please rewrite your answer and keep it "
                                                                         "about the question."))
                messages.append(f"{label}: question {number} needs a different answer.")
                continue
            results.append(QuestionResult(q["id"], "explain", score=graded.score, feedback=graded.feedback,
                                          message="Thanks, your answer was saved." if graded.score is None else
                                          "Your answer was scored."))
    if passed:
        messages.insert(0, f"{label}: passed. Every answer works.")
    return QuizResult(passed, results, messages)
