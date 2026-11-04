"""Plain-text rendering of quest screens, for the command line and the demo."""
from __future__ import annotations

from typing import Any, Dict, List

LETTERS = "abcdefghij"


def render_step(step: Dict[str, Any]) -> str:
    lines: List[str] = []
    if step.get("zone"):
        lines.append(f"[{step['zone']['name']}]")
    if step.get("intro"):
        lines.append(step["intro"])
    lines.append(step["prompt"])
    kind = step["type"]
    if kind in ("choice", "spot", "trace"):
        for letter, option in zip(LETTERS, step["options"]):
            lines.append(f"  {letter}) {option['text']}")
    elif kind == "order":
        lines.append("  Put these in the right order:")
        for number, card in enumerate(step["cards"], start=1):
            lines.append(f"  {number}) {card['text']}")
    elif kind == "sort":
        boxes = ", ".join(f"{n}={b['text']}" for n, b in enumerate(step["buckets"], start=1))
        lines.append(f"  Boxes: {boxes}")
        for number, card in enumerate(step["cards"], start=1):
            lines.append(f"  {number}) {card['text']}")
    elif kind == "text":
        lines.append("  (type a short answer, or press Enter to skip)")
    return "\n".join(lines)


def parse_input(step: Dict[str, Any], raw: str) -> Any:
    """Turn what a person typed into the response the engine expects. Raises ValueError if it does not fit."""
    raw = raw.strip()
    kind = step["type"]
    if kind == "text":
        return {"skip": True} if not raw else {"text": raw}
    if kind in ("choice", "spot", "trace"):
        index = LETTERS.find(raw.lower()[:1])
        if len(raw) != 1 or not 0 <= index < len(step["options"]):
            raise ValueError("type the letter of your answer")
        return step["options"][index]["id"]
    cards = step["cards"]
    if kind == "order":
        numbers = raw.replace(",", " ").split()
        if sorted(numbers) != sorted(str(n) for n in range(1, len(cards) + 1)):
            raise ValueError(f"type each card number once, in order, like: {' '.join(str(n) for n in range(1, len(cards) + 1))}")
        return [cards[int(n) - 1]["id"] for n in numbers]
    parts = raw.replace(",", " ").split()
    if len(parts) != len(cards) or any(not p.isdigit() or not 1 <= int(p) <= len(step["buckets"]) for p in parts):
        raise ValueError(f"type a box number (1-{len(step['buckets'])}) for each card, in card order")
    return {card["id"]: step["buckets"][int(p) - 1]["id"] for card, p in zip(cards, parts)}
