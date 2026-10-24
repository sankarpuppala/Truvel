"""Comments on videos (SPEC §8.11 Tier 2, §8.13 reports)."""
from __future__ import annotations

from app.models import Comment, Media
from app.routers.comments import clean_comment
from tests.conftest import make_city, make_place, make_user
from tests.test_api import register


def _video(session) -> Media:
    city = make_city(session)
    owner = make_user(session, "filmer")
    place = make_place(session, city, "Falls", added_by=int(owner.id))
    media = Media(place_id=int(place.id), user_id=int(owner.id), kind="video", caption="Falls")
    session.add(media)
    session.commit()
    session.refresh(media)
    return media


def test_clean_comment_rules():
    assert clean_comment("  nice   view ", 300, []) == "nice view"
    assert clean_comment("   ", 300, []) is None
    assert clean_comment("x" * 301, 300, []) is None
    assert clean_comment("what a SCAM", 300, ["scam"]) is None
    assert clean_comment("scampi here", 300, ["scam"]) == "scampi here"   # whole words only


def test_post_list_and_delete_own_comment(client, session):
    media = _video(session)
    register(client, "talker")
    posted = client.post(f"/api/media/{media.id}/comments", json={"text": "Went today!"})
    assert posted.status_code == 200, posted.text
    listed = client.get(f"/api/media/{media.id}/comments").json()["comments"]
    assert [c["text"] for c in listed] == ["Went today!"]
    assert listed[0]["mine"] is True
    assert client.delete(f"/api/comments/{posted.json()['id']}").json()["deleted"] is True
    assert client.get(f"/api/media/{media.id}/comments").json()["comments"] == []


def test_cannot_delete_someone_elses_comment(client, session):
    media = _video(session)
    register(client, "first")
    cid = client.post(f"/api/media/{media.id}/comments", json={"text": "Mine"}).json()["id"]
    client.cookies.clear()
    register(client, "second")
    assert client.delete(f"/api/comments/{cid}").status_code == 403


def test_comment_needs_sign_in_and_valid_text(client, session):
    media = _video(session)
    assert client.post(f"/api/media/{media.id}/comments", json={"text": "hi"}).status_code == 401
    register(client, "blank")
    assert client.post(f"/api/media/{media.id}/comments", json={"text": " "}).status_code == 400


def test_three_reports_hide_a_comment(client, session):
    media = _video(session)
    register(client, "author")
    cid = client.post(f"/api/media/{media.id}/comments", json={"text": "Rude"}).json()["id"]
    hidden = False
    for name in ("rep1", "rep2", "rep3"):
        client.cookies.clear()
        register(client, name)
        hidden = client.post(
            "/api/reports",
            json={"target_type": "comment", "target_id": cid, "reason": "offensive"},
        ).json()["hidden"]
    assert hidden is True
    session.expire_all()
    assert session.get(Comment, cid).status == "hidden"
    assert client.get(f"/api/media/{media.id}/comments").json()["comments"] == []


def test_stand_in_photo_kept_only_when_it_names_the_place():
    from scripts.undo_stock_photos import looks_like_this_place

    assert looks_like_this_place("Golden Temple Amritsar 2019.jpg", "Golden Temple")
    assert not looks_like_this_place("Three Sisters Blue Mountains.jpg", "National Horticulture Museum")
