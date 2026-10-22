"""Password reset, deleting your own upload, and the official publisher account."""
from __future__ import annotations

import pytest
from sqlmodel import select

from app import kadam, mailer
from app.models import KadamEntry, Media, MediaLike, Place, Session as LoginSession, Touch
from tests.conftest import make_city, make_place, make_user

PASSWORD = "correct horse battery"


@pytest.fixture()
def outbox(monkeypatch):
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


def token_from(outbox) -> str:
    return outbox[-1][2].split("token=")[1].split()[0]


def test_reset_link_sets_a_new_password_once(client, session, outbox):
    make_user(session, "riya", email="riya@example.com")
    assert client.post("/api/auth/forgot", json={"email": "riya@example.com"}).json() == {"ok": True}
    token = token_from(outbox)

    done = client.post("/api/auth/reset", json={"token": token, "password": "a brand new phrase"})
    assert done.status_code == 200
    assert client.get("/api/me").json()["user"]["username"] == "riya"

    again = client.post("/api/auth/reset", json={"token": token, "password": "another new phrase"})
    assert again.status_code == 400                      # a link works once
    client.post("/api/auth/logout")
    login = client.post(
        "/api/auth/login", json={"identifier": "riya", "password": "a brand new phrase"}
    )
    assert login.status_code == 200


def test_forgot_answers_the_same_for_unknown_email(client, session, outbox):
    make_user(session, "riya", email="riya@example.com")
    known = client.post("/api/auth/forgot", json={"email": "riya@example.com"})
    unknown = client.post("/api/auth/forgot", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert len(outbox) == 1                              # only the real account got mail


def test_reset_enforces_the_password_rules_and_revokes_sessions(client, session, outbox):
    user = make_user(session, "riya", email="riya@example.com")
    client.post("/api/auth/login", json={"identifier": "riya", "password": PASSWORD})
    client.post("/api/auth/forgot", json={"email": "riya@example.com"})
    token = token_from(outbox)

    weak = client.post("/api/auth/reset", json={"token": token, "password": "short"})
    assert weak.status_code == 400
    assert client.post("/api/auth/reset", json={"token": "nonsense-token", "password": "a brand new phrase"}).status_code == 400

    client.post("/api/auth/reset", json={"token": token, "password": "a brand new phrase"})
    rows = session.exec(select(LoginSession).where(LoginSession.user_id == user.id)).all()
    assert len(rows) == 1                                # only the one just started


def test_you_can_delete_your_own_upload_and_nobody_elses(client, session, tmp_media):
    city = make_city(session)
    place = make_place(session, city)
    mine = make_user(session, "riya", email="riya@example.com")
    other = make_user(session, "arjun", email="arjun@example.com")
    folder = tmp_media / "photos"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "a.jpg").write_bytes(b"x")
    media = Media(place_id=int(place.id), user_id=int(mine.id), path_display="photos/a.jpg")
    session.add(media)
    session.commit()
    media_id = int(media.id)
    session.add(MediaLike(user_id=int(other.id), media_id=media_id))
    session.commit()

    client.post("/api/auth/login", json={"identifier": "arjun", "password": PASSWORD})
    assert client.delete(f"/api/media/{media_id}").status_code == 403
    client.post("/api/auth/logout")

    client.post("/api/auth/login", json={"identifier": "riya", "password": PASSWORD})
    assert client.delete(f"/api/media/{media_id}").status_code == 200
    session.expire_all()
    assert session.get(Media, media_id) is None
    assert not (folder / "a.jpg").exists()
    assert client.delete(f"/api/media/{media_id}").status_code == 404


def test_commons_photos_cannot_be_deleted(client, session):
    city = make_city(session)
    place = make_place(session, city)
    mine = make_user(session, "riya", email="riya@example.com")
    media = Media(
        place_id=int(place.id), user_id=int(mine.id), source="commons", licence="CC BY 4.0"
    )
    session.add(media)
    session.commit()
    client.post("/api/auth/login", json={"identifier": "riya", "password": PASSWORD})
    assert client.delete(f"/api/media/{media.id}").status_code == 404


def test_official_account_earns_no_kadam(session):
    city = make_city(session)
    official = make_user(session, "truvel", official=True)
    place = make_place(session, city, added_by=int(official.id))
    assert kadam.award(session, int(official.id), kadam.DISCOVERY, ref_type="place", ref_id=int(place.id)) == 0
    assert session.exec(select(KadamEntry).where(KadamEntry.user_id == official.id)).first() is None


def test_official_places_say_posted_by_and_cannot_be_credited_with_visits(client, session):
    city = make_city(session)
    official = make_user(session, "truvel", official=True)
    place = make_place(session, city, added_by=int(official.id))
    make_user(session, "riya", email="riya@example.com")
    client.post("/api/auth/login", json={"identifier": "riya", "password": PASSWORD})

    found_by = client.get(f"/api/places/{place.id}").json()["found_by"]
    assert found_by["official"] is True

    client.post(f"/api/places/{place.id}/like")          # allowed: it is not riya's own place
    touch = client.post(
        "/api/touch", json={"place_id": int(place.id), "content_type": "place"}
    )
    assert touch.json().get("recorded") is False
    assert session.exec(select(Touch)).first() is None
    assert session.get(Place, place.id).added_by == official.id
