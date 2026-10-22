"""End-to-end API behaviour: AC-8, AC-9, AC-12, AC-15, AC-22, AC-23, AC-25."""
from __future__ import annotations

from datetime import timedelta

from sqlmodel import select

from app.models import Place, Pulse, Touch, Visit, utcnow
from tests.conftest import make_city, make_place, make_user

PASSWORD = "correct horse battery"
KHAJAGUDA = (17.4186, 78.3391)


def register(client, username: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"{username}@example.com",
            "username": username,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["user"]


def login(client, identifier: str) -> None:
    response = client.post(
        "/api/auth/login", json={"identifier": identifier, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text


# --- health, config, auth -------------------------------------------------- #

def test_health_reports_the_flags(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["simulated_money"] is True
    assert body["dev_fake_location"] is False          # off unless the flag is set
    assert "te" in body["languages"]


def test_register_and_me(client, session):
    make_city(session)
    user = register(client, "riya")
    assert user["username"] == "riya"
    assert user["kadam"] == 0
    assert user["level"] == "Wanderer"

    me = client.get("/api/me").json()["user"]
    assert me["username"] == "riya"


def test_login_failure_is_generic(client, session):
    """The error must not reveal whether the username exists (SPEC §11)."""
    make_city(session)
    register(client, "riya")
    client.post("/api/auth/logout")

    wrong_password = client.post(
        "/api/auth/login", json={"identifier": "riya", "password": "wrong password here"}
    )
    no_such_user = client.post(
        "/api/auth/login", json={"identifier": "nobody", "password": "wrong password here"}
    )
    assert wrong_password.status_code == no_such_user.status_code == 401
    assert wrong_password.json()["error"]["message"] == no_such_user.json()["error"]["message"]


def test_mutating_request_needs_the_csrf_header(client, session):
    """SPEC §11: X-Requested-With is required on mutating requests."""
    make_city(session)
    response = client.post(
        "/api/auth/register",
        json={"email": "nocsrf@example.com", "username": "nocsrf", "password": PASSWORD},
        headers={"X-Requested-With": ""},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf"


def test_username_and_password_rules(client, session):
    make_city(session)

    def signup(**overrides):
        body = {"email": "ok@example.com", "username": "okname", "password": PASSWORD}
        body.update(overrides)
        return client.post("/api/auth/register", json=body)

    assert signup(username="AB").status_code in (400, 422)
    assert signup(password="short").status_code in (400, 422)
    assert signup(email="not-an-email").status_code in (400, 422)
    # NIST SP 800-63B: a blocklist, not a symbol rule.
    assert signup(password="password123").status_code in (400, 422)
    # And a password must not just be your own name back at you.
    assert signup(password="okname-okname").status_code in (400, 422)


def test_login_accepts_the_email_as_well_as_the_handle(client, session):
    make_city(session)
    register(client, "riya")
    client.post("/api/auth/logout")
    login(client, "riya@example.com")


def test_an_email_is_used_once(client, session):
    make_city(session)
    register(client, "riya")
    client.post("/api/auth/logout")
    clash = client.post(
        "/api/auth/register",
        json={"email": "riya@example.com", "username": "someoneelse", "password": PASSWORD},
    )
    assert clash.status_code == 400
    assert clash.json()["error"]["code"] == "email_taken"


def test_login_is_throttled_after_repeated_failures(client, session):
    """SPEC §11: guessing a password has to get slower, not stay free."""
    from app import auth

    make_city(session)
    register(client, "riya")
    client.post("/api/auth/logout")

    codes = [
        client.post(
            "/api/auth/login", json={"identifier": "riya", "password": "wrong one here"}
        ).status_code
        for _ in range(auth.LOGIN_MAX_FAILURES + 2)
    ]
    assert codes[0] == 401
    assert codes[-1] == 429

    # The right password is refused too while the brake is on, so a correct
    # guess at the end of a run of wrong ones does not get through.
    assert client.post(
        "/api/auth/login", json={"identifier": "riya", "password": PASSWORD}
    ).status_code == 429
    auth._login_failures.clear()


def test_error_shape_matches_the_spec(client):
    body = client.get("/api/places/999999").json()
    assert set(body["error"]) == {"code", "message", "detail"}


# --- AC-9: likes, views, follows ------------------------------------------- #

def test_ac9_one_like_per_user_and_likes_never_exceed_viewers(client, session):
    city = make_city(session)
    owner = make_user(session, "owner")
    place = make_place(session, city, "Khajaguda Rocks", added_by=int(owner.id))
    register(client, "liker")

    first = client.post(f"/api/places/{place.id}/like")
    second = client.post(f"/api/places/{place.id}/like")
    assert first.json()["likes"] == 1
    assert second.json()["likes"] == 1, "liking twice must not count twice"

    detail = client.get(f"/api/places/{place.id}").json()
    assert detail["likes"] <= detail["viewers"], "likes <= viewers invariant"


def test_ac9_self_like_is_rejected(client, session):
    city = make_city(session)
    me = register(client, "selfliker")
    place = make_place(session, city, "My Own Find", added_by=me["id"])
    response = client.post(f"/api/places/{place.id}/like")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "self_like"


def test_ac9_unlike_then_like_again(client, session):
    city = make_city(session)
    owner = make_user(session, "owner2")
    place = make_place(session, city, "A Place", added_by=int(owner.id))
    register(client, "fickle")
    client.post(f"/api/places/{place.id}/like")
    assert client.delete(f"/api/places/{place.id}/like").json()["likes"] == 0
    assert client.post(f"/api/places/{place.id}/like").json()["likes"] == 1


def test_ac9_follow_is_idempotent(client, session):
    make_city(session)
    make_user(session, "creator")          # the row is what matters, not the handle
    register(client, "follower")
    assert client.post("/api/users/creator/follow").json()["following"] is True
    assert client.post("/api/users/creator/follow").json()["following"] is True
    assert client.delete("/api/users/creator/follow").json()["following"] is False
    assert client.delete("/api/users/creator/follow").json()["following"] is False


def test_cannot_follow_yourself(client, session):
    make_city(session)
    register(client, "narcissus")
    assert client.post("/api/users/narcissus/follow").status_code == 403


# --- AC-8: check-in verification ------------------------------------------- #

def test_ac8_checkin_inside_the_radius_verifies(client, session):
    city = make_city(session)
    place = make_place(session, city, "Khajaguda Rocks", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "walker")

    body = client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0] + 0.0004, "lng": KHAJAGUDA[1], "accuracy": 12},
    ).json()
    assert body["verified"] is True
    assert body["kadam"] == 5                      # own_visit
    assert body["first_visit"] is True
    assert body["stamp"]["name"] == "Khajaguda Rocks"


def test_ac8_too_far_is_refused_with_the_distance(client, session):
    city = make_city(session)
    place = make_place(session, city, "Far Place", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "faraway")

    body = client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0] + 0.0126, "lng": KHAJAGUDA[1], "accuracy": 10},
    ).json()
    assert body["verified"] is False
    assert body["code"] == "too_far"
    assert "away" in body["message"]


