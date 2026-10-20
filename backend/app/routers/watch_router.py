"""The Watch feed and its view heartbeat (SPEC §8.3, §9.5, §9.10).

`POST /watch/{media_id}/view` takes `{watched_s, duration_s}` and the **server**
decides whether that was an engaged view, a completion, or invalid traffic. The
client is never asked "was this engaged?" because engaged views feed earnings.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import services
from ..auth import current_user_optional, require_csrf_header
from ..config import cfg, dev_allow_fake_location
from ..db import get_session
from ..deck.thompson import update
from ..errors import not_found
from ..geo import haversine_km
from ..models import (
    CategoryPref,
    City,
    Follow,
    Media,
    MediaLike,
    MediaView,
    Place,
    Touch,
    User,
    utcnow,
)
from ..watch.rank import VideoCandidate, diversify, score_videos, watch_rng
from ..watch.views import classify

router = APIRouter(tags=["watch"])

RISKY_FLAGS = ("steep_edge", "water_danger")


@router.get("/watch")
def get_watch(
    tab: str = Query("foryou"),
    lat: float | None = None,
    lng: float | None = None,
    cursor: int = 0,
    limit: int = Query(10, ge=1, le=30),
    session: DbSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
) -> dict:
    """A page of videos for one tab (SPEC §8.3)."""
    if tab not in ("foryou", "nearby", "following"):
        tab = "foryou"
    now = utcnow()

    if lat is None or lng is None:
        city = None
        if user is not None and user.home_city_id:
            city = session.get(City, user.home_city_id)
        if city is None:
            city = session.exec(select(City).where(City.slug == str(cfg("city_default")))).first()
        if city is not None:
            lat, lng = city.centre_lat, city.centre_lng

    following: set[int] = set()
    prefs: dict[str, tuple[float, float]] = {}
    if user is not None:
        following = {
            int(cid)
            for cid in session.exec(
                select(Follow.creator_id).where(Follow.follower_id == user.id)
            ).all()
        }
        prefs = {
            p.category: (p.alpha, p.beta)
            for p in session.exec(select(CategoryPref).where(CategoryPref.user_id == user.id)).all()
        }

    # Candidates: videos of verified places only (SPEC §9.5).
    rows = list(
        session.exec(
            select(Media, Place)
            .join(Place, Place.id == Media.place_id)
            .where(
                Media.kind == "video",
                Media.status == "ok",
                Place.status == "verified",
            )
        ).all()
    )

    media_ids = [int(m.id) for m, _ in rows]
    engaged_counts: dict[int, int] = {}
    completion_counts: dict[int, int] = {}
    like_counts: dict[int, int] = {}
    if media_ids:
        engaged_counts = {
            mid: int(n)
            for mid, n in session.exec(
                select(MediaView.media_id, func.count())
                .where(
                    MediaView.media_id.in_(media_ids),
                    MediaView.engaged == True,  # noqa: E712
                    MediaView.invalid_reason == None,  # noqa: E711
                )
                .group_by(MediaView.media_id)
            ).all()
        }
        completion_counts = {
            mid: int(n)
            for mid, n in session.exec(
                select(MediaView.media_id, func.count())
                .where(
                    MediaView.media_id.in_(media_ids),
                    MediaView.completed == True,  # noqa: E712
                    MediaView.invalid_reason == None,  # noqa: E711
                )
                .group_by(MediaView.media_id)
            ).all()
        }
        like_counts = {
            mid: int(n)
            for mid, n in session.exec(
                select(MediaLike.media_id, func.count())
                .where(MediaLike.media_id.in_(media_ids))
                .group_by(MediaLike.media_id)
            ).all()
        }

    nearby_max = float(cfg("watch.nearby_max_km", 25))
    candidates: list[VideoCandidate] = []
    keep: dict[int, tuple[Media, Place]] = {}

    for media, place in rows:
        mid = int(media.id)
        distance = (
            haversine_km(lat, lng, place.lat, place.lng) if lat is not None and lng is not None else 0.0
        )
        creator_id = int(media.user_id or 0)

        if tab == "nearby" and distance > nearby_max:
            continue
        if tab == "following":
            if creator_id not in following:
                continue
        if tab == "foryou" and place.fragile:
            continue              # fragile places are excluded from For you (§8.14)

        safety = place.safety or {}
        risky = any(str(safety.get(flag)) == "yes" for flag in RISKY_FLAGS)

        keep[mid] = (media, place)
        candidates.append(
            VideoCandidate(
                media_id=mid,
                creator_id=creator_id,
                place_id=int(place.id),
                category=place.category,
                distance_km=distance,
                engaged_views=engaged_counts.get(mid, 0),
                completions=completion_counts.get(mid, 0),
                created_at=media.created_at,
                following=creator_id in following,
                fragile=bool(place.fragile),
                risky=risky,
            )
        )

    if tab == "following":
        # Following is simply newest first (SPEC §9.5).
        ordered = sorted(candidates, key=lambda c: (-c.created_at.timestamp(), c.media_id))
    else:
        rng = watch_rng(int(user.id) if user else 0, now.date().isoformat(), cursor)
        ordered = diversify(score_videos(candidates, prefs, now, rng))

    window = ordered[cursor : cursor + limit]
    items = []
    for cand in window:
        media, place = keep[cand.media_id]
        uploader = session.get(User, media.user_id) if media.user_id else None
        place_payload = services.place_payload(session, place, user, lat=lat, lng=lng, now=now)
        item = {
            "media": services.media_payload(media, uploader),
            "place": place_payload,
            "likes": like_counts.get(cand.media_id, 0),
            "engaged_views": cand.engaged_views,
            "following": cand.following,
            "score": round(cand.score, 4),
            "score_parts": {k: round(v, 4) for k, v in cand.parts.items()},
            "safety_overlay": cand.risky,
        }
        if cand.fragile:
            # Videos of fragile places blur the location line (SPEC §8.14).
            item["place"]["area"] = ""
            item["blur_location"] = True
        if user is not None:
            item["liked"] = (
                session.exec(
                    select(MediaLike.id).where(
                        MediaLike.user_id == user.id, MediaLike.media_id == cand.media_id
                    )
                ).first()
                is not None
            )
        items.append(item)

    return {
        "tab": tab,
        "cursor": cursor,
        "next_cursor": cursor + len(window) if cursor + len(window) < len(ordered) else None,
        "total": len(ordered),
        "items": items,
        "nudge_after_min": int(cfg("watch.break_nudge_min", 20)),
    }


class ViewIn(BaseModel):
    watched_s: float = Field(ge=0)
    duration_s: float = Field(ge=0)
    simulated_session: bool = False


@router.post("/watch/{media_id}/view", dependencies=[Depends(require_csrf_header)])
def record_view(
    media_id: int,
    body: ViewIn,
    session: DbSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
) -> dict:
    """The heartbeat sent on leaving a video. The server classifies it (§9.10)."""
    media = session.get(Media, media_id)
    if media is None or media.status != "ok":
        raise not_found("That video is not here.", "no_media")

    now = utcnow()
    simulated = bool(body.simulated_session) and dev_allow_fake_location()

    previous_at = None
    if user is not None:
        window_h = float(cfg("invalid_traffic.repeat_window_hours", 24))
        previous = session.exec(
            select(MediaView)
            .where(
                MediaView.user_id == user.id,
                MediaView.media_id == media_id,
                MediaView.started_at >= now - timedelta(hours=window_h),
            )
            .order_by(MediaView.started_at.desc())
            .limit(1)
        ).first()
        previous_at = previous.started_at if previous else None

    verdict = classify(
        watched_s=body.watched_s,
        duration_s=body.duration_s or media.duration_s,
        viewer_id=int(user.id) if user else None,
        creator_id=int(media.user_id or 0),
        viewer_created_at=user.created_at if user else None,
        now=now,
        previous_view_at=previous_at,
        simulated_session=simulated,
    )

    session.add(
        MediaView(
            user_id=int(user.id) if user else None,
            media_id=media_id,
            started_at=now,
            watched_s=float(verdict["watched_s"]),
            completed=bool(verdict["completed"]),
            engaged=bool(verdict["engaged"]),
            invalid_reason=verdict["invalid_reason"],
        )
    )

    # An engaged view of someone else's video is a touch: it may later be
    # credited with causing a visit (SPEC §9.9).
    if (
        user is not None
        and verdict["engaged"]
        and media.user_id
        and int(media.user_id) != int(user.id)
    ):
        session.add(
            Touch(
                user_id=int(user.id),
                place_id=int(media.place_id),
                creator_id=int(media.user_id),
                content_type="video",
                content_id=media_id,
                at=now,
                invalid_reason=verdict["invalid_reason"],
            )
        )

    # A skip inside 2 seconds is a negative signal for the category (SPEC §9.5).
    if user is not None and float(verdict["watched_s"]) < 2.0:
        place = session.get(Place, media.place_id)
        if place is not None:
            pref = session.exec(
                select(CategoryPref).where(
                    CategoryPref.user_id == user.id, CategoryPref.category == place.category
                )
            ).first()
            if pref is None:
                pref = CategoryPref(user_id=int(user.id), category=place.category)
            pref.alpha, pref.beta = update("skip", pref.alpha, pref.beta)
            session.add(pref)

    session.commit()
    return {
        "engaged": verdict["engaged"],
        "completed": verdict["completed"],
        "invalid_reason": verdict["invalid_reason"],
    }
