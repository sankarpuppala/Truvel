"""Trending: time-decayed recent activity (SPEC §9.3).

    trend = sum over events of  w * 2^(-age_days / 7)

over likes (w = 1), verified visits (w = 3) and Pulse reports (w = 1) in the
last 30 days. The half-life of 7 days means a like from yesterday counts almost
fully, one from a week ago counts half, and one from a month ago barely
registers -- so "trending" tracks this week, not all-time popularity, which is
what the Top sort is already for.

Visits weigh 3x a like because actually going somewhere is a much stronger
signal than tapping a heart.
"""
from __future__ import annotations

from datetime import datetime

from ..config import cfg


def decay(age_days: float, half_life_days: float | None = None) -> float:
    """2^(-age/half_life). 1.0 right now, 0.5 at one half-life, never negative."""
    if half_life_days is None:
        half_life_days = float(cfg("ranking.trending_half_life_days", 7))
    if half_life_days <= 0:
        return 1.0
    return 2.0 ** (-max(0.0, age_days) / half_life_days)


def age_days(at: datetime, now: datetime) -> float:
    """Event age in days (fractional). Future timestamps are treated as now."""
    return max(0.0, (now - at).total_seconds() / 86400.0)


def trending_score(
    events: list[tuple[str, datetime]],
    now: datetime,
    window_days: int | None = None,
) -> float:
    """Score a place from its recent events.

    `events` is a list of (kind, timestamp) where kind is 'like', 'visit' or
    'pulse'. Events older than the window contribute nothing; an unknown kind
    is ignored rather than guessed at.
    """
    if window_days is None:
        window_days = int(cfg("ranking.trending_window_days", 30))
    weights = cfg("ranking.trending_weights", {}) or {}
    total = 0.0
    for kind, at in events:
        w = weights.get(kind)
        if w is None:
            continue
        a = age_days(at, now)
        if a > window_days:
            continue
        total += float(w) * decay(a)
    return total