def test_ac8_poor_accuracy_is_refused(client, session):
    city = make_city(session)
    place = make_place(session, city, "Blurry", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "blurry")

    body = client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 240},
    ).json()
    assert body["verified"] is False
    assert body["code"] == "poor_accuracy"
    assert "open sky" in body["message"]


def test_ac8_accuracy_boundary_is_inclusive(client, session):
    city = make_city(session)
    place = make_place(session, city, "Edge", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "edgecase")
    body = client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 100},
    ).json()
    assert body["verified"] is True


def test_ac8_second_checkin_the_same_day_pays_nothing(client, session):
    city = make_city(session)
    place = make_place(session, city, "Twice", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "twice")
    payload = {"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 10}
    client.post(f"/api/places/{place.id}/checkin", json=payload)
    again = client.post(f"/api/places/{place.id}/checkin", json=payload).json()
    assert again["code"] == "already_today"
    assert again["kadam"] == 0


def test_ac8_no_coordinates_are_stored_anywhere(client, session):
    """Invariant 1, asserted against the table columns themselves."""
    city = make_city(session)
    place = make_place(session, city, "Private", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "private")
    client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 9},
    )

    for model in (Visit, Pulse, Touch):
        columns = set(model.model_fields)
        assert not columns & {"lat", "lng", "latitude", "longitude", "accuracy_lat"}, (
            f"{model.__name__} must not have coordinate columns"
        )

    visit = session.exec(select(Visit)).first()
    assert visit is not None
    assert visit.distance_m >= 0 and visit.accuracy_m == 9


