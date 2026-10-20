"""SPEC §10.1 kadam: every rule and every cap (AC-14)."""
from __future__ import annotations

from datetime import timedelta

from sqlmodel import select

from app import kadam
from app.models import KadamEntry, utcnow
from tests.conftest import make_user


def test_ac14_balance_is_the_sum_of_the_ledger(session):
    """There is no balance column: the balance *is* the ledger (invariant 4)."""
    user = make_user(session, "riya", created_at=utcnow() - timedelta(days=30))
    assert kadam.balance(session, int(user.id)) == 0

    kadam.award(session, int(user.id), kadam.PULSE, ref_type="place", ref_id=1)
    kadam.award(session, int(user.id), kadam.OWN_VISIT, ref_type="place", ref_id=1)

    entries = session.exec(select(KadamEntry).where(KadamEntry.user_id == user.id)).all()
    assert kadam.balance(session, int(user.id)) == sum(e.delta for e in entries)
    assert kadam.balance(session, int(user.id)) == 3 + 5


def test_ac14_amounts_match_the_spec_table(session):
    user = make_user(session, "amounts", created_at=utcnow() - timedelta(days=30))
    uid = int(user.id)
    assert kadam.award(session, uid, kadam.DISCOVERY, ref_type="place", ref_id=1) == 50
    assert kadam.award(session, uid, kadam.OWN_VISIT, ref_type="place", ref_id=1) == 5
    assert kadam.award(session, uid, kadam.PULSE, ref_type="place", ref_id=1) == 3
    assert kadam.award(session, uid, kadam.STEPS_HELPFUL, ref_type="steps", ref_id=1) == 2
    assert kadam.award(session, uid, kadam.LIKE_RECEIVED, ref_type="place", ref_id=1) == 1


def test_ac14_discovery_is_once_per_place(session):
    user = make_user(session, "finder", created_at=utcnow() - timedelta(days=30))
    uid = int(user.id)
    assert kadam.award(session, uid, kadam.DISCOVERY, ref_type="place", ref_id=7) == 50
    assert kadam.award(session, uid, kadam.DISCOVERY, ref_type="place", ref_id=7) == 0
    # A different place still pays.
    assert kadam.award(session, uid, kadam.DISCOVERY, ref_type="place", ref_id=8) == 50


def test_ac14_own_visit_is_once_per_place(session):
    user = make_user(session, "walker", created_at=utcnow() - timedelta(days=30))
    uid = int(user.id)
    assert kadam.award(session, uid, kadam.OWN_VISIT, ref_type="place", ref_id=3) == 5
    assert kadam.award(session, uid, kadam.OWN_VISIT, ref_type="place", ref_id=3) == 0


def test_ac14_pulse_daily_cap_is_five_reports(session):
    user = make_user(session, "reporter", created_at=utcnow() - timedelta(days=30))
    uid = int(user.id)
    awarded = [
        kadam.award(session, uid, kadam.PULSE, ref_type="place", ref_id=i) for i in range(1, 8)
    ]
    # 5 reports x 3 kadam = 15, then nothing.
    assert sum(awarded) == 15
    assert awarded[:5] == [3, 3, 3, 3, 3]
    assert awarded[5:] == [0, 0]


def test_ac14_like_received_daily_cap_is_fifty(session):
    user = make_user(session, "popular", created_at=utcnow() - timedelta(days=30))
    uid = int(user.id)
    total = sum(
        kadam.award(session, uid, kadam.LIKE_RECEIVED, ref_type="place", ref_id=i)
        for i in range(1, 60)
    )
    assert total == 50


def test_ac14_steps_helpful_daily_cap(session):
    """20 helpful votes a day at +2 each = 40 kadam, then nothing."""
    user = make_user(session, "guide", created_at=utcnow() - timedelta(days=30))
    uid = int(user.id)
    awarded = [
        kadam.award(session, uid, kadam.STEPS_HELPFUL, ref_type="steps", ref_id=i)
        for i in range(1, 30)
    ]
    assert sum(awarded) == 40
    assert awarded.count(2) == 20
    assert awarded[-1] == 0


