"""The game layer: XP, streaks, badges, the guide's words, and what students may see.

Students see effort and fun: XP, a rank title, badges, a friendly guide. They never see
stages, scores, confidence or what the answer key said (evaluation plan: "feedback,
never scores"). Teachers get the numbers from diagnostic/report.py.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .content import Content
from .models import Item
from .scoring import ItemScore
from .state import DiagnosticState

# Keys that must never appear in anything shown to a student.
STUDENT_FORBIDDEN_KEYS = frozenset({
    "stage", "stages", "score", "scores", "confidence", "credit", "mastery", "ratio", "points",
    "answer", "correct_answer", "misconception", "misconceptions", "game_stage", "rationale", "evidence_quotes",
    "status_ratio",
})


def _pick(lines: Sequence[str], key: str) -> str:
    """A stable pick: the same student and question always get the same line."""
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return lines[int(digest, 16) % len(lines)]


def guide(content: Content) -> Dict[str, Any]:
    return content.config.game["guide"]


def fill(text: str, content: Content, state: Optional[DiagnosticState] = None) -> str:
    buddy_id = state.buddy if state else None
    label = next((lbl for bid, lbl in content.config.buddies if bid == buddy_id), "friend")
    return text.replace("{guide}", guide(content)["name"]).replace("{buddy}", label)


def rank_title(content: Content, xp: int) -> str:
    title = content.config.game["ranks"][0]["title"]
    for rank in content.config.game["ranks"]:
        if xp >= rank["xp"]:
            title = rank["title"]
    return title


def badge_name(content: Content, badge_id: str) -> str:
    for badge in content.config.game["badges"]:
        if badge["id"] == badge_id:
            return badge["name"]
    return badge_id


def award_badge(state: DiagnosticState, badge_id: str) -> Optional[str]:
    if badge_id in state.badges:
        return None
    state.badges.append(badge_id)
    return badge_id


# Awards ---------------------------------------------------------------------------

def record_answer(content: Content, state: DiagnosticState, passed: bool) -> List[str]:
    """Update XP, streak and badges for one scored answer. Returns the badges earned now."""
    xp = content.config.game["xp"]
    earned: List[str] = []
    previous_missed = state.consecutive_misses > 0
    gain = xp["try"]
    if passed:
        gain += xp["correct"]
        state.streak += 1
        state.best_streak = max(state.best_streak, state.streak)
        state.consecutive_misses = 0
        if state.streak > 3:
            gain += xp["streak_bonus"]
        if state.streak == 3:
            earned.append(award_badge(state, "hot_streak") or "")
        if previous_missed:
            earned.append(award_badge(state, "bounce_back") or "")
    else:
        state.streak = 0
        state.consecutive_misses += 1
    state.xp += gain
    earned.append(award_badge(state, "first_step") or "")
    return [b for b in earned if b]


def record_explain(content: Content, state: DiagnosticState) -> List[str]:
    state.xp += content.config.game["xp"]["explain"]
    return [b for b in [award_badge(state, "storyteller")] if b]


def record_booster(content: Content, state: DiagnosticState) -> None:
    state.xp += content.config.game["xp"]["booster"]
    state.consecutive_misses = 0


# Words ---------------------------------------------------------------------------------

def answer_feedback(content: Content, state: DiagnosticState, item: Item, score: ItemScore,
                    badges: Sequence[str]) -> Dict[str, Any]:
    """What the student reads after an answer. Kind, short, and never a number."""
    lines = guide(content)
    key = f"{state.student_id}:{item.id}:{'r' if score.passed else 'w'}"
    if score.passed:
        message = item.feedback_right or _pick(lines["right"], key)
        tip = None
    else:
        message = _pick(lines["wrong"], key)
        tip = score.picked_why or item.feedback_wrong
    payload: Dict[str, Any] = {"correct": score.passed, "message": message, "tip": tip,
                               "new_badges": [{"id": b, "name": badge_name(content, b)} for b in badges]}
    if score.passed and state.streak == 3:
        payload["cheer"] = lines["streak"]
    return payload


def default_student_message(content: Content, state: DiagnosticState, focus_order: Sequence[str]) -> str:
    """The closing message when no model wrote one (or the model's text failed the filter)."""
    goal = content.goals.get(state.goal_id) or content.default_goal()
    zone = content.zone_for(focus_order[0]).name if focus_order else content.zones[0].name
    parts = [fill(guide(content)["finish"], content, state), f"Your goal: {goal.label}.", f"First stop: {zone}."]
    return " ".join(parts)


def game_view(content: Content, state: DiagnosticState) -> Dict[str, Any]:
    return {
        "guide": guide(content)["name"],
        "xp": state.xp,
        "rank": rank_title(content, state.xp),
        "streak": state.streak,
        "badges": [{"id": b, "name": badge_name(content, b)} for b in state.badges],
    }


def zone_progress(content: Content, state: DiagnosticState, current_concept: Optional[str]) -> List[Dict[str, Any]]:
    return [{"id": z.id, "name": z.name, "story": z.story, "done": z.concept in state.zones_done,
             "current": z.concept == current_concept} for z in content.zones]


# Safety net --------------------------------------------------------------------------------

def find_leaks(payload: Any, banned_words: Iterable[str], path: str = "") -> List[str]:
    """Walk a student-facing payload and report anything that should stay with teachers."""
    banned = [w.lower() for w in banned_words]
    leaks: List[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            here = f"{path}.{key}" if path else str(key)
            if str(key).lower() in STUDENT_FORBIDDEN_KEYS:
                leaks.append(f"forbidden key: {here}")
            leaks += find_leaks(value, banned, here)
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            leaks += find_leaks(value, banned, f"{path}[{index}]")
    elif isinstance(payload, str):
        low = payload.lower()
        for word in banned:
            if f" {word} " in f" {low} ":
                leaks.append(f"banned word {word!r} at {path}")
    return leaks
