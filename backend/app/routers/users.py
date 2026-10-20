"""Public creator profiles (SPEC §8.9)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import kadam, services
from ..auth import current_user_optional
from ..db import get_session
from ..errors import not_found
from ..models import Follow, Media, Place, User, utcnow
from ..partner.eligibility import EligibilityInput, is_eligible
from ..routers.studio import engaged_views_for, verified_content_count

router = APIRouter(tags=["users"])


@router.get("/users/{handle}")
def profile(
    handle: str,
    session: DbSession = Depends(get_session),
    viewer: User | None = Depends(current_user_optional),
) -> dict:
    creator = session.exec(select(User).where(User.username == handle.lower())).first()
    if creator is None:
        raise not_found("No such creator.", "no_user")

    now = utcnow()
    cid = int(creator.id)
    followers = int(
        session.exec(select(func.count()).select_from(Follow).where(Follow.creator_id == cid)).one()
        or 0
    )
    found = list(
        session.exec(
            select(Place)
            .where(Place.added_by == cid, Place.status != "hidden")
            .order_by(Place.created_at.desc())
        ).all()
    )
    videos = list(
        session.exec(
            select(Media)
            .where(Media.user_id == cid, Media.kind == "video", Media.status == "ok")
            .order_by(Media.created_at.desc())
            .limit(24)
        ).all()
    )
    caused = services.visits_caused(session, cid)

    from datetime import timedelta

    since_90 = now - timedelta(days=90)
    media_ids = [
        int(m.id)
        for m in session.exec(
            select(Media).where(Media.user_id == cid, Media.status == "ok")
        ).all()
    ]
    partner = is_eligible(
        EligibilityInput(
            account_created_at=creator.created_at,
            strikes=creator.strikes,
            verified_content=verified_content_count(session, cid),
            visits_caused_90d=services.visits_caused(session, cid, since_90),
            engaged_views_90d=engaged_views_for(session, media_ids, since_90),
        ),
        now,
    )

    following = False
    if viewer is not None:
        following = (
            session.exec(
                select(Follow.id).where(Follow.follower_id == viewer.id, Follow.creator_id == cid)
            ).first()
            is not None
        )

    balance = kadam.balance(session, cid)
    level_name, _, _, _ = kadam.level(balance)

    return {
        "id": cid,
        "username": creator.username,
        "display_name": creator.display_name or creator.username,
        "bio": creator.bio,
        "level": level_name,
        "followers": followers,
        "following": following,
        "is_self": viewer is not None and int(viewer.id) == cid,
        "places_found": len(found),
        "visits_caused": round(caused, 1),
        "partner": partner,
        "found": [services.place_payload(session, p, viewer, now=now) for p in found[:12]],
        "videos": [services.media_payload(m, creator) for m in videos],
        "created_at": creator.created_at.isoformat(),
    }