def test_ac8_impossible_travel_is_flagged_and_pays_nothing(client, session):
    """A check-in in Kerala one minute after one in Hyderabad."""
    city = make_city(session)
    near = make_place(session, city, "Hyderabad Spot", lat=17.4000, lng=78.4000)
    far = make_place(session, city, "Kerala Spot", lat=10.2850, lng=76.5690)
    register(client, "teleporter")

    client.post(
        f"/api/places/{near.id}/checkin",
        json={"lat": 17.4000, "lng": 78.4000, "accuracy": 10},
    )
    body = client.post(
        f"/api/places/{far.id}/checkin",
        json={"lat": 10.2850, "lng": 76.5690, "accuracy": 10},
    ).json()
    assert body["verified"] is True
    assert body["flag"] == "speed"
    assert body["kadam"] == 0, "a flagged visit earns nothing"


# --- AC-12: Pulse ---------------------------------------------------------- #

def test_ac12_pulse_needs_a_recent_verified_visit(client, session):
    city = make_city(session)
    place = make_place(session, city, "Waterfall", category="waterfall", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "reporter")

    refused = client.post(f"/api/places/{place.id}/pulse", json={"crowd": "quiet"})
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "no_recent_visit"

    client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 10},
    )
    accepted = client.post(
        f"/api/places/{place.id}/pulse",
        json={"water": "flowing", "crowd": "quiet", "note": "Breezy on top"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["kadam"] == 3


def test_ac12_live_pill_appears_on_the_place(client, session):
    city = make_city(session)
    place = make_place(session, city, "Live Place", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "livereporter")
    client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 10},
    )
    client.post(f"/api/places/{place.id}/pulse", json={"crowd": "quiet"})

    detail = client.get(f"/api/places/{place.id}").json()
    assert detail["live"] is True
    assert detail["pulse"]["freshness"] == "live"
    assert detail["pulse"]["fields"]["crowd"]["value"] == "quiet"


def test_ac12_mixed_reports_rule(client, session):
    """Two disagreeing reports inside 6 h must be reported as mixed."""
    city = make_city(session)
    place = make_place(session, city, "Disputed", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    now = utcnow()
    first = make_user(session, "saysquiet")
    second = make_user(session, "sayspacked")
    for user, crowd in ((first, "quiet"), (second, "packed")):
        session.add(
            Pulse(place_id=int(place.id), user_id=int(user.id), at=now - timedelta(minutes=30), crowd=crowd)
        )
    session.add(
        Pulse(place_id=int(place.id), user_id=int(first.id), at=now - timedelta(minutes=10), crowd="quiet")
    )
    session.commit()

    from app.services import pulse_summary

    summary = pulse_summary(session, int(place.id), now)
    assert summary["fields"]["crowd"]["mixed"] is True
    assert summary["fields"]["crowd"]["value"] == "quiet"      # the majority


def test_ac12_water_field_is_ignored_for_dry_categories(client, session):
    city = make_city(session)
    place = make_place(session, city, "A Fort", category="fort_heritage", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "wrongfield")
    client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 10},
    )
    client.post(f"/api/places/{place.id}/pulse", json={"water": "flowing", "crowd": "busy"})
    detail = client.get(f"/api/places/{place.id}").json()
    assert "water" not in detail["pulse"]["fields"]


# --- AC-15: unverified and fragile ----------------------------------------- #

def test_ac15_unverified_places_are_excluded_from_top_and_gems(client, session):
    city = make_city(session)
    make_place(session, city, "Verified Place", status="verified")
    make_place(session, city, "Unverified Place", status="unverified", lat=17.41, lng=78.41)

    for sort in ("top", "gems", "trending"):
        names = [
            p["name"]["primary"]["text"]
            for p in client.get(f"/api/cities/hyderabad/places?sort={sort}").json()["places"]
        ]
        assert "Unverified Place" not in names, f"unverified leaked into {sort}"

    # It is still findable by distance and by search.
    near = client.get("/api/cities/hyderabad/places?sort=near").json()["places"]
    assert "Unverified Place" in [p["name"]["primary"]["text"] for p in near]


