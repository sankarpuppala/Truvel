"""Shared read helpers: stats, name blocks, Pulse summaries, place payloads.

The routers stay thin by calling into here. Two rules are enforced in this file
so that *every* route gets them, rather than being re-implemented per endpoint:

* **Fragile places** (CLAUDE.md invariant 5, SPEC §8.14): the API never returns
  exact coordinates or last-mile steps for a fragile place until the user has
  saved it and pledged. `place_payload` takes `pledged` and redacts if it is
  false, so forgetting the check in a new route cannot leak a pin.
* **Hidden media and places** are filtered out of every list.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from urllib.parse import quote_plus

from sqlmodel import Session, func, select

from .config import cfg, regional_langs
from .geo import haversine_km, travel_minutes
from .models import (
    Attribution,
    City,
    Like,
    Media,
    Place,
    PlaceName,
    Pulse,
    Save,
    User,
    View,
    Visit,
    utcnow,
)
from .names import NameRow, display, to_dict

# Rounded coordinates for a fragile place: ~1 km of fuzz, enough to show the
# area on a map without leading anyone to the spot.
FRAGILE_PRECISION = 2


@dataclass
class PlaceStats:
    likes: int
    viewers: int
    verified_visits: int
    visits_this_month: int
    photos: int
    videos: int


def name_rows(session: Session, place_id: int) -> list[NameRow]:
    rows = session.exec(select(PlaceName).where(PlaceName.place_id == place_id)).all()
    return [NameRow(lang=r.lang, name=r.name, source=r.source, votes=r.votes) for r in rows]


def name_block(
    session: Session,
    place: Place,
    user: User | None = None,
    rows: list[NameRow] | None = None,
) -> dict:
    """The §7.2 name block for a place, honouring the viewer's settings."""
    rows = rows if rows is not None else name_rows(session, int(place.id))
    mode = user.names_mode if user else "en_local"
    lang = user.names_lang if user else "en"
    return to_dict(display(rows, place.state, mode, lang))


def english_name(session: Session, place_id: int) -> str:
    """The plain English name, for shares, stamps and Maps links."""
    rows = name_rows(session, place_id)
    for r in sorted(rows, key=lambda r: (r.lang != "en", -r.votes)):
        if r.lang == "en":
            return r.name
    return rows[0].name if rows else "Unnamed place"


def place_stats(session: Session, place_id: int, now: datetime | None = None) -> PlaceStats:
    """Counts used by ranking and by the UI. One query each, all indexed."""
    now = now or utcnow()
    month_start = now - timedelta(days=30)

    likes = session.exec(
        select(func.count()).select_from(Like).where(Like.place_id == place_id)
    ).one()
    viewers = session.exec(
        select(func.count()).select_from(View).where(View.place_id == place_id)
    ).one()
    verified = session.exec(
        select(func.count())
        .select_from(Visit)
        .where(
            Visit.place_id == place_id,
            Visit.verified == True,  # noqa: E712
            Visit.flag == None,  # noqa: E711
            Visit.simulated == False,  # noqa: E712
        )
    ).one()
    this_month = session.exec(
        select(func.count())
        .select_from(Visit)
        .where(
            Visit.place_id == place_id,
            Visit.verified == True,  # noqa: E712
            Visit.flag == None,  # noqa: E711
            Visit.simulated == False,  # noqa: E712
            Visit.at >= month_start,
        )
    ).one()
    photos = session.exec(
        select(func.count())
        .select_from(Media)
        .where(Media.place_id == place_id, Media.kind == "photo", Media.status == "ok")
    ).one()
    videos = session.exec(
        select(func.count())
        .select_from(Media)
        .where(Media.place_id == place_id, Media.kind == "video", Media.status == "ok")
    ).one()

    return PlaceStats(
        likes=int(likes or 0),
        viewers=int(viewers or 0),
        verified_visits=int(verified or 0),
        visits_this_month=int(this_month or 0),
        photos=int(photos or 0),
        videos=int(videos or 0),
    )


# --------------------------------------------------------------------------- #
# Pulse summaries (SPEC §8.8)
# --------------------------------------------------------------------------- #

PULSE_FIELDS = ("water", "crowd", "path", "open")


def freshness_label(at: datetime, now: datetime | None = None) -> str | None:
    """'live' within 6 h, 'recent' within 48 h, None once it is hidden at 7 days."""
    now = now or utcnow()
    age_h = (now - at).total_seconds() / 3600.0
    if age_h <= float(cfg("pulse.live_hours", 6)):
        return "live"
    if age_h <= float(cfg("pulse.recent_hours", 48)):
        return "recent"
    if age_h <= float(cfg("pulse.hide_days", 7)) * 24:
        return "old"
    return None


