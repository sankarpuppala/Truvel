"""The kadam ledger (SPEC §10.1).

Kadam (क़दम, "steps") are points, not money. There is deliberately **no balance
column** on `User`: a balance is always `sum(KadamEntry.delta)`. Every change
goes through `award()` or `reverse()` (CLAUDE.md invariant 4), which means the
answer to "why do I have 340 kadam?" is always a list of rows with reasons --
and a bug can never silently create points.

Rules and caps, all from `config.yaml`:

| reason        | kadam | cap                                  |
|---------------|-------|--------------------------------------|
| discovery     | +50   | once per place                       |
| visit_caused  | +10   | 20 per place per day                 |
| like_received | +1    | 50 per day                           |
| own_visit     | +5    | once per place                       |
| steps_helpful | +2    | 20 per day                           |
| pulse         | +3    | 5 per day                            |
| weekly_trail  | +50   | once per week (Tier 2)               |

The caps count **events**, not kadam: "pulse, 5 per day" means five reports a
day, which is 15 kadam, and "steps_helpful, 20 per day" means twenty helpful
votes, which is 40. So a cap is converted to kadam by multiplying by the
reason's own rate, and usage is measured the same way.

New accounts (< 24 h) earn nothing from likes given or received (SPEC §9.8), and
nobody ever earns from their own likes, visits or views.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, func, select

from .config import cfg
from .models import KadamEntry, User, utcnow

# Reasons are a closed set: a typo should fail loudly, not create a new category.
DISCOVERY = "discovery"
VISIT_CAUSED = "visit_caused"
LIKE_RECEIVED = "like_received"
OWN_VISIT = "own_visit"
STEPS_HELPFUL = "steps_helpful"
PULSE = "pulse"
WEEKLY_TRAIL = "weekly_trail"
REVERSAL = "reversal"

REASONS = {
    DISCOVERY,
    VISIT_CAUSED,
    LIKE_RECEIVED,
    OWN_VISIT,
    STEPS_HELPFUL,
    PULSE,
    WEEKLY_TRAIL,
    REVERSAL,
}

# Caps that are "once per <thing>" rather than "N per day".
ONCE_PER_REF = {DISCOVERY, OWN_VISIT}

DAILY_CAPS = {
    LIKE_RECEIVED: "kadam.like_received_daily_cap",
    STEPS_HELPFUL: "kadam.steps_helpful_daily_cap",
    PULSE: "kadam.pulse_daily_cap",
}


def amount_for(reason: str) -> int:
    """The configured kadam for a reason."""
    return int(cfg(f"kadam.{reason}", 0))


def balance(session: Session, user_id: int) -> int:
    """The user's balance: the sum of the ledger, computed not stored."""
    total = session.exec(
        select(func.coalesce(func.sum(KadamEntry.delta), 0)).where(
            KadamEntry.user_id == user_id
        )
    ).one()
    return int(total or 0)


def level(balance_value: int) -> tuple[str, str | None, int, int]:
    """(current level, next level, floor of current, floor of next).

    Levels from config: Wanderer 0, Pathfinder 200, Trailblazer 800,
    Local Legend 2500. At the top, `next` is None.
    """
    levels = cfg("kadam.levels", {}) or {}
    ordered = sorted(levels.items(), key=lambda kv: kv[1])
    current, current_floor = ordered[0][0], int(ordered[0][1])
    next_name, next_floor = None, int(ordered[-1][1])
    for name, floor in ordered:
        if balance_value >= int(floor):
            current, current_floor = name, int(floor)
        else:
            next_name, next_floor = name, int(floor)
            break
    return (current, next_name, current_floor, next_floor)


def _day_window(now: datetime) -> tuple[datetime, datetime]:
    """The UTC day containing `now`. Caps are per calendar day."""
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (start, start + timedelta(days=1))


def earned_today(session: Session, user_id: int, reason: str, now: datetime) -> int:
    """Kadam already earned today for a reason, for the daily caps."""
    start, end = _day_window(now)
    total = session.exec(
        select(func.coalesce(func.sum(KadamEntry.delta), 0)).where(
            KadamEntry.user_id == user_id,
            KadamEntry.reason == reason,
            KadamEntry.at >= start,
            KadamEntry.at < end,
            KadamEntry.delta > 0,
        )
    ).one()
    return int(total or 0)


def earned_for_ref(
    session: Session, user_id: int, reason: str, ref_type: str | None, ref_id: int | None
) -> int:
    """Kadam already earned for one specific thing (the once-per-X caps)."""
    total = session.exec(
        select(func.coalesce(func.sum(KadamEntry.delta), 0)).where(
            KadamEntry.user_id == user_id,
            KadamEntry.reason == reason,
            KadamEntry.ref_type == ref_type,
            KadamEntry.ref_id == ref_id,
            KadamEntry.delta > 0,
        )
    ).one()
    return int(total or 0)