def test_ac15_fragile_place_hides_its_pin_until_the_pledge(client, session):
    """Invariant 5, tested directly against the API (not the UI)."""
    city = make_city(session)
    place = make_place(
        session, city, "Secret Stepwell", fragile=True, lat=17.412345, lng=78.398765
    )
    register(client, "curious")

    before = client.get(f"/api/places/{place.id}").json()
    assert before["coords_exact"] is False
    assert before["lat"] == round(17.412345, 2)
    assert before["maps_url"] is None
    assert client.get(f"/api/places/{place.id}/steps").json()["locked"] is True

    client.post(f"/api/places/{place.id}/fragile-pledge")

    after = client.get(f"/api/places/{place.id}").json()
    assert after["coords_exact"] is True
    assert after["lat"] == 17.412345
    assert after["maps_url"].endswith("17.412345,78.398765")


def test_ac15_fragile_places_are_excluded_from_gems_and_the_deck(client, session):
    city = make_city(session)
    make_place(session, city, "Fragile Gem", fragile=True)
    register(client, "deckuser")

    gems = client.get("/api/cities/hyderabad/places?sort=gems").json()["places"]
    assert "Fragile Gem" not in [p["name"]["primary"]["text"] for p in gems]

    cards = client.get("/api/deck?lat=17.40&lng=78.40&radius_km=25").json()["cards"]
    assert "Fragile Gem" not in [c["name"]["primary"]["text"] for c in cards]


def test_ac15_community_place_verifies_after_two_visitors(client, session):
    city = make_city(session)
    finder = make_user(session, "thefinder")
    place = make_place(
        session,
        city,
        "New Find",
        added_by=int(finder.id),
        status="unverified",
        source="community",
        lat=KHAJAGUDA[0],
        lng=KHAJAGUDA[1],
    )
    payload = {"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 10}

    register(client, "visitor_one")
    first = client.post(f"/api/places/{place.id}/checkin", json=payload).json()
    assert first["place_verified"] is False
    client.post("/api/auth/logout")

    register(client, "visitor_two")
    second = client.post(f"/api/places/{place.id}/checkin", json=payload).json()
    assert second["place_verified"] is True

    session.expire_all()
    assert session.get(Place, place.id).status == "verified"

    from app import kadam

    assert kadam.balance(session, int(finder.id)) == 50       # discovery paid once


# --- AC-25: dev tools ------------------------------------------------------ #

def test_ac25_teleport_is_404_without_the_flag(client, session):
    make_city(session)
    register(client, "devuser")
    response = client.post("/api/dev/teleport", json={})
    assert response.status_code == 404


def test_ac25_simulated_checkin_is_refused_without_the_flag(client, session):
    city = make_city(session)
    place = make_place(session, city, "Real Place", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "faker")
    response = client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 10, "simulated": True},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "no_fake_location"


def test_ac25_simulated_visits_never_reach_attribution_or_earnings(client, session, monkeypatch):
    """With the flag on, a simulated visit still earns and attributes nothing."""
    monkeypatch.setenv("DEV_ALLOW_FAKE_LOCATION", "1")
    city = make_city(session)
    creator = make_user(session, "simcreator")
    place = make_place(
        session, city, "Sim Place", added_by=int(creator.id), lat=KHAJAGUDA[0], lng=KHAJAGUDA[1]
    )
    user = register(client, "simvisitor")
    session.add(
        Touch(
            user_id=user["id"],
            place_id=int(place.id),
            creator_id=int(creator.id),
            content_type="place",
            at=utcnow() - timedelta(days=1),
        )
    )
    session.commit()

    body = client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 10, "simulated": True},
    ).json()
    assert body["verified"] is True
    assert body["simulated"] is True
    assert body["kadam"] == 0
    assert body["attributed"] == []

    from app import kadam
    from app.models import Attribution

    assert kadam.balance(session, int(creator.id)) == 0
    assert session.exec(select(Attribution)).first() is None


# --- AC-23: every rupee is labelled simulated ------------------------------ #

def test_ac23_studio_always_carries_the_simulated_banner(client, session):
    make_city(session)
    register(client, "creatorx")
    studio = client.get("/api/studio").json()
    assert studio["simulated"] is True
    assert "Simulated" in studio["banner"]
    assert "No real money" in studio["banner"]
    # Earnings are reported in paise, so the UI can format and label them.
    assert "estimated_earnings_paise" in studio["metrics"]


