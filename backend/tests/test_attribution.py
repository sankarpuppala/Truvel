"""SPEC §9.9 visit attribution (AC-16).

The AC asks for shares that match hand-computed values to 1e-9, sum to 1,
exclude self and invalid touches, and give organic visits nothing.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.partner.attribution import (
    TouchRow,
    attribute,
    attribute_last_touch,
    attribute_linear,
    touch_weight,
)

VISIT_AT = datetime(2026, 10, 20, 12, 0)


def days_before(n: float) -> datetime:
    return VISIT_AT - timedelta(days=n)


def test_ac16_hand_computed_two_creators():
    """One touch 0 days old (w=1), one 7 days old (w=0.5): 2/3 and 1/3."""
    touches = [
        TouchRow(creator_id=10, at=days_before(0)),
        TouchRow(creator_id=20, at=days_before(7)),
    ]
    shares = attribute(touches, visitor_id=99, visit_at=VISIT_AT)
    assert shares[10] == pytest.approx(2 / 3, abs=1e-9)
    assert shares[20] == pytest.approx(1 / 3, abs=1e-9)


def test_ac16_hand_computed_three_touches_one_creator_twice():
    """Weights 1 + 0.25 for creator 10, 0.5 for creator 20 -> 1.25/1.75, 0.5/1.75."""
    touches = [
        TouchRow(creator_id=10, at=days_before(0)),
        TouchRow(creator_id=10, at=days_before(14)),
        TouchRow(creator_id=20, at=days_before(7)),
    ]
    shares = attribute(touches, visitor_id=99, visit_at=VISIT_AT)
    assert shares[10] == pytest.approx(1.25 / 1.75, abs=1e-9)
    assert shares[20] == pytest.approx(0.50 / 1.75, abs=1e-9)


def test_ac16_shares_always_sum_to_one():
    for ages in ([0], [0, 1, 3], [2, 9, 15, 29], [0.5, 0.5, 0.5]):
        touches = [TouchRow(creator_id=i, at=days_before(a)) for i, a in enumerate(ages)]
        shares = attribute(touches, visitor_id=999, visit_at=VISIT_AT)
        assert sum(shares.values()) == pytest.approx(1.0, abs=1e-9)


def test_ac16_organic_visit_gets_no_attribution():
    assert attribute([], visitor_id=1, visit_at=VISIT_AT) == {}


def test_ac16_self_touches_are_dropped():
    """Your own content cannot cause your own visit."""
    touches = [
        TouchRow(creator_id=7, at=days_before(1)),
        TouchRow(creator_id=99, at=days_before(0)),      # the visitor
    ]
    shares = attribute(touches, visitor_id=99, visit_at=VISIT_AT)
    assert set(shares) == {7}
    assert shares[7] == pytest.approx(1.0)


def test_ac16_only_self_touches_means_organic():
    touches = [TouchRow(creator_id=99, at=days_before(1))]
    assert attribute(touches, visitor_id=99, visit_at=VISIT_AT) == {}


def test_ac16_invalid_touches_are_dropped():
    touches = [
        TouchRow(creator_id=10, at=days_before(0), invalid_reason="new_account"),
        TouchRow(creator_id=20, at=days_before(0)),
    ]
    shares = attribute(touches, visitor_id=99, visit_at=VISIT_AT)
    assert set(shares) == {20}


def test_touches_outside_the_lookback_are_ignored():
    touches = [
        TouchRow(creator_id=10, at=days_before(31)),      # outside 30 days
        TouchRow(creator_id=20, at=days_before(29)),
    ]
    shares = attribute(touches, visitor_id=99, visit_at=VISIT_AT)
    assert set(shares) == {20}


def test_touches_after_the_visit_are_ignored():
    """Something seen after arriving cannot have caused the trip."""
    touches = [
        TouchRow(creator_id=10, at=VISIT_AT + timedelta(hours=2)),
        TouchRow(creator_id=20, at=days_before(1)),
    ]
    shares = attribute(touches, visitor_id=99, visit_at=VISIT_AT)
    assert set(shares) == {20}


def test_touch_weight_half_life():
    assert touch_weight(days_before(0), VISIT_AT) == pytest.approx(1.0)
    assert touch_weight(days_before(7), VISIT_AT) == pytest.approx(0.5)
    assert touch_weight(days_before(14), VISIT_AT) == pytest.approx(0.25)


# --- the alternatives compared in SPEC §17 item 3 -------------------------- #

def test_last_touch_gives_everything_to_the_most_recent():
    touches = [
        TouchRow(creator_id=10, at=days_before(5)),
        TouchRow(creator_id=20, at=days_before(1)),
    ]
    assert attribute_last_touch(touches, 99, VISIT_AT) == {20: 1.0}


def test_linear_splits_evenly_regardless_of_age():
    touches = [
        TouchRow(creator_id=10, at=days_before(25)),
        TouchRow(creator_id=20, at=days_before(1)),
    ]
    shares = attribute_linear(touches, 99, VISIT_AT)
    assert shares[10] == pytest.approx(0.5)
    assert shares[20] == pytest.approx(0.5)


def test_time_decay_sits_between_last_touch_and_linear():
    """The design claim in SPEC §9.9, as an assertion."""
    touches = [
        TouchRow(creator_id=10, at=days_before(21)),     # the early influence
        TouchRow(creator_id=20, at=days_before(0)),      # the final nudge
    ]
    decay = attribute(touches, 99, VISIT_AT)
    last = attribute_last_touch(touches, 99, VISIT_AT)
    linear = attribute_linear(touches, 99, VISIT_AT)
    assert last.get(10, 0.0) < decay[10] < linear[10]
    assert linear[20] < decay[20] < last[20]
