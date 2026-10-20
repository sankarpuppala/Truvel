"""The signed-in user: passport, kadam, fog, settings (SPEC §8.9, §8.4).

The fog map is the one piece of real geometry here. Each verified, unflagged
visit clears a 1 km circle; progress is counted in **neighbourhoods explored**
rather than square kilometres, because "12 of 87 areas" feels reachable while
"0.4 % of the city" does not (SPEC §8.4). A neighbourhood counts as explored
when its node falls inside a cleared circle, which is Voronoi membership done
the cheap way: the nearest node to a visit is the one that gets credited.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import kadam, services
from ..auth import current_user, require_csrf_header
from ..config import cfg
from ..db import get_session
from ..errors import bad_request, not_found
from ..geo import haversine_km
from ..models import (
    City,
    Neighbourhood,
    Place,
    Save,
    User,
    Visit,
    utcnow,
)
from ..routers.auth_router import user_payload

router = APIRouter(tags=["me"])

KADAM_REASON_TEXT = {
    kadam.DISCOVERY: "{place} was confirmed by 2 visitors",
    kadam.VISIT_CAUSED: "Someone visited {place}, a place you found",
    kadam.LIKE_RECEIVED: "Someone liked {place}",
    kadam.OWN_VISIT: "Your first visit: {place}",
    kadam.STEPS_HELPFUL: "Your directions helped someone",
    kadam.PULSE: "You reported conditions at {place}",
    kadam.WEEKLY_TRAIL: "You finished the Weekly Trail",
    kadam.REVERSAL: "Removed content: kadam reversed",
}


@router.get("/me")
def get_me(
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    payload = user_payload(session, user)
    payload["streak"] = weekly_streak(session, int(user.id))
    return {"user": payload}


def weekly_streak(session: DbSession, user_id: int, now: datetime | None = None) -> dict:
    """Weeks in a row with at least one verified visit (SPEC §8.9).

    One automatic "rain check" per calendar month forgives a single missed
    week, so a bad week of weather or exams does not reset months of effort.
    """
    now = now or utcnow()
    visits = list(
        session.exec(
            select(Visit.at).where(
                Visit.user_id == user_id,
                Visit.verified == True,  # noqa: E712
                Visit.flag == None,  # noqa: E711
                Visit.simulated == False,  # noqa: E712
            )
        ).all()
    )
    weeks = {at.isocalendar()[:2] for at in visits} if visits else set()

    streak = 0
    rain_checks_used: set[tuple[int, int]] = set()
    cursor = now
    while True:
        key = cursor.isocalendar()[:2]
        if key in weeks:
            streak += 1
        else:
            month_key = (cursor.year, cursor.month)
            if month_key in rain_checks_used or streak == 0:
                break
            rain_checks_used.add(month_key)      # spend this month's rain check
        cursor -= timedelta(days=7)
        if streak > 520:                          # a decade: stop walking back
            break

    month_key = (now.year, now.month)
    return {
        "weeks": streak,
        "rain_checks_left": 0 if month_key in rain_checks_used else 1,
    }


@router.get("/me/passport")
def passport(
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Everything the Passport screen shows (SPEC §8.9)."""
    now = utcnow()
    uid = int(user.id)

    # Stamps: one per place, dated by the first verified visit.
    visits = list(
        session.exec(
            select(Visit)
            .where(
                Visit.user_id == uid,
                Visit.verified == True,  # noqa: E712
                Visit.flag == None,  # noqa: E711
            )
            .order_by(Visit.at)
        ).all()
    )
    first_by_place: dict[int, Visit] = {}
    for visit in visits:
        first_by_place.setdefault(int(visit.place_id), visit)

    stamps = []
    for place_id, visit in sorted(
        first_by_place.items(), key=lambda kv: kv[1].at, reverse=True
    ):
        place = session.get(Place, place_id)
        if place is None:
            continue
        stamps.append(
            {
                "place_id": place_id,
                "name": services.english_name(session, place_id),
                "name_block": services.name_block(session, place, user),
                "category": place.category,
                "date": visit.at.date().isoformat(),
                "simulated": bool(visit.simulated),
            }
        )

    found = list(
        session.exec(
            select(Place).where(Place.added_by == uid, Place.status != "hidden").order_by(Place.created_at.desc())
        ).all()
    )
    caused = services.visits_caused(session, uid)

    saved_rows = list(
        session.exec(select(Save).where(Save.user_id == uid).order_by(Save.at.desc())).all()
    )
    want_to_go = []
    home = session.get(City, user.home_city_id) if user.home_city_id else None
    origin = (home.centre_lat, home.centre_lng) if home else None
    for row in saved_rows:
        place = session.get(Place, row.place_id)
        if place is None or place.status == "hidden":
            continue
        payload = services.place_payload(
            session,
            place,
            user,
            lat=origin[0] if origin else None,
            lng=origin[1] if origin else None,
            now=now,
        )
        want_to_go.append(payload)
    want_to_go.sort(key=lambda p: p.get("distance_km") or 1e9)

    entries = kadam.ledger(session, uid, limit=40)
    ledger_out = []
    for entry in entries:
        place_name = None
        if entry.ref_type == "place" and entry.ref_id:
            place_name = services.english_name(session, int(entry.ref_id))
        template = KADAM_REASON_TEXT.get(entry.reason, entry.reason)
        ledger_out.append(
            {
                "delta": entry.delta,
                "reason": entry.reason,
                "text": template.format(place=place_name or "a place"),
                "place": place_name,
                "at": entry.at.isoformat(),
            }
        )

    balance = kadam.balance(session, uid)
    level_name, next_level, floor, next_floor = kadam.level(balance)
    fog = fog_data(session, uid, home) if home else {"explored": 0, "total": 0}

    return {
        "user": user_payload(session, user),
        "kadam": balance,
        "level": level_name,
        "next_level": next_level,
        "level_floor": floor,
        "next_level_floor": next_floor,
        "streak": weekly_streak(session, uid, now),
        "stamps": stamps,
        "found": [services.place_payload(session, p, user, now=now) for p in found],
        "visits_caused": round(caused, 1),
        "want_to_go": want_to_go,
        "ledger": ledger_out,
        "neighbourhoods_explored": fog.get("explored", 0),
        "neighbourhoods_total": fog.get("total", 0),
    }


