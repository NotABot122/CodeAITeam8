"""A cheap reading-level check for kid-facing text. No dependencies."""
from __future__ import annotations

import re
from typing import List

_SENTENCE_END = re.compile(r"[.!?]+")
_WORD = re.compile(r"[A-Za-z0-9_']+")


def _sentences(text: str) -> List[str]:
    return [s for s in _SENTENCE_END.split(text) if s.strip()]


def longest_sentence_words(text: str) -> int:
    return max((len(_WORD.findall(s)) for s in _sentences(text)), default=0)


def longest_word_length(text: str) -> int:
    return max((len(w) for w in _WORD.findall(text)), default=0)


def readability_problems(text: str, max_sentence_words: int, max_word_length: int) -> List[str]:
    """Return plain-language problems, or an empty list when the text reads easily."""
    problems = []
    if longest_sentence_words(text) > max_sentence_words:
        problems.append(f"a sentence is longer than {max_sentence_words} words")
    if longest_word_length(text) > max_word_length:
        problems.append(f"a word is longer than {max_word_length} letters")
    return problems
