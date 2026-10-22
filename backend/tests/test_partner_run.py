"""The monthly Partner run, end to end on a fixture month (AC-18, AC-19).

The unit tests in test_partner.py check the arithmetic. These check that the
engine reads the right rows out of a real database, that the money adds up, and
that a re-run replaces a month rather than doubling it.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import select

from app.models import (
    Attribution,
    EarningLine,
    EarningPeriod,
    Media,
    MediaView,
    Visit,
    utcnow,
)
from app.partner.run import month_bounds, run_month
from tests.conftest import make_city, make_place, make_user

MONTH = "2026-09"
POOL_PAISE = 250_000 * 100


def seed_month(session, *, creators: int = 3, viewers: int = 40):
    """A month with three creators of clearly different standing."""
    city = make_city(session)
    start, end = month_bounds(MONTH)
    mid = start + timedelta(days=14)

    audience = [
        make_user(session, f"viewer{i}", created_at=start - timedelta(days=120))
        for i in range(viewers)
    ]
    made = []
    for index in range(creators):
        creator = make_user(
            session, f"creator{index}", created_at=start - timedelta(days=200)
        )
        place = make_place(
            session,
            city,
            f"Place {index}",
            added_by=int(creator.id),
            lat=17.40 + index * 0.01,
            lng=78.40,
        )
        # Enough verified content to clear the eligibility bar.
        videos = []
        for v in range(12):
            media = Media(
                place_id=int(place.id),
                user_id=int(creator.id),
                kind="video",
                caption=f"video {v}",
                duration_s=20.0,
                phash=f"{index:02d}{v:02d}cafe",
                created_at=start - timedelta(days=10),
            )
            session.add(media)
            videos.append(media)
        session.commit()
        for media in videos:
            session.refresh(media)
        made.append((creator, place, videos))

    # Views: creator 0 gets the most, creator 2 the fewest.
    for index, (creator, _place, videos) in enumerate(made):
        per_video = [30, 20, 10][index]
        for media in videos:
            for n in range(per_video):
                watcher = audience[(n + index) % len(audience)]
                session.add(
                    MediaView(
                        user_id=int(watcher.id),
                        media_id=int(media.id),
                        started_at=mid + timedelta(hours=n % 300),
                        watched_s=18.0,
                        engaged=True,
                        completed=True,
                        invalid_reason=None,
                    )
                )
    session.commit()

    # Visits, attributed so creator 2 causes the most despite having the fewest
    # views. All three clear the 300-visit reach bar (SPEC §10.4), so the test
    # is about how the pool is *divided* rather than about eligibility.
    visits_per_creator = [320, 360, 520]
    for index, (creator, place, _videos) in enumerate(made):
        for n in range(visits_per_creator[index]):
            visitor = audience[n % len(audience)]
            visit = Visit(
                user_id=int(visitor.id),
                place_id=int(place.id),
                at=mid + timedelta(hours=n),
                distance_m=30.0,
                accuracy_m=10.0,
                verified=True,
                flag=None,
                simulated=False,
            )
            session.add(visit)
            session.commit()
            session.refresh(visit)
            session.add(
                Attribution(visit_id=int(visit.id), creator_id=int(creator.id), share=1.0)
            )
    session.commit()
    del end
    return [creator for creator, _, _ in made]


def test_ac18_amounts_never_exceed_the_pool(session):
    seed_month(session)
    result = run_month(session, MONTH, POOL_PAISE)
    assert result["paid_paise"] <= POOL_PAISE
    assert result["remainder_paise"] >= 0
    assert result["paid_paise"] + result["remainder_paise"] == POOL_PAISE


def test_ac18_lines_are_written_to_the_ledger(session):
    creators = seed_month(session)
    run_month(session, MONTH, POOL_PAISE)

    period = session.exec(select(EarningPeriod).where(EarningPeriod.month == MONTH)).one()
    assert period.simulated is True
    lines = list(session.exec(select(EarningLine).where(EarningLine.period_id == period.id)).all())
    assert len(lines) >= len(creators)
    assert sum(line.amount_paise for line in lines) <= POOL_PAISE


def test_ac18_visits_outweigh_views_in_the_split(session):
    """Creator 2 has the fewest views and the most visits, and should earn most."""
    creators = seed_month(session)
    result = run_month(session, MONTH, POOL_PAISE)
    paid = {line["creator_id"]: line["amount_paise"] for line in result["lines"]}
    most_visits = int(creators[2].id)
    most_views = int(creators[0].id)
    assert paid[most_visits] > paid[most_views], (
        "a visit is weighted 25x a view, so visits must dominate"
    )


def test_ac18_rerunning_a_month_replaces_it(session):
    seed_month(session)
    first = run_month(session, MONTH, POOL_PAISE)
    second = run_month(session, MONTH, POOL_PAISE)

    period = session.exec(select(EarningPeriod).where(EarningPeriod.month == MONTH)).one()
    lines = list(session.exec(select(EarningLine).where(EarningLine.period_id == period.id)).all())
    assert len(lines) == len(second["lines"]), "a re-run must not double the lines"
    assert first["paid_paise"] == second["paid_paise"], "the run is deterministic"


def test_ac18_simulated_and_flagged_visits_never_earn(session):
    """AC-25: the dev simulator can never move money."""
    city = make_city(session)
    start, _ = month_bounds(MONTH)
    creator = make_user(session, "simcreator", created_at=start - timedelta(days=200))
    visitor = make_user(session, "simvisitor", created_at=start - timedelta(days=200))
    place = make_place(session, city, "Sim Place", added_by=int(creator.id))

    for simulated, flag in ((True, None), (False, "speed")):
        visit = Visit(
            user_id=int(visitor.id),
            place_id=int(place.id),
            at=start + timedelta(days=3),
            distance_m=20.0,
            accuracy_m=10.0,
            verified=True,
            flag=flag,
            simulated=simulated,
        )
        session.add(visit)
        session.commit()
        session.refresh(visit)
        session.add(Attribution(visit_id=int(visit.id), creator_id=int(creator.id), share=1.0))
    session.commit()

    result = run_month(session, MONTH, POOL_PAISE)
    line = next(line for line in result["lines"] if line["creator_id"] == int(creator.id))
    assert line["visits_caused"] == 0.0, "simulated and flagged visits must not count"


def test_ac19_studio_numbers_match_the_database(client, session):
    """AC-19: what the Studio shows is measured, not stored."""
    city = make_city(session)
    now = utcnow()
    creator_user = make_user(session, "studiocreator", created_at=now - timedelta(days=120))
    place = make_place(session, city, "Studio Place", added_by=int(creator_user.id))

    media = Media(
        place_id=int(place.id),
        user_id=int(creator_user.id),
        kind="video",
        caption="A video",
        duration_s=20.0,
        phash="deadbeef",
        created_at=now - timedelta(days=10),
    )
    session.add(media)
    session.commit()
    session.refresh(media)

    watcher = make_user(session, "studiowatcher", created_at=now - timedelta(days=90))
    for n in range(7):
        session.add(
            MediaView(
                user_id=int(watcher.id),
                media_id=int(media.id),
                started_at=now - timedelta(days=n + 1),
                watched_s=19.0,
                engaged=True,
                completed=True,
            )
        )
    visit = Visit(
        user_id=int(watcher.id),
        place_id=int(place.id),
        at=now - timedelta(days=2),
        distance_m=20.0,
        accuracy_m=9.0,
        verified=True,
        simulated=False,
    )
    session.add(visit)
    session.commit()
    session.refresh(visit)
    session.add(Attribution(visit_id=int(visit.id), creator_id=int(creator_user.id), share=0.6))
    session.commit()

    client.post(
        "/api/auth/login",
        json={"identifier": "studiocreator", "password": "correct horse battery"},
    )
    studio = client.get("/api/studio?period=28").json()

    counted = int(
        session.exec(
            select(Media).where(Media.user_id == creator_user.id)
        ).first()
        is not None
    )
    assert counted == 1
    assert studio["metrics"]["engaged_views"]["value"] == 7
    assert studio["metrics"]["visits_caused"]["value"] == 0.6
    # Sparkline values are available as numbers, which the UI also prints as text.
    assert len(studio["sparklines"]["engaged_views"]) > 1
    assert len(studio["sparklines"]["visits_caused"]) > 1
    # The checklist reflects the real eligibility state.
    assert studio["partner"]["total"] == 4
    assert any(r["key"] == "reach" for r in studio["partner"]["requirements"])


def test_month_bounds():
    start, end = month_bounds("2026-02")
    assert (start.year, start.month, start.day) == (2026, 2, 1)
    assert (end.year, end.month, end.day) == (2026, 3, 1)
    assert end - start == timedelta(days=28)
    assert month_bounds("2026-12")[1] == datetime(2027, 1, 1)