def test_ac23_config_declares_simulated_money(client):
    assert client.get("/api/config").json()["simulated_money"] is True


def test_split_explainer_is_present_and_honest(client, session):
    make_city(session)
    register(client, "curiouscreator")
    lines = client.get("/api/studio").json()["split_explainer"]["lines"]
    joined = " ".join(lines).lower()
    assert "simulated" in joined
    assert "no money is paid" in joined


# --- AC-22: the Maps link and attributions --------------------------------- #

def test_ac22_open_in_maps_url_is_exact(client, session):
    city = make_city(session)
    place = make_place(session, city, "Mapped", lat=17.4186, lng=78.3391)
    register(client, "mapuser")
    detail = client.get(f"/api/places/{place.id}").json()
    assert detail["maps_url"] == (
        "https://www.google.com/maps/dir/?api=1&destination=17.4186,78.3391"
    )


def test_ac22_attribution_is_present_per_source(client, session):
    city = make_city(session)
    osm = make_place(session, city, "From OSM", source="osm")
    wikidata = make_place(session, city, "From Wikidata", source="wikidata", lat=17.41, lng=78.41)
    community = make_place(session, city, "From A Local", source="community", lat=17.42, lng=78.42)
    register(client, "attributionuser")

    assert "OpenStreetMap" in client.get(f"/api/places/{osm.id}").json()["attribution"]
    assert "Wikidata" in client.get(f"/api/places/{wikidata.id}").json()["attribution"]
    assert "OpenStreetMap" in client.get(f"/api/places/{community.id}").json()["attribution"]


# --- search and sorts ------------------------------------------------------ #

def test_ac5_search_works_in_english_and_in_a_local_script(client, session):
    from app.models import PlaceName

    city = make_city(session)
    place = make_place(session, city, "Golconda Fort", category="fort_heritage")
    session.add(
        PlaceName(
            place_id=int(place.id),
            lang="te",
            name="గోల్కొండ కోట",
            source="wikidata",
        )
    )
    session.commit()

    english = client.get("/api/search?q=golconda").json()
    assert [p["id"] for p in english["places"]] == [place.id]

    telugu = client.get(
        "/api/search?q=గోల్కొండ"
    ).json()
    assert [p["id"] for p in telugu["places"]] == [place.id]

    partial = client.get("/api/search?q=golc").json()
    assert [p["id"] for p in partial["places"]] == [place.id]


def test_ac5_all_five_sorts_answer(client, session):
    city = make_city(session)
    for i in range(3):
        make_place(session, city, f"Place {i}", lat=17.40 + i * 0.01, lng=78.40)
    for sort in ("top", "liked", "gems", "trending", "near"):
        body = client.get(f"/api/cities/hyderabad/places?sort={sort}").json()
        assert body["sort"] == sort
        assert body["explainer"]
        assert isinstance(body["places"], list)


def test_top_sort_prefers_the_better_like_rate(client, session):
    """The reference's claim: 1,284 likes can beat 4,120 (SPEC §9.1)."""
    from app.models import Like, View

    city = make_city(session)
    gem = make_place(session, city, "Khajaguda Rocks")
    popular = make_place(session, city, "Durgam Cheruvu", lat=17.41, lng=78.41)

    # The gem: 90 of 100 viewers liked it. The popular place: 200 of 1000.
    for i in range(1, 101):
        user = make_user(session, f"gemviewer{i}")
        session.add(View(user_id=int(user.id), place_id=int(gem.id)))
        if i <= 90:
            session.add(Like(user_id=int(user.id), place_id=int(gem.id)))
    session.commit()
    for i in range(1, 301):
        user = make_user(session, f"popviewer{i}")
        session.add(View(user_id=int(user.id), place_id=int(popular.id)))
        if i <= 60:
            session.add(Like(user_id=int(user.id), place_id=int(popular.id)))
    session.commit()

    top = client.get("/api/cities/hyderabad/places?sort=top").json()["places"]
    assert top[0]["name"]["primary"]["text"] == "Khajaguda Rocks"
    liked = client.get("/api/cities/hyderabad/places?sort=liked").json()["places"]
    assert liked[0]["name"]["primary"]["text"] == "Khajaguda Rocks"      # 90 > 60


# --- deck ------------------------------------------------------------------ #

