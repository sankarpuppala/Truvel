"""Invalid traffic filtering for earnings (SPEC §9.10).

Two layers.

**Per-view rules** live in `watch/views.py`, because the server applies them the
moment a view arrives. This module re-exports them so the Partner engine reads
one coherent story, and adds the part that can only be judged in hindsight:

**Velocity hold.** If an item's engaged views in one hour exceed
`mean + 4*sd` of its own trailing 7-day hourly counts *and* exceed 50, the
**excess only** is held for review and excluded from earnings. Not the whole
hour and not the whole item: a genuinely viral video keeps everything up to what
its own history makes plausible. The two conditions together stop a brand-new
item (whose trailing mean and sd are both ~0) from being held for its first 20
honest views.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import cfg
from ..watch.views import (  # noqa: F401  (re-exported as the §9.10 rule set)
    NEW_ACCOUNT,
    REPEAT,
    SELF_VIEW,
    SIMULATED,
    VELOCITY_HOLD,
    invalid_reason,
)


def mean_sd(values: list[float]) -> tuple[float, float]:
    """Population mean and standard deviation. Empty -> (0, 0).

    Population rather than sample sd: these are all the hours we have, not a
    sample of some larger set, and it avoids a divide-by-zero on one hour.
    """
    if not values:
        return (0.0, 0.0)
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return (mean, var**0.5)


def velocity_threshold(
    trailing_hourly: list[float],
    sd_multiple: float | None = None,
) -> float:
    """mean + k*sd of the trailing hourly counts."""
    if sd_multiple is None:
        sd_multiple = float(cfg("invalid_traffic.velocity_sd", 4))
    mean, sd = mean_sd(trailing_hourly)
    return mean + sd_multiple * sd


@dataclass
class VelocityVerdict:
    """How many of an hour's views count, and how many are held."""

    counted: int
    held: int
    threshold: float
    triggered: bool


def velocity_hold(
    hour_views: int,
    trailing_hourly: list[float],
    sd_multiple: float | None = None,
    minimum: int | None = None,
) -> VelocityVerdict:
    """Hold the excess over the trailing threshold (SPEC §9.10).

    Both conditions must hold: above `mean + k*sd` **and** above the absolute
    floor (default 50). Otherwise every view counts.
    """
    if minimum is None:
        minimum = int(cfg("invalid_traffic.velocity_min", 50))
    threshold = velocity_threshold(trailing_hourly, sd_multiple)

    if hour_views <= minimum or hour_views <= threshold:
        return VelocityVerdict(hour_views, 0, threshold, False)

    # Keep what the item's own history makes plausible, hold the rest. The floor
    # is also respected, so a held hour never counts fewer than `minimum`.
    counted = max(int(threshold), minimum)
    counted = min(counted, hour_views)
    return VelocityVerdict(counted, hour_views - counted, threshold, True)


def filter_views(views: list[dict]) -> list[dict]:
    """Keep only engaged views with no invalid reason -- what earnings may use."""
    return [v for v in views if v.get("engaged") and not v.get("invalid_reason")]
