"""Following: who you follow, who follows you, and what they post (SPEC §8.11).

The feed is a merge, newest first, of two kinds of activity by people you
follow: photos/videos they posted, and places they added. Places go through
`services.place_payload`, so fragile-place redaction applies here exactly as
everywhere else (invariant 5). Nothing here stores or uses location.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from .. import services
from ..auth import current_user, current_user_optional
from ..db import get_session
from ..errors import bad_request, not_found
from ..models import Follow, Media, Place, User, utcnow

router = APIRouter(tags=["social"])

PAGE = 20


def _user_row(user: User, followed_ids: set[int], viewer: User | None) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "followed_by_me": int(user.id) in followed_ids,
        "is_me": viewer is not None and user.id == viewer.id,
    }


def _followed_ids(session: DbSession, viewer: User | None) -> set[int]:
    if viewer is None:
        return set()
    return set(session.exec(select(Follow.creator_id).where(Follow.follower_id == viewer.id)).all())


def _by_handle(session: DbSession, handle: str) -> User:
    user = session.exec(select(User).where(User.username == handle.lower())).first()
    if user is None:
        raise not_found("No such creator.", "no_user")
    return user


@router.get("/users/{handle}/followers")
def followers(
    handle: str,
    session: DbSession = Depends(get_session),
    viewer: User | None = Depends(current_user_optional),
) -> dict:
    user = _by_handle(session, handle)
    rows = session.exec(
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.creator_id == user.id)
        .order_by(Follow.id.desc())
        .limit(500)
    ).all()
    mine = _followed_ids(session, viewer)
    return {"users": [_user_row(u, mine, viewer) for u in rows]}


@router.get("/users/{handle}/following")
def following(
    handle: str,
    session: DbSession = Depends(get_session),
    viewer: User | None = Depends(current_user_optional),
) -> dict:
    user = _by_handle(session, handle)
    rows = session.exec(
        select(User)
        .join(Follow, Follow.creator_id == User.id)
        .where(Follow.follower_id == user.id)
        .order_by(Follow.id.desc())
        .limit(500)
    ).all()
    mine = _followed_ids(session, viewer)
    return {"users": [_user_row(u, mine, viewer) for u in rows]}


def merge_feed(posts: list[dict], places: list[dict], limit: int) -> list[dict]:
    """Merge two newest-first lists into one newest-first page (SPEC §8.11)."""
    return sorted(posts + places, key=lambda item: item["at"], reverse=True)[:limit]


@router.get("/feed")
def feed(
    before: str | None = Query(default=None),
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Posts and places from people you follow, newest first; `before` pages."""
    try:
        cutoff = datetime.fromisoformat(before) if before else utcnow()
    except ValueError as exc:
        raise bad_request("Bad page cursor.", "bad_cursor") from exc
    ids = _followed_ids(session, user)
    if not ids:
        return {"items": [], "next": None, "following": 0}
    creators = {int(u.id): u for u in session.exec(select(User).where(User.id.in_(ids))).all()}
    now = utcnow()

    media_rows = session.exec(
        select(Media, Place)
        .join(Place, Place.id == Media.place_id)
        .where(
            Media.user_id.in_(ids),
            Media.status == "ok",
            Place.status != "hidden",
            Media.created_at < cutoff,
        )
        .order_by(Media.created_at.desc())
        .limit(PAGE)
    ).all()
    posts = [
        {
            "type": "post",
            "at": m.created_at.isoformat(),
            "creator": _user_row(creators[int(m.user_id)], ids, user),
            "media": services.media_payload(m, creators[int(m.user_id)]),
            "place": services.place_payload(session, p, user, now=now),
        }
        for m, p in media_rows
    ]
    place_rows = session.exec(
        select(Place)
        .where(Place.added_by.in_(ids), Place.status != "hidden", Place.created_at < cutoff)
        .order_by(Place.created_at.desc())
        .limit(PAGE)
    ).all()
    places = [
        {
            "type": "place",
            "at": p.created_at.isoformat(),
            "creator": _user_row(creators[int(p.added_by)], ids, user),
            "media": None,
            "place": services.place_payload(session, p, user, now=now),
        }
        for p in place_rows
    ]
    items = merge_feed(posts, places, PAGE)
    nxt = items[-1]["at"] if len(items) == PAGE else None
    return {"items": items, "next": nxt, "following": len(ids)}


@router.get("/creators/suggested")
def suggested(
    session: DbSession = Depends(get_session),
    viewer: User | None = Depends(current_user_optional),
) -> dict:
    """People worth following: most places added plus posts, excluding you and
    those you already follow. A plain count, explainable in one line."""
    mine = _followed_ids(session, viewer)
    skip = mine | ({int(viewer.id)} if viewer else set())
    media_counts = dict(
        session.exec(
            select(Media.user_id, func.count())
            .where(Media.user_id.is_not(None), Media.status == "ok")
            .group_by(Media.user_id)
        ).all()
    )
    place_counts = dict(
        session.exec(
            select(Place.added_by, func.count())
            .where(Place.added_by.is_not(None), Place.status != "hidden")
            .group_by(Place.added_by)
        ).all()
    )
    totals: dict[int, int] = {}
    for uid, n in [*media_counts.items(), *place_counts.items()]:
        if uid is not None and int(uid) not in skip:
            totals[int(uid)] = totals.get(int(uid), 0) + int(n)
    top = sorted(totals, key=lambda uid: totals[uid], reverse=True)[:8]
    users = {int(u.id): u for u in session.exec(select(User).where(User.id.in_(top))).all()} if top else {}
    return {
        "users": [
            {**_user_row(users[uid], mine, viewer), "posts": totals[uid]}
            for uid in top
            if uid in users
        ]
    }
