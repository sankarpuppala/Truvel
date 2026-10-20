"""Creator Studio (SPEC §8.10).

Every number here is measured from the database -- there are no stored
aggregates to drift (AC-19). The earnings figure is an **estimate from the
simulated pool**: this creator's score as a share of all eligible creators'
scores, times `partner.demo_pool_inr`. It carries a Simulated label in the UI
and the banner is never hidden (AC-23).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import services
from ..auth import current_user
from ..config import cfg
from ..db import get_session
from ..models import (
    Attribution,
    City,
    Follow,
    LastMileStep,
    LastMileVote,
    Media,
    MediaView,
    Place,
    Pulse,
    User,
    View,
    Visit,
    utcnow,
)
from ..partner.eligibility import EligibilityInput, check
from ..partner.split import CreatorMonth, demo_pool_paise, score_creator

router = APIRouter(tags=["studio"])


def creator_media(session: DbSession, creator_id: int) -> list[Media]:
    return list(
        session.exec(
            select(Media).where(Media.user_id == creator_id, Media.status == "ok")
        ).all()
    )


def engaged_views_for(
    session: DbSession, media_ids: list[int], since: datetime | None = None
) -> int:
    """Valid engaged views only: invalid traffic never counts (SPEC §9.10)."""
    if not media_ids:
        return 0
    query = select(func.count()).select_from(MediaView).where(
        MediaView.media_id.in_(media_ids),
        MediaView.engaged == True,  # noqa: E712
        MediaView.invalid_reason == None,  # noqa: E711
    )
    if since is not None:
        query = query.where(MediaView.started_at >= since)
    return int(session.exec(query).one() or 0)


def watch_seconds(session: DbSession, media_ids: list[int], since: datetime | None = None) -> float:
    if not media_ids:
        return 0.0
    query = select(func.coalesce(func.sum(MediaView.watched_s), 0.0)).where(
        MediaView.media_id.in_(media_ids),
        MediaView.invalid_reason == None,  # noqa: E711
    )
    if since is not None:
        query = query.where(MediaView.started_at >= since)
    return float(session.exec(query).one() or 0.0)


def helpful_votes_for(session: DbSession, creator_id: int, since: datetime | None = None) -> int:
    groups = [
        g
        for g in session.exec(
            select(LastMileStep.version_group).where(LastMileStep.author_id == creator_id)
        ).all()
    ]
    if not groups:
        return 0
    query = select(func.count()).select_from(LastMileVote).where(
        LastMileVote.version_group.in_(groups),
        LastMileVote.helpful == True,  # noqa: E712
    )
    if since is not None:
        query = query.where(LastMileVote.at >= since)
    return int(session.exec(query).one() or 0)


def pulse_confirmed_for(session: DbSession, creator_id: int, since: datetime | None = None) -> int:
    """Pulse reports later corroborated by someone else's report (SPEC §10.3).

    "Confirmed" means another user filed a report for the same place within the
    recency window afterwards -- so a report that was useful to the next visitor
    counts, and one nobody ever corroborated does not.
    """
    query = select(Pulse).where(Pulse.user_id == creator_id)
    if since is not None:
        query = query.where(Pulse.at >= since)
    mine = list(session.exec(query).all())
    if not mine:
        return 0
    window_h = float(cfg("pulse.recent_hours", 48))
    confirmed = 0
    for report in mine:
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
    return confirmed


def verified_content_count(session: DbSession, creator_id: int) -> int:
    """Places that reached verified, plus media of verified places (SPEC §10.4)."""
    places = int(
        session.exec(
            select(func.count())
            .select_from(Place)
            .where(Place.added_by == creator_id, Place.status == "verified")
        ).one()
        or 0
    )
    media = int(
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
    return places + media


def daily_series(
    session: DbSession, media_ids: list[int], creator_id: int, days: int, now: datetime
) -> dict[str, list[float]]:
    """Sparkline data for all four metric cards (SPEC §8.10).

    Returned as plain numbers so the UI can also print them as text, which is
    what makes a sparkline usable without sight (SPEC §13, AC-19).
    """
    views: list[float] = []
    visits: list[float] = []
    watch_h: list[float] = []
    for offset in range(days - 1, -1, -1):
        day_end = now - timedelta(days=offset)
        day_start = day_end - timedelta(days=1)
        v = 0
        seconds = 0.0
        if media_ids:
            v = int(
                session.exec(
                    select(func.count())
                    .select_from(MediaView)
                    .where(
                        MediaView.media_id.in_(media_ids),
                        MediaView.engaged == True,  # noqa: E712
                        MediaView.invalid_reason == None,  # noqa: E711
                        MediaView.started_at >= day_start,
                        MediaView.started_at < day_end,
                    )
                ).one()
                or 0
            )
            seconds = float(
                session.exec(
                    select(func.coalesce(func.sum(MediaView.watched_s), 0.0)).where(
                        MediaView.media_id.in_(media_ids),
                        MediaView.invalid_reason == None,  # noqa: E711
                        MediaView.started_at >= day_start,
                        MediaView.started_at < day_end,
                    )
                ).one()
                or 0.0
            )
        views.append(float(v))
        watch_h.append(round(seconds / 3600.0, 3))
        caused = float(
            session.exec(
                select(func.coalesce(func.sum(Attribution.share), 0.0))
                .join(Visit, Visit.id == Attribution.visit_id)
                .where(
                    Attribution.creator_id == creator_id,
                    Visit.at >= day_start,
                    Visit.at < day_end,
                )
            ).one()
            or 0.0
        )
        visits.append(round(caused, 3))

    # The earnings line is the daily score, since a day's share of the pool is
    # proportional to that day's score. It is a shape, not a payment schedule.
    weights = cfg("partner.weights", {}) or {}
    w_view = float(weights.get("engaged_view", 1))
    w_visit = float(weights.get("visit_caused", 25))
    earnings = [round(w_view * v + w_visit * c, 2) for v, c in zip(views, visits)]

    return {
        "engaged_views": views,
        "visits_caused": visits,
        "watch_time_h": watch_h,
        "earnings": earnings,
    }


@router.get("/studio")
def studio(
    period: int = Query(28, ge=1, le=365),
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Metrics, Partner progress, top content and audience for the creator."""
    now = utcnow()
    uid = int(user.id)
    since = now - timedelta(days=period)
    since_90 = now - timedelta(days=90)

    media = creator_media(session, uid)
    media_ids = [int(m.id) for m in media]

    engaged = engaged_views_for(session, media_ids, since)
    seconds = watch_seconds(session, media_ids, since)
    caused = services.visits_caused(session, uid, since)
    helpful = helpful_votes_for(session, uid, since)
    confirmed = pulse_confirmed_for(session, uid, since)

    # Previous period, for the "+18 %" deltas on the metric cards.
    prev_start = since - timedelta(days=period)
    prev_engaged = engaged_views_for(session, media_ids, prev_start) - engaged
    prev_caused = services.visits_caused(session, uid, prev_start) - caused

    def delta_pct(current: float, previous: float) -> int | None:
        if previous <= 0:
            return None
        return int(round(100.0 * (current - previous) / previous))

    row = CreatorMonth(
        creator_id=uid,
        engaged_views=engaged,
        visits_caused=caused,
        helpful_votes=helpful,
        pulse_confirmed=confirmed,
    )
    my_score = score_creator(row)

    requirements = check(
        EligibilityInput(
            account_created_at=user.created_at,
            strikes=user.strikes,
            verified_content=verified_content_count(session, uid),
            visits_caused_90d=services.visits_caused(session, uid, since_90),
            engaged_views_90d=engaged_views_for(session, media_ids, since_90),
        ),
        now,
    )
    eligible = all(r.met for r in requirements)

    # Estimated earnings: this creator's share of the simulated pool.
    #
    # A creator who is not yet a Partner still sees the figure, because "what
    # would my work be worth" is the question the checklist is answering -- but
    # it is marked a projection, and the monthly engine (partner/run.py) pays
    # ineligible creators exactly 0 (AC-18). The two numbers are different
    # things and the UI says which is which.
    pool = demo_pool_paise()
    all_scores = _all_creator_scores(session, since, now)
    total_score = sum(all_scores.values())
    estimated_paise = int(pool * my_score / total_score) if total_score > 0 else 0

    # Top content by visits caused -- the metric the app exists for.
    top: list[dict] = []
    for m in media:
        m_caused = float(
            session.exec(
                select(func.coalesce(func.sum(Attribution.share), 0.0))
                .join(Visit, Visit.id == Attribution.visit_id)
                .where(
                    Attribution.creator_id == uid,
                    Visit.at >= since,
                    Attribution.visit_id.in_(
                        select(Visit.id).where(Visit.place_id == m.place_id)
                    ),
                )
            ).one()
            or 0.0
        )
        m_views = engaged_views_for(session, [int(m.id)], since)
        avg_pct = 0.0
        if m_views and m.duration_s:
            watched = watch_seconds(session, [int(m.id)], since)
            avg_pct = min(100.0, 100.0 * watched / (m_views * m.duration_s))
        top.append(
            {
                "type": m.kind,
                "media_id": m.id,
                "place_id": m.place_id,
                "title": m.caption[:80] or services.english_name(session, int(m.place_id)),
                "duration_s": m.duration_s,
                "engaged_views": m_views,
                "avg_watched_pct": round(avg_pct),
                "visits_caused": round(m_caused, 1),
                "thumb": f"/media/{m.path_thumb}" if m.path_thumb else None,
            }
        )
    for place in session.exec(
        select(Place).where(Place.added_by == uid, Place.status != "hidden")
    ).all():
        page_views = int(
            session.exec(
                select(func.count()).select_from(View).where(View.place_id == place.id)
            ).one()
            or 0
        )
        top.append(
            {
                "type": "place",
                "place_id": place.id,
                "title": services.english_name(session, int(place.id)),
                "engaged_views": page_views,
                "avg_watched_pct": None,
                "visits_caused": round(
                    float(
                        session.exec(
                            select(func.coalesce(func.sum(Attribution.share), 0.0))
                            .join(Visit, Visit.id == Attribution.visit_id)
                            .where(
                                Attribution.creator_id == uid,
                                Visit.place_id == place.id,
                                Visit.at >= since,
                            )
                        ).one()
                        or 0.0
                    ),
                    1,
                ),
                "thumb": None,
            }
        )
    top.sort(key=lambda t: -t["visits_caused"])

    followers = int(
        session.exec(
            select(func.count()).select_from(Follow).where(Follow.creator_id == uid)
        ).one()
        or 0
    )

    return {
        "creator": {
            "id": uid,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "followers": followers,
        },
        "period_days": period,
        "simulated": True,
        "banner": "Simulated earnings. No real money is paid in this version.",
        "metrics": {
            "engaged_views": {"value": engaged, "delta_pct": delta_pct(engaged, prev_engaged)},
            "watch_time_h": {"value": round(seconds / 3600.0, 1), "delta_pct": None},
            "visits_caused": {"value": round(caused, 1), "delta_pct": delta_pct(caused, prev_caused)},
            "estimated_earnings_paise": estimated_paise,
            # True while the creator is not yet a Partner: the figure is what
            # their score would be worth, not what the engine would pay.
            "earnings_are_projection": not eligible,
        },
        "score": round(my_score, 2),
        "score_parts": {k: round(v, 2) for k, v in row.parts.items()},
        "sparklines": daily_series(session, media_ids, uid, min(period, 28), now),
        "partner": {
            "eligible": eligible,
            "done": sum(1 for r in requirements if r.met),
            "total": len(requirements),
            "requirements": [
                {
                    "key": r.key,
                    "label": r.label,
                    "met": r.met,
                    "value": round(r.value, 1),
                    "target": r.target,
                    "note": r.note,
                }
                for r in requirements
            ],
        },
        "top_content": top[:6],
        "audience": _audience(session, media_ids),
        "split_explainer": _split_explainer(),
    }


