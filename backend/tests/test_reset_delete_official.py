"""Password reset, deleting your own upload, and the official publisher account."""
from __future__ import annotations

import pytest
from sqlmodel import select

from app import kadam, mailer
from app.models import KadamEntry, Media, MediaLike, Place, Session as LoginSession, Touch

from tests.conftest import make_city, make_place, make_user

PASSWORD = "correct horse battery"
KHAJAGUDA = (17.4186, 78.3391)


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


# --- duplicates ------------------------------------------------------------ #

def _new_place(client, name: str, lat: float, lng: float, **extra):
    return client.post(
        "/api/places",
        json={"lat": lat, "lng": lng, "name": name, "category": "fort_heritage", **extra},
    )


def test_a_certain_duplicate_is_refused_whatever_the_client_did(client, session):
    city = make_city(session)
    make_place(session, city, "Golconda Fort", lat=17.3833, lng=78.4011, category="fort_heritage")
    make_user(session, "riya", email="riya@example.com")
    client.post("/api/auth/login", json={"identifier": "riya", "password": PASSWORD})

    same = _new_place(client, "Fort Golconda", 17.3834, 78.4012)
    assert same.status_code == 409
    assert same.json()["error"]["code"] == "duplicate_place"
    assert same.json()["error"]["detail"]["place_id"]


def test_a_different_place_beside_it_is_allowed(client, session):
    city = make_city(session)
    make_place(session, city, "Golconda Fort", lat=17.3833, lng=78.4011, category="fort_heritage")
    make_user(session, "riya", email="riya@example.com")
    client.post("/api/auth/login", json={"identifier": "riya", "password": PASSWORD})

    other = _new_place(client, "Golconda Jail", 17.3836, 78.4014)
    assert other.status_code == 200


# --- reports --------------------------------------------------------------- #

def test_reports_are_grouped_and_visitors_count_for_more(client, session):
    from app.models import Visit

    city = make_city(session)
    place = make_place(session, city)
    other = make_place(session, city, "Other", lat=17.5, lng=78.5)
    make_user(session, "admin", role="admin", official=True, email="a@example.com")
    for name in ("riya", "arjun", "meera"):
        make_user(session, name, email=f"{name}@example.com")
    session.add(Visit(user_id=2, place_id=int(place.id), verified=True))     # riya was there
    session.commit()

    def report(who: str, target: int, reason: str = "wrong_location", note: str = ""):
        client.post("/api/auth/login", json={"identifier": who, "password": PASSWORD})
        out = client.post(
            "/api/reports",
            json={"target_type": "place", "target_id": target, "reason": reason, "note": note},
        )
        client.post("/api/auth/logout")
        return out

    report("arjun", int(other.id))
    report("meera", int(other.id))
    report("riya", int(place.id), note="pin is on the next lane")
    assert report("riya", int(place.id), note="again").json()["already"] is True

    client.post("/api/auth/login", json={"identifier": "admin", "password": PASSWORD})
    cases = client.get("/api/admin/cases").json()["cases"]
    assert [c["place_id"] for c in cases] == [int(place.id), int(other.id)]  # the visitor first
    assert cases[0]["reporters_who_visited"] == 1 and cases[0]["reports"] == 1
    assert cases[1]["reporters"] == 2

    done = client.post(
        "/api/admin/actions",
        json={"action": "resolve", "target_type": "place", "target_id": int(place.id)},
    )
    assert done.status_code == 200
    assert len(client.get("/api/admin/cases").json()["cases"]) == 1


# --- state-wide browsing ----------------------------------------------------- #

def test_searching_a_state_name_surfaces_it_to_browse(client, session):
    city = make_city(session)
    make_place(session, city, "Mallikarjuna Temple, Goa", state="Goa", lat=15.5, lng=73.9)
    make_place(session, city, "Goa Science Centre", state="Goa", lat=15.49, lng=73.91)
    make_place(session, city, "Basilica of Bom Jesus", state="Goa", lat=15.5007, lng=73.9119)

    result = client.get("/api/search?q=Goa").json()
    assert [s["name"] for s in result["states"]] == ["Goa"]
    assert result["states"][0]["place_count"] == 3


