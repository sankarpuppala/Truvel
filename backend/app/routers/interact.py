"""Likes, saves, follows, reports and touches (SPEC §8.11, §8.13, §9.9).

The rules that matter here are the self-dealing bans and the `likes <= viewers`
invariant: liking a place implies you have seen it, so a like creates the View
row if there is not one already (AC-9). Without that, a place could show 5 likes
from 3 viewers and Wilson's bound would exceed 1.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import kadam
from ..auth import current_user, require_csrf_header
from ..config import cfg
from ..db import get_session
from ..errors import bad_request, forbidden, not_found, too_many
from ..integrity.fraud import rate_limited
from ..models import (
    Follow,
    Like,
    Media,
    MediaLike,
    Place,
    Report,
    Save,
    Touch,
    User,
    View,
    utcnow,
)

router = APIRouter(tags=["interact"], dependencies=[Depends(require_csrf_header)])

REPORT_REASONS = {
    "wrong_location",
    "wrong_name",
    "wrong_info",
    "closed_or_gone",
    "private_property",
    "unsafe",
    "offensive",
    "stolen_photo",
    "photo_of_me",
    "spam",
    "duplicate",
    "other",
}


def _hourly_count(session: DbSession, model, user_id: int, column, now: datetime) -> int:
    since = now - timedelta(hours=1)
    return int(
        session.exec(
            select(func.count()).select_from(model).where(column == user_id, model.at >= since)
        ).one()
        or 0
    )


@router.post("/places/{place_id}/like")
def like_place(
    place_id: int,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    place = session.get(Place, place_id)
    if place is None or place.status == "hidden":
        raise not_found("That place is not here.", "no_place")
    if place.added_by == user.id and not user.official:
        raise forbidden("You can't like your own place.", "self_like")

    now = utcnow()
    if rate_limited(_hourly_count(session, Like, int(user.id), Like.user_id, now), "likes_per_hour"):
        raise too_many("That's a lot of likes in an hour. Try again shortly.")

    existing = session.exec(
        select(Like).where(Like.user_id == user.id, Like.place_id == place_id)
    ).first()
    if existing is None:
        # A like implies a view: keeps likes <= viewers true (AC-9).
        seen = session.exec(
            select(View).where(View.user_id == user.id, View.place_id == place_id)
        ).first()
        if seen is None:
            session.add(View(user_id=int(user.id), place_id=place_id, first_seen_at=now))
        session.add(Like(user_id=int(user.id), place_id=place_id, at=now))
        session.commit()
        if place.added_by:
            kadam.award(
                session,
                int(place.added_by),
                kadam.LIKE_RECEIVED,
                ref_type="place",
                ref_id=place_id,
                now=now,
            )

    likes = int(
        session.exec(select(func.count()).select_from(Like).where(Like.place_id == place_id)).one()
        or 0
    )
    return {"liked": True, "likes": likes}


@router.delete("/places/{place_id}/like")
def unlike_place(
    place_id: int,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    existing = session.exec(
        select(Like).where(Like.user_id == user.id, Like.place_id == place_id)
    ).first()
    if existing is not None:
        session.delete(existing)
        session.commit()
    likes = int(
        session.exec(select(func.count()).select_from(Like).where(Like.place_id == place_id)).one()
        or 0
    )
    return {"liked": False, "likes": likes}


@router.post("/places/{place_id}/save")
def save_place(
    place_id: int,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    place = session.get(Place, place_id)
    if place is None or place.status == "hidden":
        raise not_found("That place is not here.", "no_place")
    existing = session.exec(
        select(Save).where(Save.user_id == user.id, Save.place_id == place_id)
    ).first()
    if existing is None:
        session.add(Save(user_id=int(user.id), place_id=place_id))
        session.commit()
    return {"saved": True, "pledged": bool(existing.pledged) if existing else False}


@router.delete("/places/{place_id}/save")
def unsave_place(
    place_id: int,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    existing = session.exec(
        select(Save).where(Save.user_id == user.id, Save.place_id == place_id)
    ).first()
    if existing is not None:
        session.delete(existing)
        session.commit()
    return {"saved": False}


@router.post("/places/{place_id}/fragile-pledge")
def fragile_pledge(
    place_id: int,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Save + pledge unlocks a fragile place's pin and steps (SPEC §8.14)."""
    place = session.get(Place, place_id)
    if place is None:
        raise not_found("That place is not here.", "no_place")
    row = session.exec(
        select(Save).where(Save.user_id == user.id, Save.place_id == place_id)
    ).first()
    if row is None:
        row = Save(user_id=int(user.id), place_id=place_id)
        session.add(row)
    row.pledged = True
    session.add(row)
    session.commit()
    return {"saved": True, "pledged": True}


