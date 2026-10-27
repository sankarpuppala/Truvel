"""Register, log in, log out (SPEC §11)."""
from __future__ import annotations

import os
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session as DbSession
from sqlmodel import select

from .. import auth, kadam, mailer
from ..db import get_session
from ..errors import bad_request, unauthorized
from ..models import City, PasswordReset, Session, User, utcnow

RESET_HOURS = 1
MAIL_BODY = """\
Someone asked to reset the password for @{username}.

Choose a new one here (the link works for {hours} hour, once):
{link}

If that was not you, ignore this email and nothing changes."""

router = APIRouter(prefix="/auth", tags=["auth"])


class Registration(BaseModel):
    """What it takes to open an account (SPEC §11).

    An email address is how an account is recovered and how we can ever tell a
    person they have been reported; the handle is what other people see.
    """

    email: str = Field(max_length=254)
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=1, max_length=200)
    display_name: str = Field(default="", max_length=60)


class Credentials(BaseModel):
    """Sign in with either the email address or the handle."""

    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)


def user_payload(session: DbSession, user: User) -> dict:
    balance = kadam.balance(session, int(user.id))
    current, next_level, floor, next_floor = kadam.level(balance)
    city = session.get(City, user.home_city_id) if user.home_city_id else None
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "official": user.official,
        "display_name": user.display_name or user.username,
        "bio": user.bio,
        "role": user.role,
        "strikes": user.strikes,
        "kadam": balance,
        "level": current,
        "next_level": next_level,
        "level_floor": floor,
        "next_level_floor": next_floor,
        "names_mode": user.names_mode,
        "names_lang": user.names_lang,
        "ui_lang": user.ui_lang,
        "theme": user.theme,
        "home_city": {"id": city.id, "slug": city.slug, "name": city.name_en} if city else None,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/register")
def register(
    body: Registration,
    response: Response,
    session: DbSession = Depends(get_session),
    _: None = Depends(auth.require_csrf_header),
) -> dict:
    username = auth.validate_username(body.username)
    email = auth.validate_email(body.email)
    auth.validate_password(body.password, email=email, username=username)

    if session.exec(select(User).where(User.username == username)).first() is not None:
        raise bad_request("That handle is taken.", "username_taken")
    if session.exec(select(User).where(User.email == email)).first() is not None:
        raise bad_request("An account already uses that email address.", "email_taken")

    # Initialize account in user's detected location, or default city if undetected
    from ..config import cfg
    from .places import detect_location

    city = None
    try:
        detected = detect_location(request, session, None)
        if detected and detected.get("city_id"):
            city = session.get(City, detected["city_id"])
    except Exception:
        pass

    if city is None:
        city = session.exec(select(City).where(City.slug == str(cfg("city_default")))).first()

    user = User(
        username=username,
        email=email,
        password_hash=auth.hash_password(body.password),
        display_name=(body.display_name or "").strip()[:60] or username,
        home_city_id=city.id if city else None,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = auth.start_session(session, response, user)
    return {"user": user_payload(session, user), "token": token}


@router.post("/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    session: DbSession = Depends(get_session),
    _: None = Depends(auth.require_csrf_header),
) -> dict:
    identifier = (body.identifier or "").strip().lower()
    client = request.client.host if request.client else "unknown"
    keys = [f"id:{identifier}", f"ip:{client}"]
    auth.check_login_allowed(keys)

    column = User.email if "@" in identifier else User.username
    user = session.exec(select(User).where(column == identifier)).first()

    # One generic error for both "no such account" and "wrong password", so the
    # endpoint cannot be used to find out who has an account (SPEC §11). The
    # hash to check against is always a real argon2id hash -- a dummy one when
    # there's no such user -- so a non-existent identifier takes the same time
    # as a wrong password on a real one.
    hash_to_check = user.password_hash if user is not None else auth.dummy_hash()
    password_ok = auth.verify_password(hash_to_check, body.password)
    if user is None or not password_ok:
        auth.record_login_failure(keys)
        raise unauthorized("That email and password do not match.")

    # If the user is logging in and their home city was still default/unset, sync it
    try:
        from .places import detect_location
        detected = detect_location(request, session, user)
        if detected and detected.get("city_id") and (user.home_city_id is None or user.home_city_id == 1):
            user.home_city_id = detected["city_id"]
            session.add(user)
            session.commit()
            session.refresh(user)
    except Exception:
        pass

    auth.clear_login_failures(keys)
    token = auth.start_session(session, response, user)
    return {"user": user_payload(session, user), "token": token}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    session: DbSession = Depends(get_session),
    _: None = Depends(auth.require_csrf_header),
) -> dict:
    auth.end_session(session, request, response)
    return {"ok": True}


class ForgotIn(BaseModel):
    email: str = Field(min_length=1, max_length=254)


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=1, max_length=200)


@router.post("/forgot")
def forgot_password(
    body: ForgotIn,
    request: Request,
    session: DbSession = Depends(get_session),
    _: None = Depends(auth.require_csrf_header),
) -> dict:
    """Email a reset link. Always answers the same, so it cannot reveal who has an account."""
    email = (body.email or "").strip().lower()
    client = request.client.host if request.client else "unknown"
    keys = [f"reset:{email}", f"reset-ip:{client}"]
    auth.check_login_allowed(keys)
    auth.record_login_failure(keys)          # each request counts, so it cannot be used to spam

    user = session.exec(select(User).where(User.email == email)).first()
    if user is not None and not user.official:
        token = secrets.token_urlsafe(32)
        now = utcnow()
        session.add(
            PasswordReset(
                id=auth._hash_token(token),
                user_id=int(user.id),
                created_at=now,
                expires_at=now + timedelta(hours=RESET_HOURS),
            )
        )
        session.commit()
        base = os.environ.get("TRUVEL_PUBLIC_URL", "http://localhost:5173").rstrip("/")
        link = f"{base}/reset?token={token}"
        mailer.send(
            user.email,
            "Reset your Truvel password",
            MAIL_BODY.format(username=user.username, hours=RESET_HOURS, link=link),
        )
    return {"ok": True}


@router.post("/reset")
def reset_password(
    body: ResetIn,
    response: Response,
    session: DbSession = Depends(get_session),
    _: None = Depends(auth.require_csrf_header),
) -> dict:
    """Set a new password from an emailed link, and sign every other device out."""
    row = session.get(PasswordReset, auth._hash_token(body.token))
    now = utcnow()
    if row is None or row.used or row.expires_at < now:
        raise bad_request(
            "That reset link has expired or was already used. Ask for a new one.",
            "bad_reset_token",
        )
    user = session.get(User, row.user_id)
    if user is None:
        raise bad_request("That reset link is not valid.", "bad_reset_token")

    auth.validate_password(body.password, email=user.email, username=user.username)
    user.password_hash = auth.hash_password(body.password)
    row.used = True
    session.add(user)
    session.add(row)
    for old in session.exec(select(Session).where(Session.user_id == user.id)).all():
        session.delete(old)
    session.commit()

    auth.start_session(session, response, user)
    return {"user": user_payload(session, user)}
