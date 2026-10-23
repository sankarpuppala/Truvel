"""Check-in, Pulse, last-mile steps and user-added names.

Check-in (SPEC §8.7) is where the privacy invariant is load-bearing: the request
body carries `{lat, lng, accuracy}`, and the handler turns them into
`distance_m`, `accuracy_m`, `verified` and `flag` **before** anything is
written. The coordinates live in local variables for the length of one function
call and are never logged (CLAUDE.md invariant 1).

A successful first check-in also runs visit attribution (§9.9) and may promote a
community place to `verified` and pay its discoverer (§9.8).
"""
from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import kadam, services
from ..auth import current_user, require_csrf_header
from ..config import cfg, dev_allow_fake_location
from ..db import get_session
from ..errors import bad_request, forbidden, not_found, too_many
from ..geo import haversine_m
from ..integrity.fraud import PriorVisit, impossible_travel, place_can_verify, rate_limited
from ..models import (
    Attribution,
    LastMileStep,
    LastMileVote,
    Place,
    PlaceName,
    Pulse,
    Touch,
    User,
    Visit,
    utcnow,
)
from ..partner.attribution import TouchRow, attribute
from ..ranking.wilson import wilson_lb

router = APIRouter(tags=["checkin"], dependencies=[Depends(require_csrf_header)])

WATER_CATEGORIES = {"waterfall", "lake", "beach_river"}

# FastAPI runs a sync `def` route in a thread pool, so two check-ins from the
# same person for the same place can genuinely overlap: both can read "no
# visit today yet" before either has committed its Visit row, and both then
# pass every award/attribution check meant to run once. A per-(user, place)
# lock makes the whole read-then-write section below atomic within this one
# process -- the only process this app ever runs as (CLAUDE.md: SQLite file,
# no Postgres/Redis). It does not need to survive restarts or span processes.
_checkin_locks: dict[tuple[int, int], threading.Lock] = defaultdict(threading.Lock)
_checkin_locks_guard = threading.Lock()


def _lock_for(user_id: int, place_id: int) -> threading.Lock:
    key = (user_id, place_id)
    with _checkin_locks_guard:
        return _checkin_locks[key]


class CheckinIn(BaseModel):
    lat: float
    lng: float
    accuracy: float = Field(ge=0)
    simulated: bool = False


