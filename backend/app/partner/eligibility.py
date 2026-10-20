"""Partner Program eligibility (SPEC §10.4).

Four requirements, all from config:

1. Account at least 30 days old.
2. No active strikes.
3. At least 10 pieces of verified content -- places that reached `verified`, or
   photos/videos of verified places.
4. In the last 90 days, **either** 300 visits caused **or** 100,000 engaged
   views.

Requirement 4 is an either/or on purpose: it lets in both the creator whose
videos send a few hundred people out to real places and the one with a big
audience who is still building that track record. The thresholds exist to make
farming with fake accounts cost more than it pays (SPEC §10.6).

The Studio renders exactly this, as a checklist with progress bars, so a creator
is never guessing why they are not a Partner yet (AC-19).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..config import cfg


@dataclass
class EligibilityInput:
    """Everything the decision needs, already measured from the database."""

    account_created_at: datetime
    strikes: int
    verified_content: int
    visits_caused_90d: float
    engaged_views_90d: int


@dataclass
class Requirement:
    """One checklist line, as the Studio shows it."""

    key: str
    label: str
    met: bool
    value: float
    target: float
    note: str = ""


def account_age_days(created_at: datetime, now: datetime) -> float:
    return max(0.0, (now - created_at).total_seconds() / 86400.0)


def indian_digits(value: float) -> str:
    """Group digits the Indian way: 1,00,000 rather than 100,000 (SPEC §7.3).

    The frontend formats its own numbers with `Intl.NumberFormat('en-IN')`;
    this is for the one string the server composes itself.
    """
    whole = int(round(value))
    sign = "-" if whole < 0 else ""
    digits = str(abs(whole))
    if len(digits) <= 3:
        return sign + digits
    # The last three digits, then pairs: 1,00,00,000.
    head, tail = digits[:-3], digits[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return sign + ",".join(parts + [tail])


def check(data: EligibilityInput, now: datetime) -> list[Requirement]:
    """The four requirements, in the order the Studio lists them."""
    min_days = float(cfg("partner.min_account_days", 30))
    min_content = float(cfg("partner.min_verified_content", 10))
    min_visits = float(cfg("partner.min_visits_caused_90d", 300))
    min_views = float(cfg("partner.min_engaged_views_90d", 100000))

    age = account_age_days(data.account_created_at, now)
    reach_met = data.visits_caused_90d >= min_visits or data.engaged_views_90d >= min_views

    return [
        Requirement(
            key="account_age",
            label=f"Account {int(min_days)}+ days old",
            met=age >= min_days,
            value=age,
            target=min_days,
        ),
        Requirement(
            key="verified_content",
            label=f"{int(min_content)} verified places or videos",
            met=data.verified_content >= min_content,
            value=float(data.verified_content),
            target=min_content,
        ),
        Requirement(
            key="reach",
            label="Visits caused, last 90 days",
            met=reach_met,
            value=data.visits_caused_90d,
            target=min_visits,
            note=(
                f"or {indian_digits(int(min_views))} engaged views "
                f"({indian_digits(data.engaged_views_90d)} so far)"
            ),
        ),
        Requirement(
            key="no_strikes",
            label="No strikes",
            met=data.strikes <= 0,
            value=float(data.strikes),
            target=0.0,
        ),
    ]


def is_eligible(data: EligibilityInput, now: datetime) -> bool:
    """A creator is eligible only when every requirement is met."""
    return all(r.met for r in check(data, now))
