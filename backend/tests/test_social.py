"""Following lists, the Following feed and suggestions (SPEC §8.11)."""
from __future__ import annotations

from datetime import timedelta

from app.models import Media, utcnow
from app.routers.social import merge_feed
from tests.conftest import make_city, make_place, make_user
from tests.test_api import register


def test_merge_feed_is_newest_first_and_capped():
    posts = [{"at": "2026-10-03"}, {"at": "2026-10-01"}]
    places = [{"at": "2026-10-02"}]
    assert [i["at"] for i in merge_feed(posts, places, 2)] == ["2026-10-03", "2026-10-02"]


def test_feed_shows_posts_and_places_of_people_you_follow(client, session):
    city = make_city(session)
    star = make_user(session, "star")
    other = make_user(session, "other")
    old = utcnow() - timedelta(days=2)
    spot = make_place(session, city, "Hidden Rock", added_by=int(star.id), created_at=old)
    make_place(session, city, "Not Followed", added_by=int(other.id))
    session.add(Media(place_id=int(spot.id), user_id=int(star.id), kind="photo", caption="Dawn"))
    session.commit()

    register(client, "fan")
    assert client.get("/api/feed").json()["items"] == []
    client.post("/api/users/star/follow")
    items = client.get("/api/feed").json()["items"]
    assert [i["type"] for i in items] == ["post", "place"]          # newest first
    assert {i["creator"]["username"] for i in items} == {"star"}


def test_feed_needs_sign_in(client, session):
    make_city(session)
    assert client.get("/api/feed").status_code == 401


def test_follower_and_following_lists(client, session):
    make_city(session)
    make_user(session, "creator")
    register(client, "fan")
    client.post("/api/users/creator/follow")
    followers = client.get("/api/users/creator/followers").json()["users"]
    assert [u["username"] for u in followers] == ["fan"] and followers[0]["is_me"]
    following = client.get("/api/users/fan/following").json()["users"]
    assert following[0]["username"] == "creator" and following[0]["followed_by_me"]
    profile = client.get("/api/users/fan").json()
    assert profile["following_count"] == 1


def test_suggestions_skip_you_and_people_you_follow(client, session):
    city = make_city(session)
    for name in ("busy", "quiet"):
        u = make_user(session, name)
        make_place(session, city, f"{name} spot", added_by=int(u.id))
    register(client, "newbie")
    client.post("/api/users/busy/follow")
    names = [u["username"] for u in client.get("/api/creators/suggested").json()["users"]]
    assert names == ["quiet"]