@router.post("/places/{place_id}/checkin")
def check_in(
    place_id: int,
    body: CheckinIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Verify a visit from one position reading. Coordinates are not stored.

    Held for the length of the real work below so two overlapping requests
    for the same (user, place) -- two tabs, a double-tap, a scripted retry --
    cannot both read "no visit yet today" before either has written one.
    """
    with _lock_for(int(user.id), place_id):
        return _check_in_locked(place_id, body, session, user)


def _check_in_locked(
    place_id: int,
    body: CheckinIn,
    session: DbSession,
    user: User,
) -> dict:
    place = session.get(Place, place_id)
    if place is None or place.status == "hidden":
        raise not_found("That place is not here.", "no_place")

    now = utcnow()
    since = now - timedelta(hours=1)
    attempts = int(
        session.exec(
            select(func.count())
            .select_from(Visit)
            .where(Visit.user_id == user.id, Visit.at >= since)
        ).one()
        or 0
    )
    if rate_limited(attempts, "checkins_per_hour"):
        raise too_many("Too many check-in attempts this hour.")

    # A simulated check-in is only possible when the server was started with the
    # flag, and the resulting visit is marked and excluded from everything that
    # matters (SPEC §8.7, AC-25).
    simulated = bool(body.simulated) and dev_allow_fake_location()
    if body.simulated and not dev_allow_fake_location():
        raise forbidden("Simulated location is not enabled.", "no_fake_location")

    # --- the only place the coordinates are used -------------------------- #
    distance_m = haversine_m(body.lat, body.lng, place.lat, place.lng)
    accuracy_m = float(body.accuracy)
    # ---------------------------------------------------------------------- #

    min_radius = float(cfg("verification.min_radius_m", 150))
    max_accuracy = float(cfg("verification.max_accuracy_m", 100))
    allowed_m = max(float(place.radius_m), min_radius)

    verified = distance_m <= allowed_m and accuracy_m <= max_accuracy

    # Impossible travel: compare with the user's previous visit (SPEC §9.8).
    previous = session.exec(
        select(Visit).where(Visit.user_id == user.id).order_by(Visit.at.desc()).limit(1)
    ).first()
    flag = None
    if previous is not None:
        prev_place = session.get(Place, previous.place_id)
        if prev_place is not None and impossible_travel(
            PriorVisit(at=previous.at, lat=prev_place.lat, lng=prev_place.lng),
            now,
            place.lat,
            place.lng,
        ):
            flag = "speed"

    # One verified visit per user per place per day (SPEC §8.7).
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    already_today = session.exec(
        select(Visit).where(
            Visit.user_id == user.id,
            Visit.place_id == place_id,
            Visit.at >= day_start,
            Visit.verified == True,  # noqa: E712
        )
    ).first()

    if not verified:
        if accuracy_m > max_accuracy:
            message = (
                f"Your phone isn't sure where you are (±{int(accuracy_m)} m). "
                "Step into open sky and try again."
            )
            code = "poor_accuracy"
        else:
            km = distance_m / 1000.0
            how_far = f"{km:.1f} km" if km >= 1 else f"{int(distance_m)} m"
            message = f"You're {how_far} away. Check in when you get there."
            code = "too_far"
        session.add(
            Visit(
                user_id=int(user.id),
                place_id=place_id,
                at=now,
                distance_m=distance_m,
                accuracy_m=accuracy_m,
                verified=False,
                flag=flag,
                simulated=simulated,
            )
        )
        session.commit()
        return {
            "verified": False,
            "code": code,
            "message": message,
            "distance_m": round(distance_m),
            "accuracy_m": round(accuracy_m),
        }

    if already_today is not None:
        return {
            "verified": True,
            "code": "already_today",
            "message": "You already checked in here today.",
            "kadam": 0,
            "first_visit": False,
            "distance_m": round(distance_m),
        }

    is_first_ever = (
        session.exec(
            select(Visit).where(
                Visit.user_id == user.id,
                Visit.place_id == place_id,
                Visit.verified == True,  # noqa: E712
            )
        ).first()
        is None
    )

    visit = Visit(
        user_id=int(user.id),
        place_id=place_id,
        at=now,
        distance_m=distance_m,
        accuracy_m=accuracy_m,
        verified=True,
        flag=flag,
        simulated=simulated,
    )
    session.add(visit)
    session.commit()
    session.refresh(visit)

    awarded = 0
    attributed: dict[int, float] = {}
    place_verified_now = False

    # A flagged or simulated visit earns nothing, verifies nothing and
    # attributes to nobody (SPEC §8.7, §9.8, AC-25).
    if flag is None and not simulated:
        awarded = kadam.award(
            session,
            int(user.id),
            kadam.OWN_VISIT,
            ref_type="place",
            ref_id=place_id,
            now=now,
        )

        if is_first_ever:
            attributed = _run_attribution(session, visit, int(user.id), place_id, now)

        if place.status != "verified" and place.source == "community":
            visits = [
                {
                    "user_id": v.user_id,
                    "verified": v.verified,
                    "flag": v.flag,
                    "simulated": v.simulated,
                }
                for v in session.exec(select(Visit).where(Visit.place_id == place_id)).all()
            ]
            if place_can_verify(place.added_by, visits):
                place.status = "verified"
                place.updated_at = now
                session.add(place)
                session.commit()
                place_verified_now = True
                if place.added_by:
                    kadam.award(
                        session,
                        int(place.added_by),
                        kadam.DISCOVERY,
                        ref_type="place",
                        ref_id=place_id,
                        now=now,
                    )

    can_pulse = True
    return {
        "verified": True,
        "code": "ok",
        "message": "You're here!",
        "kadam": awarded,
        "first_visit": is_first_ever,
        "flag": flag,
        "simulated": simulated,
        "visit_id": visit.id,
        "distance_m": round(distance_m),
        "place_verified": place_verified_now,
        "attributed": [{"creator_id": c, "share": round(s, 6)} for c, s in attributed.items()],
        "can_pulse": can_pulse,
        "stamp": {
            "place_id": place_id,
            "name": services.english_name(session, place_id),
            "category": place.category,
            "date": now.date().isoformat(),
        },
    }


def _run_attribution(
    session: DbSession, visit: Visit, user_id: int, place_id: int, now: datetime
) -> dict[int, float]:
    """Split one visit between the creators whose content led to it (§9.9)."""
    lookback = int(cfg("attribution.lookback_days", 30))
    window_start = now - timedelta(days=lookback)
    rows = session.exec(
        select(Touch).where(
            Touch.user_id == user_id,
            Touch.place_id == place_id,
            Touch.at >= window_start,
        )
    ).all()
    touches = [
        TouchRow(
            creator_id=int(t.creator_id),
            at=t.at,
            content_type=t.content_type,
            content_id=t.content_id,
            invalid_reason=t.invalid_reason,
        )
        for t in rows
    ]
    shares = attribute(touches, user_id, now)
    for creator_id, share in shares.items():
        session.add(
            Attribution(visit_id=int(visit.id), creator_id=int(creator_id), share=float(share))
        )
    session.commit()

    # Kadam for visits caused: whole visits only, so fractional shares are
    # summed per creator per day and rounded (SPEC §10.1).
    for creator_id, share in shares.items():
        whole = int(round(share))
        if whole > 0:
            kadam.award(
                session,
                int(creator_id),
                kadam.VISIT_CAUSED,
                ref_type="place",
                ref_id=place_id,
                amount=int(cfg("kadam.visit_caused", 10)) * whole,
                now=now,
            )
    return shares


# --------------------------------------------------------------------------- #
# Pulse (SPEC §8.8)
# --------------------------------------------------------------------------- #

class PulseIn(BaseModel):
    water: str | None = None
    crowd: str | None = None
    path: str | None = None
    open: str | None = None
    note: str = Field(default="", max_length=80)
    media_id: int | None = None


PULSE_VALUES = {
    "water": {"flowing", "low", "dry"},
    "crowd": {"quiet", "busy", "packed"},
    "path": {"dry", "muddy", "flooded", "closed"},
    "open": {"yes", "closed_today"},
}


@router.get("/places/{place_id}/pulse")
def get_pulse(place_id: int, session: DbSession = Depends(get_session)) -> dict:
    summary = services.pulse_summary(session, place_id)
    return {"pulse": summary}


@router.post("/places/{place_id}/pulse")
def post_pulse(
    place_id: int,
    body: PulseIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Post live conditions. Only from someone who was just there (SPEC §8.8)."""
    place = session.get(Place, place_id)
    if place is None or place.status == "hidden":
        raise not_found("That place is not here.", "no_place")

    now = utcnow()
    since = now - timedelta(hours=1)
    recent_pulses = int(
        session.exec(
            select(func.count())
            .select_from(Pulse)
            .where(Pulse.user_id == user.id, Pulse.at >= since)
        ).one()
        or 0
    )
    if rate_limited(recent_pulses, "pulse_per_hour"):
        raise too_many("Too many reports this hour.")

    window_h = float(cfg("pulse.visit_window_hours", 2))
    visit = session.exec(
        select(Visit)
        .where(
            Visit.user_id == user.id,
            Visit.place_id == place_id,
            Visit.verified == True,  # noqa: E712
            Visit.flag == None,  # noqa: E711
            Visit.simulated == False,  # noqa: E712
            Visit.at >= now - timedelta(hours=window_h),
        )
        .order_by(Visit.at.desc())
        .limit(1)
    ).first()
    if visit is None:
        raise forbidden(
            f"Only people who checked in here in the last {int(window_h)} hours can report.",
            "no_recent_visit",
        )

    for field_name, allowed in PULSE_VALUES.items():
        value = getattr(body, field_name)
        if value is not None and value not in allowed:
            raise bad_request(f"Unknown value for {field_name}.", "bad_pulse")

    # Water only applies to water places.
    water = body.water if place.category in WATER_CATEGORIES else None

    if not any([water, body.crowd, body.path, body.open, body.note.strip()]):
        raise bad_request("Tell us at least one thing.", "empty_pulse")

    session.add(
        Pulse(
            place_id=place_id,
            user_id=int(user.id),
            at=now,
            water=water,
            crowd=body.crowd,
            path=body.path,
            open=body.open,
            note=body.note.strip()[:80],
            media_id=body.media_id,
            visit_id=visit.id,
        )
    )
    session.commit()

    awarded = kadam.award(session, int(user.id), kadam.PULSE, ref_type="place", ref_id=place_id, now=now)
    return {"posted": True, "kadam": awarded, "pulse": services.pulse_summary(session, place_id, now)}


# --------------------------------------------------------------------------- #
# Last-mile steps (SPEC §8.5)
# --------------------------------------------------------------------------- #

class StepIn(BaseModel):
    text: str = Field(min_length=3, max_length=140)
    media_id: int | None = None


class StepsIn(BaseModel):
    steps: list[StepIn] = Field(min_length=1, max_length=10)


@router.get("/places/{place_id}/steps")
def get_steps(
    place_id: int,
    session: DbSession = Depends(get_session),
    user: User | None = None,
) -> dict:
    """All versions, best first by the Wilson score of their helpful votes.

    Why Wilson again: a version with 3 of 3 helpful votes should not outrank one
    with 48 of 52 just because it is unanimous so far (SPEC §8.5).
    """
    place = session.get(Place, place_id)
    if place is None:
        raise not_found("That place is not here.", "no_place")
    # Fragile places withhold steps until the pledge (invariant 5, AC-15).
    if place.fragile and not services.is_pledged(session, place_id, user):
        return {"locked": True, "versions": []}

    rows = list(
        session.exec(
            select(LastMileStep)
            .where(LastMileStep.place_id == place_id, LastMileStep.status == "ok")
            .order_by(LastMileStep.version_group, LastMileStep.order)
        ).all()
    )
    groups: dict[str, list[LastMileStep]] = {}
    for row in rows:
        groups.setdefault(row.version_group, []).append(row)

    versions = []
    for group, steps in groups.items():
        votes = list(
            session.exec(select(LastMileVote).where(LastMileVote.version_group == group)).all()
        )
        helpful = sum(1 for v in votes if v.helpful)
        author = session.get(User, steps[0].author_id)
        versions.append(
            {
                "version_group": group,
                "author": (
                    {"id": author.id, "username": author.username} if author else None
                ),
                "helpful": helpful,
                "votes": len(votes),
                "score": round(wilson_lb(helpful, len(votes)), 4),
                "steps": [
                    {"order": s.order, "text": s.text, "media_id": s.media_id} for s in steps
                ],
            }
        )
    versions.sort(key=lambda v: (-v["score"], -v["helpful"]))
    return {"locked": False, "versions": versions}


@router.post("/places/{place_id}/steps")
def add_steps(
    place_id: int,
    body: StepsIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Write a new version of the last-mile directions."""
    place = session.get(Place, place_id)
    if place is None:
        raise not_found("That place is not here.", "no_place")
    group = str(uuid.uuid4())
    for index, step in enumerate(body.steps, start=1):
        session.add(
            LastMileStep(
                place_id=place_id,
                author_id=int(user.id),
                version_group=group,
                order=index,
                text=step.text.strip()[:140],
                media_id=step.media_id,
            )
        )
    session.commit()
    return {"version_group": group}


class VoteIn(BaseModel):
    helpful: bool


@router.post("/steps/{group}/vote")
def vote_steps(
    group: str,
    body: VoteIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """One vote per user per version. Helpful votes pay the author (SPEC §10.1)."""
    first = session.exec(
        select(LastMileStep).where(LastMileStep.version_group == group).limit(1)
    ).first()
    if first is None:
        raise not_found("No such directions.", "no_steps")
    if first.author_id == user.id:
        raise forbidden("You can't vote on your own directions.", "self_vote")

    existing = session.exec(
        select(LastMileVote).where(
            LastMileVote.user_id == user.id, LastMileVote.version_group == group
        )
    ).first()
    now = utcnow()
    if existing is None:
        session.add(
            LastMileVote(user_id=int(user.id), version_group=group, helpful=body.helpful, at=now)
        )
        session.commit()
        if body.helpful:
            kadam.award(
                session,
                int(first.author_id),
                kadam.STEPS_HELPFUL,
                ref_type="steps",
                ref_id=first.id,
                now=now,
            )
    else:
        existing.helpful = body.helpful
        session.add(existing)
        session.commit()

    votes = list(session.exec(select(LastMileVote).where(LastMileVote.version_group == group)).all())
    helpful = sum(1 for v in votes if v.helpful)
    return {"helpful": helpful, "votes": len(votes), "score": round(wilson_lb(helpful, len(votes)), 4)}


# --------------------------------------------------------------------------- #
# Names in your language (SPEC §7.2)
# --------------------------------------------------------------------------- #

class PlaceNameIn(BaseModel):
    lang: str
    name: str = Field(min_length=1, max_length=120)


@router.get("/places/{place_id}/names")
def list_names(place_id: int, session: DbSession = Depends(get_session)) -> dict:
    rows = session.exec(select(PlaceName).where(PlaceName.place_id == place_id)).all()
    return {
        "names": [
            {
                "id": r.id,
                "lang": r.lang,
                "name": r.name,
                "source": r.source,
                "votes": r.votes,
            }
            for r in rows
        ]
    }


@router.post("/places/{place_id}/names")
def add_name(
    place_id: int,
    body: PlaceNameIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Add a name in your language. Needs a verified visit (SPEC §7.2)."""
    place = session.get(Place, place_id)
    if place is None:
        raise not_found("That place is not here.", "no_place")
    if body.lang not in (cfg("languages") or []):
        raise bad_request("We don't have that language yet.", "bad_lang")

    visited = session.exec(
        select(Visit).where(
            Visit.user_id == user.id,
            Visit.place_id == place_id,
            Visit.verified == True,  # noqa: E712
            Visit.flag == None,  # noqa: E711
        )
    ).first()
    if visited is None:
        raise forbidden(
            "Only people who have checked in here can add a name.", "no_visit"
        )

    existing = session.exec(
        select(PlaceName).where(
            PlaceName.place_id == place_id,
            PlaceName.lang == body.lang,
            PlaceName.source == "user",
        )
    ).first()
    if existing is not None:
        # Someone already proposed a user name in this language: vote it up
        # rather than creating a second row (the table is unique on these three).
        existing.votes += 1
        session.add(existing)
        session.commit()
        return {"added": False, "voted": True, "votes": existing.votes}

    session.add(
        PlaceName(place_id=place_id, lang=body.lang, name=body.name.strip(), source="user", votes=1)
    )
    session.commit()
    return {"added": True, "voted": False, "votes": 1}
