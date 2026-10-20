"""SPEC §9.10 invalid traffic and §10.3-10.4 the split (AC-17, AC-18)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.partner.eligibility import EligibilityInput, check, is_eligible
from app.partner.invalid import mean_sd, velocity_hold, velocity_threshold
from app.partner.split import (
    CreatorMonth,
    creator_pool_paise,
    demo_pool_paise,
    remainder_paise,
    rupees_to_paise,
    score_creator,
    split_pool,
)
from app.watch.views import (
    NEW_ACCOUNT,
    REPEAT,
    SELF_VIEW,
    SIMULATED,
    invalid_reason,
)

NOW = datetime(2026, 10, 20, 12, 0)
OLD_ACCOUNT = NOW - timedelta(days=200)


# --- AC-17: one test per §9.10 rule ---------------------------------------- #

def test_ac17_self_view_is_invalid():
    assert (
        invalid_reason(
            viewer_id=5,
            creator_id=5,
            viewer_created_at=OLD_ACCOUNT,
            now=NOW,
            previous_view_at=None,
        )
        == SELF_VIEW
    )


def test_ac17_new_account_is_invalid():
    assert (
        invalid_reason(
            viewer_id=6,
            creator_id=5,
            viewer_created_at=NOW - timedelta(hours=3),
            now=NOW,
            previous_view_at=None,
        )
        == NEW_ACCOUNT
    )


def test_ac17_account_just_over_24h_is_valid():
    assert (
        invalid_reason(
            viewer_id=6,
            creator_id=5,
            viewer_created_at=NOW - timedelta(hours=24, minutes=1),
            now=NOW,
            previous_view_at=None,
        )
        is None
    )


def test_ac17_repeat_within_24h_is_invalid():
    assert (
        invalid_reason(
            viewer_id=6,
            creator_id=5,
            viewer_created_at=OLD_ACCOUNT,
            now=NOW,
            previous_view_at=NOW - timedelta(hours=5),
        )
        == REPEAT
    )


def test_ac17_repeat_after_24h_is_valid():
    assert (
        invalid_reason(
            viewer_id=6,
            creator_id=5,
            viewer_created_at=OLD_ACCOUNT,
            now=NOW,
            previous_view_at=NOW - timedelta(hours=25),
        )
        is None
    )


def test_ac17_simulated_session_is_invalid():
    assert (
        invalid_reason(
            viewer_id=6,
            creator_id=5,
            viewer_created_at=OLD_ACCOUNT,
            now=NOW,
            previous_view_at=None,
            simulated_session=True,
        )
        == SIMULATED
    )


def test_ac17_a_clean_view_is_valid():
    assert (
        invalid_reason(
            viewer_id=6,
            creator_id=5,
            viewer_created_at=OLD_ACCOUNT,
            now=NOW,
            previous_view_at=None,
        )
        is None
    )


# --- AC-17: the velocity hold excludes only the excess --------------------- #

def test_mean_sd():
    assert mean_sd([]) == (0.0, 0.0)
    mean, sd = mean_sd([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
    assert mean == pytest.approx(5.0)
    assert sd == pytest.approx(2.0)


def test_ac17_velocity_hold_holds_only_the_excess():
    trailing = [10.0] * 6 + [20.0]          # mean 11.43, sd ~3.5
    threshold = velocity_threshold(trailing)
    verdict = velocity_hold(900, trailing)
    assert verdict.triggered is True
    assert verdict.counted + verdict.held == 900, "no views may vanish"
    assert verdict.counted == max(int(threshold), 50)
    assert verdict.held > 0


def test_ac17_velocity_hold_needs_both_conditions():
    """A quiet item's first 40 honest views must not be held."""
    verdict = velocity_hold(40, [0.0] * 7)
    assert verdict.triggered is False
    assert verdict.counted == 40 and verdict.held == 0


def test_ac17_velocity_hold_ignores_normal_growth():
    trailing = [100.0, 110.0, 95.0, 105.0, 120.0, 98.0, 102.0]
    verdict = velocity_hold(130, trailing)
    assert verdict.triggered is False
    assert verdict.held == 0


def test_ac17_brand_new_item_keeps_the_floor():
    """No history at all: the absolute floor of 50 still counts."""
    verdict = velocity_hold(60, [])
    assert verdict.counted >= 50
    assert verdict.counted + verdict.held == 60


# --- AC-18: scores, eligibility, the split --------------------------------- #

