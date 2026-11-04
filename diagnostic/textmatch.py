"""Small, dependency-free helpers for matching key ideas in a student's own words."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .models import ExplainPrompt, KeyIdea, MAX_STAGE

_TOKEN = re.compile(r"[a-z0-9']+")
_SEGMENT = re.compile(r"[^.!?\n]+")


def _stem(token: str) -> str:
    token = token.replace("'", "")
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def tokens(text: str) -> List[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower())]


FUZZY_MIN_TARGET_LEN = 5      # only longer key words tolerate a typo ("loop" must not match "look")


def _one_edit(a: str, b: str) -> bool:
    """True when a and b differ by one insertion, deletion, substitution or swap of neighbours."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(short) and short[i] == long_[i]:
        i += 1
    return short[i:] == long_[i + 1:]


def _same(word: str, target: str) -> bool:
    """A child's word matches a key word exactly, or within one typo for longer key words."""
    return word == target or (len(target) >= FUZZY_MIN_TARGET_LEN and len(word) >= FUZZY_MIN_TARGET_LEN - 1
                              and _one_edit(word, target))


def _contains(haystack: List[str], needle: List[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    return any(all(_same(h, n) for h, n in zip(haystack[i:i + len(needle)], needle))
               for i in range(len(haystack) - len(needle) + 1))


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def quote_in_text(quote: str, text: str) -> bool:
    """True when `quote` really appears in `text` (ignoring case and spacing)."""
    return bool(quote.strip()) and normalize(quote) in normalize(text)


def idea_hit(idea: KeyIdea, text_tokens: List[str]) -> bool:
    return any(_contains(text_tokens, tokens(word)) for word in idea.words)


def evidence_quote(idea: KeyIdea, text: str, limit: int = 120) -> Optional[str]:
    """The part of the student's text that shows the idea, cut from the original text."""
    for match in _SEGMENT.finditer(text):
        segment = match.group(0).strip()
        if segment and idea_hit(idea, tokens(segment)):
            return segment[:limit].strip()
    return None


def key_idea_hits(prompt: ExplainPrompt, text: str) -> List[KeyIdea]:
    toks = tokens(text)
    return [idea for idea in prompt.key_ideas if idea_hit(idea, toks)]


COPY_OVERLAP = 0.8
COPY_MIN_TOKENS = 4


def copies_question(prompt: ExplainPrompt, text: str) -> bool:
    """True when (nearly) every word of the answer comes straight from the question."""
    mine = tokens(text)
    if len(mine) < COPY_MIN_TOKENS:
        return False
    asked = set(tokens(prompt.prompt))
    return sum(1 for t in mine if t in asked) / len(mine) >= COPY_OVERLAP


def keyword_stage(prompt: ExplainPrompt, text: str) -> Tuple[int, List[str]]:
    """A crude, repeatable stage from key ideas: the highest level reached without skipping one.

    Returns (stage, evidence quotes). With no idea found, the quote is the start of the
    student's own text so that every stage still points at their words. Echoing the
    question back earns nothing.
    """
    if copies_question(prompt, text):
        return 0, [" ".join(text.split())[:80]]
    hits = key_idea_hits(prompt, text)
    levels = {idea.level for idea in hits}
    stage = 0
    for level in range(1, MAX_STAGE + 1):
        if level in levels:
            stage = level
        else:
            break
    quotes: List[str] = []
    for idea in hits:
        quote = evidence_quote(idea, text)
        if quote and quote not in quotes:
            quotes.append(quote)
    if not quotes and text.strip():
        quotes.append(" ".join(text.split())[:80])
    return stage, quotes[:5]
