"""Agreement metrics for E01 / E02 / E11. Pure Python, no dependencies."""
from __future__ import annotations

from collections import Counter

STAGES = (0, 1, 2, 3)


def _pairs(gold: list, pred: list) -> list[tuple[int, int]]:
    return [(g, p) for g, p in zip(gold, pred) if g is not None and p is not None]


def confusion_matrix(gold: list, pred: list) -> list[list[int]]:
    """Rows = gold (human / target) stage, columns = predicted stage."""
    m = [[0] * len(STAGES) for _ in STAGES]
    for g, p in _pairs(gold, pred):
        m[g][p] += 1
    return m


def exact_agreement(gold: list, pred: list) -> float | None:
    pairs = _pairs(gold, pred)
    return round(sum(g == p for g, p in pairs) / len(pairs), 3) if pairs else None


def adjacent_agreement(gold: list, pred: list) -> float | None:
    """Share of pairs within one stage of each other."""
    pairs = _pairs(gold, pred)
    return round(sum(abs(g - p) <= 1 for g, p in pairs) / len(pairs), 3) if pairs else None


def quadratic_weighted_kappa(gold: list, pred: list) -> float | None:
    pairs = _pairs(gold, pred)
    if not pairs:
        return None
    k = len(STAGES)
    n = len(pairs)
    obs = confusion_matrix([g for g, _ in pairs], [p for _, p in pairs])
    hist_g = Counter(g for g, _ in pairs)
    hist_p = Counter(p for _, p in pairs)
    num = den = 0.0
    for i in STAGES:
        for j in STAGES:
            w = (i - j) ** 2 / (k - 1) ** 2
            expected = hist_g[i] * hist_p[j] / n
            num += w * obs[i][j]
            den += w * expected
    if den == 0:
        return 1.0 if num == 0 else 0.0
    return round(1 - num / den, 3)


def repeat_stability(runs: list[list]) -> float | None:
    """E02: share of items whose stage is identical across all repeated runs."""
    if not runs or len(runs) < 2:
        return None
    items = list(zip(*runs))
    scored = [it for it in items if all(v is not None for v in it)]
    if not scored:
        return None
    return round(sum(len(set(it)) == 1 for it in scored) / len(scored), 3)


def summarize(gold: list, pred: list) -> dict:
    return {
        "n": len(_pairs(gold, pred)),
        "exact": exact_agreement(gold, pred),
        "adjacent": adjacent_agreement(gold, pred),
        "qwk": quadratic_weighted_kappa(gold, pred),
        "confusion": confusion_matrix(gold, pred),
    }
