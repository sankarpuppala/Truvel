"""Comments on videos and photos (SPEC §8.11, Tier 2).

Rules: ≤ 300 characters, a keyword filter from config, an hourly rate limit,
and the same report path as media -- 3 reports from different people hide a
comment pending review (SPEC §8.13, handled in `interact.create_report`).
Comments earn no kadam, so there is nothing to farm.
"""
from __future__ import annotations

import re
from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session as DbSession
from sqlmodel import func, select

from ..auth import current_user, current_user_optional, require_csrf_header
from ..config import cfg
from ..db import get_session
from ..errors import bad_request, forbidden, not_found, too_many
from ..integrity.fraud import rate_limited
from ..models import Comment, Media, User, utcnow

router = APIRouter(tags=["comments"], dependencies=[Depends(require_csrf_header)])


class CommentIn(BaseModel):
    text: str


def clean_comment(text: str, max_chars: int, blocked: list[str]) -> str | None:
    """Trim and check one comment (SPEC §8.11). Returns the text to store, or
    None when it is empty, too long, or contains a blocked word."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text or len(text) > max_chars:
        return None
    words = set(re.findall(r"\w+", text.lower()))
    if any(word.lower() in words for word in blocked):
        return None
    return text


def _payload(comment: Comment, author: User | None, viewer: User | None) -> dict:
    return {
        "id": comment.id,
        "text": comment.text,
        "at": comment.at.isoformat(),
        "user": {
            "username": author.username if author else "someone",
            "display_name": author.display_name if author else "",
        },
        "mine": viewer is not None and comment.user_id == viewer.id,
    }


def _visible_media(session: DbSession, media_id: int) -> Media:
    media = session.get(Media, media_id)
    if media is None or media.status != "ok":
        raise not_found("That video is not here.", "no_media")
    return media


@router.get("/media/{media_id}/comments")
def list_comments(
    media_id: int,
    session: DbSession = Depends(get_session),
    viewer: User | None = Depends(current_user_optional),
) -> dict:
    """Newest first; hidden comments are never returned."""
    _visible_media(session, media_id)
    rows = session.exec(
        select(Comment, User)
        .join(User, User.id == Comment.user_id)
        .where(Comment.media_id == media_id, Comment.status == "ok")
        .order_by(Comment.at.desc())
        .limit(100)
    ).all()
    return {"comments": [_payload(c, u, viewer) for c, u in rows]}


@router.post("/media/{media_id}/comments")
def add_comment(
    media_id: int,
    body: CommentIn,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    _visible_media(session, media_id)
    since = utcnow() - timedelta(hours=1)
    recent = int(
        session.exec(
            select(func.count())
            .select_from(Comment)
            .where(Comment.user_id == user.id, Comment.at >= since)
        ).one()
        or 0
    )
    if rate_limited(recent, "comments_per_hour"):
        raise too_many("That's a lot of comments this hour. Try again later.")
    text = clean_comment(
        body.text,
        int(cfg("comments.max_chars", 300)),
        list(cfg("comments.blocked_words", []) or []),
    )
    if text is None:
        raise bad_request("Comments are 1 to 300 characters, and kind.", "bad_comment")
    comment = Comment(media_id=media_id, user_id=int(user.id), text=text)
    session.add(comment)
    session.commit()
    session.refresh(comment)
    return _payload(comment, user, user)


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    session: DbSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    comment = session.get(Comment, comment_id)
    if comment is None:
        raise not_found("That comment is not here.", "no_comment")
    if comment.user_id != user.id:
        raise forbidden("You can only delete your own comments.", "not_yours")
    session.delete(comment)
    session.commit()
    return {"deleted": True}