@router.post("/media/{media_id}/like")
def like_media(
    media_id: int,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    media = session.get(Media, media_id)
    if media is None or media.status != "ok":
        raise not_found("That video is not here.", "no_media")
    if media.user_id == user.id:
        raise forbidden("You can't like your own video.", "self_like")

    existing = session.exec(
        select(MediaLike).where(MediaLike.user_id == user.id, MediaLike.media_id == media_id)
    ).first()
    if existing is None:
        session.add(MediaLike(user_id=int(user.id), media_id=media_id))
        session.commit()
        # A like on a video is a positive signal for its category, shared with
        # the deck's Thompson prior (SPEC §9.5).
        _bump_category(session, int(user.id), media.place_id, "save")
    count = int(
        session.exec(
            select(func.count()).select_from(MediaLike).where(MediaLike.media_id == media_id)
        ).one()
        or 0
    )
    return {"liked": True, "likes": count}


@router.delete("/media/{media_id}/like")
def unlike_media(
    media_id: int,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    existing = session.exec(
        select(MediaLike).where(MediaLike.user_id == user.id, MediaLike.media_id == media_id)
    ).first()
    if existing is not None:
        session.delete(existing)
        session.commit()
    count = int(
        session.exec(
            select(func.count()).select_from(MediaLike).where(MediaLike.media_id == media_id)
        ).one()
        or 0
    )
    return {"liked": False, "likes": count}


def _bump_category(session: DbSession, user_id: int, place_id: int, action: str) -> None:
    """Update the Beta prior for a place's category (SPEC §9.4, §9.5)."""
    from ..deck.thompson import update
    from ..models import CategoryPref

    place = session.get(Place, place_id)
    if place is None:
        return
    pref = session.exec(
        select(CategoryPref).where(
            CategoryPref.user_id == user_id, CategoryPref.category == place.category
        )
    ).first()
    if pref is None:
        pref = CategoryPref(user_id=user_id, category=place.category)
    pref.alpha, pref.beta = update(action, pref.alpha, pref.beta)
    session.add(pref)
    session.commit()


@router.post("/users/{handle}/follow")
def follow(
    handle: str,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    creator = session.exec(select(User).where(User.username == handle.lower())).first()
    if creator is None:
        raise not_found("No such creator.", "no_user")
    if creator.id == user.id:
        raise forbidden("You can't follow yourself.", "self_follow")
    existing = session.exec(
        select(Follow).where(Follow.follower_id == user.id, Follow.creator_id == creator.id)
    ).first()
    if existing is None:
        session.add(Follow(follower_id=int(user.id), creator_id=int(creator.id)))
        session.commit()
    return {"following": True}


@router.delete("/users/{handle}/follow")
def unfollow(
    handle: str,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    creator = session.exec(select(User).where(User.username == handle.lower())).first()
    if creator is None:
        raise not_found("No such creator.", "no_user")
    existing = session.exec(
        select(Follow).where(Follow.follower_id == user.id, Follow.creator_id == creator.id)
    ).first()
    if existing is not None:
        session.delete(existing)
        session.commit()
    return {"following": False}


class TouchIn(BaseModel):
    place_id: int
    content_type: str = "place"
    content_id: int | None = None


@router.post("/touch")
def record_touch(
    body: TouchIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Record something the user saw about a place (SPEC §9.9).

    The **server** decides the creator and the timestamp from the content it
    looks up -- the client only says what was seen. Otherwise a client could
    credit any creator it liked for a visit it was about to make.
    """
    if body.content_type not in ("place", "video", "photo", "steps"):
        raise bad_request("Unknown content type.", "bad_touch")
    place = session.get(Place, body.place_id)
    if place is None or place.status == "hidden":
        raise not_found("That place is not here.", "no_place")

    creator_id: int | None = None
    if body.content_type in ("video", "photo") and body.content_id:
        media = session.get(Media, body.content_id)
        if media is not None and media.place_id == place.id:
            creator_id = media.user_id
    elif body.content_type == "steps" and body.content_id:
        from ..models import LastMileStep

        step = session.get(LastMileStep, body.content_id)
        if step is not None and step.place_id == place.id:
            creator_id = step.author_id
    else:
        creator_id = place.added_by

    if creator_id is None or creator_id == user.id:
        # Nothing to credit (seeded place with no finder, or their own content).
        return {"recorded": False}
    publisher = session.get(User, int(creator_id))
    if publisher is None or publisher.official:
        # The official account publishes; visits are not credited to it.
        return {"recorded": False}

    session.add(
        Touch(
            user_id=int(user.id),
            place_id=int(place.id),
            creator_id=int(creator_id),
            content_type=body.content_type,
            content_id=body.content_id,
        )
    )
    session.commit()
    return {"recorded": True}


class ReportIn(BaseModel):
    target_type: str
    target_id: int
    reason: str
    note: str = Field(default="", max_length=300)


@router.post("/reports")
def create_report(
    body: ReportIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """File a report. 3 from verified visitors auto-hide media (SPEC §8.13)."""
    if body.reason not in REPORT_REASONS:
        raise bad_request("Unknown reason.", "bad_reason")
    if body.target_type not in ("place", "media", "steps"):
        raise bad_request("Unknown target.", "bad_target")

    already = session.exec(
        select(Report).where(
            Report.reporter_id == user.id,
            Report.target_type == body.target_type,
            Report.target_id == body.target_id,
            Report.reason == body.reason,
            Report.status == "open",
        )
    ).first()
    if already is not None:
        # Filing the same thing twice must not look like two people agreeing.
        return {"filed": True, "hidden": False, "already": True}
    today = int(
        session.exec(
            select(func.count())
            .select_from(Report)
            .where(Report.reporter_id == user.id, Report.at >= utcnow() - timedelta(days=1))
        ).one()
        or 0
    )
    if today >= int(cfg("moderation.reports_per_day", 20)):
        raise too_many("That's a lot of reports today. We'll work through them.")

    session.add(
        Report(
            reporter_id=int(user.id),
            target_type=body.target_type,
            target_id=body.target_id,
            reason=body.reason,
            note=body.note[:300],
        )
    )
    session.commit()

    hidden = False
    if body.target_type == "media":
        media = session.get(Media, body.target_id)
        if media is not None and media.status == "ok":
            # "Photo of me" hides at once -- a person asking to be taken out of
            # a photo should not wait in a queue.
            if body.reason == "photo_of_me":
                media.status = "hidden"
                session.add(media)
                session.commit()
                hidden = True
            else:
                threshold = int(cfg("moderation.auto_hide_reports", 3))
                reporters = session.exec(
                    select(func.count(func.distinct(Report.reporter_id))).where(
                        Report.target_type == "media",
                        Report.target_id == body.target_id,
                        Report.status == "open",
                    )
                ).one()
                if int(reporters or 0) >= threshold:
                    media.status = "hidden"
                    session.add(media)
                    session.commit()
                    hidden = True
    return {"filed": True, "hidden": hidden}
