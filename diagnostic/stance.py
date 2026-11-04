"""Pick a pedagogical stance (names match evaluation/schemas/route_next.schema.json).

  PROJECT_SYNTHESIS  every concept is solid and the evidence is confident
  REINFORCE          some concept is missing or its evidence is shaky: practice first
  BRIDGE             two or more concepts are solid: a cross-cutting challenge suits
  ADVANCE            everything has a start; keep moving through the levels
"""
from __future__ import annotations

from typing import Mapping

REINFORCE = "STANCE_REINFORCE"
ADVANCE = "STANCE_ADVANCE"
BRIDGE = "STANCE_BRIDGE"
PROJECT_SYNTHESIS = "STANCE_PROJECT_SYNTHESIS"

SOLID_STAGE = 2


def choose_stance(stages: Mapping[str, int], confident: Mapping[str, bool]) -> str:
    """`confident[c]` is true when the evidence for concept c is not borderline."""
    if not stages:
        return REINFORCE
    solid = [c for c, s in stages.items() if s >= SOLID_STAGE]
    shaky = [c for c in stages if stages[c] == 0 or not confident.get(c, False)]
    if len(solid) == len(stages) and not shaky:
        return PROJECT_SYNTHESIS
    if shaky:
        return REINFORCE
    if len(solid) >= 2:
        return BRIDGE
    return ADVANCE
