"""Card A1 -- one test per fixed finding from the independent security review.

See docs/SECURITY_REVIEW.md for the finding each test closes.
"""
from __future__ import annotations

import threading

from sqlmodel import select

from app import auth, services
from app.geo import haversine_km
from app.models import KadamEntry, Touch, Visit
from tests.conftest import make_city, make_place, make_user

PASSWORD = "correct horse battery"
KHAJAGUDA = (17.4186, 78.3391)


def register(client, username: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": f"{username}@example.com", "username": username, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["user"]


def login(client, identifier: str) -> None:
    response = client.post(
        "/api/auth/login", json={"identifier": identifier, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text


# --- 1. Critical: fragile-place distance oracle --------------------------- #

def test_fragile_place_distance_comes_from_fuzzed_not_true_coordinates(session, client):
    """Finding 1: distance_km must not let three readings trilaterate the pin."""
    city = make_city(session)
    lat, lng = KHAJAGUDA
    place = make_place(session, city, lat=lat, lng=lng, fragile=True)
    register(client, "finder_a1")

    out_lat = round(lat, services.FRAGILE_PRECISION)
    out_lng = round(lng, services.FRAGILE_PRECISION)

    for probe_lat, probe_lng in [(lat + 0.05, lng), (lat, lng + 0.05), (lat - 0.03, lng + 0.02)]:
        resp = client.get(
            f"/api/places/{place.id}", params={"lat": probe_lat, "lng": probe_lng}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["coords_exact"] is False
        expected = round(haversine_km(probe_lat, probe_lng, out_lat, out_lng), 2)
        assert body["distance_km"] == expected, (
            "distance_km leaked true-coordinate precision -- a fragile place's "
            "exact pin would be recoverable without ever pledging"
        )


def test_duplicate_candidates_hide_exact_distance_for_fragile_unpledged_place(session, client):
    """Finding 1 continued: the dedupe 'is it one of these?' oracle."""
    city = make_city(session)
    lat, lng = KHAJAGUDA
    make_place(session, city, name="Secret Falls", lat=lat, lng=lng, fragile=True, category="waterfall")
    register(client, "finder_a1b")

    resp = client.post(
        "/api/places/candidates",
        json={"lat": lat + 0.001, "lng": lng, "name": "Secret Falls", "category": "waterfall"},
    )
    assert resp.status_code == 200, resp.text
    candidates = resp.json()["candidates"]
    assert candidates, "expected the fragile place to surface as a duplicate candidate"
    assert candidates[0]["coords_exact"] is False
    assert "distance_m" not in candidates[0]


# --- 2. High: /api/touch trusted the client for video/photo --------------- #

def test_touch_rejects_video_and_photo_content_types(session, client):
    """Finding 2: legitimate video/photo touches only come from a real watch view."""
    city = make_city(session)
    place = make_place(session, city)
    register(client, "viewer_a1")

    resp = client.post(
        "/api/touch", json={"place_id": place.id, "content_type": "video", "content_id": 1}
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "bad_touch"


def test_touch_does_not_duplicate_on_repeated_calls(session, client):
    """Finding 2 continued: one real page view must not become many weighted touches."""
    city = make_city(session)
    place = make_place(session, city)
    finder = make_user(session, "finder_touch")
    place.added_by = finder.id
    session.add(place)
    session.commit()
    register(client, "viewer_dedupe")

    for _ in range(5):
        client.post("/api/touch", json={"place_id": place.id, "content_type": "place"})

    rows = session.exec(select(Touch).where(Touch.place_id == place.id)).all()
    assert len(rows) == 1


def test_touch_is_rate_limited(session, client):
    """Finding 2 continued: flooding /api/touch must hit a cap, same as every other write."""
    from app.config import cfg

    limit = int(cfg("rate_limits.touches_per_hour"))
    city = make_city(session)
    finder = make_user(session, "finder_flood")
    places = [
        make_place(session, city, name=f"P{i}", lat=17.30 + i * 0.01, added_by=finder.id)
        for i in range(limit + 2)
    ]
    register(client, "flooder_a1")

    codes = [
        client.post("/api/touch", json={"place_id": p.id, "content_type": "place"}).status_code
        for p in places
    ]
    assert 429 in codes, "expected the rate limit to eventually trigger"


# --- 3. High: viewer lat/lng in uvicorn access logs ------------------------ #

def test_uvicorn_access_logger_is_disabled():
    """Finding 3: every deck/watch/search request carries the viewer's lat/lng
    as a query parameter, which uvicorn's default access logger prints in
    full -- a location history in plaintext log files (invariant 1)."""
    import logging

    assert logging.getLogger("uvicorn.access").disabled is True


# --- 4. High: check-in race condition -------------------------------------- #

def test_concurrent_checkins_award_kadam_only_once(session, client):
    """Finding 4: two near-simultaneous check-ins must not double-award."""
    city = make_city(session)
    lat, lng = KHAJAGUDA
    place = make_place(session, city, lat=lat, lng=lng, radius_m=50)
    place_id = int(place.id)
    user = register(client, "racer_a1")

    results = []
    results_lock = threading.Lock()

    def do_checkin():
        resp = client.post(
            f"/api/places/{place_id}/checkin",
            json={"lat": lat, "lng": lng, "accuracy": 10.0},
        )
        body = resp.json()
        with results_lock:
            results.append(body)

    threads = [threading.Thread(target=do_checkin) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    verified_first_visits = [r for r in results if r.get("code") == "ok"]
    assert len(verified_first_visits) == 1, (
        f"expected exactly one request to win the race, got {len(verified_first_visits)}: {results}"
    )

    own_visit_entries = session.exec(
        select(KadamEntry).where(
            KadamEntry.user_id == user["id"], KadamEntry.reason == "own_visit"
        )
    ).all()
    assert len(own_visit_entries) == 1

    verified_visits = session.exec(
        select(Visit).where(Visit.user_id == user["id"], Visit.verified == True)  # noqa: E712
    ).all()
    assert len(verified_visits) == 1


# --- 5. Medium: login timing side-channel ---------------------------------- #

def test_login_with_nonexistent_identifier_still_calls_verify_password(session, client, monkeypatch):
    """Finding 5: a non-existent identifier must pay the same argon2id cost as
    a wrong password on a real account, or the identical error message (SPEC
    §11) is undone by a measurable timing difference."""
    calls = []
    real_verify = auth.verify_password

    def spy(password_hash: str, password: str) -> bool:
        calls.append(password_hash)
        return real_verify(password_hash, password)

    monkeypatch.setattr("app.routers.auth_router.auth.verify_password", spy)

    resp = client.post(
        "/api/auth/login", json={"identifier": "nobody-with-this-name", "password": "whatever123"}
    )
    assert resp.status_code == 401
    assert len(calls) == 1
    assert calls[0] == auth.dummy_hash()


def test_dummy_hash_never_verifies_as_a_real_password():
    assert auth.verify_password(auth.dummy_hash(), "anything") is False


# --- 6. Medium: dev teleport leaked fragile coordinates -------------------- #

def test_teleport_hides_fragile_place_before_pledge(session, client):
    """Finding 6: the dev simulator must obey the same pledge gate as the API."""
    city = make_city(session)
    lat, lng = KHAJAGUDA
    place = make_place(session, city, lat=lat, lng=lng, fragile=True)
    register(client, "demo_a1")

    import os

    os.environ["DEV_ALLOW_FAKE_LOCATION"] = "1"
    try:
        resp = client.post("/api/dev/teleport", json={"place_id": place.id})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["lat"] == round(lat, services.FRAGILE_PRECISION)
        assert body["lng"] == round(lng, services.FRAGILE_PRECISION)

        pledge = client.post(f"/api/places/{place.id}/fragile-pledge")
        assert pledge.status_code == 200, pledge.text

        resp2 = client.post("/api/dev/teleport", json={"place_id": place.id})
        assert resp2.json()["lat"] == lat
        assert resp2.json()["lng"] == lng
    finally:
        os.environ.pop("DEV_ALLOW_FAKE_LOCATION", None)


# --- security headers ------------------------------------------------------ #

def test_security_headers_present(client):
    resp = client.get("/api/health")
    assert "default-src 'self'" in resp.headers["content-security-policy"]
    assert "tiles.openfreemap.org" in resp.headers["content-security-policy"]
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["referrer-policy"] == "same-origin"
    assert "geolocation=(self)" in resp.headers["permissions-policy"]
