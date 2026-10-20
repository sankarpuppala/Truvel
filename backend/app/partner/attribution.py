"""Visit attribution: who caused this visit? (SPEC §9.9)

This is the heart of the Partner Program. When someone makes their **first**
verified, unflagged, non-simulated visit to a place, we look back 30 days at
everything they saw about that place -- the place page, videos, last-mile steps
they actually read, deck saves -- and split one whole visit between the creators
of those touches.

Each touch is weighted `w = 2^(-age_days / 7)` and the weights are normalised so
the shares sum to exactly 1. Why time-decay rather than last-touch? The video
watched the night before probably mattered most, but the one three weeks ago is
why the place was on their mind at all. Last-touch gives that earlier creator
nothing; linear gives a touch from three weeks ago the same credit as last
night. Time-decay sits between the two, and §17 item 3 measures all three
against a known ground-truth influence model.

Touches by the visitor themselves are dropped (no self-dealing), as are touches
marked invalid by §9.10. No touches at all means the visit was organic and
nobody is credited -- we do not hand out a visit just because someone went.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..config import cfg


@dataclass
class TouchRow:
    """One thing the visitor saw, and who made it."""

    creator_id: int
    at: datetime
    content_type: str = "place"
    content_id: int | None = None
    invalid_reason: str | None = None


def touch_weight(at: datetime, visit_at: datetime, half_life_days: float | None = None) -> float:
    """2^(-age/half_life). 1.0 for a touch at the moment of the visit."""
    if half_life_days is None:
        half_life_days = float(cfg("attribution.half_life_days", 7))
    age_days = max(0.0, (visit_at - at).total_seconds() / 86400.0)
    if half_life_days <= 0:
        return 1.0
    return 2.0 ** (-age_days / half_life_days)


def eligible_touches(
    touches: list[TouchRow],
    visitor_id: int,
    visit_at: datetime,
    lookback_days: int | None = None,
) -> list[TouchRow]:
    """Keep touches inside the window, not self-made, and not invalid."""
    if lookback_days is None:
        lookback_days = int(cfg("attribution.lookback_days", 30))
    window_start = visit_at - timedelta(days=lookback_days)
    out = []
    for t in touches:
        if t.creator_id == visitor_id:
            continue                      # your own content cannot cause your visit
        if t.invalid_reason:
            continue                      # §9.10 filtered it out
        if t.at < window_start or t.at > visit_at:
            continue                      # outside the 30-day lookback
        out.append(t)
    return out


def attribute(
    touches: list[TouchRow],
    visitor_id: int,
    visit_at: datetime,
    lookback_days: int | None = None,
    half_life_days: float | None = None,
) -> dict[int, float]:
    """Shares per creator for one visit. Sums to 1.0, or empty if organic.

    Returns {creator_id: share}. Tested to 1e-9 against hand-computed values
    (AC-16).
    """
    kept = eligible_touches(touches, visitor_id, visit_at, lookback_days)
    if not kept:
        return {}

    raw: dict[int, float] = {}
    for t in kept:
        raw[t.creator_id] = raw.get(t.creator_id, 0.0) + touch_weight(
            t.at, visit_at, half_life_days
        )

    total = sum(raw.values())
    if total <= 0:
        return {}
    return {creator: w / total for creator, w in raw.items()}


# --------------------------------------------------------------------------- #
# The two alternatives, for the simulation in SPEC §17 item 3
# --------------------------------------------------------------------------- #

def attribute_last_touch(
    touches: list[TouchRow],
    visitor_id: int,
    visit_at: datetime,
    lookback_days: int | None = None,
) -> dict[int, float]:
    """All credit to the most recent touch. The industry default, for comparison."""
    kept = eligible_touches(touches, visitor_id, visit_at, lookback_days)
    if not kept:
        return {}
    last = max(kept, key=lambda t: t.at)
    return {last.creator_id: 1.0}


def attribute_linear(
    touches: list[TouchRow],
    visitor_id: int,
    visit_at: datetime,
    lookback_days: int | None = None,
) -> dict[int, float]:
    """Every touch counts the same, regardless of when it happened."""
    kept = eligible_touches(touches, visitor_id, visit_at, lookback_days)
    if not kept:
        return {}
    share = 1.0 / len(kept)
    out: dict[int, float] = {}
    for t in kept:
        out[t.creator_id] = out.get(t.creator_id, 0.0) + share
    return out