def earned_for_ref_today(
    session: Session,
    user_id: int,
    reason: str,
    ref_type: str | None,
    ref_id: int | None,
    now: datetime,
) -> int:
    """Kadam earned for one thing today -- the visit_caused per-place-per-day cap."""
    start, end = _day_window(now)
    total = session.exec(
        select(func.coalesce(func.sum(KadamEntry.delta), 0)).where(
            KadamEntry.user_id == user_id,
            KadamEntry.reason == reason,
            KadamEntry.ref_type == ref_type,
            KadamEntry.ref_id == ref_id,
            KadamEntry.at >= start,
            KadamEntry.at < end,
            KadamEntry.delta > 0,
        )
    ).one()
    return int(total or 0)


def allowed_amount(
    session: Session,
    user_id: int,
    reason: str,
    ref_type: str | None,
    ref_id: int | None,
    now: datetime,
    requested: int,
) -> int:
    """How much of `requested` the caps actually allow. May be 0.

    Caps are event counts, so both the cap and the kadam already earned are
    converted into kadam at the reason's own rate before comparing.
    """
    if requested <= 0:
        return 0

    if reason in ONCE_PER_REF:
        if earned_for_ref(session, user_id, reason, ref_type, ref_id) > 0:
            return 0
        return requested

    rate = max(1, amount_for(reason))        # kadam per event

    if reason == VISIT_CAUSED:
        cap_events = int(cfg("kadam.visit_caused_daily_cap_per_place", 20))
        used = earned_for_ref_today(session, user_id, reason, ref_type, ref_id, now)
        return max(0, min(requested, cap_events * rate - used))

    cap_key = DAILY_CAPS.get(reason)
    if cap_key:
        cap_events = int(cfg(cap_key, 0))
        used = earned_today(session, user_id, reason, now)
        return max(0, min(requested, cap_events * rate - used))

    return requested


def award(
    session: Session,
    user_id: int,
    reason: str,
    *,
    ref_type: str | None = None,
    ref_id: int | None = None,
    amount: int | None = None,
    now: datetime | None = None,
    commit: bool = True,
) -> int:
    """Award kadam, respecting every cap. Returns what was actually awarded.

    The only way kadam is ever created. Returning the awarded amount (0 when a
    cap is hit) lets callers show an honest toast.
    """
    if reason not in REASONS:
        raise ValueError(f"unknown kadam reason: {reason}")
    # The official account publishes places; it is not a person who found them,
    # so it earns nothing (invariant 3: no shortcut that pays kadam).
    holder = session.get(User, user_id)
    if holder is not None and holder.official:
        return 0
    now = now or utcnow()
    requested = amount_for(reason) if amount is None else int(amount)

    # New accounts earn nothing from likes (SPEC §9.8).
    if reason == LIKE_RECEIVED:
        user = session.get(User, user_id)
        if user is not None:
            hours = float(cfg("kadam.new_account_hours", 24))
            if (now - user.created_at) < timedelta(hours=hours):
                return 0

    granted = allowed_amount(session, user_id, reason, ref_type, ref_id, now, requested)
    if granted <= 0:
        return 0

    session.add(
        KadamEntry(
            user_id=user_id,
            delta=granted,
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
            at=now,
        )
    )
    if commit:
        session.commit()
    return granted


def reverse(
    session: Session,
    user_id: int,
    *,
    ref_type: str | None,
    ref_id: int | None,
    reason: str | None = None,
    now: datetime | None = None,
    commit: bool = True,
) -> int:
    """Undo kadam earned for one thing (removed content -- SPEC §8.13).

    Writes a negative entry rather than deleting the original, so the ledger
    still explains the history. Returns the (negative) delta written.
    """
    now = now or utcnow()
    query = select(func.coalesce(func.sum(KadamEntry.delta), 0)).where(
        KadamEntry.user_id == user_id,
        KadamEntry.ref_type == ref_type,
        KadamEntry.ref_id == ref_id,
    )
    if reason:
        query = query.where(KadamEntry.reason == reason)
    earned = int(session.exec(query).one() or 0)
    if earned <= 0:
        return 0

    session.add(
        KadamEntry(
            user_id=user_id,
            delta=-earned,
            reason=REVERSAL,
            ref_type=ref_type,
            ref_id=ref_id,
            at=now,
        )
    )
    if commit:
        session.commit()
    return -earned


def ledger(session: Session, user_id: int, limit: int = 50) -> list[KadamEntry]:
    """The user's ledger, newest first -- the Kadam tab in the passport."""
    return list(
        session.exec(
            select(KadamEntry)
            .where(KadamEntry.user_id == user_id)
            .order_by(KadamEntry.at.desc(), KadamEntry.id.desc())
            .limit(limit)
        ).all()
    )
