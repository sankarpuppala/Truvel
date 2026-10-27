"""The Nearby deck (SPEC §8.2, §9.4).

The candidate rules matter as much as the scoring: we exclude places the user
has saved, visited, or swiped in the last 14 days, so the deck never shows the
same card twice in a week, and the deck **ends** rather than looping (SPEC §8.2,
D12) -- the habit we want is going out, not scrolling.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import services
from ..auth import current_user, current_user_optional, require_csrf_header
from ..config import cfg
from ..db import get_session
from ..deck.rank import Candidate, deck_rng, diversify, score_candidates
from ..deck.thompson import update
from ..errors import not_found
from ..geo import bbox_around, haversine_km
from ..models import (
    CategoryPref,
    City,
    LastMileStep,
    Like,
    Place,
    Save,
    Swipe,
    User,
    View,
    Visit,
    utcnow,
)

router = APIRouter(tags=["deck"])


@router.get("/deck")
def get_deck(
    request: Request,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float = Query(10.0, ge=1, le=100),
    request_no: int = 0,
    session: DbSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
) -> dict:
    """One page of deck cards, ranked by SPEC §9.4."""
    now = utcnow()

    fallback = False
    if lat is None or lng is None:
        from .places import detect_location

        # 1. Try detecting client location dynamically from IP / network headers
        try:
            detected = detect_location(request, session, user)
            if detected and detected.get("lat") and detected.get("lng") and detected.get("source") != "fallback":
                lat, lng = float(detected["lat"]), float(detected["lng"])
                fallback = True
                # If detected matched a seeded city and user had default home city, sync it
                if user is not None and detected.get("city_id") and user.home_city_id != detected.get("city_id"):
                    user.home_city_id = detected["city_id"]
                    session.add(user)
                    session.commit()
        except Exception:
            pass

        # 2. If IP detection failed or returned fallback, use user's configured home city or city_default
        if lat is None or lng is None:
            city = None
            if user is not None and user.home_city_id:
                city = session.get(City, user.home_city_id)
            if city is None:
                city = session.exec(select(City).where(City.slug == str(cfg("city_default")))).first()
            if city is None:
                raise not_found("No city is seeded yet.", "no_city")
            lat, lng = city.centre_lat, city.centre_lng
            fallback = True

    # bbox prefilter, then exact haversine (SPEC §15).
    box = bbox_around(lat, lng, radius_km)
    rows = session.exec(
        select(Place).where(
            Place.status != "hidden",
            Place.fragile == False,  # noqa: E712
            Place.lat.between(box[0], box[2]),
            Place.lng.between(box[1], box[3]),
        )
    ).all()

    unverified_radius = float(cfg("deck.unverified_radius_km", 5))
    saved_or_visited: set[int] = set()
    skipped: set[int] = set()
    prefs: dict[str, tuple[float, float]] = {}

    if user is not None:
        cooldown_days = int(cfg("deck.skip_cooldown_days", 14))
        cutoff = now - timedelta(days=cooldown_days)
        saved_or_visited |= {
            int(pid)
            for pid in session.exec(select(Save.place_id).where(Save.user_id == user.id)).all()
        }
        saved_or_visited |= {
            int(pid)
            for pid in session.exec(
                select(Visit.place_id).where(Visit.user_id == user.id, Visit.verified == True)  # noqa: E712
            ).all()
        }
        skipped |= {
            int(pid)
            for pid in session.exec(
                select(Swipe.place_id).where(Swipe.user_id == user.id, Swipe.action == "skip", Swipe.at >= cutoff)
            ).all()
        }
        prefs = {
            p.category: (p.alpha, p.beta)
            for p in session.exec(select(CategoryPref).where(CategoryPref.user_id == user.id)).all()
        }

    excluded = saved_or_visited | skipped

    place_ids = [int(p.id) for p in rows]
    likes = {
        pid: int(n)
        for pid, n in session.exec(
            select(Like.place_id, func.count()).where(Like.place_id.in_(place_ids)).group_by(Like.place_id)
        ).all()
    } if place_ids else {}
    viewers = {
        pid: int(n)
        for pid, n in session.exec(
            select(View.place_id, func.count()).where(View.place_id.in_(place_ids)).group_by(View.place_id)
        ).all()
    } if place_ids else {}

    candidates: list[Candidate] = []
    keep: dict[int, Place] = {}
    for place in rows:
        pid = int(place.id)
        if pid in excluded:
            continue
        distance = haversine_km(lat, lng, place.lat, place.lng)
        if distance > radius_km:
            continue
        if place.status != "verified" and distance > unverified_radius:
            continue                      # unverified only within 5 km, and marked
        keep[pid] = place
        candidates.append(
            Candidate(
                place_id=pid,
                category=place.category,
                distance_km=distance,
                likes=likes.get(pid, 0),
                viewers=viewers.get(pid, 0),
                created_at=place.created_at,
                status=place.status,
            )
        )

    # If all candidates within this radius were skipped, recycle skipped places
    # so Nearby does not turn into an empty dead screen for 14 days.
    if not candidates and skipped:
        for place in rows:
            pid = int(place.id)
            if pid in saved_or_visited:
                continue
            distance = haversine_km(lat, lng, place.lat, place.lng)
            if distance > radius_km:
                continue
            if place.status != "verified" and distance > unverified_radius:
                continue
            keep[pid] = place
            candidates.append(
                Candidate(
                    place_id=pid,
                    category=place.category,
                    distance_km=distance,
                    likes=likes.get(pid, 0),
                    viewers=viewers.get(pid, 0),
                    created_at=place.created_at,
                    status=place.status,
                )
            )

    # The ranking itself is seeded by (user, day) only, never by request_no:
    # `request_no` pages through that one stable order instead of re-drawing
    # it. A re-draw per request was leaving some in-radius places essentially
    # unreachable -- a place that scored just outside the first `page_size`
    # every time it was redrawn would never appear until the radius changed
    # the candidate pool, which looked like the radius or distance was wrong
    # (it was not: every in-radius place is always a candidate here, see the
    # haversine filter above -- it just never got *shown*).
    rng = deck_rng(int(user.id) if user else 0, now.date().isoformat(), 0)
    # Stratify candidates into distance bands across the requested radius so Nearby
    # deck cards reflect the full chosen exploration radius (e.g. 5, 10, 25 km)
    # instead of clustering 100% of the first 30 cards within < 2 km.
    if radius_km >= 5.0 and len(candidates) > 10:
        b1 = [c for c in candidates if c.distance_km < radius_km / 3]
        b2 = [c for c in candidates if radius_km / 3 <= c.distance_km < 2 * radius_km / 3]
        b3 = [c for c in candidates if c.distance_km >= 2 * radius_km / 3]
        s1 = score_candidates(b1, prefs, now, rng)
        s2 = score_candidates(b2, prefs, now, rng)
        s3 = score_candidates(b3, prefs, now, rng)
        interleaved: list[Candidate] = []
        i1 = i2 = i3 = 0
        while len(interleaved) < len(candidates):
            added = False
            if i1 < len(s1):
                interleaved.append(s1[i1])
                i1 += 1
                added = True
            if i2 < len(s2):
                interleaved.append(s2[i2])
                i2 += 1
                added = True
            if i3 < len(s3):
                interleaved.append(s3[i3])
                i3 += 1
                added = True
            if not added:
                break
        ranked = diversify(interleaved)
    else:
        ranked = diversify(score_candidates(candidates, prefs, now, rng))
    page_size = int(cfg("deck.page_size", 30))
    start = max(0, request_no) * page_size
    window = ranked[start : start + page_size]
    more_at_this_radius = start + page_size < len(ranked)

    cards = []
    for cand in window:
        place = keep[cand.place_id]
        payload = services.place_payload(session, place, user, lat=lat, lng=lng, now=now)
        payload["unverified_nearby"] = place.status != "verified"
        payload["score"] = round(cand.score, 4)
        payload["score_parts"] = {k: round(v, 4) for k, v in cand.parts.items()}
        best = session.exec(
            select(LastMileStep)
            .where(LastMileStep.place_id == cand.place_id, LastMileStep.status == "ok")
            .order_by(LastMileStep.order)
            .limit(1)
        ).first()
        if best is not None:
            author = session.get(User, best.author_id)
            payload["tip"] = {
                "text": best.text,
                "by": author.username if author else None,
            }
        cards.append(payload)

    return {
        "cards": cards,
        "radius_km": radius_km,
        "location_fallback": fallback,
        "total_candidates": len(ranked),
        "more_at_this_radius": more_at_this_radius,
        "end_card": {
            "message": (
                "Keep swiping for more within this radius."
                if more_at_this_radius
                else f"That's everything within {int(radius_km)} km. "
                "Widen the radius, or go see one you saved?"
            )
        },
    }


class SwipeIn(BaseModel):
    place_id: int
    action: str


@router.post("/deck/swipe", dependencies=[Depends(require_csrf_header)])
def swipe(
    body: SwipeIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Record a swipe and update the category's Beta prior (SPEC §9.4).

    save -> alpha + 1, skip -> beta + 1, open -> no change. Saving also creates
    the Save row, because swiping right *is* saving.
    """
    if body.action not in ("save", "skip", "open"):
        from ..errors import bad_request

        raise bad_request("Unknown swipe.", "bad_action")

    place = session.get(Place, body.place_id)
    if place is None or place.status == "hidden":
        raise not_found("That place is not here.", "no_place")

    now = utcnow()
    session.add(
        Swipe(user_id=int(user.id), place_id=int(place.id), action=body.action, at=now)
    )

    pref = session.exec(
        select(CategoryPref).where(
            CategoryPref.user_id == user.id, CategoryPref.category == place.category
        )
    ).first()
    if pref is None:
        pref = CategoryPref(user_id=int(user.id), category=place.category)
    pref.alpha, pref.beta = update(body.action, pref.alpha, pref.beta)
    session.add(pref)

    if body.action == "save":
        existing = session.exec(
            select(Save).where(Save.user_id == user.id, Save.place_id == place.id)
        ).first()
        if existing is None:
            session.add(Save(user_id=int(user.id), place_id=int(place.id), at=now))

    session.commit()
    return {
        "recorded": True,
        "category": place.category,
        "alpha": pref.alpha,
        "beta": pref.beta,
    }
