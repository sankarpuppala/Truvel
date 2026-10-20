"""Top: the Wilson score lower bound (SPEC §9.1).

Why not just likes / viewers? Because a place seen by 2 people and liked by both
would beat a place seen by 2,000 and liked by 1,600, and that is not what anyone
means by "the best places in this city".

The Wilson interval asks a different question: given k likes out of n viewers,
what is the *lowest* like rate we can still believe at 95 % confidence? A small
sample is punished because we genuinely do not know much about it yet, and the
score climbs towards the raw ratio as n grows. z = 1.96 is the 95 % normal
quantile and lives in config.yaml as `ranking.wilson_z`.
"""
from __future__ import annotations

import math

from ..config import cfg


def wilson_lb(k: int, n: int, z: float | None = None) -> float:
    """Lower bound of the 95 % Wilson interval for k likes from n viewers.

    Returns 0.0 for n = 0: a place nobody has seen gets no credit, and this
    keeps the function total so callers never special-case it.

    Test values from SPEC §9.1: (0,0)=0, (1,1)~0.2065, (80,100)~0.7112,
    (8,10)~0.4902.
    """
    if n <= 0:
        return 0.0
    k = max(0, min(k, n))                      # likes can never exceed viewers
    if z is None:
        z = float(cfg("ranking.wilson_z", 1.96))
    p = k / n
    z2 = z * z
    centre = p + z2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return (centre - margin) / (1 + z2 / n)


def percentile_rank(value: float, population: list[float]) -> float:
    """Where `value` sits in `population`, as a number in [0, 1].

    The deck and Watch both need "how good is this compared with the other
    candidates" rather than a raw score, because a raw Wilson bound is not
    comparable across cities with different like volumes (SPEC §9.4, §9.5).
    A population of one scores 1.0 -- it is the best of what there is.
    """
    if not population:
        return 0.0
    if len(population) == 1:
        return 1.0
    below = sum(1 for v in population if v < value)
    equal = sum(1 for v in population if v == value)
    # Mid-rank for ties, so identical candidates get identical scores.
    return (below + 0.5 * equal) / len(population)