def pulse_summary(session: Session, place_id: int, now: datetime | None = None) -> dict | None:
    """Latest conditions per field, with a 'mixed reports' rule (SPEC §8.8).

    Per field the summary is the latest report, unless two or more reports in
    the last 6 hours disagree -- then it is the majority answer, marked mixed,
    because "flowing" and "dry" an hour apart is a real disagreement that the
    reader should see rather than a silent coin-flip.
    """
    now = now or utcnow()
    hide_before = now - timedelta(days=float(cfg("pulse.hide_days", 7)))
    reports = list(
        session.exec(
            select(Pulse)
            .where(Pulse.place_id == place_id, Pulse.at >= hide_before)
            .order_by(Pulse.at.desc())
        ).all()
    )
    if not reports:
        return None

    live_window = now - timedelta(hours=float(cfg("pulse.live_hours", 6)))
    recent = [r for r in reports if r.at >= live_window]

    fields: dict[str, dict] = {}
    for field_name in PULSE_FIELDS:
        latest = next((getattr(r, field_name) for r in reports if getattr(r, field_name)), None)
        if latest is None:
            continue
        values = [getattr(r, field_name) for r in recent if getattr(r, field_name)]
        mixed = False
        value = latest
        if len(values) >= 2 and len(set(values)) > 1:
            mixed = True
            value = Counter(values).most_common(1)[0][0]
        fields[field_name] = {"value": value, "mixed": mixed}

    newest = reports[0]
    note = next((r.note for r in reports if (r.note or "").strip()), "")
    return {
        "at": newest.at.isoformat(),
        "freshness": freshness_label(newest.at, now),
        "reporters": len({r.user_id for r in recent}) or 1,
        "fields": fields,
        "note": note,
    }


def is_live(session: Session, place_id: int, now: datetime | None = None) -> bool:
    """Whether the Live pill should show: any Pulse within 6 hours (SPEC §8.8)."""
    now = now or utcnow()
    cutoff = now - timedelta(hours=float(cfg("pulse.live_hours", 6)))
    found = session.exec(
        select(Pulse.id).where(Pulse.place_id == place_id, Pulse.at >= cutoff).limit(1)
    ).first()
    return found is not None


# --------------------------------------------------------------------------- #
# Media and payloads
# --------------------------------------------------------------------------- #

def media_payload(m: Media, uploader: User | None = None) -> dict:
    """One media item. Commons items always carry their attribution."""
    return {
        "id": m.id,
        "kind": m.kind,
        "url": f"/media/{m.path_display}" if m.source == "upload" else f"/api/media/commons/{m.id}",
        "thumb": f"/media/{m.path_thumb}" if m.path_thumb else None,
        "poster": f"/media/{m.path_poster}" if m.path_poster else None,
        "width": m.width,
        "height": m.height,
        "duration_s": m.duration_s,
        "caption": m.caption,
        "lang": m.lang,
        "source": m.source,
        "licence": m.licence,
        "attribution": m.attribution,
        "source_url": m.source_url,
        "shot_here": m.shot_here,
        "creator": (
            {"id": uploader.id, "username": uploader.username, "display_name": uploader.display_name}
            if uploader
            else None
        ),
    }


def lead_media(session: Session, place_id: int) -> Media | None:
    """The photo a card or row shows: an upload if we have one, else Commons."""
    rows = list(
        session.exec(
            select(Media)
            .where(Media.place_id == place_id, Media.status == "ok", Media.kind == "photo")
            .order_by(Media.source.desc(), Media.created_at)
        ).all()
    )
    return rows[0] if rows else None


def maps_url(place: Place, name: str = "", city: str = "") -> str:
    """The free Google Maps directions link -- the only Google we use (SPEC §6.6).

    Coordinates are exact, but Google snaps a pin to the nearest thing it knows,
    and inside a large site that is the wrong thing: the Salar Jung Museum's pin
    opened "Metal Ware Gallery", one hall within it. A place with a Wikidata
    item is a notable, unambiguous thing, so it is sent by name and city, which
    Google resolves to the place itself. Everything else keeps its coordinates.
    """
    if place.wikidata and name:
        target = quote_plus(", ".join(part for part in (name, city) if part))
    else:
        target = f"{place.lat},{place.lng}"
    return f"https://www.google.com/maps/dir/?api=1&destination={target}"


def osm_url(place: Place) -> str:
    """Link back to the OSM object, or to the coordinates if it is ours."""
    if place.osm_type and place.osm_id:
        return f"https://www.openstreetmap.org/{place.osm_type}/{place.osm_id}"
    return f"https://www.openstreetmap.org/?mlat={place.lat}&mlon={place.lng}#map=17/{place.lat}/{place.lng}"


def attribution_line(place: Place) -> str:
    """The footer line. Required on every seeded place (invariant 6)."""
    if place.source == "osm":
        return "From OpenStreetMap - map data (c) OpenStreetMap contributors (ODbL)"
    if place.source == "wikidata":
        return "From Wikidata (CC0) - map data (c) OpenStreetMap contributors"
    return "Community place - map data (c) OpenStreetMap contributors"


