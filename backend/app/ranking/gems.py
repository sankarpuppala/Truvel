"""Hidden gems (SPEC §9.2).

A gem is a place people who went liked, that the internet has not already
decided is famous. So: take the Wilson lower bound and multiply it by how
*unfamous* the place is.

    gem = wilson_lb(likes, viewers) x {hidden 1.0, known 0.7, famous 0.3}[fame]

Golconda Fort has a great like rate and 40 Wikipedia sitelinks, so its 0.3
weight pushes it below a quiet ridge that locals rate just as highly. Only
verified, non-fragile places with at least one verified visit are eligible:
nobody should be sent down a footpath on the strength of one unchecked post,
and fragile places are kept off every discovery surface (SPEC §8.14).
"""
from __future__ import annotations

from ..config import cfg
from .wilson import wilson_lb


def fame_weight(fame: str) -> float:
    """The multiplier for a fame bucket, from `ranking.hidden_weight`."""
    weights = cfg("ranking.hidden_weight", {}) or {}
    return float(weights.get(fame, weights.get("known", 0.7)))


def gem_score(likes: int, viewers: int, fame: str) -> float:
    """Hidden-gem score. Higher is gemmier."""
    return wilson_lb(likes, viewers) * fame_weight(fame)


def is_gem_eligible(
    status: str,
    fragile: bool,
    verified_visits: int,
) -> bool:
    """Whether a place may appear in the Hidden gems sort at all (SPEC §9.2)."""
    return status == "verified" and not fragile and verified_visits >= 1