@router.get("/me/kadam")
def kadam_ledger(
    limit: int = Query(50, ge=1, le=200),
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    uid = int(user.id)
    entries = kadam.ledger(session, uid, limit=limit)
    return {
        "balance": kadam.balance(session, uid),
        "entries": [
            {
                "delta": e.delta,
                "reason": e.reason,
                "ref_type": e.ref_type,
                "ref_id": e.ref_id,
                "at": e.at.isoformat(),
            }
            for e in entries
        ],
    }


def fog_data(session: DbSession, user_id: int, city: City) -> dict:
    """Cleared circles and the neighbourhood count for a city (SPEC §8.4).

    Simulated visits clear fog in dev so the viva demo works, but they are
    excluded from every metric that matters (AC-13, AC-25).
    """
    radius_km = float(cfg("fog.clear_radius_km", 1.0))
    visits = list(
        session.exec(
            select(Visit)
            .where(
                Visit.user_id == user_id,
                Visit.verified == True,  # noqa: E712
                Visit.flag == None,  # noqa: E711
            )
            .order_by(Visit.at)
        ).all()
    )
    circles: list[dict] = []
    seen: set[int] = set()
    for visit in visits:
        pid = int(visit.place_id)
        if pid in seen:
            continue
        place = session.get(Place, pid)
        if place is None or place.city_id != city.id:
            continue
        seen.add(pid)
        circles.append(
            {
                "lat": place.lat,
                "lng": place.lng,
                "radius_km": radius_km,
                "simulated": bool(visit.simulated),
            }
        )

    hoods = list(session.exec(select(Neighbourhood).where(Neighbourhood.city_id == city.id)).all())

    # The denominator is the neighbourhoods that have somewhere to go in them,
    # not every node OSM tags as a neighbourhood.
    #
    # SPEC §8.4 asks this number to "feel reachable", and gives "12 of 87" as
    # the shape of it. Real OSM data for Hyderabad has about 1,600 nodes tagged
    # suburb or neighbourhood -- mostly residential colonies -- so counting all
    # of them would read "4 of 1331 (0%)", which is the opposite of reachable
    # and would not be telling the user anything true either: an area with no
    # place in it is not somewhere the app can send them. So an area counts
    # once at least one place sits closer to it than to any other area, which
    # is the same nearest-node (Voronoi) membership the SPEC describes.
    counted = _countable_neighbourhoods(session, city, hoods)

    explored = 0
    explored_names: list[str] = []
    for hood in counted:
        for circle in circles:
            if haversine_km(hood.lat, hood.lng, circle["lat"], circle["lng"]) <= radius_km:
                explored += 1
                explored_names.append(hood.name)
                break

    return {
        "city": {"slug": city.slug, "name": city.name_en, "bbox": city.bbox},
        "circles": circles,
        "explored": explored,
        "total": len(counted),
        "neighbourhoods_mapped": len(hoods),
        "explored_names": explored_names,
        "percent": round(100.0 * explored / len(counted)) if counted else 0,
    }


# The countable set depends only on the seeded data, so it is computed once per
# (city, place count, neighbourhood count) rather than on every passport load.
# Without this, the pairing is O(places x neighbourhoods) -- about 2.8 million
# haversine calls for Hyderabad, which took ~650 ms per request.
_COUNTABLE_CACHE: dict[tuple[int, int, int], list[Neighbourhood]] = {}


def _countable_neighbourhoods(
    session: DbSession, city: City, hoods: list[Neighbourhood]
) -> list[Neighbourhood]:
    """Neighbourhoods with at least one place nearest to them (SPEC §8.4)."""
    if not hoods:
        return []

    place_count = int(
        session.exec(
            select(func.count())
            .select_from(Place)
            .where(Place.city_id == city.id, Place.status != "hidden")
        ).one()
        or 0
    )
    key = (int(city.id), place_count, len(hoods))
    cached = _COUNTABLE_CACHE.get(key)
    if cached is not None:
        return cached

    places = list(
        session.exec(
            select(Place).where(Place.city_id == city.id, Place.status != "hidden")
        ).all()
    )
    # Bucket the neighbourhoods into a coarse grid (about 5 km a side) so each
    # place only compares against the cells around it, rather than all 1,400.
    cell = 0.05
    grid: dict[tuple[int, int], list[Neighbourhood]] = {}
    for hood in hoods:
        grid.setdefault((int(hood.lat / cell), int(hood.lng / cell)), []).append(hood)

    worth_visiting: set[int] = set()
    for place in places:
        gx, gy = int(place.lat / cell), int(place.lng / cell)
        nearby: list[Neighbourhood] = []
        ring = 1
        while not nearby and ring <= 8:
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    nearby.extend(grid.get((gx + dx, gy + dy), ()))
            ring += 1
        candidates = nearby or hoods
        nearest = min(
            candidates, key=lambda h: haversine_km(h.lat, h.lng, place.lat, place.lng)
        )
        worth_visiting.add(int(nearest.id))

    counted = [h for h in hoods if int(h.id) in worth_visiting] or hoods
    _COUNTABLE_CACHE[key] = counted
    return counted


@router.get("/me/fog")
def get_fog(
    city: str | None = None,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    slug = city or str(cfg("city_default"))
    city_row = session.exec(select(City).where(City.slug == slug)).first()
    if city_row is None:
        raise not_found("No such city.", "no_city")
    return fog_data(session, int(user.id), city_row)


class SettingsIn(BaseModel):
    names_mode: str | None = None
    names_lang: str | None = None
    ui_lang: str | None = None
    theme: str | None = None
    home_city_id: int | None = None


@router.get("/me/settings")
def get_settings(
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    languages = list(cfg("languages") or [])
    return {
        "names_mode": user.names_mode,
        "names_lang": user.names_lang,
        "ui_lang": user.ui_lang,
        "theme": user.theme,
        "home_city_id": user.home_city_id,
        "languages": languages,
        "ui_available": list(cfg("ui_languages.available") or ["en"]),
        "ui_in_review": list(cfg("ui_languages.in_review") or []),
    }


@router.patch("/me/settings", dependencies=[Depends(require_csrf_header)])
def patch_settings(
    body: SettingsIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    languages = list(cfg("languages") or [])
    if body.names_mode is not None:
        if body.names_mode not in ("en_local", "mine_local", "en"):
            raise bad_request("Unknown name mode.", "bad_names_mode")
        user.names_mode = body.names_mode
    if body.names_lang is not None:
        if body.names_lang not in languages:
            raise bad_request("We don't have that language yet.", "bad_lang")
        user.names_lang = body.names_lang
    if body.ui_lang is not None:
        # Only reviewed UI languages can be selected (CLAUDE.md invariant 11).
        available = list(cfg("ui_languages.available") or ["en"])
        if body.ui_lang not in available:
            raise bad_request(
                "That language is still being checked by a native speaker.",
                "lang_not_reviewed",
            )
        user.ui_lang = body.ui_lang
    if body.theme is not None:
        if body.theme not in ("system", "light", "dark"):
            raise bad_request("Unknown theme.", "bad_theme")
        user.theme = body.theme
    if body.home_city_id is not None:
        city = session.get(City, body.home_city_id)
        if city is None:
            raise not_found("No such city.", "no_city")
        user.home_city_id = body.home_city_id

    session.add(user)
    session.commit()
    session.refresh(user)
    return get_settings(session, user)