def is_pledged(session: Session, place_id: int, user: User | None) -> bool:
    """Whether this user has saved + pledged for a fragile place (SPEC §8.14)."""
    if user is None:
        return False
    row = session.exec(
        select(Save).where(Save.user_id == user.id, Save.place_id == place_id)
    ).first()
    return bool(row and row.pledged)


def place_payload(
    session: Session,
    place: Place,
    user: User | None = None,
    *,
    lat: float | None = None,
    lng: float | None = None,
    full: bool = False,
    pledged: bool | None = None,
    now: datetime | None = None,
) -> dict:
    """Serialise a place. Fragile redaction happens here and only here.

    `full=False` gives the list/card shape; `full=True` adds everything the
    Place page needs. When the place is fragile and the viewer has not pledged,
    the coordinates are rounded to ~1 km and `steps` is withheld entirely --
    enforced server-side so a direct API call cannot bypass it (AC-15).
    """
    now = now or utcnow()
    pid = int(place.id)
    stats = place_stats(session, pid, now)
    if pledged is None:
        pledged = is_pledged(session, pid, user)

    redact = bool(place.fragile) and not pledged
    out_lat = round(place.lat, FRAGILE_PRECISION) if redact else place.lat
    out_lng = round(place.lng, FRAGILE_PRECISION) if redact else place.lng

    distance_km = None
    if lat is not None and lng is not None:
        distance_km = haversine_km(lat, lng, place.lat, place.lng)

    finder = session.get(User, place.added_by) if place.added_by else None
    city = session.get(City, place.city_id) if place.city_id else None
    city_name = city.name_en if city else ""
    lead = lead_media(session, pid)

    payload: dict = {
        "id": pid,
        "name": name_block(session, place, user),
        "category": place.category,
        "area": place.area,
        "state": place.state,
        "lat": out_lat,
        "lng": out_lng,
        "coords_exact": not redact,
        "fragile": bool(place.fragile),
        "pledged": bool(pledged),
        "status": place.status,
        "fame": place.fame,
        "source": place.source,
        "radius_m": place.radius_m,
        "likes": stats.likes,
        "viewers": stats.viewers,
        "verified_visits": stats.verified_visits,
        "visits_this_month": stats.visits_this_month,
        "photo_count": stats.photos,
        "video_count": stats.videos,
        "live": is_live(session, pid, now),
        "lead_media": media_payload(lead) if lead else None,
        "found_by": (
            {
                "id": finder.id,
                "username": finder.username,
                "display_name": finder.display_name,
                "official": bool(finder.official),
            }
            if finder
            else None
        ),
        "created_at": place.created_at.isoformat(),
        "attribution": attribution_line(place),
    }
    if distance_km is not None:
        payload["distance_km"] = round(distance_km, 2)
        payload["travel_min"] = travel_minutes(distance_km)

    if user is not None:
        payload["liked"] = (
            session.exec(
                select(Like.id).where(Like.user_id == user.id, Like.place_id == pid)
            ).first()
            is not None
        )
        payload["saved"] = (
            session.exec(
                select(Save.id).where(Save.user_id == user.id, Save.place_id == pid)
            ).first()
            is not None
        )

    if not full:
        return payload

    media_rows = list(
        session.exec(
            select(Media)
            .where(Media.place_id == pid, Media.status == "ok")
            .order_by(Media.kind, Media.source.desc(), Media.created_at)
        ).all()
    )
    uploaders = {
        int(u.id): u
        for u in session.exec(
            select(User).where(User.id.in_([m.user_id for m in media_rows if m.user_id]))
        ).all()
    } if any(m.user_id for m in media_rows) else {}

    payload.update(
        {
            "description": place.description,
            "activities": place.activities or [],
            "best_time": place.best_time or {},
            "entry_fee_text": place.entry_fee_text,
            "timings_text": place.timings_text,
            "access": place.access or {},
            "accessibility": place.accessibility or {},
            "safety": place.safety or {},
            "tags": place.tags or [],
            "media": [media_payload(m, uploaders.get(m.user_id or -1)) for m in media_rows],
            "pulse": pulse_summary(session, pid, now),
            "maps_url": maps_url(place, english_name(session, pid), city_name) if not redact else None,
            "osm_url": osm_url(place) if not redact else None,
            "regional_langs": regional_langs(place.state),
            "added_remotely": place.added_remotely,
        }
    )
    return payload


def visits_caused(session: Session, creator_id: int, since: datetime | None = None) -> float:
    """Sum of attribution shares for a creator -- the Studio headline metric."""
    query = select(func.coalesce(func.sum(Attribution.share), 0.0)).where(
        Attribution.creator_id == creator_id
    )
    if since is not None:
        query = query.join(Visit, Visit.id == Attribution.visit_id).where(Visit.at >= since)
    return float(session.exec(query).one() or 0.0)
