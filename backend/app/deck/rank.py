"""Nearby deck scoring and diversity re-rank (SPEC §9.4).

    score = 0.40*q + 0.25*prox + 0.25*pref + 0.10*fresh

q      percentile rank of the place's Wilson bound among the candidates
prox   exp(-d_km / 4): a place 4 km away scores ~0.37, 1 km ~0.78, 25 km ~0.002
pref   theta drawn from the user's Beta belief for the category (Thompson)
fresh  1 if added in the last 14 days or seen by fewer than 10 people, else 0

The weights say what the deck is for: mostly "is it good" and "can I get there",
a quarter "is it my kind of thing", and a tenth reserved for new places so a
good find is not invisible until it happens to collect viewers.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime

from ..config import cfg
from ..ranking.diversity import rearrange
from ..ranking.wilson import percentile_rank, wilson_lb
from .thompson import draw_all


@dataclass
class Candidate:
    """One place in the running, with everything scoring needs and nothing else."""

    place_id: int
    category: str
    distance_km: float
    likes: int
    viewers: int
    created_at: datetime
    status: str = "verified"
    score: float = 0.0
    parts: dict[str, float] = field(default_factory=dict)


def proximity(distance_km: float, tau_km: float | None = None) -> float:
    """exp(-d / tau). Smooth, so there is no cliff at the radius edge."""
    if tau_km is None:
        tau_km = float(cfg("deck.prox_tau_km", 4))
    return math.exp(-max(0.0, distance_km) / max(1e-9, tau_km))


def freshness(created_at: datetime, viewers: int, now: datetime) -> float:
    """1.0 for a new or barely-seen place, else 0.0 (SPEC §9.4).

    Deliberately a step, not a decay: this is a fixed 10 % budget for things the
    ranking cannot know about yet, and a step is easier to explain and to test.
    """
    fresh_days = float(cfg("deck.fresh_days", 14))
    fresh_viewers = int(cfg("deck.fresh_viewers", 10))
    age_days = (now - created_at).total_seconds() / 86400.0
    return 1.0 if (age_days <= fresh_days or viewers < fresh_viewers) else 0.0


def score_candidates(
    candidates: list[Candidate],
    prefs: dict[str, tuple[float, float]],
    now: datetime,
    rng: random.Random,
) -> list[Candidate]:
    """Score every candidate and return them sorted best first.

    `prefs` maps category -> (alpha, beta). Categories missing from `prefs` get
    the uniform prior (1, 1), which is exactly right for "never seen this type".
    """
    if not candidates:
        return []

    weights = cfg("deck.weights", {}) or {}
    w_q = float(weights.get("q", 0.40))
    w_prox = float(weights.get("prox", 0.25))
    w_pref = float(weights.get("pref", 0.25))
    w_fresh = float(weights.get("fresh", 0.10))

    # One Beta draw per category per request -- see thompson.draw_all.
    categories = {c.category for c in candidates}
    prefs_full = {cat: prefs.get(cat, (1.0, 1.0)) for cat in categories}
    thetas = draw_all(prefs_full, rng)

    wilsons = [wilson_lb(c.likes, c.viewers) for c in candidates]
    for cand, w in zip(candidates, wilsons):
        q = percentile_rank(w, wilsons)
        prox = proximity(cand.distance_km)
        pref = thetas.get(cand.category, 0.5)
        fresh = freshness(cand.created_at, cand.viewers, now)
        cand.parts = {"q": q, "prox": prox, "pref": pref, "fresh": fresh, "wilson": w}
        cand.score = w_q * q + w_prox * prox + w_pref * pref + w_fresh * fresh

    # Tie-break on place_id so a seeded deck is byte-for-byte reproducible.
    return sorted(candidates, key=lambda c: (-c.score, c.place_id))


def diversify(
    ranked: list[Candidate],
    max_run: int | None = None,
) -> list[Candidate]:
    """Re-rank so no more than `max_run` cards in a row share a category.

    The ordering logic lives in `app.ranking.diversity.rearrange`, which the
    deck and Watch share: follow the ranking except where doing so would strand
    a long run of one category at the end of the deck. Nothing is ever dropped
    -- a deck of five waterfalls beats an empty deck.
    """
    if max_run is None:
        max_run = int(cfg("deck.max_same_category_run", 2))
    return rearrange(ranked, key=lambda c: c.category, max_run=max_run)


def deck_rng(user_id: int, day: str, request_no: int) -> random.Random:
    """Seeded RNG per (user, date, request) so a deck can be reproduced (AC-10)."""
    return random.Random(f"{user_id}:{day}:{request_no}")