def test_ac14_visit_caused_cap_is_per_place_per_day(session):
    """20 caused visits per place per day at +10 each = 200 kadam."""
    user = make_user(session, "creator", created_at=utcnow() - timedelta(days=30))
    uid = int(user.id)
    awarded = [
        kadam.award(session, uid, kadam.VISIT_CAUSED, ref_type="place", ref_id=1)
        for _ in range(25)
    ]
    assert sum(awarded) == 200
    assert awarded[-1] == 0
    # A different place has its own allowance.
    assert kadam.award(session, uid, kadam.VISIT_CAUSED, ref_type="place", ref_id=2) == 10


def test_ac14_daily_caps_reset_the_next_day(session):
    user = make_user(session, "tomorrow", created_at=utcnow() - timedelta(days=30))
    uid = int(user.id)
    yesterday = utcnow() - timedelta(days=1)
    for i in range(1, 7):
        kadam.award(session, uid, kadam.PULSE, ref_type="place", ref_id=i, now=yesterday)
    # Today's allowance is untouched.
    assert kadam.award(session, uid, kadam.PULSE, ref_type="place", ref_id=9) == 3


def test_ac14_new_accounts_earn_nothing_from_likes(session):
    """SPEC §9.8: under 24 h old, likes pay nothing."""
    fresh = make_user(session, "brandnew", created_at=utcnow() - timedelta(hours=2))
    assert kadam.award(session, int(fresh.id), kadam.LIKE_RECEIVED, ref_type="place", ref_id=1) == 0
    # But other reasons still work -- the rule is about likes.
    assert kadam.award(session, int(fresh.id), kadam.OWN_VISIT, ref_type="place", ref_id=1) == 5


def test_ac14_reversal_writes_a_negative_entry(session):
    user = make_user(session, "reversed", created_at=utcnow() - timedelta(days=30))
    uid = int(user.id)
    kadam.award(session, uid, kadam.DISCOVERY, ref_type="place", ref_id=4)
    assert kadam.balance(session, uid) == 50

    delta = kadam.reverse(session, uid, ref_type="place", ref_id=4)
    assert delta == -50
    assert kadam.balance(session, uid) == 0
    # The original entry survives: the ledger still explains the history.
    entries = session.exec(select(KadamEntry).where(KadamEntry.user_id == uid)).all()
    assert len(entries) == 2
    assert {e.reason for e in entries} == {kadam.DISCOVERY, kadam.REVERSAL}


def test_reversing_nothing_is_a_no_op(session):
    user = make_user(session, "nothing", created_at=utcnow() - timedelta(days=30))
    assert kadam.reverse(session, int(user.id), ref_type="place", ref_id=99) == 0


def test_unknown_reason_raises(session):
    user = make_user(session, "typo", created_at=utcnow() - timedelta(days=30))
    try:
        kadam.award(session, int(user.id), "discovry")      # deliberate typo
    except ValueError as exc:
        assert "unknown kadam reason" in str(exc)
    else:
        raise AssertionError("a typo'd reason must raise, not silently award")


def test_levels_match_the_spec():
    assert kadam.level(0)[0] == "Wanderer"
    assert kadam.level(199)[0] == "Wanderer"
    assert kadam.level(200)[0] == "Pathfinder"
    assert kadam.level(340)[0] == "Pathfinder"
    assert kadam.level(800)[0] == "Trailblazer"
    assert kadam.level(2500)[0] == "Local Legend"


def test_level_reports_the_next_threshold():
    name, next_name, floor, next_floor = kadam.level(340)
    assert (name, next_name, floor, next_floor) == ("Pathfinder", "Trailblazer", 200, 800)
    # At the top there is nothing further to reach.
    assert kadam.level(5000)[1] is None


def test_ledger_is_newest_first(session):
    user = make_user(session, "ordered", created_at=utcnow() - timedelta(days=30))
    uid = int(user.id)
    now = utcnow()
    kadam.award(session, uid, kadam.OWN_VISIT, ref_type="place", ref_id=1, now=now - timedelta(days=2))
    kadam.award(session, uid, kadam.PULSE, ref_type="place", ref_id=1, now=now)
    entries = kadam.ledger(session, uid)
    assert [e.reason for e in entries] == [kadam.PULSE, kadam.OWN_VISIT]