def test_ac10_deck_swipe_updates_the_category_prior(client, session):
    city = make_city(session)
    place = make_place(session, city, "Waterfall One", category="waterfall")
    register(client, "swiper")

    body = client.post("/api/deck/swipe", json={"place_id": place.id, "action": "save"}).json()
    assert (body["alpha"], body["beta"]) == (2.0, 1.0)
    body = client.post("/api/deck/swipe", json={"place_id": place.id, "action": "skip"}).json()
    assert (body["alpha"], body["beta"]) == (2.0, 2.0)


def test_ac10_deck_excludes_saved_and_visited_places(client, session):
    city = make_city(session)
    saved = make_place(session, city, "Already Saved")
    make_place(session, city, "Still New", lat=17.401, lng=78.401)
    register(client, "deckfilter")

    client.post(f"/api/places/{saved.id}/save")
    cards = client.get("/api/deck?lat=17.40&lng=78.40&radius_km=25").json()["cards"]
    names = [c["name"]["primary"]["text"] for c in cards]
    assert "Already Saved" not in names
    assert "Still New" in names


def test_deck_falls_back_to_the_city_centre(client, session):
    city = make_city(session)
    make_place(session, city, "Central", lat=city.centre_lat, lng=city.centre_lng)
    register(client, "nolocation")
    body = client.get("/api/deck").json()
    assert body["location_fallback"] is True
    assert body["cards"]


def test_deck_has_an_end_card_rather_than_an_infinite_feed(client, session):
    make_city(session)
    register(client, "endoftheroad")
    body = client.get("/api/deck?lat=17.40&lng=78.40&radius_km=5").json()
    assert body["cards"] == []
    assert "Widen" in body["end_card"]["message"]


# --- settings -------------------------------------------------------------- #

def test_unreviewed_ui_language_is_refused(client, session):
    """CLAUDE.md invariant 11: only native-reviewed UI languages can be set."""
    make_city(session)
    register(client, "languser")
    refused = client.patch("/api/me/settings", json={"ui_lang": "ta"})
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "lang_not_reviewed"
    assert client.patch("/api/me/settings", json={"ui_lang": "en"}).status_code == 200


def test_names_mode_changes_what_the_api_returns(client, session):
    from app.models import PlaceName

    city = make_city(session)
    place = make_place(session, city, "Golconda Fort")
    session.add(
        PlaceName(
            place_id=int(place.id),
            lang="te",
            name="గోల్కొండ కోట",
            source="wikidata",
        )
    )
    session.commit()
    register(client, "namemodes")

    default = client.get(f"/api/places/{place.id}").json()["name"]
    assert default["primary"]["lang"] == "en"
    assert default["secondary"]["lang"] == "te"

    client.patch("/api/me/settings", json={"names_mode": "en"})
    english_only = client.get(f"/api/places/{place.id}").json()["name"]
    assert english_only["secondary"] is None


def test_adding_a_name_needs_a_verified_visit(client, session):
    city = make_city(session)
    place = make_place(session, city, "Unvisited", lat=KHAJAGUDA[0], lng=KHAJAGUDA[1])
    register(client, "nameadder")

    refused = client.post(f"/api/places/{place.id}/names", json={"lang": "te", "name": "అటో"})
    assert refused.status_code == 403

    client.post(
        f"/api/places/{place.id}/checkin",
        json={"lat": KHAJAGUDA[0], "lng": KHAJAGUDA[1], "accuracy": 10},
    )
    accepted = client.post(
        f"/api/places/{place.id}/names", json={"lang": "te", "name": "అటో"}
    )
    assert accepted.status_code == 200
    assert accepted.json()["added"] is True


# --- reports --------------------------------------------------------------- #

def test_photo_of_me_hides_immediately(client, session):
    from app.models import Media

    city = make_city(session)
    owner = make_user(session, "photoowner")
    place = make_place(session, city, "Pictured", added_by=int(owner.id))
    media = Media(
        place_id=int(place.id), user_id=int(owner.id), kind="photo", caption="A photo", phash="ff00"
    )
    session.add(media)
    session.commit()
    session.refresh(media)

    register(client, "inthephoto")
    body = client.post(
        "/api/reports",
        json={"target_type": "media", "target_id": media.id, "reason": "photo_of_me"},
    ).json()
    assert body["hidden"] is True
    session.expire_all()
    assert session.get(Media, media.id).status == "hidden"
