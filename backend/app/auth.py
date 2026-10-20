"""Accounts and sessions (SPEC §11).

Passwords are hashed with **argon2id**, the current recommendation for password
storage: it is memory-hard, so a stolen database cannot be cracked cheaply on
GPUs the way bcrypt or a bare SHA-256 can.

Sessions are opaque random tokens in an `HttpOnly` cookie. The database stores
only the **SHA-256 of the token**, so a database dump does not hand over live
sessions -- the same reason we hash passwords. `SameSite=Lax` plus a required
`X-Requested-With: pagdandi` header on mutating requests is the CSRF defence: a
cross-site form post cannot set a custom header.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, Request, Response
from sqlmodel import Session as DbSession

from .config import is_https
from .db import get_session
from .errors import bad_request, forbidden, unauthorized
from .models import Session, User, utcnow

COOKIE_NAME = "pagdandi_session"
SESSION_DAYS = 30
REQUIRED_HEADER = "x-requested-with"
REQUIRED_HEADER_VALUE = "pagdandi"
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
MIN_PASSWORD = 8

_hasher = PasswordHasher()


# --- passwords -------------------------------------------------------------

def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Constant-time-ish verification; any failure is just False."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


def validate_username(username: str) -> str:
    """a-z0-9_ and 3-20 characters (SPEC §5)."""
    name = (username or "").strip().lower()
    if not USERNAME_RE.match(name):
        raise bad_request(
            "Usernames use 3-20 lowercase letters, numbers or underscores.",
            "bad_username",
        )
    return name


def validate_password(password: str) -> str:
    if len(password or "") < MIN_PASSWORD:
        raise bad_request(
            f"Use at least {MIN_PASSWORD} characters.", "weak_password"
        )
    return password


# --- sessions --------------------------------------------------------------

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def start_session(session: DbSession, response: Response, user: User) -> str:
    """Create a session row and set the cookie. Returns the raw token."""
    token = secrets.token_urlsafe(32)
    now = utcnow()
    session.add(
        Session(
            id=_hash_token(token),
            user_id=int(user.id),
            created_at=now,
            expires_at=now + timedelta(days=SESSION_DAYS),
        )
    )
    session.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=is_https(),
        path="/",
    )
    return token


def end_session(session: DbSession, request: Request, response: Response) -> None:
    """Delete the session row and clear the cookie."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        row = session.get(Session, _hash_token(token))
        if row is not None:
            session.delete(row)
            session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


def current_user_optional(
    request: Request,
    session: DbSession = Depends(get_session),
) -> User | None:
    """The signed-in user, or None. Expired sessions are deleted as we find them."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    row = session.get(Session, _hash_token(token))
    if row is None:
        return None
    if row.expires_at < utcnow():
        session.delete(row)
        session.commit()
        return None
    return session.get(User, row.user_id)


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    """Require a signed-in user."""
    if user is None:
        raise unauthorized()
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise forbidden("Admins only.", "not_admin")
    return user


def require_csrf_header(request: Request) -> None:
    """Mutating requests must carry `X-Requested-With: pagdandi` (SPEC §11).

    A cross-site HTML form cannot set custom headers, so this plus SameSite=Lax
    stops an attacker's page from acting as the signed-in user.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    value = request.headers.get(REQUIRED_HEADER, "").strip().lower()
    if value != REQUIRED_HEADER_VALUE:
        raise forbidden("Missing request header.", "csrf")


def can_post(user: User) -> bool:
    """3 strikes and the user cannot post (SPEC §8.13)."""
    from .config import cfg

    return user.strikes < int(cfg("moderation.strikes_to_block", 3))


def session_age_hours(user: User, now: datetime | None = None) -> float:
    now = now or utcnow()
    return (now - user.created_at).total_seconds() / 3600.0
