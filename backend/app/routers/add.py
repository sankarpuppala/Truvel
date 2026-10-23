"""Adding places and media (SPEC §8.6).

Three things happen on the server that the client cannot be trusted to do:

* **Duplicate detection** (§9.6) against every name of every nearby place.
* **On-site verification** (§8.7): a place added within 300 m at <= 100 m
  accuracy is an on-site add; anything else is "added from elsewhere" and stays
  `unverified` until two other people check in.
* **pHash** (§9.7) and the EXIF-free re-encode (invariant 2) on every photo.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from sqlalchemy import delete as sa_delete
from sqlalchemy import update as sa_update
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import media_store, services
from ..auth import can_post, current_user, require_csrf_header
from ..config import cfg
from ..db import get_session
from ..errors import bad_request, conflict, forbidden, not_found, too_many
from ..geo import bbox_around, haversine_m
from ..integrity.dedupe import find_duplicates, name_similarity
from ..integrity.exif import GPS_MISMATCH, gps_mismatch
from ..integrity.fraud import rate_limited
from ..integrity.phash import check_upload
from ..models import (
    LastMileStep,
    Media,
    MediaLike,
    MediaView,
    Place,
    PlaceName,
    Pulse,
    Report,
    User,
    utcnow,
)

router = APIRouter(tags=["add"], dependencies=[Depends(require_csrf_header)])

CATEGORIES = (
    "viewpoint",
    "waterfall",
    "lake",
    "hill_trek",
    "fort_heritage",
    "temple_sacred",
    "park_garden",
    "museum_art",
    "market_street",
    "beach_river",
    "other",
)

SAFETY_KEYS = (
    "steep_edge",
    "water_danger",
    "slippery_in_monsoon",
    "no_mobile_signal",
    "isolated",
    "wildlife",
    "permit_needed",
    "sacred",
)


class CandidatesIn(BaseModel):
    lat: float
    lng: float
    name: str = ""
    category: str = "other"


def _nearby_for_dedupe(session: DbSession, lat: float, lng: float) -> list[dict]:
    """Places within the dedupe radius, as plain dicts with every name they have."""
    radius_m = float(cfg("dedupe.radius_m", 300))
    box = bbox_around(lat, lng, radius_m / 1000.0 * 1.2)
    places = session.exec(
        select(Place).where(
            Place.status != "hidden",
            Place.lat.between(box[0], box[2]),
            Place.lng.between(box[1], box[3]),
        )
    ).all()
    return [
        {
            "id": int(place.id),
            "lat": place.lat,
            "lng": place.lng,
            "category": place.category,
            "names": [r.name for r in services.name_rows(session, int(place.id))],
        }
        for place in places
    ]


def _refuse_certain_duplicate(session: DbSession, body: "PlaceIn") -> None:
    """Refuse a place that is the same one again, whatever the client did.

    The "Is it one of these?" prompt (SPEC §9.6) is a courtesy that a modified
    client can skip, so the server also checks. Only a near-certain match is
    refused: a name that matches in any language at the `dedupe.certain_name_sim`
    score, within `dedupe.certain_radius_m`. Anything vaguer is left to the
    person, because refusing a genuinely different place loses a find.
    """
    certain_sim = int(cfg("dedupe.certain_name_sim", 90))
    certain_m = float(cfg("dedupe.certain_radius_m", 150))
    certain_raw = int(cfg("dedupe.certain_raw_sim", 72))
    typed = [body.name, *(n.name for n in body.names)]
    for place in _nearby_for_dedupe(session, body.lat, body.lng):
        if haversine_m(body.lat, body.lng, place["lat"], place["lng"]) > certain_m:
            continue
        # token_set_ratio alone calls "Golconda Fort" and "Golconda Jail" identical
        # (both reduce to "golconda"), so a ratio that keeps every word must agree too
        # (token_sort ignores word order but not missing words).
        raw = max(
            fuzz.token_sort_ratio(name.lower().strip(), other.lower().strip())
            for name in typed
            for other in place["names"]
        )
        if max(name_similarity(name, place["names"]) for name in typed) >= certain_sim and (
            raw >= certain_raw
        ):
            raise conflict(
                "This place is already on Truvel. Open it and add your photos there.",
                "duplicate_place",
                {"place_id": place["id"]},
            )


@router.post("/places/candidates")
def duplicate_candidates(
    body: CandidatesIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """"Is it one of these?" -- up to 3 likely duplicates (SPEC §9.6).

    Runs as the pin moves, so it is a bbox query plus in-memory string work: no
    scan of the whole table.
    """
    nearby = _nearby_for_dedupe(session, body.lat, body.lng)

    found = find_duplicates(body.lat, body.lng, body.name, body.category, nearby)
    out = []
    for cand in found:
        place = session.get(Place, cand.place_id)
        if place is None:
            continue
        payload = services.place_payload(session, place, user, lat=body.lat, lng=body.lng)
        payload["distance_m"] = round(cand.distance_m)
        payload["name_sim"] = cand.name_sim
        payload["reason"] = cand.reason
        out.append(payload)
    return {"candidates": out}


class NameIn(BaseModel):
    lang: str
    name: str = Field(min_length=1, max_length=120)


class PlaceIn(BaseModel):
    lat: float
    lng: float
    accuracy_m: float | None = None
    name: str = Field(min_length=2, max_length=120)
    names: list[NameIn] = Field(default_factory=list)
    category: str = "other"
    description: str = Field(default="", max_length=600)
    activities: list[str] = Field(default_factory=list)
    best_time: dict = Field(default_factory=dict)
    entry_fee_text: str = Field(default="", max_length=120)
    timings_text: str = Field(default="", max_length=120)
    access: dict = Field(default_factory=dict)
    accessibility: dict = Field(default_factory=dict)
    safety: dict = Field(default_factory=dict)
    fragile: bool = False
    media_ids: list[int] = Field(default_factory=list)
    city_id: int | None = None


@router.post("/places")
def create_place(
    body: PlaceIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Create a community place. Always starts `unverified` (SPEC §8.6)."""
    if not can_post(user):
        raise forbidden("Your account can't post right now.", "blocked")
    if body.category not in CATEGORIES:
        raise bad_request("Pick a category from the list.", "bad_category")
    _refuse_certain_duplicate(session, body)

    now = utcnow()
    # On-site add? Within 300 m of the pin at <= 100 m accuracy (SPEC §8.7).
    max_accuracy = float(cfg("verification.max_accuracy_m", 100))
    on_site = body.accuracy_m is not None and body.accuracy_m <= max_accuracy

    city_id = body.city_id
    state = None
    if city_id:
        from ..models import City

        city = session.get(City, city_id)
        if city is not None:
            state = city.state
    if state is None:
        from ..models import City

        # Fall back to whichever seeded city's bbox contains the pin.
        for city in session.exec(select(City)).all():
            bbox = city.bbox or []
            if len(bbox) == 4 and bbox[0] <= body.lat <= bbox[2] and bbox[1] <= body.lng <= bbox[3]:
                city_id, state = city.id, city.state
                break

    place = Place(
        city_id=city_id,
        state=state,
        lat=body.lat,
        lng=body.lng,
        category=body.category,
        source="community",
        fame="hidden",                      # community-added, not in OSM/Wikidata (§6.7)
        status="unverified",                # always; 2 check-ins promote it (§9.8)
        fragile=bool(body.fragile),
        added_by=int(user.id),
        added_remotely=not on_site,
        description=body.description.strip(),
        activities=[a[:40] for a in body.activities][:8],
        best_time=body.best_time or {},
        entry_fee_text=body.entry_fee_text.strip(),
        timings_text=body.timings_text.strip(),
        access=body.access or {},
        accessibility=body.accessibility or {},
        safety={k: body.safety.get(k, "unknown") for k in SAFETY_KEYS}
        | ({"women_safety_note": str(body.safety.get("women_safety_note", ""))[:300]}
           if body.safety.get("women_safety_note") else {}),
        created_at=now,
        updated_at=now,
    )
    session.add(place)
    session.commit()
    session.refresh(place)

    # The typed name is an English-language user name unless they said otherwise.
    session.add(
        PlaceName(place_id=int(place.id), lang="en", name=body.name.strip(), source="user", votes=0)
    )
    for extra in body.names[:10]:
        if extra.lang == "en":
            continue
        session.add(
            PlaceName(
                place_id=int(place.id),
                lang=extra.lang,
                name=extra.name.strip(),
                source="user",
                votes=0,
            )
        )
    # Attach media uploaded in step 1, which had no place id yet.
    for media_id in body.media_ids[:12]:
        media = session.get(Media, media_id)
        if media is not None and media.user_id == user.id and media.place_id == 0:
            media.place_id = int(place.id)
            media.shot_here = on_site
            session.add(media)
    session.commit()

    needed = int(cfg("verification.verify_visits_needed", 2))
    discovery = int(cfg("kadam.discovery", 50))
    return {
        "place": services.place_payload(session, place, user, full=True, now=now),
        "on_site": on_site,
        "message": (
            f"You'll get {discovery} kadam when {needed} people confirm it."
            if True
            else ""
        ),
    }


