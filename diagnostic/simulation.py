"""Simulated children, for tests, the demo and the evaluation harness.

Each simulated child has a hidden true level (stage 0-3) per concept and a writing
style. They answer through the engine's public API, exactly like a real client.

How answers are drawn: a question at or below the child's level is passed 92% of the
time (slips happen); a question above it is passed only by luck (the question's own
guess chance). Wrong answers are drawn from the question's wrong choices.

Read results with care: the engine is scored against levels the simulator itself
decided. That checks the pipeline recovers what it should, and it overstates
real-world agreement. It is not the evaluation plan's E01 result, which needs
human-rated answers from real children.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .content import Content
from .engine import DiagnosticEngine
from .models import CHOICE_LIKE, ORDER, Item

PASS_WHEN_ABLE = 0.92
STYLES = ("standard", "terse", "informal", "esl")
SIM_PREFIX = "SIM-"

# Hand-written answers a child at each stage might give. Index = stage.
EXPLAIN_BANK: Dict[str, List[List[str]]] = {
    "database_retrieval": [
        ["i dont know", "its a big book of facts"],
        ["you look through the log and find the day you want", "i would look at the log and read the page"],
        ["i look in the log and only keep the days that match the station and the date",
         "you find the page and just the days that match the date"],
        ["look in the log, keep only the days that match the station, sort them in order, and say no days found if there are none",
         "i look in the log then keep the matching rows and sort them, and if nothing matches it is empty"],
    ],
    "conditionals": [
        ["no idea", "i like when it rains"],
        ["an if rule only runs when something is true", "it will decide first and only when it is true it goes"],
        ["the rule only runs when it is true, like 35 or more is a heat wave, otherwise it is not hot",
         "it only runs when true so 35 or more is hot and otherwise not"],
        ["it only runs when true, 35 or more counts as a heat wave, otherwise not, and a day can be hot and rainy both at the same time",
         "if only runs when true, equal to 35 counts, otherwise no, and two rules can both fit the same day"],
    ],
    "loops": [
        ["i dont get it", "loops are like circles"],
        ["you do the same step again and again for each day", "it will repeat the step over and over"],
        ["it repeats for each day and keeps a total, you add the rain each time", "do it again each day and add up the total"],
        ["repeat for each day, keep a running total, remember the biggest day, and start at zero so an empty list works",
         "it goes again for every day, adds up the total so far, and remember the highest one"],
    ],
    "functions": [
        ["i dont know what it is", "not sure at all"],
        ["a helper has a name and you can use it again", "you give steps one name and reuse it over and over"],
        ["a helper has a name, you give it a number and it gives back an answer", "it takes an input and returns an output you can use again"],
        ["helpers can team up, one helper hands its answer to the next helper in order", "a helper has a name, takes input, gives back output and you combine each helper in order"],
    ],
}

PROFILES: Dict[str, Dict[str, int]] = {
    "strong": {"database_retrieval": 3, "conditionals": 3, "loops": 3, "functions": 3},
    "middle": {"database_retrieval": 2, "conditionals": 2, "loops": 1, "functions": 1},
    "mixed": {"database_retrieval": 3, "conditionals": 1, "loops": 2, "functions": 0},
    "struggling": {"database_retrieval": 1, "conditionals": 0, "loops": 0, "functions": 0},
    "guesser": {"database_retrieval": 0, "conditionals": 0, "loops": 0, "functions": 0},
}


@dataclass
class SimStudent:
    sim_id: str
    latent: Dict[str, int]
    style: str = "standard"
    goal: str = "not_sure"
    seed: int = 0
    explains: bool = True
    notes: Dict[str, Any] = field(default_factory=dict)

    def rng(self, *parts: Any) -> random.Random:
        return random.Random(":".join([str(self.seed), self.sim_id, *map(str, parts)]))


def make_cohort(content: Content, n: int, seed: int = 2026) -> List[SimStudent]:
    """A balanced, repeatable group: most start low, styles take turns."""
    rng = random.Random(seed)
    concepts = content.concepts()
    goals = list(content.goals)
    cohort = []
    for index in range(n):
        base = rng.choices([0, 1, 2, 3], weights=[0.25, 0.35, 0.25, 0.15])[0]
        latent = {c: min(3, max(0, base + rng.choice([-1, 0, 0, 1]))) for c in concepts}
        cohort.append(SimStudent(f"{SIM_PREFIX}{index + 1:03d}", latent, STYLES[index % len(STYLES)],
                                 goals[index % len(goals)], seed))
    return cohort


def profile_student(name: str, seed: int = 7, style: str = "standard", goal: str = "weather_report") -> SimStudent:
    return SimStudent(f"{SIM_PREFIX}{name}", dict(PROFILES[name]), style, goal, seed)


# Writing style ------------------------------------------------------------------------------

def _typo(word: str, rng: random.Random) -> str:
    if len(word) < 4:
        return word
    i = rng.randrange(1, len(word) - 2)
    return word[:i] + word[i + 1] + word[i] + word[i + 2:]


def apply_style(text: str, style: str, rng: random.Random) -> str:
    if style == "terse":
        return text.lower().replace(",", "")
    if style == "informal":
        return " ".join(_typo(w, rng) if rng.random() < 0.08 else w for w in text.split())
    if style == "esl":
        return " ".join(w for w in text.split() if w not in ("the", "a"))
    return text


def explanation(student: SimStudent, concept: str) -> str:
    rng = student.rng("explain", concept)
    stage = student.latent[concept]
    variants = EXPLAIN_BANK[concept][stage]
    return apply_style(rng.choice(variants), student.style, rng)


# Answers ----------------------------------------------------------------------------------------

def _wrong(item: Item, rng: random.Random) -> Any:
    if item.type in CHOICE_LIKE:
        return rng.choice([o.id for o in item.options if o.id != item.answer])
    if item.type == ORDER:
        order = list(item.answer)
        i = rng.randrange(len(order) - 1)
        order[i], order[i + 1] = order[i + 1], order[i]
        return order
    response = dict(item.answer)
    flip = rng.choice(sorted(response))
    other = [b.id for b in item.buckets if b.id != response[flip]]
    response[flip] = rng.choice(other)
    return response


def respond(student: SimStudent, item: Item, step_number: int) -> Any:
    rng = student.rng("item", item.id, step_number)
    able = item.concept is None or item.tier <= student.latent.get(item.concept, 0)
    p_pass = PASS_WHEN_ABLE if able else item.guess_chance
    return item.answer if rng.random() < p_pass else _wrong(item, rng)


# Play ----------------------------------------------------------------------------------------------

def play(engine: DiagnosticEngine, student: SimStudent, max_steps: int = 60) -> Dict[str, Any]:
    """Drive a whole quest through the engine API. Returns the student id and both views."""
    start = engine.start(buddy="cloud", goal=student.goal)
    student_id = start["student_id"]
    step = start["first"]
    steps = 0
    while not step.get("done"):
        steps += 1
        if steps > max_steps:
            raise RuntimeError("simulated quest did not finish")
        view = step["step"]
        if view["kind"] == "explain":
            concept = next(c for c, p in engine.content.explain.items() if p.id == view["id"])
            response: Any = {"text": explanation(student, concept)} if student.explains else {"skip": True}
        else:
            item = engine.content.items.get(view["id"]) or next(b for b in engine.content.boosters if b.id == view["id"])
            response = respond(student, item, steps)
        engine.answer(student_id, response, elapsed_ms=rng_ms(student, steps))
        step = engine.next(student_id)
    return {"student_id": student_id, "student_view": step, "report": engine.teacher_report(student_id), "steps": steps}


def rng_ms(student: SimStudent, step_number: int) -> int:
    return int(student.rng("ms", step_number).uniform(4000, 22000))
