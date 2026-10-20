"""Shared test fixtures.

Each test module gets its own throwaway SQLite file and media directory, set
*before* `app.config` is imported, so no test can touch the real database or
write into `backend/media/`.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="pagdandi-test-"))
os.environ.setdefault("PAGDANDI_DB", str(_TMP / "test.db"))
os.environ.setdefault("PAGDANDI_MEDIA_DIR", str(_TMP / "media"))
os.environ.setdefault("PAGDANDI_DATA_DIR", str(_TMP / "data"))

from app.db import engine, init_db  # noqa: E402
from app.models import SQLModel  # noqa: E402


@pytest.fixture()
def session():
    """A clean database per test: every table dropped and recreated."""
    from sqlmodel import Session

    SQLModel.metadata.drop_all(engine)
    with engine.begin() as conn:
        from sqlalchemy import text

        conn.execute(text("DROP TABLE IF EXISTS placename_fts"))
        for trigger in ("placename_ai", "placename_ad", "placename_au"):
            conn.execute(text(f"DROP TRIGGER IF EXISTS {trigger}"))
    init_db()
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(session):
    """A TestClient sharing the test database, with the CSRF header preset."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.headers.update({"X-Requested-With": "pagdandi"})
        yield c


@pytest.fixture()
def tmp_media():
    return Path(os.environ["PAGDANDI_MEDIA_DIR"])


def make_user(session, username: str, **kwargs):
    """A user with a usable password hash, for tests that need an owner."""
    from app.auth import hash_password
    from app.models import User

    user = User(
        username=username,
        password_hash=hash_password("correct horse battery"),
        display_name=kwargs.pop("display_name", username),
        **kwargs,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def make_city(session, slug: str = "hyderabad", **kwargs):
    from app.models import City

    city = City(
        slug=slug,
        name_en=kwargs.pop("name_en", "Hyderabad"),
        state=kwargs.pop("state", "Telangana"),
        bbox=kwargs.pop("bbox", [17.20, 78.20, 17.62, 78.70]),
        centre_lat=kwargs.pop("centre_lat", 17.3850),
        centre_lng=kwargs.pop("centre_lng", 78.4867),
        regional_langs=kwargs.pop("regional_langs", ["te", "ur"]),
        **kwargs,
    )
    session.add(city)
    session.commit()
    session.refresh(city)
    return city


def make_place(session, city=None, name: str = "Test Place", **kwargs):
    from app.models import Place, PlaceName

    place = Place(
        city_id=city.id if city else None,
        state=kwargs.pop("state", city.state if city else "Telangana"),
        lat=kwargs.pop("lat", 17.4000),
        lng=kwargs.pop("lng", 78.4000),
        category=kwargs.pop("category", "viewpoint"),
        source=kwargs.pop("source", "community"),
        status=kwargs.pop("status", "verified"),
        fame=kwargs.pop("fame", "hidden"),
        **kwargs,
    )
    session.add(place)
    session.commit()
    session.refresh(place)
    session.add(PlaceName(place_id=int(place.id), lang="en", name=name, source="osm"))
    session.commit()
    return place