def _hourly_uploads(session: DbSession, user_id: int, now: datetime) -> int:
    since = now - timedelta(hours=1)
    return int(
        session.exec(
            select(func.count())
            .select_from(Media)
            .where(Media.user_id == user_id, Media.created_at >= since)
        ).one()
        or 0
    )


@router.post("/places/{place_id}/media")
async def upload_media(
    place_id: int,
    file: UploadFile = File(...),
    poster: UploadFile | None = File(None),
    kind: str = Form("photo"),
    caption: str = Form(""),
    lang: str = Form("en"),
    duration_s: float = Form(0.0),
    exif_lat: float | None = Form(None),
    exif_lng: float | None = Form(None),
    on_site: bool = Form(False),
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Upload a photo or video to a place (SPEC §8.6, §9.7).

    `place_id` 0 is allowed: step 1 of "Add a new place" uploads before the
    place exists, and `POST /places` attaches the media afterwards.
    """
    if not can_post(user):
        raise forbidden("Your account can't post right now.", "blocked")
    now = utcnow()
    if rate_limited(_hourly_uploads(session, int(user.id), now), "uploads_per_hour"):
        raise too_many("That's a lot of uploads in an hour. Try again shortly.")

    place = None
    if place_id:
        place = session.get(Place, place_id)
        if place is None or place.status == "hidden":
            raise not_found("That place is not here.", "no_place")

    caption = (caption or "").strip()
    if not caption:
        # Captions are alt text, and alt text is required (SPEC §13).
        raise bad_request("Add a caption -- it is the photo's alt text.", "caption_required")
    caption = caption[: int(cfg("media.caption_max_chars", 150))]

    data = await file.read()
    if not data:
        raise bad_request("That file is empty.", "empty_file")

    if kind == "video":
        if poster is None:
            raise bad_request("A video needs a poster frame.", "poster_required")
        poster_bytes = await poster.read()
        stored = media_store.process_video(data, poster_bytes, duration_s, now)
        new_hash = stored.phash
    else:
        stored_photo = media_store.process_photo(data, now)
        stored = stored_photo
        new_hash = stored_photo.phash

    # pHash against everything we hold (SPEC §9.7).
    existing = [
        {"id": m.id, "phash": m.phash, "user_id": m.user_id, "place_id": m.place_id}
        for m in session.exec(
            select(Media).where(Media.phash != None, Media.status == "ok")  # noqa: E711
        ).all()
    ]
    verdict = check_upload(new_hash, int(user.id), place_id, existing)
    if verdict.action == "reject":
        raise bad_request(verdict.message, "duplicate_photo", {"media_id": verdict.matched_media_id})
    if verdict.action == "skip":
        return {"media": None, "skipped": True, "message": verdict.message}

    media = Media(
        place_id=place_id,
        user_id=int(user.id),
        kind="video" if kind == "video" else "photo",
        caption=caption,
        lang=lang or "en",
        source="upload",
        shot_here=bool(on_site),
        phash=new_hash,
        created_at=now,
    )
    if kind == "video":
        media.path_display = stored.path_display
        media.path_poster = stored.path_poster
        media.path_thumb = stored.path_thumb
        media.duration_s = stored.duration_s
    else:
        media.path_display = stored.path_display
        media.path_thumb = stored.path_thumb
        media.width = stored.width
        media.height = stored.height

    warning = None
    if place is not None and gps_mismatch(exif_lat, exif_lng, place.lat, place.lng):
        # Not a rejection: EXIF can be wrong, and we would rather flag for
        # review than refuse a real photo (SPEC §9.7).
        warning = GPS_MISMATCH

    session.add(media)
    session.commit()
    session.refresh(media)

    if warning == GPS_MISMATCH:
        # Recorded as a report so it lands in the admin queue for review.
        session.add(
            Report(
                reporter_id=int(user.id),
                target_type="media",
                target_id=int(media.id),
                reason="wrong_location",
                note="EXIF GPS more than 2 km from the pin",
            )
        )
        session.commit()
    return {"media": services.media_payload(media, user), "warning": warning}


@router.delete("/media/{media_id}")
def delete_media(
    media_id: int,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Remove your own photo or video, and its files from disk.

    Only the person who uploaded it (or an admin) may. Commons photos are not
    ours to delete. Kadam already earned stays in the ledger: the ledger is
    append-only (invariant 4), so deleting a post never rewrites history.
    """
    media = session.get(Media, media_id)
    if media is None or media.source != "upload":
        raise not_found("That upload is not here.", "no_media")
    if media.user_id != user.id and not user.official:
        raise forbidden("You can only delete your own uploads.", "not_yours")

    # Children first: bulk deletes run in the order written.
    for related in (MediaLike, MediaView):
        session.exec(sa_delete(related).where(related.media_id == media_id))
    for model, column in ((Pulse, Pulse.media_id), (LastMileStep, LastMileStep.media_id)):
        session.exec(sa_update(model).where(column == media_id).values(media_id=None))
    session.exec(sa_update(User).where(User.avatar_media_id == media_id).values(avatar_media_id=None))

    root = media_store.media_root()
    for rel in (media.path_display, media.path_poster, media.path_thumb):
        target = root / rel if rel else None
        if target is not None and target.is_file():
            target.unlink()
    session.exec(sa_delete(Media).where(Media.id == media_id))
    session.commit()
    return {"ok": True}
