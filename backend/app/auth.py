"""Accounts and sessions (SPEC §11).

Passwords are hashed with **argon2id**, the current recommendation for password
storage: it is memory-hard, so a stolen database cannot be cracked cheaply on
GPUs the way bcrypt or a bare SHA-256 can.

Sessions are opaque random tokens in an `HttpOnly` cookie. The database stores
only the **SHA-256 of the token**, so a database dump does not hand over live
sessions -- the same reason we hash passwords. `SameSite=Lax` plus a required
`X-Requested-With: truvel` header on mutating requests is the CSRF defence: a
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
from .errors import bad_request, forbidden, too_many, unauthorized
from .models import Session, User, utcnow

COOKIE_NAME = "truvel_session"
SESSION_DAYS = 30
REQUIRED_HEADER = "x-requested-with"
REQUIRED_HEADER_VALUE = "truvel"
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
# Deliberately permissive: the one rule every address must follow is a single
# @ with something either side and a dot in the domain. Anything stricter
# rejects real addresses, and the only proof an address works is sending to it.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

# NIST SP 800-63B: length and a blocklist of known-bad choices do the work.
# Forced symbols and digits only push people towards "Password1!".
MIN_PASSWORD = 8
MAX_PASSWORD = 128
COMMON_PASSWORDS = {
    "password", "password1", "password123", "123456", "1234567", "12345678",
    "123456789", "1234567890", "qwerty", "qwerty123", "abc123", "111111",
    "iloveyou", "admin", "welcome", "monkey", "dragon", "letmein", "football",
    "princess", "sunshine", "shadow", "master", "superman", "trustno1",
    "passw0rd", "p@ssw0rd", "india123", "truvel", "truvel123",
}

# Login throttling (SPEC §11). Counted per account *and* per address, so one
# attacker cannot lock out a user and one user cannot be used as cover.
LOGIN_MAX_FAILURES = 8
LOGIN_WINDOW = timedelta(minutes=15)
_login_failures: dict[str, list[datetime]] = {}

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


def validate_email(email: str) -> str:
    """Normalise and check an address (SPEC §11)."""
    value = (email or "").strip().lower()
    if not value:
        raise bad_request("Enter your email address.", "bad_email")
    if len(value) > 254 or not EMAIL_RE.match(value):
        raise bad_request("That does not look like an email address.", "bad_email")
    return value


def validate_password(password: str, *, email: str = "", username: str = "") -> str:
    """Length, a blocklist, and not your own name back at you.

    Three checks, in the order a person meets them, each with the one thing
    they have to change rather than a list of rules to decode.
    """
    value = password or ""
    if len(value) < MIN_PASSWORD:
        raise bad_request(
            f"Use at least {MIN_PASSWORD} characters. A short phrase you will "
            "remember beats a short password you will not.",
            "weak_password",
        )
    if len(value) > MAX_PASSWORD:
        raise bad_request(f"Use at most {MAX_PASSWORD} characters.", "weak_password")

    folded = value.lower()
    if folded in COMMON_PASSWORDS or folded.strip("0123456789!") in COMMON_PASSWORDS:
        raise bad_request(
            "That password is one of the most common ones in use. Pick something else.",
            "weak_password",
        )

    local = (email or "").split("@")[0].lower()
    for own in (local, (username or "").lower()):
        if own and len(own) >= 3 and own in folded:
            raise bad_request(
                "Your password should not contain your name or email.",
                "weak_password",
            )
    return value


# --- login throttling ------------------------------------------------------

def _recent_failures(key: str, now: datetime) -> list[datetime]:
    hits = [at for at in _login_failures.get(key, []) if now - at < LOGIN_WINDOW]
    if hits:
        _login_failures[key] = hits
    else:
        _login_failures.pop(key, None)
    return hits


def check_login_allowed(keys: list[str]) -> None:
    """Refuse a login attempt once an account or address has failed too often.

    In memory, so it resets when the server restarts: this is a brake on
    guessing, not an audit trail, and the SPEC does not ask for more.
    """
    now = utcnow()
    for key in keys:
        if len(_recent_failures(key, now)) >= LOGIN_MAX_FAILURES:
            raise too_many(
                "Too many sign-in attempts. Wait a few minutes and try again.",
                "login_throttled",
            )


def record_login_failure(keys: list[str]) -> None:
    now = utcnow()
    for key in keys:
        _login_failures.setdefault(key, []).append(now)


def clear_login_failures(keys: list[str]) -> None:
    for key in keys:
        _login_failures.pop(key, None)


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
    """Mutating requests must carry `X-Requested-With: truvel` (SPEC §11).

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
