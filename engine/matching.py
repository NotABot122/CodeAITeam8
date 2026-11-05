"""Pair a student with a project: interests pick the story, skills pick the starting point.

Every first-topic project (catalog `topics[0].choices`) teaches the same four skills with the same
levels and checks, so skill can't make one story a better fit than another. Skill decides where the
student starts and what they warm up on first (the readiness placement, planned practice and the
pathway). Interests decide the story: the readiness check's goal, plus any words the student typed
about what they're into, matched against each project's `interests` keywords.

Privacy: this module only sees text that already passed the readiness check's screen
(diagnostic.safety.clean_goal_text drops personal details, profanity and injection attempts). It
matches that text locally and never logs it or sends it anywhere. Reasons shown to the student
repeat only the words that matched a catalog keyword, never anything else the student typed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

GOAL_POINTS = 3          # the goal the student picked names this project
WORD_POINTS = 2          # each of the student's words that matches one of the project's interests
MAX_WORDS_SHOWN = 3
NOT_SURE_GOAL = "not_sure"

_WORD = re.compile(r"[a-z]+")


def _stem(word: str) -> str:
    """A rough singular, so "animals" matches "animal" and "games" matches "game"."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _keyword_hits(keywords: Iterable[str], text: Optional[str]) -> List[str]:
    """The parts of the student's text that match a catalog keyword (one or more words), as they wrote them
    and in their order. Only catalog keywords can match, so nothing else the student typed is ever repeated."""
    tokens = _WORD.findall((text or "").lower())
    stems = [_stem(t) for t in tokens]
    found: List[tuple] = []
    for keyword in keywords:
        want = [_stem(w) for w in _WORD.findall(str(keyword).lower())]
        for start in range(len(stems) - len(want) + 1) if want else ():
            if stems[start:start + len(want)] == want:
                found.append((start, len(want), " ".join(tokens[start:start + len(want)])))
                break
    # Keep the longest match where two overlap ("video games" over "games"), then the student's order.
    found.sort(key=lambda f: (f[0], -f[1]))
    hits: List[str] = []
    covered = -1
    for start, length, surface in found:
        if start > covered and surface not in hits:
            hits.append(surface)
            covered = start + length - 1
    return hits


@dataclass(frozen=True)
class StoryFit:
    project: str
    points: int
    goal_match: bool
    words: List[str]           # the student's words that matched a catalog keyword, as written


@dataclass
class StoryMatch:
    project: str
    fits: List[StoryFit]       # every choice, best first
    reasons: List[str]         # student-facing sentences about interests
    theme_idea: Optional[str]  # the student's own words, offered for "Make it yours" when no story matched them


def match_story(choices: Sequence[Mapping], goal_id: Optional[str], goal_label: Optional[str],
                interest_text: Optional[str], default: str) -> StoryMatch:
    """Rank the ready-made stories by the student's interests. Ties keep catalog order, so with no signal
    the first choice (the original project) wins."""
    fits = []
    for choice in choices:
        goal_match = bool(goal_id) and goal_id in (choice.get("goals") or [])
        hits = _keyword_hits(choice.get("interests") or [], interest_text)
        points = (GOAL_POINTS if goal_match and goal_id != NOT_SURE_GOAL else 0) + WORD_POINTS * len(hits)
        fits.append(StoryFit(choice["project"], points, goal_match, hits))
    ranked = sorted(fits, key=lambda f: -f.points)      # stable: catalog order breaks ties
    best = ranked[0] if ranked and ranked[0].points > 0 else next((f for f in fits if f.project == default), None)
    project = best.project if best else default

    reasons: List[str] = []
    if best and best.words:
        reasons.append(f"You said you're into {_join(best.words[:MAX_WORDS_SHOWN], lower=False)}, "
                       "and this story is about that.")
    if best and best.goal_match and goal_id != NOT_SURE_GOAL and goal_label:
        reasons.append(f"You picked \"{goal_label}\" as your goal.")
    if not reasons:
        reasons.append("You weren't sure yet, so we picked the original project. You can switch below."
                       if goal_id == NOT_SURE_GOAL or not goal_id
                       else "This is the closest match to what you told us. You can switch below.")
    any_word_hit = any(f.words for f in fits)
    theme_idea = interest_text.strip() if interest_text and interest_text.strip() and not any_word_hit else None
    return StoryMatch(project, ranked, reasons, theme_idea)


@dataclass
class SkillFit:
    strengths: List[str] = field(default_factory=list)   # concept names the check is confident are solid
    warm_ups: List[str] = field(default_factory=list)    # concept names that get a practice problem first
    new_ideas: List[str] = field(default_factory=list)   # confident gaps with no practice problem: full help instead
    reasons: List[str] = field(default_factory=list)


def skill_fit(decisions: Mapping[str, Mapping], names: Mapping[str, str], planned: Iterable[str] = ()) -> SkillFit:
    """What the readiness check is confident about, in plain words. Uses only results the course trusted
    (decision["used"]), so a lucky guess never shows up as a strength. No stages or numbers."""
    used = {c: d for c, d in decisions.items() if d.get("used")}
    strengths = [names.get(c, c) for c, d in used.items() if int(d.get("stage", 0)) >= 2]
    planned = set(planned)
    gaps = [c for c, d in used.items() if int(d.get("stage", 0)) == 0]
    warm_ups = [names.get(c, c) for c in gaps if c in planned]
    new_ideas = [names.get(c, c) for c in gaps if c not in planned]
    reasons = []
    if strengths:
        reasons.append(f"You showed you know {_join(strengths)}, so you won't repeat the basics there.")
    if warm_ups:
        reasons.append(f"You'll get a short warm-up on {_join(warm_ups)} before the level that uses it.")
    if new_ideas:
        # engine/support.py gives the most help on a concept the check is confident is new.
        reasons.append(f"{_join(new_ideas).capitalize()} will be newer to you, so you'll get extra help there.")
    if not reasons:
        reasons.append("You'll build it one level at a time, with hints when you need them.")
    return SkillFit(strengths, warm_ups, new_ideas, reasons)


def _join(items: List[str], lower: bool = True) -> str:
    items = [i.lower() for i in items] if lower else list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def match_view(story: StoryMatch, skills: Optional[SkillFit], title: str, pitch: str) -> Dict:
    """The student-facing match: why this project, and how it fits their skills."""
    return {"project": story.project, "title": title, "pitch": pitch, "because": list(story.reasons),
            "fit": list(skills.reasons) if skills else [], "themeIdea": story.theme_idea}
