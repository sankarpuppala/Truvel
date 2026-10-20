"""Watch feed ranking (SPEC §9.5).

    score = 0.35*quality + 0.20*prox + 0.20*pref + 0.15*fresh + 0.10*following

quality   percentile of wilson_lb(completions, engaged_views) among candidates
prox      exp(-d / 25 km)
pref      the same CategoryPref Beta draw the deck uses (SPEC §9.4)
fresh     exp(-age_days / 5), so a week-old video still shows but fades
following 1 if the viewer follows the creator

Quality is completion rate, not like count: a video that people watch to the end
told them something useful about getting to the place. Freshness decays smoothly
here (unlike the deck's step) because a video feed goes stale fast.

Two re-rank rules stop the feed collapsing into one person or one category:
at most 2 in a row from one creator, at most 3 in a row from one category.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime

from ..config import cfg
from ..deck.thompson import draw_all
from ..ranking.diversity import rearrange
from ..ranking.wilson import percentile_rank, wilson_lb


@dataclass
class VideoCandidate:
    media_id: int
    creator_id: int
    place_id: int
    category: str
    distance_km: float
    engaged_views: int
    completions: int
    created_at: datetime
    following: bool = False
    fragile: bool = False
    risky: bool = False          # steep_edge / water_danger: no boost (SPEC §8.14)
    score: float = 0.0
    parts: dict[str, float] = field(default_factory=dict)


def proximity(distance_km: float, tau_km: float | None = None) -> float:
    if tau_km is None:
        tau_km = float(cfg("watch.prox_tau_km", 25))
    return math.exp(-max(0.0, distance_km) / max(1e-9, tau_km))


def freshness(created_at: datetime, now: datetime, tau_days: float | None = None) -> float:
    """exp(-age/tau): 1.0 today, ~0.82 after a day, ~0.37 after 5 days."""
    if tau_days is None:
        tau_days = float(cfg("watch.fresh_tau_days", 5))
    age = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return math.exp(-age / max(1e-9, tau_days))


def score_videos(
    candidates: list[VideoCandidate],
    prefs: dict[str, tuple[float, float]],
    now: datetime,
    rng: random.Random,
) -> list[VideoCandidate]:
    """Score and sort Watch candidates, best first."""
    if not candidates:
        return []

    w = cfg("watch.weights", {}) or {}
    w_quality = float(w.get("quality", 0.35))
    w_prox = float(w.get("prox", 0.20))
    w_pref = float(w.get("pref", 0.20))
    w_fresh = float(w.get("fresh", 0.15))
    w_follow = float(w.get("following", 0.10))

    categories = {c.category for c in candidates}
    thetas = draw_all({c: prefs.get(c, (1.0, 1.0)) for c in categories}, rng)

    quals = [wilson_lb(c.completions, c.engaged_views) for c in candidates]
    for cand, qual in zip(candidates, quals):
        quality = percentile_rank(qual, quals)
        prox = proximity(cand.distance_km)
        pref = thetas.get(cand.category, 0.5)
        fresh = freshness(cand.created_at, now)
        follow = 1.0 if cand.following else 0.0
        cand.parts = {
            "quality": quality,
            "prox": prox,
            "pref": pref,
            "fresh": fresh,
            "following": follow,
            "wilson": qual,
        }
        cand.score = (
            w_quality * quality
            + w_prox * prox
            + w_pref * pref
            + w_fresh * fresh
            + w_follow * follow
        )
        # Nothing rewards risky content (SPEC §8.14): a video of a cliff edge or
        # dangerous water keeps its place in the feed but gets no ranking boost.
        if cand.risky:
            cand.score = min(cand.score, w_quality * quality + w_prox * prox)
    return sorted(candidates, key=lambda c: (-c.score, c.media_id))


def diversify(
    ranked: list[VideoCandidate],
    max_creator_run: int | None = None,
    max_category_run: int | None = None,
) -> list[VideoCandidate]:
    """At most N in a row from one creator and M in a row from one category.

    Creator is the primary constraint, because seeing the same person three
    times running is far more noticeable than seeing three waterfalls. The
    category limit rides along as a secondary filter (see
    `app.ranking.diversity.rearrange`).
    """
    if max_creator_run is None:
        max_creator_run = int(cfg("watch.max_same_creator_run", 2))
    if max_category_run is None:
        max_category_run = int(cfg("watch.max_same_category_run", 3))

    def category_blocked(
        candidate: VideoCandidate, placed: list[VideoCandidate]
    ) -> bool:
        run = 0
        for previous in reversed(placed):
            if previous.category != candidate.category:
                break
            run += 1
        return run >= max_category_run

    return rearrange(
        ranked,
        key=lambda c: c.creator_id,
        max_run=max_creator_run,
        blocked=category_blocked,
    )


def watch_rng(user_id: int, day: str, cursor: int) -> random.Random:
    """Seeded RNG so the Watch order is reproducible in tests (AC-11)."""
    return random.Random(f"watch:{user_id}:{day}:{cursor}")
