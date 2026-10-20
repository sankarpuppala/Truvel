"""SPEC §9.1-9.3 ranking: Wilson, hidden gems, trending (AC-5)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.ranking.gems import fame_weight, gem_score, is_gem_eligible
from app.ranking.trending import decay, trending_score
from app.ranking.wilson import percentile_rank, wilson_lb


# --- AC-5: the exact test values stated in SPEC §9.1 ----------------------- #

@pytest.mark.parametrize(
    "k,n,expected",
    [
        (0, 0, 0.0),
        (1, 1, 0.2065),
        (80, 100, 0.7112),
        (8, 10, 0.4902),
    ],
)
def test_ac5_wilson_spec_values(k, n, expected):
    assert wilson_lb(k, n) == pytest.approx(expected, abs=5e-4)


def test_wilson_small_sample_loses_to_large_one():
    """The whole point of Wilson: 2/2 must not beat 1600/2000."""
    assert wilson_lb(2, 2) < wilson_lb(1600, 2000)


def test_wilson_is_bounded_and_monotonic():
    assert 0.0 <= wilson_lb(5, 10) <= 1.0
    # More likes from the same viewers can only help.
    assert wilson_lb(9, 10) > wilson_lb(5, 10)
    # The bound rises towards the true rate as the sample grows.
    assert wilson_lb(800, 1000) > wilson_lb(80, 100) > wilson_lb(8, 10)


def test_wilson_clamps_impossible_input():
    """likes <= viewers is an invariant; a bad row must not produce p > 1."""
    assert wilson_lb(20, 10) == wilson_lb(10, 10)
    assert wilson_lb(-5, 10) == wilson_lb(0, 10)


def test_percentile_rank():
    population = [0.1, 0.4, 0.9]
    assert percentile_rank(0.1, population) == pytest.approx(1 / 6)
    assert percentile_rank(0.9, population) == pytest.approx(5 / 6)
    assert percentile_rank(0.5, []) == 0.0
    assert percentile_rank(0.5, [0.5]) == 1.0


# --- SPEC §9.2 hidden gems ------------------------------------------------- #

def test_gem_weights_from_config():
    assert fame_weight("hidden") == 1.0
    assert fame_weight("known") == 0.7
    assert fame_weight("famous") == 0.3


def test_gem_score_demotes_famous_places():
    """A quiet ridge liked as much as a famous fort should outrank it."""
    hidden = gem_score(60, 80, "hidden")
    famous = gem_score(60, 80, "famous")
    assert hidden > famous
    assert famous == pytest.approx(hidden * 0.3)


def test_gem_eligibility_rules():
    assert is_gem_eligible("verified", False, 1) is True
    assert is_gem_eligible("unverified", False, 5) is False     # unverified excluded
    assert is_gem_eligible("verified", True, 5) is False        # fragile excluded
    assert is_gem_eligible("verified", False, 0) is False       # needs a real visit


# --- SPEC §9.3 trending ---------------------------------------------------- #

def test_decay_half_life_is_seven_days():
    assert decay(0) == 1.0
    assert decay(7) == pytest.approx(0.5)
    assert decay(14) == pytest.approx(0.25)


def test_trending_weights_visits_above_likes():
    now = datetime(2026, 10, 20, 12, 0)
    like_only = trending_score([("like", now)], now)
    visit_only = trending_score([("visit", now)], now)
    assert visit_only == pytest.approx(3 * like_only)


def test_trending_ignores_events_outside_the_window():
    now = datetime(2026, 10, 20, 12, 0)
    old = now - timedelta(days=45)
    assert trending_score([("like", old)], now) == 0.0
    assert trending_score([("unknown_kind", now)], now) == 0.0


def test_trending_prefers_recent_activity():
    now = datetime(2026, 10, 20, 12, 0)
    fresh = trending_score([("like", now - timedelta(days=1))] * 4, now)
    stale = trending_score([("like", now - timedelta(days=25))] * 4, now)
    assert fresh > stale
