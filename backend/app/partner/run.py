"""The monthly Partner run (SPEC §10.3, AC-18).

`run_month(session, "2026-10")` measures every creator's month from the
database, applies the §9.10 filters and the velocity hold, decides eligibility
per §10.4, splits the simulated pool, and writes one `EarningLine` per creator.

Earnings exist **only** as EarningLine rows written here (CLAUDE.md invariant
4). Re-running a month replaces that month's lines rather than adding to them,
so the run is idempotent and a mistake can be corrected by running it again.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta

from sqlmodel import Session, func, select

from ..config import cfg
from ..models import (
    Attribution,
    EarningLine,
    EarningPeriod,
    LastMileStep,
    LastMileVote,
    Media,
    MediaView,
    Place,
    Pulse,
    User,
    Visit,
    utcnow,
)
from .eligibility import EligibilityInput, is_eligible
from .invalid import velocity_hold
from .split import CreatorMonth, demo_pool_paise, remainder_paise, split_pool


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """(start, end) datetimes for a 'YYYY-MM' string."""
    year, mon = (int(x) for x in month.split("-"))
    start = datetime(year, mon, 1)
    last_day = calendar.monthrange(year, mon)[1]
    end = datetime(year, mon, last_day) + timedelta(days=1)
    return (start, end)


def creator_ids(session: Session) -> set[int]:
    """Everyone who has content: uploaders and place finders."""
    ids = {
        int(uid)
        for uid in session.exec(
            select(Media.user_id).where(Media.user_id != None, Media.status == "ok")  # noqa: E711
        ).all()
    }
    ids |= {
        int(uid)
        for uid in session.exec(
            select(Place.added_by).where(Place.added_by != None)  # noqa: E711
        ).all()
    }
    # The official account publishes places; it is not a creator and earns nothing.
    ids -= {int(u) for u in session.exec(select(User.id).where(User.official == True)).all()}  # noqa: E712
    return ids


def _hourly_counts(
    session: Session, media_id: int, start: datetime, end: datetime
) -> dict[datetime, int]:
    """Engaged views per hour for one item, for the velocity check."""
    rows = session.exec(
        select(MediaView.started_at).where(
            MediaView.media_id == media_id,
            MediaView.engaged == True,  # noqa: E712
            MediaView.invalid_reason == None,  # noqa: E711
            MediaView.started_at >= start,
            MediaView.started_at < end,
        )
    ).all()
    buckets: dict[datetime, int] = {}
    for at in rows:
        hour = at.replace(minute=0, second=0, microsecond=0)
        buckets[hour] = buckets.get(hour, 0) + 1
    return buckets


def engaged_views_after_hold(
    session: Session, media_id: int, start: datetime, end: datetime
) -> tuple[int, int]:
    """(counted, held) engaged views for an item in the month (SPEC §9.10).

    Each hour is compared with the item's own trailing 7 days of hourly counts.
    """
    buckets = _hourly_counts(session, media_id, start - timedelta(days=7), end)
    counted = held = 0
    for hour, views in sorted(buckets.items()):
        if hour < start:
            continue                       # trailing history only, not this month
        trailing_start = hour - timedelta(days=7)
        trailing = [
            float(v) for h, v in buckets.items() if trailing_start <= h < hour
        ]
        verdict = velocity_hold(views, trailing)
        counted += verdict.counted
        held += verdict.held
    return (counted, held)


def measure_creator(
    session: Session, creator_id: int, start: datetime, end: datetime, now: datetime
) -> tuple[CreatorMonth, int]:
    """One creator's month. Returns the row and how many views were held."""
    media = list(
        session.exec(
            select(Media).where(Media.user_id == creator_id, Media.status == "ok")
        ).all()
    )

    engaged = 0
    held_total = 0
    for item in media:
        counted, held = engaged_views_after_hold(session, int(item.id), start, end)
        engaged += counted
        held_total += held

    # Visits caused: verified, unflagged, non-simulated visits only (AC-25).
    caused = float(
        session.exec(
            select(func.coalesce(func.sum(Attribution.share), 0.0))
            .join(Visit, Visit.id == Attribution.visit_id)
            .where(
                Attribution.creator_id == creator_id,
                Visit.at >= start,
                Visit.at < end,
                Visit.verified == True,  # noqa: E712
                Visit.flag == None,  # noqa: E711
                Visit.simulated == False,  # noqa: E712
            )
        ).one()
        or 0.0
    )

    groups = [
        g
        for g in session.exec(
            select(LastMileStep.version_group).where(LastMileStep.author_id == creator_id)
        ).all()
    ]
    helpful = 0
    if groups:
        helpful = int(
            session.exec(
                select(func.count())
                .select_from(LastMileVote)
                .where(
                    LastMileVote.version_group.in_(groups),
                    LastMileVote.helpful == True,  # noqa: E712
                    LastMileVote.at >= start,
                    LastMileVote.at < end,
                )
            ).one()
            or 0
        )

    window_h = float(cfg("pulse.recent_hours", 48))
    confirmed = 0
    for report in session.exec(
        select(Pulse).where(Pulse.user_id == creator_id, Pulse.at >= start, Pulse.at < end)
    ).all():
        later = session.exec(
            select(Pulse.id)
            .where(
                Pulse.place_id == report.place_id,
                Pulse.user_id != creator_id,
                Pulse.at > report.at,
                Pulse.at <= report.at + timedelta(hours=window_h),
            )
            .limit(1)
        ).first()
        if later is not None:
            confirmed += 1

    user = session.get(User, creator_id)
    eligible = False
    if user is not None:
        since_90 = end - timedelta(days=90)
        verified_places = int(
            session.exec(
                select(func.count())
                .select_from(Place)
                .where(Place.added_by == creator_id, Place.status == "verified")
            ).one()
            or 0
        )
        verified_media = int(
            session.exec(
                select(func.count())
                .select_from(Media)
                .join(Place, Place.id == Media.place_id)
                .where(
                    Media.user_id == creator_id,
                    Media.status == "ok",
                    Place.status == "verified",
                )
            ).one()
            or 0
        )
        views_90 = 0
        if media:
            views_90 = int(
                session.exec(
                    select(func.count())
                    .select_from(MediaView)
                    .where(
                        MediaView.media_id.in_([int(m.id) for m in media]),
                        MediaView.engaged == True,  # noqa: E712
                        MediaView.invalid_reason == None,  # noqa: E711
                        MediaView.started_at >= since_90,
                    )
                ).one()
                or 0
            )
        caused_90 = float(
            session.exec(
                select(func.coalesce(func.sum(Attribution.share), 0.0))
                .join(Visit, Visit.id == Attribution.visit_id)
                .where(
                    Attribution.creator_id == creator_id,
                    Visit.at >= since_90,
                    Visit.verified == True,  # noqa: E712
                    Visit.flag == None,  # noqa: E711
                    Visit.simulated == False,  # noqa: E712
                )
            ).one()
            or 0.0
        )
        eligible = is_eligible(
            EligibilityInput(
                account_created_at=user.created_at,
                strikes=user.strikes,
                verified_content=verified_places + verified_media,
                visits_caused_90d=caused_90,
                engaged_views_90d=views_90,
            ),
            end,
        )

    return (
        CreatorMonth(
            creator_id=creator_id,
            engaged_views=engaged,
            visits_caused=caused,
            helpful_votes=helpful,
            pulse_confirmed=confirmed,
            eligible=eligible,
        ),
        held_total,
    )


