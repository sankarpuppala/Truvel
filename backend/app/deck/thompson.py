"""Thompson sampling over category preferences (SPEC §9.4).

The problem: we do not know which categories a user likes, and we only learn by
showing them cards. Always showing the current favourite means we never discover
they love stepwells; showing random cards wastes their time.

Thompson sampling solves this with one line of arithmetic. Each category keeps a
Beta(alpha, beta) belief about "how often does this user save a card of this
category". We **draw** a sample from each belief and rank by the draw instead of
by the mean. A category with little data has a wide belief, so its draw is
sometimes high -- that is exploration, and it costs nothing when the category is
genuinely bad because the draw is usually low too. A category saved many times
has a narrow belief centred high, so it reliably wins -- that is exploitation.

Starting at alpha = beta = 1 is a uniform prior: we assume nothing about a new
user. Save -> alpha + 1, skip -> beta + 1, open -> no change (opening a card
says the user wanted to look, not that they wanted to go).
"""
from __future__ import annotations

import random


def draw_theta(alpha: float, beta: float, rng: random.Random) -> float:
    """One sample from Beta(alpha, beta), in [0, 1].

    `random.betavariate` is the standard library's Beta sampler; passing our own
    seeded `rng` is what makes a deck reproducible in tests (AC-10).
    """
    a = max(1e-9, float(alpha))
    b = max(1e-9, float(beta))
    return rng.betavariate(a, b)


def draw_all(prefs: dict[str, tuple[float, float]], rng: random.Random) -> dict[str, float]:
    """One theta per category, drawn once per request (SPEC §9.4).

    Once per request, not once per card: if we redrew per card the ordering
    would be noise rather than a ranking, and two cards of the same category
    could score wildly differently in the same deck.
    """
    return {cat: draw_theta(a, b, rng) for cat, (a, b) in prefs.items()}


def update(action: str, alpha: float, beta: float) -> tuple[float, float]:
    """The learning step. Returns the new (alpha, beta) for the category."""
    if action == "save":
        return alpha + 1.0, beta
    if action == "skip":
        return alpha, beta + 1.0
    return alpha, beta          # 'open' and anything unknown teach us nothing


def posterior_mean(alpha: float, beta: float) -> float:
    """alpha / (alpha + beta). Only for display -- ranking uses a draw."""
    total = alpha + beta
    return alpha / total if total > 0 else 0.5
