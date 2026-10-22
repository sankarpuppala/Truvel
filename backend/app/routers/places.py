"""Cities, Explore lists, search, and the Place page (SPEC §8.4, §8.5).

The five sorts are the SPEC §9.1-9.3 functions applied to the same candidate
set: Top is the Wilson lower bound, Most liked is raw likes, Hidden gems is
Wilson x fame weight, Trending is time-decayed recent activity, Nearest is
distance. Unverified places are excluded from Top, Gems and Trending (AC-15) --
an unchecked place should not be recommended, only findable.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import commons, services
from ..auth import current_user_optional
from ..config import cfg, regional_langs
from ..db import fts_query, get_session
from ..errors import not_found
from ..geo import bbox_around, haversine_km
from ..models import City, Like, Media, Neighbourhood, Place, Pulse, User, View, Visit, utcnow
from ..ranking.gems import gem_score, is_gem_eligible
from ..ranking.trending import trending_score
from ..ranking.wilson import wilson_lb

router = APIRouter(tags=["places"])

SORTS = ("top", "liked", "gems", "trending", "near")
PAGE_SIZE = 20

SORT_EXPLAINERS = {
    "top": "Ranked by the share of viewers who liked it, adjusted so 2 likes can't beat 2,000.",
    "liked": "Most hearts, all time. Famous places win here.",
    "gems": "Places people who went liked, that the internet hasn't noticed yet.",
    "trending": "Likes, visits and live reports from the last 30 days, with the last week counting most.",
    "near": "Closest to you first.",
}


def city_payload(session: DbSession, city: City) -> dict:
    places = session.exec(
        select(func.count())
        .select_from(Place)
        .where(Place.city_id == city.id, Place.status != "hidden")
    ).one()
    community = session.exec(
        select(func.count())
        .select_from(Place)
        .where(Place.city_id == city.id, Place.source == "community", Place.status != "hidden")
    ).one()
    hoods = session.exec(
        select(func.count()).select_from(Neighbourhood).where(Neighbourhood.city_id == city.id)
    ).one()
    # The city's own name in its regional script, for the Explore header.
    names: dict[str, str] = {}
    for lang in regional_langs(city.state):
        row = session.exec(
            select(Place.id).where(Place.city_id == city.id).limit(1)
        ).first()
        if row is None:
            break
    return {
        "id": city.id,
        "slug": city.slug,
        "name": city.name_en,
        "state": city.state,
        "centre": [city.centre_lat, city.centre_lng],
        "bbox": city.bbox,
        "regional_langs": city.regional_langs or regional_langs(city.state),
        "names": names,
        "place_count": int(places or 0),
        "community_count": int(community or 0),
        "neighbourhood_count": int(hoods or 0),
    }


@router.get("/cities")
def list_cities(session: DbSession = Depends(get_session)) -> dict:
    cities = session.exec(select(City).order_by(City.name_en)).all()
    return {"cities": [city_payload(session, c) for c in cities]}


def _events_for_trending(
    session: DbSession, place_ids: list[int], now: datetime
) -> dict[int, list[tuple[str, datetime]]]:
    """Likes, verified visits and Pulse reports in the trending window."""
    window_days = int(cfg("ranking.trending_window_days", 30))
    since = now - timedelta(days=window_days)
    events: dict[int, list[tuple[str, datetime]]] = {pid: [] for pid in place_ids}
    if not place_ids:
        return events

    for pid, at in session.exec(
        select(Like.place_id, Like.at).where(Like.place_id.in_(place_ids), Like.at >= since)
    ).all():
        events[pid].append(("like", at))
    for pid, at in session.exec(
        select(Visit.place_id, Visit.at).where(
            Visit.place_id.in_(place_ids),
            Visit.at >= since,
            Visit.verified == True,  # noqa: E712
            Visit.flag == None,  # noqa: E711
            Visit.simulated == False,  # noqa: E712
        )
    ).all():
        events[pid].append(("visit", at))
    for pid, at in session.exec(
        select(Pulse.place_id, Pulse.at).where(Pulse.place_id.in_(place_ids), Pulse.at >= since)
    ).all():
        events[pid].append(("pulse", at))
    return events


def _counts(session: DbSession, place_ids: list[int]) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    """likes, viewers and verified visits per place, in three grouped queries."""
    if not place_ids:
        return ({}, {}, {})
    likes = {
        pid: int(n)
        for pid, n in session.exec(
            select(Like.place_id, func.count()).where(Like.place_id.in_(place_ids)).group_by(Like.place_id)
        ).all()
    }
    viewers = {
        pid: int(n)
        for pid, n in session.exec(
            select(View.place_id, func.count()).where(View.place_id.in_(place_ids)).group_by(View.place_id)
        ).all()
    }
    visits = {
        pid: int(n)
        for pid, n in session.exec(
            select(Visit.place_id, func.count())
            .where(
                Visit.place_id.in_(place_ids),
                Visit.verified == True,  # noqa: E712
                Visit.flag == None,  # noqa: E711
                Visit.simulated == False,  # noqa: E712
            )
            .group_by(Visit.place_id)
        ).all()
    }
    return (likes, viewers, visits)


@router.get("/cities/{slug}/places")
def city_places(
    slug: str,
    sort: str = Query("top"),
    cat: str | None = None,
    verified: int = 0,
    lat: float | None = None,
    lng: float | None = None,
    page: int = 1,
    q: str | None = None,
    session: DbSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
) -> dict:
    """One page of ranked places for a city (SPEC §8.4, 20 per page)."""
    if sort not in SORTS:
        sort = "top"
    city = session.exec(select(City).where(City.slug == slug)).first()
    if city is None:
        raise not_found("No such city.", "no_city")

    now = utcnow()
    query = select(Place).where(Place.city_id == city.id, Place.status != "hidden")
    if cat and cat != "all":
        query = query.where(Place.category == cat)
    if verified:
        query = query.where(Place.status == "verified")
    # Top, Hidden gems and Trending only recommend verified places (AC-15).
    if sort in ("top", "gems", "trending"):
        query = query.where(Place.status == "verified")
    if sort == "gems":
        query = query.where(Place.fragile == False)  # noqa: E712

    places = list(session.exec(query).all())

    if q:
        allowed = set(fts_query(session, q, limit=500))
        places = [p for p in places if int(p.id) in allowed]

    ids = [int(p.id) for p in places]
    likes, viewers, visits = _counts(session, ids)

    def distance_of(p: Place) -> float:
        if lat is None or lng is None:
            return haversine_km(city.centre_lat, city.centre_lng, p.lat, p.lng)
        return haversine_km(lat, lng, p.lat, p.lng)

    def _tiebreak(place: Place) -> tuple[int, int]:
        """How to order places nothing has been said about yet.

        On a fresh install every place has nought likes and nought viewers, so
        the Wilson bound is nought for all of them and the sort does nothing.
        Falling back to how many Wikipedias describe a place puts Golconda Fort
        above an unnamed viewpoint without inventing any engagement, and the id
        keeps the order the same between requests. Once anyone likes anything,
        Wilson decides and this is never reached.
        """
        return (-place.sitelinks, int(place.id or 0))

    if sort == "top":
        places.sort(
            key=lambda p: (
                -wilson_lb(likes.get(int(p.id), 0), viewers.get(int(p.id), 0)),
                -likes.get(int(p.id), 0),
                *_tiebreak(p),
            )
        )
    elif sort == "liked":
        places.sort(key=lambda p: (-likes.get(int(p.id), 0), *_tiebreak(p)))
    elif sort == "gems":
        places = [
            p
            for p in places
            if is_gem_eligible(p.status, bool(p.fragile), visits.get(int(p.id), 0))
        ]
        places.sort(
            key=lambda p: -gem_score(
                likes.get(int(p.id), 0), viewers.get(int(p.id), 0), p.fame
            )
        )
    elif sort == "trending":
        events = _events_for_trending(session, ids, now)
        places.sort(key=lambda p: -trending_score(events.get(int(p.id), []), now))
    else:  # near
        places.sort(key=distance_of)

    total = len(places)
    page = max(1, page)
    window = places[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

    out = []
    for rank, place in enumerate(window, start=(page - 1) * PAGE_SIZE + 1):
        payload = services.place_payload(session, place, user, lat=lat, lng=lng, now=now)
        payload["rank"] = rank
        payload["wilson"] = round(
            wilson_lb(likes.get(int(place.id), 0), viewers.get(int(place.id), 0)), 4
        )
        payload["is_gem"] = (
            is_gem_eligible(place.status, bool(place.fragile), visits.get(int(place.id), 0))
            and place.fame in ("hidden", "known")
            and payload["wilson"] >= 0.3
        )
        if lat is None or lng is None:
            payload["distance_km"] = round(distance_of(place), 2)
        out.append(payload)

    # Trending badge: the top 3 of the trending sort, so the badge agrees with
    # the tab rather than being a second definition.
    trending_ids: set[int] = set()
    if ids:
        events = _events_for_trending(session, ids, now)
        ranked = sorted(ids, key=lambda pid: -trending_score(events.get(pid, []), now))
        trending_ids = {pid for pid in ranked[:3] if trending_score(events.get(pid, []), now) > 0}
    for payload in out:
        payload["is_trending"] = payload["id"] in trending_ids

    return {
        "city": city_payload(session, city),
        "sort": sort,
        "explainer": SORT_EXPLAINERS[sort],
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
        "places": out,
    }


@router.get("/search")
def search(
    q: str = Query(min_length=1),
    lat: float | None = None,
    lng: float | None = None,
    session: DbSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
) -> dict:
    """Search cities and places by any name in any script (SPEC §7.4)."""
    cities = list(
        session.exec(
            select(City).where(City.name_en.ilike(f"%{q}%")).order_by(City.name_en).limit(5)
        ).all()
    )
    place_ids = fts_query(session, q, limit=30)
    places = []
    if place_ids:
        rows = {
            int(p.id): p
            for p in session.exec(
                select(Place).where(Place.id.in_(place_ids), Place.status != "hidden")
            ).all()
        }
        for pid in place_ids:                      # keep FTS relevance order
            place = rows.get(pid)
            if place is not None:
                places.append(services.place_payload(session, place, user, lat=lat, lng=lng))

    hoods = list(
        session.exec(
            select(Neighbourhood).where(Neighbourhood.name.ilike(f"%{q}%")).limit(5)
        ).all()
    )
    return {
        "query": q,
        "cities": [city_payload(session, c) for c in cities],
        "areas": [{"id": h.id, "name": h.name, "city_id": h.city_id} for h in hoods],
        "places": places,
    }


@router.get("/places/{place_id}")
def place_detail(
    place_id: int,
    lat: float | None = None,
    lng: float | None = None,
    session: DbSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
) -> dict:
    """The full Place page. Records a distinct View, which is Wilson's n."""
    place = session.get(Place, place_id)
    if place is None or place.status == "hidden":
        raise not_found("That place is not here.", "no_place")

    now = utcnow()
    if user is not None:
        seen = session.exec(
            select(View).where(View.user_id == user.id, View.place_id == place_id)
        ).first()
        if seen is None:
            session.add(View(user_id=int(user.id), place_id=place_id, first_seen_at=now))
            session.commit()

    # Commons photos get their author and licence the first time a page needs
    # them, so the credit is in this response and not one request late.
    for item in session.exec(
        select(Media).where(
            Media.place_id == place_id, Media.source == "commons", Media.status == "ok"
        )
    ).all():
        if not (item.licence and item.attribution):
            commons.resolve_media(session, item)

    payload = services.place_payload(
        session, place, user, lat=lat, lng=lng, full=True, now=now
    )

    # Nearby places: a cheap bbox prefilter, then exact distance (SPEC §15).
    box = bbox_around(place.lat, place.lng, 8.0)
    neighbours = session.exec(
        select(Place).where(
            Place.id != place_id,
            Place.status != "hidden",
            Place.lat.between(box[0], box[2]),
            Place.lng.between(box[1], box[3]),
        )
    ).all()
    scored = sorted(
        ((haversine_km(place.lat, place.lng, p.lat, p.lng), p) for p in neighbours),
        key=lambda t: t[0],
    )[:3]
    payload["nearby"] = [
        {
            **services.place_payload(session, p, user, lat=place.lat, lng=place.lng, now=now),
            "distance_km": round(d, 2),
        }
        for d, p in scored
    ]

    videos = session.exec(
        select(Media)
        .where(Media.place_id == place_id, Media.kind == "video", Media.status == "ok")
        .order_by(Media.created_at.desc())
        .limit(6)
    ).all()
    uploaders = {
        int(u.id): u
        for u in session.exec(
            select(User).where(User.id.in_([m.user_id for m in videos if m.user_id]))
        ).all()
    } if videos else {}
    payload["videos"] = [services.media_payload(m, uploaders.get(m.user_id or -1)) for m in videos]
    return payload