def run_month(
    session: Session,
    month: str,
    pool_paise: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Compute and store a month's earnings. Idempotent per month."""
    now = now or utcnow()
    start, end = month_bounds(month)
    pool = demo_pool_paise() if pool_paise is None else int(pool_paise)

    rows: list[CreatorMonth] = []
    held_views = 0
    for cid in sorted(creator_ids(session)):
        row, held = measure_creator(session, cid, start, end, now)
        rows.append(row)
        held_views += held

    split_pool(rows, pool)

    period = session.exec(select(EarningPeriod).where(EarningPeriod.month == month)).first()
    if period is None:
        period = EarningPeriod(month=month, pool_paise=pool, simulated=True, status="computed")
        session.add(period)
        session.commit()
        session.refresh(period)
    else:
        period.pool_paise = pool
        period.created_at = now
        session.add(period)
        # Replace the month's lines rather than doubling them up.
        for line in session.exec(
            select(EarningLine).where(EarningLine.period_id == period.id)
        ).all():
            session.delete(line)
        session.commit()

    for row in rows:
        session.add(
            EarningLine(
                period_id=int(period.id),
                creator_id=row.creator_id,
                score=row.score,
                share=row.share,
                amount_paise=row.amount_paise,
                eligible=row.eligible,
            )
        )
    session.commit()

    return {
        "month": month,
        "simulated": True,
        "pool_paise": pool,
        "paid_paise": sum(r.amount_paise for r in rows),
        "remainder_paise": remainder_paise(rows, pool),
        "held_engaged_views": held_views,
        "creators": len(rows),
        "eligible_creators": sum(1 for r in rows if r.eligible),
        "lines": [
            {
                "creator_id": r.creator_id,
                "score": round(r.score, 3),
                "share": round(r.share, 6),
                "amount_paise": r.amount_paise,
                "eligible": r.eligible,
                "engaged_views": r.engaged_views,
                "visits_caused": round(r.visits_caused, 3),
                "helpful_votes": r.helpful_votes,
                "pulse_confirmed": r.pulse_confirmed,
            }
            for r in sorted(rows, key=lambda r: -r.amount_paise)
        ],
    }
