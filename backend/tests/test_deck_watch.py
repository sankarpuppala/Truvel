"""SPEC §9.4 deck and §9.5 Watch ranking (AC-10, AC-11)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.deck.rank import Candidate, deck_rng, diversify, freshness, proximity, score_candidates
from app.deck.thompson import draw_theta, posterior_mean, update
from app.watch.rank import VideoCandidate
from app.watch.rank import diversify as watch_diversify
from app.watch.rank import freshness as watch_freshness
from app.watch.rank import score_videos, watch_rng
from app.watch.views import classify, is_completed, is_engaged

NOW = datetime(2026, 10, 20, 12, 0)


def candidate(pid: int, category: str, km: float, likes=10, viewers=20, age_days=400):
    return Candidate(
        place_id=pid,
        category=category,
        distance_km=km,
        likes=likes,
        viewers=viewers,
        created_at=NOW - timedelta(days=age_days),
    )


# --- Thompson sampling ----------------------------------------------------- #

def test_thompson_update_rules():
    """save -> alpha+1, skip -> beta+1, open -> unchanged (SPEC §9.4)."""
    assert update("save", 1.0, 1.0) == (2.0, 1.0)
    assert update("skip", 1.0, 1.0) == (1.0, 2.0)
    assert update("open", 1.0, 1.0) == (1.0, 1.0)
    assert update("anything_else", 3.0, 4.0) == (3.0, 4.0)


def test_thompson_draw_is_in_range_and_reproducible():
    import random

    a = draw_theta(2, 5, random.Random(7))
    b = draw_theta(2, 5, random.Random(7))
    assert a == b
    assert 0.0 <= a <= 1.0


def test_thompson_concentrates_with_evidence():
    """A category saved often should draw high nearly always."""
    import random

    rng = random.Random(1)
    draws = [draw_theta(50, 2, rng) for _ in range(200)]
    assert sum(draws) / len(draws) > 0.85
    assert posterior_mean(50, 2) == pytest.approx(50 / 52)


def test_thompson_explores_when_uninformed():
    """A uniform prior must sometimes draw high: that is exploration."""
    import random

    rng = random.Random(2)
    draws = [draw_theta(1, 1, rng) for _ in range(200)]
    assert max(draws) > 0.9
    assert min(draws) < 0.1


# --- deck scoring ---------------------------------------------------------- #

def test_proximity_decays_with_distance():
    assert proximity(0) == pytest.approx(1.0)
    assert proximity(4) == pytest.approx(0.3679, abs=1e-3)   # exp(-1)
    assert proximity(25) < 0.01


def test_freshness_is_a_step():
    new = NOW - timedelta(days=3)
    old = NOW - timedelta(days=400)
    assert freshness(new, 500, NOW) == 1.0            # recently added
    assert freshness(old, 5, NOW) == 1.0              # barely seen
    assert freshness(old, 500, NOW) == 0.0


def test_score_uses_the_spec_weights():
    """A hand-checked single candidate: parts x weights must equal the score."""
    cands = [candidate(1, "viewpoint", 0.0, likes=10, viewers=20)]
    scored = score_candidates(cands, {"viewpoint": (1.0, 1.0)}, NOW, deck_rng(1, "d", 0))
    c = scored[0]
    expected = (
        0.40 * c.parts["q"]
        + 0.25 * c.parts["prox"]
        + 0.25 * c.parts["pref"]
        + 0.10 * c.parts["fresh"]
    )
    assert c.score == pytest.approx(expected)


def test_ac10_deck_is_reproducible_with_a_seed():
    cands = [candidate(i, "viewpoint" if i % 2 else "lake", i) for i in range(1, 11)]
    first = [c.place_id for c in score_candidates(list(cands), {}, NOW, deck_rng(7, "2026-10-20", 0))]
    again = [c.place_id for c in score_candidates(list(cands), {}, NOW, deck_rng(7, "2026-10-20", 0))]
    assert first == again


def test_nearer_wins_when_everything_else_matches():
    near = candidate(1, "viewpoint", 1.0)
    far = candidate(2, "viewpoint", 20.0)
    ranked = score_candidates([far, near], {"viewpoint": (1.0, 1.0)}, NOW, deck_rng(1, "d", 0))
    assert ranked[0].place_id == 1


def test_ac10_no_three_of_the_same_category_in_a_row():
    cands = [candidate(i, "waterfall", i * 0.1) for i in range(1, 7)]
    cands += [candidate(100 + i, "lake", 5 + i * 0.1) for i in range(1, 4)]
    ranked = score_candidates(cands, {}, NOW, deck_rng(3, "d", 0))
    out = diversify(ranked, max_run=2)
    run = 1
    for a, b in zip(out, out[1:]):
        run = run + 1 if a.category == b.category else 1
        assert run <= 2, "three of the same category in a row"
    assert len(out) == len(cands), "diversify must not drop cards"


def test_diversify_gives_up_rather_than_emptying_the_deck():
    """All one category: we stop enforcing instead of returning nothing."""
    cands = [candidate(i, "waterfall", i) for i in range(1, 6)]
    out = diversify(score_candidates(cands, {}, NOW, deck_rng(1, "d", 0)), max_run=2)
    assert len(out) == 5


def test_empty_deck_scores_to_empty_list():
    assert score_candidates([], {}, NOW, deck_rng(1, "d", 0)) == []


# --- Watch ranking (SPEC §9.5) --------------------------------------------- #

def video(mid: int, creator: int, category: str, km=1.0, engaged=100, completions=50, age=1.0, following=False, risky=False):
    return VideoCandidate(
        media_id=mid,
        creator_id=creator,
        place_id=mid,
        category=category,
        distance_km=km,
        engaged_views=engaged,
        completions=completions,
        created_at=NOW - timedelta(days=age),
        following=following,
        risky=risky,
    )


def test_ac11_watch_uses_the_spec_weights():
    scored = score_videos([video(1, 10, "waterfall")], {}, NOW, watch_rng(1, "d", 0))
    c = scored[0]
    expected = (
        0.35 * c.parts["quality"]
        + 0.20 * c.parts["prox"]
        + 0.20 * c.parts["pref"]
        + 0.15 * c.parts["fresh"]
        + 0.10 * c.parts["following"]
    )
    assert c.score == pytest.approx(expected)


def test_watch_freshness_decays_smoothly():
    assert watch_freshness(NOW, NOW) == pytest.approx(1.0)
    assert watch_freshness(NOW - timedelta(days=5), NOW) == pytest.approx(0.3679, abs=1e-3)


def test_following_gives_a_boost():
    plain = score_videos([video(1, 10, "lake")], {}, NOW, watch_rng(1, "d", 0))[0].score
    followed = score_videos(
        [video(1, 10, "lake", following=True)], {}, NOW, watch_rng(1, "d", 0)
    )[0].score
    assert followed > plain


def test_risky_videos_get_no_boost():
    """SPEC §8.14: nothing rewards risky content."""
    safe = score_videos([video(1, 10, "hill_trek")], {}, NOW, watch_rng(1, "d", 0))[0].score
    risky = score_videos(
        [video(1, 10, "hill_trek", risky=True)], {}, NOW, watch_rng(1, "d", 0)
    )[0].score
    assert risky <= safe


def test_ac11_at_most_two_in_a_row_from_one_creator():
    cands = [video(i, 10, "waterfall" if i % 2 else "lake", km=i * 0.1) for i in range(1, 8)]
    cands += [video(50 + i, 20, "viewpoint", km=2 + i * 0.1) for i in range(1, 5)]
    out = watch_diversify(score_videos(cands, {}, NOW, watch_rng(1, "d", 0)))
    run = 1
    for a, b in zip(out, out[1:]):
        run = run + 1 if a.creator_id == b.creator_id else 1
        assert run <= 2, "three in a row from one creator"
    assert len(out) == len(cands)


def test_ac11_at_most_three_in_a_row_from_one_category():
    cands = [video(i, 10 + i, "waterfall", km=i * 0.1) for i in range(1, 9)]
    cands += [video(50 + i, 90 + i, "lake", km=3 + i * 0.1) for i in range(1, 5)]
    out = watch_diversify(score_videos(cands, {}, NOW, watch_rng(1, "d", 0)))
    run = 1
    for a, b in zip(out, out[1:]):
        run = run + 1 if a.category == b.category else 1
        assert run <= 3


# --- engaged views and completion (SPEC §9.10) ----------------------------- #

def test_ac11_engaged_view_threshold():
    assert is_engaged(3.0, 30.0) is True
    assert is_engaged(2.9, 30.0) is False
    # Short video clause: >= 50 % of anything under 6 s.
    assert is_engaged(2.0, 4.0) is True
    assert is_engaged(1.5, 4.0) is False


def test_ac11_completion_threshold():
    assert is_completed(27.0, 30.0) is True
    assert is_completed(26.9, 30.0) is False
    assert is_completed(5.0, 0.0) is False


def test_ac11_server_clamps_a_lying_client():
    """A client claiming 10,000 s of watch time must not inflate watch time."""
    verdict = classify(
        watched_s=10_000,
        duration_s=30,
        viewer_id=2,
        creator_id=1,
        viewer_created_at=NOW - timedelta(days=100),
        now=NOW,
    )
    assert verdict["watched_s"] <= 31
    assert verdict["engaged"] is True
    assert verdict["completed"] is True
