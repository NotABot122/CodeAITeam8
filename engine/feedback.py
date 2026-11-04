"""Turn a grade result into plain-language messages and pick the next hint."""
from __future__ import annotations

from typing import List, Optional, Tuple

from . import grader as g
from .project import Problem

MAX_MESSAGE_CHARS = 200


def _clip(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_MESSAGE_CHARS else text[: MAX_MESSAGE_CHARS - 3].rstrip() + "..."


def _with_label(problem: Problem, text: str) -> str:
    # Messages start lowercase on purpose ("Level 2: a temperature of 35.0 ...")
    # so function names like summarize keep their exact spelling.
    return _clip(f"{problem.label}: {text}")


def messages_for(problem: Problem, result: g.GradeResult) -> List[str]:
    if result.status == g.PASSED:
        return [_with_label(problem, "passed. Every check works.")]
    if result.status == g.TIMEOUT:
        return [_with_label(problem, f"your code ran longer than {result.timeout_s:g} seconds. "
                                     "Look for a loop that never ends.")]
    if result.status == g.SYNTAX_ERROR:
        where = f" (line {result.error_line})" if result.error_line else ""
        return [_with_label(problem, f"Python couldn't read your file: {result.error_message}{where}.")]
    if result.status == g.IMPORT_ERROR:
        where = f" (line {result.error_line})" if result.error_line else ""
        return [_with_label(problem, f"your file raised an error when it loaded: {result.error_message}{where}.")]
    if result.status == g.UNGRADED:
        return [_with_label(problem, "grading isn't available right now, so this attempt wasn't counted. "
                                     "Your work is safe; try submitting again in a moment.")]
    return [_with_label(problem, failure["message"]) for failure in result.failures] or \
        [_with_label(problem, "some checks didn't pass.")]


def next_hint(problem: Problem, hints_seen: int) -> Tuple[Optional[str], int]:
    """Return (hint, new hints_seen). After the last hint, repeat it."""
    if not problem.hints:
        return None, hints_seen
    if hints_seen < len(problem.hints):
        return problem.hints[hints_seen], hints_seen + 1
    return problem.hints[-1], hints_seen