def test_a_state_can_be_browsed_like_a_city_including_places_with_no_goa_in_the_name(client, session):
    city = make_city(session)
    make_place(session, city, "Mallikarjuna Temple, Goa", state="Goa", lat=15.5, lng=73.9)
    make_place(session, city, "Basilica of Bom Jesus", state="Goa", lat=15.5007, lng=73.9119)
    make_place(session, city, "Something in Telangana", state="Telangana", lat=17.4, lng=78.4)

    out = client.get("/api/states/goa/places?sort=liked").json()
    assert out["city"]["name"] == "Goa"
    assert out["total"] == 2
    names = {p["name"]["primary"]["text"] for p in out["places"]}
    assert "Basilica of Bom Jesus" in names          # no "Goa" in its name at all
    assert "Something in Telangana" not in names


def test_unknown_state_404s(client, session):
    make_city(session)
    assert client.get("/api/states/atlantis/places").status_code == 404


def test_admin_controls_are_for_the_official_account_only(client, session):
    """A `role="admin"` account that is not `official` must not reach them."""
    make_user(session, "wannabe", role="admin", email="wannabe@example.com")
    client.post("/api/auth/login", json={"identifier": "wannabe", "password": PASSWORD})
    assert client.get("/api/admin/cases").status_code == 403

    make_user(session, "truvel2", official=True, email="truvel2@example.com")
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"identifier": "truvel2", "password": PASSWORD})
    assert client.get("/api/admin/cases").status_code == 200


def test_searching_a_locality_surfaces_it_and_browsing_it_works(client, session):
    city = make_city(session)
    make_place(
        session, city, "Tirumala Venkateswara Temple", state="Andhra Pradesh",
        locality="Tirupati", lat=13.68, lng=79.35,
    )
    make_place(
        session, city, "Govindaraja Temple, Tirupati", state="Andhra Pradesh",
        locality="Tirupati", lat=13.65, lng=79.42,
    )
    make_place(
        session, city, "Something in Chennai", state="Tamil Nadu",
        locality="Chennai", lat=13.08, lng=80.27,
    )

    result = client.get("/api/search?q=tirupati").json()
    assert [loc["name"] for loc in result["localities"]] == ["Tirupati"]
    assert result["localities"][0]["place_count"] == 2

    out = client.get("/api/localities/tirupati/places").json()
    assert out["total"] == 2
    names = {p["name"]["primary"]["text"] for p in out["places"]}
    assert names == {"Tirumala Venkateswara Temple", "Govindaraja Temple, Tirupati"}


def test_unknown_locality_404s(client, session):
    make_city(session)
    assert client.get("/api/localities/atlantis/places").status_code == 404


def test_searching_within_a_city_stays_scoped_to_it(client, session):
    """The Explore search box must not quietly become an all-India search."""
    city = make_city(session)
    make_place(session, city, "Birla Mandir Temple", lat=17.4, lng=78.46)
    make_place(
        session, None, "Birla Mandir, Jaipur", state="Rajasthan", lat=26.9, lng=75.8,
    )

    out = client.get(f"/api/cities/{city.slug}/places?q=birla").json()
    names = {p["name"]["primary"]["text"] for p in out["places"]}
    assert names == {"Birla Mandir Temple"}
    assert "Birla Mandir, Jaipur" not in names


def test_place_location_falls_back_to_locality_not_just_area(client, session):
    """Most places have no neighbourhood (only a deeply-seeded city does); the
    nearest town Wikidata records should still show, not just the state."""
    city = make_city(session)
    with_area = make_place(session, city, "Has Area", area="Banjara Hills")
    with_locality = make_place(session, None, "Has Locality", locality="Tirupati")
    with_neither = make_place(session, None, "Has Neither")

    a = client.get(f"/api/places/{with_area.id}").json()
    b = client.get(f"/api/places/{with_locality.id}").json()
    c = client.get(f"/api/places/{with_neither.id}").json()
    assert a["area"] == "Banjara Hills"
    assert b["area"] == "Tirupati"
    assert c["area"] == ""


def test_here_says_the_seeded_city_inside_its_bbox(client, session):
    city = make_city(session)  # Hyderabad bbox from the fixture
    out = client.get("/api/here?lat=17.40&lng=78.45").json()
    assert out == {"name": city.name_en, "state": city.state, "kind": "city", "slug": city.slug}


def test_here_falls_back_to_the_nearest_localitys_town(client, session):
    make_place(session, None, "Tirumala Venkateswara Temple", state="Andhra Pradesh",
               locality="Tirupati", lat=13.68, lng=79.35)
    out = client.get("/api/here?lat=13.681&lng=79.351").json()
    assert out["name"] == "Tirupati"
    assert out["kind"] == "locality"
    # Explore's default scope relies on this slug matching `locality_places`
    # exactly, so a town like Tirupati (or Araku) can be jumped to without
    # ever being added to the hand-picked city list (SPEC §8.4).
    assert out["slug"] == "tirupati"


