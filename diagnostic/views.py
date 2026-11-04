"""Everything a student's screen receives. Built here so one safety net covers it.

No stages, scores, confidence, answer keys or misconception tags. Question payloads
carry only what is needed to play. `find_leaks` (game.py) checks these in tests and in
the engine before anything is returned.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, Optional

from .content import Content
from .game import fill, game_view, guide, zone_progress
from .models import AVAILABLE, LOCKED, MASTERED, Item, NodeState
from .state import DiagnosticState

# Friendly names for node status. "star" means the quest saw it go well.
STUDENT_STATUS = {LOCKED: "locked", AVAILABLE: "open", MASTERED: "star"}


def _rng(state: DiagnosticState, item_id: str) -> random.Random:
    return random.Random(f"{state.student_id}:{item_id}:view")


def item_view(content: Content, state: DiagnosticState, item: Item, kind: str = "item") -> Dict[str, Any]:
    payload = item.public(_rng(state, item.id))
    payload["kind"] = kind
    if item.concept is not None:
        zone = content.zone_for(item.concept)
        payload["zone"] = {"id": zone.id, "name": zone.name}
    return payload


def explain_view(content: Content, state: DiagnosticState, concept: str) -> Dict[str, Any]:
    prompt = content.explain[concept]
    zone = content.zone_for(concept)
    return {"kind": "explain", "id": prompt.id, "type": "text", "prompt": prompt.prompt,
            "intro": fill(guide(content)["explain_intro"], content, state),
            "zone": {"id": zone.id, "name": zone.name}, "can_skip": True,
            "max_chars": content.config.text.max_chars}


def tree_view(content: Content, node_states: Mapping[str, NodeState],
              start_nodes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    start = set(start_nodes or [])
    rows = []
    for nid in content.tree.order:
        node = content.tree.node(nid)
        rows.append({"id": nid, "name": node.name, "zone": content.zone_for(node.concept).name,
                     "parents": list(node.parents), "state": STUDENT_STATUS[node_states[nid].status],
                     "try_next": nid in start})
    return rows


def welcome_view(content: Content, state: DiagnosticState) -> Dict[str, Any]:
    cfg = content.config
    return {
        "title": cfg.title,
        "message": fill(guide(content)["welcome"], content, state),
        "buddies": [{"id": bid, "label": label} for bid, label in cfg.buddies],
        "goals": [{"id": g.id, "label": g.label} for g in content.goals.values()],
        "zones": zone_progress(content, state, None),
        "game": game_view(content, state),
    }
