"""Input prefilter and output filter for the diagnostic.

Input (what students type):
  Flag names match evaluation/schemas/validate_submission.schema.json so the
  evaluation harness reads them unchanged: empty, too_short, gibberish,
  prompt_injection, inappropriate, personal_info.
  Rules follow evaluation/harness/validator.py, tuned for short answers:
  a lower "too short" bar (short answers are fine) and a spelling-tolerant
  gibberish check. The shared word lists come from engine.safety.

Output (what the model wrote for students):
  Text must be short, plain, free of markup, links, scores and stage numbers,
  and must pass the same word lists. Anything else is replaced by a fixed
  message from the content files.

Nothing here makes a network call.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from engine.safety import EMAIL, PHONE, looks_like_ai_paste, screen_text

from .readability import readability_problems

EMPTY, TOO_SHORT, GIBBERISH = "empty", "too_short", "gibberish"
PROMPT_INJECTION, INAPPROPRIATE, PERSONAL_INFO = "prompt_injection", "inappropriate", "personal_info"
SUSPECTED_AI_PASTE = "suspected_ai_paste"   # review only: the answer is still scored

HARNESS_MIN_WORDS = 8            # the evaluation harness's bar (used only for parity checks)
GIBBERISH_CLUSTER_FRACTION = 0.4
MAX_OUTPUT_CHARS = 320

_WORD = re.compile(r"[A-Za-z\u00C0-\u024F\u4e00-\u9fff]+")

_INJECTION_PATTERNS = [
    r"ignore (all|the|any|your|previous|above).{0,40}(instruction|rubric|rule|prompt)",
    r"disregard (all|the|any|your|previous|above)",
    r"(give|assign|score|grade|mark|rate) (me|this|it|my answer)? ?(a |an )?(stage|score|level)? ?(3|three)\b",
    r"you are (now )?(no longer|not) (a )?(grader|judge|teacher)",
    r"you are now\b",
    r"pretend (to be|you are)",
    r"system prompt|developer message|jailbreak",
    r"</?(student_submission|evidence|system|assistant|instructions?)>",
]
_INJECTION = [re.compile(p) for p in _INJECTION_PATTERNS]

# Mild rudeness: flagged, but a fair answer in the same text is still scored.
_MILD_INSULTS = ("stupid", "idiot", "hate you", "shut up", "damn", "dumb")
_NAME_INTRO = re.compile(r"\b(my name is|i am called|i live (at|on|in)|my address is|my school is|i go to)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Prefilter:
    flags: Tuple[str, ...]
    unscorable: bool                  # true when the text must not be graded or sent to a model
    category: Optional[str] = None    # word-list category behind an `inappropriate` flag, for the teacher

    def has(self, flag: str) -> bool:
        return flag in self.flags


def _looks_like_gibberish(text: str) -> bool:
    letters = sum(ch.isalpha() for ch in text)
    alnum = sum(ch.isalnum() for ch in text)
    vowels = sum(ch in "aeiouAEIOU" for ch in text)
    if not letters:
        return alnum == 0 and len(text) > 2
    words = [w for w in _WORD.findall(text)]
    latin = [w.lower() for w in words if w.isascii() and len(w) >= 4]
    clustered = [w for w in latin if re.search(r"[bcdfghjklmnpqrstvwxz]{4,}", w)]
    stretched = [w for w in latin if len(w) >= 6 and max(w.count(c) for c in set(w)) / len(w) > 0.7]
    return (
        alnum / max(len(text), 1) < 0.5
        or vowels / letters < 0.15
        or (len(latin) >= 4 and len(clustered) / len(latin) > GIBBERISH_CLUSTER_FRACTION)
        or (len(stretched) >= 2 and len(stretched) / len(latin) >= 0.5)
    )


def prefilter(text: Optional[str], min_words: int = 3) -> Prefilter:
    """Check one free-text answer before any grading or model call."""
    stripped = (text or "").strip()
    if not stripped:
        return Prefilter((EMPTY,), True)
    flags: List[str] = []
    unscorable = False
    category: Optional[str] = None

    if len(_WORD.findall(stripped)) + len(re.findall(r"\b\d+\b", stripped)) < min_words:
        flags.append(TOO_SHORT)
        unscorable = True
    if _looks_like_gibberish(stripped):
        flags.append(GIBBERISH)
        unscorable = True
    low = stripped.lower()
    if any(p.search(low) for p in _INJECTION):
        flags.append(PROMPT_INJECTION)
        unscorable = True
    if EMAIL.search(stripped) or PHONE.search(stripped) or _NAME_INTRO.search(stripped):
        flags.append(PERSONAL_INFO)
        unscorable = True
    screened = screen_text(stripped)
    if screened.blocked and screened.category != "personal_information":
        flags.append(INAPPROPRIATE)
        unscorable = True
        category = screened.category
    elif any(word in low for word in _MILD_INSULTS):
        flags.append(INAPPROPRIATE)          # flagged, still scorable
    if looks_like_ai_paste(stripped):
        flags.append(SUSPECTED_AI_PASTE)     # flagged for the teacher, still scorable
    return Prefilter(tuple(flags), unscorable, category)


def clean_goal_text(text: Optional[str], max_chars: int) -> Tuple[Optional[str], Tuple[str, ...]]:
    """The student's optional "what do you want to make?" words. Returns (text or None, flags)."""
    if text is None or not text.strip():
        return None, ()
    collapsed = " ".join(text.split())[:max_chars]
    result = prefilter(collapsed, min_words=1)
    if result.unscorable or result.has(INAPPROPRIATE):
        return None, result.flags
    return collapsed, ()


# Output ---------------------------------------------------------------------------

_SCORE_LIKE = re.compile(r"(\b\d+\s*(/|out of)\s*\d+\b)|%|\bstage\s*\d\b|\bscore[sd]?\b", re.IGNORECASE)
_MARKUP = re.compile(r"[<>`{}\[\]]|https?:|www\.|\.com\b")


@dataclass(frozen=True)
class OutputCheck:
    ok: bool
    reasons: Tuple[str, ...] = ()


def check_student_text(text: Optional[str], banned_words: Tuple[str, ...], max_sentence_words: int,
                       max_word_length: int, max_chars: int = MAX_OUTPUT_CHARS) -> OutputCheck:
    """Is this model-written text fit to show a student?"""
    if not isinstance(text, str) or not text.strip():
        return OutputCheck(False, ("empty",))
    reasons: List[str] = []
    if len(text) > max_chars:
        reasons.append("too long")
    if _MARKUP.search(text):
        reasons.append("markup or link")
    if _SCORE_LIKE.search(text):
        reasons.append("shows a score or stage")
    low = text.lower()
    for word in banned_words:
        if re.search(r"\b" + re.escape(word) + r"\b", low):
            reasons.append(f"uses '{word}'")
    if screen_text(text).blocked:
        reasons.append("failed the content word lists")
    # Sentences get a little room (a model writes longer ones than an author); words get none.
    reasons += readability_problems(text, max_sentence_words + 4, max_word_length)
    return OutputCheck(not reasons, tuple(reasons))