def test_here_is_none_far_from_anything_known(client, session):
    out = client.get("/api/here?lat=5.0&lng=5.0").json()
    assert out["name"] is None
    assert out["slug"] is None


def test_deck_eventually_shows_every_place_within_radius(client, session):
    """A place within the chosen radius must not be permanently invisible just
    because it did not score into the first page (SPEC §9.4 is a ranking, not
    a filter: `request_no` pages a stable order rather than re-drawing it)."""
    city = make_city(session)
    for i in range(45):
        make_place(
            session, city, f"Place {i}",
            lat=KHAJAGUDA[0] + i * 0.0003, lng=KHAJAGUDA[1], fame="famous", sitelinks=i,
        )
    make_user(session, "pagerider", email="pagerider@example.com")
    client.post("/api/auth/login", json={"identifier": "pagerider", "password": PASSWORD})

    seen: set[str] = set()
    total = None
    for request_no in range(3):
        out = client.get(
            f"/api/deck?lat={KHAJAGUDA[0]}&lng={KHAJAGUDA[1]}&radius_km=10&request_no={request_no}"
        ).json()
        total = out["total_candidates"]
        seen |= {c["name"]["primary"]["text"] for c in out["cards"]}
        if not out["more_at_this_radius"]:
            break

    assert total == 45
    assert len(seen) == 45


def test_deck_page_is_stable_when_radius_is_unchanged(client, session):
    city = make_city(session)
    for i in range(5):
        make_place(session, city, f"Stable {i}", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1], fame="famous")
    make_user(session, "stableuser", email="stableuser@example.com")
    client.post("/api/auth/login", json={"identifier": "stableuser", "password": PASSWORD})

    first = client.get(f"/api/deck?lat={KHAJAGUDA[0]}&lng={KHAJAGUDA[1]}&radius_km=10").json()
    again = client.get(f"/api/deck?lat={KHAJAGUDA[0]}&lng={KHAJAGUDA[1]}&radius_km=10").json()
    assert [c["id"] for c in first["cards"]] == [c["id"] for c in again["cards"]]


# --- uploading a photo before the place exists (Add a place, step 1) ------- #

def _jpeg_bytes(colour=(80, 110, 60)) -> bytes:
    import io as _io

    from PIL import Image

    img = Image.new("RGB", (640, 480), colour)
    for x in range(0, 640, 40):
        for y in range(0, 480, 40):
            shade = ((x + y) // 40) % 2
            img.paste((200, 200, 200) if shade else (20, 20, 20), (x, y, x + 20, y + 20))
    buf = _io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def test_you_can_upload_a_photo_before_the_place_exists(client, session):
    """Add a place step 1: a photo with no place yet (SPEC §8.6). This used to
    insert place_id=0, which is not a place and always violated the foreign
    key -- "something went wrong" on every upload."""
    make_user(session, "founder", email="founder@example.com")
    client.post("/api/auth/login", json={"identifier": "founder", "password": PASSWORD})

    up = client.post(
        "/api/places/0/media",
        files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
        data={"kind": "photo", "caption": "A rock"},
    )
    assert up.status_code == 200, up.text
    media_id = up.json()["media"]["id"]
    assert session.get(Media, media_id).place_id is None

    created = client.post(
        "/api/places",
        json={
            "lat": 17.41, "lng": 78.41, "name": "A New Rock",
            "category": "hill_trek", "media_ids": [media_id],
        },
    )
    assert created.status_code == 200, created.text
    place_id = created.json()["place"]["id"]
    session.expire_all()
    assert session.get(Media, media_id).place_id == place_id


def test_a_second_photo_with_no_place_yet_is_not_a_duplicate_of_the_first(client, session):
    """Two different, unattached uploads must not collide on place_id=None."""
    make_user(session, "founder2", email="founder2@example.com")
    client.post("/api/auth/login", json={"identifier": "founder2", "password": PASSWORD})

    first = client.post(
        "/api/places/0/media",
        files={"file": ("a.jpg", _jpeg_bytes((10, 20, 30)), "image/jpeg")},
        data={"kind": "photo", "caption": "First"},
    )
    second = client.post(
        "/api/places/0/media",
        files={"file": ("b.jpg", _jpeg_bytes((200, 210, 220)), "image/jpeg")},
        data={"kind": "photo", "caption": "Second"},
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["media"]["id"] != second.json()["media"]["id"]
