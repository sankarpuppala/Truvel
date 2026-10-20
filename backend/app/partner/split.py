"""The monthly pool split (SPEC §10.3).

    score  = 1*engaged_views + 25*visits_caused + 5*helpful_votes_on_steps
           + 2*pulse_reports_confirmed_by_a_later_report

    amount = pool * score / sum(scores)        over eligible creators only

Money is integer **paise** everywhere and every amount is rounded **down**; the
remainder stays in the pool rather than being conjured into existence. That is
why the AC-18 test asserts the amounts sum to *at most* the pool, never more.

Why 25 for a visit: a visit is the outcome the whole app exists for, and it is
expensive to fake because you have to physically go. Views still count at 1 so a
video creator whose work sends people out next month is not shut out this month.
The number is a config value, not a law -- `partner.weights.visit_caused`.

In this version the pool is `partner.demo_pool_inr` and every rupee shown in the
UI is labelled **Simulated** (SPEC §10.5, AC-23).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import cfg

PAISE_PER_RUPEE = 100


def rupees_to_paise(rupees: float) -> int:
    """Convert a rupee figure to integer paise, rounding down."""
    return int(rupees * PAISE_PER_RUPEE)


def paise_to_rupees(paise: int) -> float:
    """For display only. Formatting happens in the frontend with en-IN grouping."""
    return paise / PAISE_PER_RUPEE


def creator_pool_paise(net_revenue_paise: int, share: float | None = None) -> int:
    """The creator pool: 55 % of net revenue by default (SPEC §10.3)."""
    if share is None:
        share = float(cfg("partner.creator_share", 0.55))
    return int(net_revenue_paise * share)


def demo_pool_paise() -> int:
    """The simulated pool for this version, from `partner.demo_pool_inr`."""
    return rupees_to_paise(float(cfg("partner.demo_pool_inr", 250000)))


@dataclass
class CreatorMonth:
    """One creator's month, after §9.10 filtering."""

    creator_id: int
    engaged_views: int = 0
    visits_caused: float = 0.0
    helpful_votes: int = 0
    pulse_confirmed: int = 0
    eligible: bool = False
    score: float = 0.0
    share: float = 0.0
    amount_paise: int = 0
    parts: dict[str, float] = field(default_factory=dict)


def score_creator(row: CreatorMonth) -> float:
    """The weighted score for one creator-month (SPEC §10.3)."""
    w = cfg("partner.weights", {}) or {}
    parts = {
        "engaged_views": float(w.get("engaged_view", 1)) * row.engaged_views,
        "visits_caused": float(w.get("visit_caused", 25)) * row.visits_caused,
        "helpful_votes": float(w.get("helpful_vote", 5)) * row.helpful_votes,
        "pulse_confirmed": float(w.get("pulse_confirmed", 2)) * row.pulse_confirmed,
    }
    row.parts = parts
    return sum(parts.values())


def split_pool(rows: list[CreatorMonth], pool_paise: int) -> list[CreatorMonth]:
    """Score everyone, then divide the pool among the eligible (SPEC §10.3).

    Ineligible creators keep their score -- the Studio shows it so they can see
    where they stand -- but get 0 paise and 0 share.
    """
    for row in rows:
        row.score = score_creator(row)

    eligible = [r for r in rows if r.eligible and r.score > 0]
    total = sum(r.score for r in eligible)

    for row in rows:
        if row not in eligible or total <= 0:
            row.share = 0.0
            row.amount_paise = 0
            continue
        row.share = row.score / total
        # Round down: never pay out more than the pool holds.
        row.amount_paise = int(pool_paise * row.score / total)
    return rows


def remainder_paise(rows: list[CreatorMonth], pool_paise: int) -> int:
    """What rounding down left in the pool. Reported, never silently dropped."""
    return pool_paise - sum(r.amount_paise for r in rows)
