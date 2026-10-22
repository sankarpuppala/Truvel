"""Register, log in, log out (SPEC §11)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session as DbSession
from sqlmodel import select

from .. import auth, kadam
from ..db import get_session
from ..errors import bad_request, unauthorized
from ..models import City, User

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

    # New accounts start in the default city so the deck and Explore have
    # somewhere to open (SPEC §8.2 location-denied fallback).
    from ..config import cfg

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

    auth.start_session(session, response, user)
    return {"user": user_payload(session, user)}


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
    # endpoint cannot be used to find out who has an account (SPEC §11).
    if user is None or not auth.verify_password(user.password_hash, body.password):
        auth.record_login_failure(keys)
        raise unauthorized("That email and password do not match.")

    auth.clear_login_failures(keys)
    auth.start_session(session, response, user)
    return {"user": user_payload(session, user)}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    session: DbSession = Depends(get_session),
    _: None = Depends(auth.require_csrf_header),
) -> dict:
    auth.end_session(session, request, response)
    return {"ok": True}