def test_ac18_score_uses_the_spec_weights():
    row = CreatorMonth(
        creator_id=1, engaged_views=1000, visits_caused=4.0, helpful_votes=3, pulse_confirmed=2
    )
    # 1*1000 + 25*4 + 5*3 + 2*2 = 1000 + 100 + 15 + 4 = 1119
    assert score_creator(row) == pytest.approx(1119.0)


def test_ac18_a_visit_is_worth_25_views():
    views_only = CreatorMonth(creator_id=1, engaged_views=25)
    one_visit = CreatorMonth(creator_id=2, visits_caused=1.0)
    assert score_creator(views_only) == score_creator(one_visit)


def test_ac18_amounts_never_exceed_the_pool_and_round_down():
    pool = rupees_to_paise(1000)             # 100000 paise
    rows = [
        CreatorMonth(creator_id=1, engaged_views=1, eligible=True),
        CreatorMonth(creator_id=2, engaged_views=1, eligible=True),
        CreatorMonth(creator_id=3, engaged_views=1, eligible=True),
    ]
    split_pool(rows, pool)
    total = sum(r.amount_paise for r in rows)
    assert total <= pool
    assert all(r.amount_paise == 33333 for r in rows)     # floor of 33333.33
    assert remainder_paise(rows, pool) == 1               # the leftover paisa


def test_ac18_ineligible_creators_get_nothing():
    pool = rupees_to_paise(1000)
    rows = [
        CreatorMonth(creator_id=1, visits_caused=10, eligible=True),
        CreatorMonth(creator_id=2, visits_caused=10, eligible=False),
    ]
    split_pool(rows, pool)
    paid = {r.creator_id: r.amount_paise for r in rows}
    assert paid[2] == 0
    assert paid[1] == pool                      # the only eligible creator takes it all
    # The ineligible creator still sees their score, so the Studio can explain.
    assert rows[1].score > 0
    assert rows[1].share == 0.0


def test_ac18_shares_sum_to_one_over_eligible_creators():
    rows = [
        CreatorMonth(creator_id=1, engaged_views=500, eligible=True),
        CreatorMonth(creator_id=2, visits_caused=20, eligible=True),
        CreatorMonth(creator_id=3, engaged_views=100, eligible=False),
    ]
    split_pool(rows, rupees_to_paise(250000))
    assert sum(r.share for r in rows) == pytest.approx(1.0)


def test_ac18_empty_month_pays_nothing():
    rows = [CreatorMonth(creator_id=1, eligible=True)]
    split_pool(rows, rupees_to_paise(1000))
    assert rows[0].amount_paise == 0


def test_creator_pool_is_55_percent():
    assert creator_pool_paise(1_000_000) == 550_000


def test_demo_pool_comes_from_config():
    assert demo_pool_paise() == rupees_to_paise(250000)


def test_ac18_eligibility_requires_all_four():
    good = EligibilityInput(
        account_created_at=NOW - timedelta(days=60),
        strikes=0,
        verified_content=14,
        visits_caused_90d=350,
        engaged_views_90d=5000,
    )
    assert is_eligible(good, NOW) is True

    too_new = EligibilityInput(**{**good.__dict__, "account_created_at": NOW - timedelta(days=10)})
    assert is_eligible(too_new, NOW) is False

    striked = EligibilityInput(**{**good.__dict__, "strikes": 1})
    assert is_eligible(striked, NOW) is False

    thin = EligibilityInput(**{**good.__dict__, "verified_content": 9})
    assert is_eligible(thin, NOW) is False

    no_reach = EligibilityInput(
        **{**good.__dict__, "visits_caused_90d": 10, "engaged_views_90d": 10}
    )
    assert is_eligible(no_reach, NOW) is False


def test_ac18_reach_is_an_either_or():
    """300 visits OR 100,000 engaged views -- either route qualifies."""
    by_views = EligibilityInput(
        account_created_at=NOW - timedelta(days=60),
        strikes=0,
        verified_content=12,
        visits_caused_90d=5,
        engaged_views_90d=150_000,
    )
    assert is_eligible(by_views, NOW) is True


def test_ac19_checklist_shape_matches_the_studio():
    reqs = check(
        EligibilityInput(
            account_created_at=NOW - timedelta(days=45),
            strikes=0,
            verified_content=14,
            visits_caused_90d=214,
            engaged_views_90d=62_480,
        ),
        NOW,
    )
    assert [r.key for r in reqs] == ["account_age", "verified_content", "reach", "no_strikes"]
    reach = next(r for r in reqs if r.key == "reach")
    assert reach.met is False
    assert reach.value == 214 and reach.target == 300
    assert "engaged views" in reach.note
    assert sum(1 for r in reqs if r.met) == 3