def _all_creator_scores(session: DbSession, since: datetime, now: datetime) -> dict[int, float]:
    """Scores for every creator with content, so one share can be computed."""
    creator_ids = {
        int(uid)
        for uid in session.exec(
            select(Media.user_id).where(Media.user_id != None, Media.status == "ok")  # noqa: E711
        ).all()
    }
    creator_ids |= {
        int(uid)
        for uid in session.exec(
            select(Place.added_by).where(Place.added_by != None)  # noqa: E711
        ).all()
    }
    scores: dict[int, float] = {}
    for cid in creator_ids:
        media_ids = [int(m.id) for m in creator_media(session, cid)]
        row = CreatorMonth(
            creator_id=cid,
            engaged_views=engaged_views_for(session, media_ids, since),
            visits_caused=services.visits_caused(session, cid, since),
            helpful_votes=helpful_votes_for(session, cid, since),
            pulse_confirmed=pulse_confirmed_for(session, cid, since),
        )
        scores[cid] = score_creator(row)
    return scores


def _audience(session: DbSession, media_ids: list[int]) -> dict:
    """Top cities and the languages viewers read names in (SPEC §8.10)."""
    if not media_ids:
        return {"cities": [], "languages": []}
    viewer_ids = {
        int(uid)
        for uid in session.exec(
            select(MediaView.user_id).where(
                MediaView.media_id.in_(media_ids),
                MediaView.user_id != None,  # noqa: E711
                MediaView.invalid_reason == None,  # noqa: E711
            )
        ).all()
    }
    if not viewer_ids:
        return {"cities": [], "languages": []}
    cities: dict[str, int] = {}
    languages: dict[str, int] = {}
    for user in session.exec(select(User).where(User.id.in_(viewer_ids))).all():
        if user.home_city_id:
            city = session.get(City, user.home_city_id)
            if city is not None:
                cities[city.name_en] = cities.get(city.name_en, 0) + 1
        lang = user.names_lang if user.names_mode == "mine_local" else "en"
        languages[lang] = languages.get(lang, 0) + 1
    return {
        "cities": sorted(
            ({"name": k, "viewers": v} for k, v in cities.items()),
            key=lambda d: -d["viewers"],
        )[:5],
        "languages": sorted(
            ({"lang": k, "viewers": v} for k, v in languages.items()),
            key=lambda d: -d["viewers"],
        )[:5],
    }


def _split_explainer() -> dict:
    """"How earnings are split", in plain words (SPEC §8.10, §10.3)."""
    weights = cfg("partner.weights", {}) or {}
    share = float(cfg("partner.creator_share", 0.55))
    return {
        "creator_share_pct": int(share * 100),
        "weights": weights,
        "lines": [
            f"{int(share * 100)}% of net revenue goes into a creator pool each month.",
            "Your score is 1 point per engaged view, "
            f"{int(weights.get('visit_caused', 25))} per visit you caused, "
            f"{int(weights.get('helpful_vote', 5))} per helpful vote on your directions, and "
            f"{int(weights.get('pulse_confirmed', 2))} per live report someone else confirmed.",
            "Your share of the pool is your score divided by all eligible creators' scores.",
            "A visit counts far more than a view because a visit is what the app is for, "
            "and it is hard to fake: you have to physically go.",
            "In this version the pool is simulated and no money is paid.",
        ],
    }
