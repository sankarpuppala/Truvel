"""The re-rank rules under pressure (SPEC §9.4, §9.5).

A greedy "take the best one that is allowed" re-rank has a failure mode: it can
spend the scarce items early and strand a long run of the common one at the
end. These tests push exactly that case, because a feed that looks diverse for
ten items and then shows six waterfalls in a row has not done its job.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.deck.rank import Candidate, deck_rng, diversify, score_candidates
from app.watch.rank import VideoCandidate
from app.watch.rank import diversify as watch_diversify
from app.watch.rank import score_videos, watch_rng

NOW = datetime(2026, 10, 20, 12, 0)


def longest_run(values: list) -> int:
    best = run = 1
    for a, b in zip(values, values[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best if values else 0


def video(mid: int, creator: int, category: str) -> VideoCandidate:
    return VideoCandidate(
        media_id=mid,
        creator_id=creator,
        place_id=mid,
        category=category,
        distance_km=float(mid % 10),
        engaged_views=100,
        completions=50,
        created_at=NOW - timedelta(days=1),
    )


@pytest.mark.parametrize(
    "many,few",
    [(7, 4), (10, 5), (12, 6), (9, 5), (6, 3)],
)
def test_watch_keeps_creator_runs_short_whenever_it_is_possible(many: int, few: int):
    """With `few` items of B, runs of A can be held to 2 while 2*(few+1) >= many."""
    cands = [video(i, 10, "waterfall") for i in range(1, many + 1)]
    cands += [video(100 + i, 20, "lake") for i in range(1, few + 1)]
    out = watch_diversify(score_videos(cands, {}, NOW, watch_rng(1, "d", 0)))

    assert len(out) == len(cands), "nothing may be dropped"
    creators = [c.creator_id for c in out]
    if many <= 2 * (few + 1):
        assert longest_run(creators) <= 2, (
            f"a run of {longest_run(creators)} with {many} vs {few} items: "
            f"{creators}"
        )


def test_watch_degrades_gracefully_when_separation_is_impossible():
    """20 from one creator and 2 from another cannot be separated; do not drop any."""
    cands = [video(i, 10, "waterfall") for i in range(1, 21)]
    cands += [video(100 + i, 20, "lake") for i in range(1, 3)]
    out = watch_diversify(score_videos(cands, {}, NOW, watch_rng(2, "d", 0)))
    assert len(out) == len(cands)


def test_watch_single_creator_is_returned_whole():
    cands = [video(i, 10, "waterfall") for i in range(1, 6)]
    out = watch_diversify(score_videos(cands, {}, NOW, watch_rng(3, "d", 0)))
    assert len(out) == 5


def candidate(pid: int, category: str) -> Candidate:
    return Candidate(
        place_id=pid,
        category=category,
        distance_km=float(pid % 7),
        likes=10,
        viewers=20,
        created_at=NOW - timedelta(days=400),
    )


@pytest.mark.parametrize("many,few", [(6, 3), (8, 4), (10, 5), (5, 3)])
def test_deck_keeps_category_runs_short_whenever_it_is_possible(many: int, few: int):
    cands = [candidate(i, "waterfall") for i in range(1, many + 1)]
    cands += [candidate(100 + i, "lake") for i in range(1, few + 1)]
    out = diversify(score_candidates(cands, {}, NOW, deck_rng(1, "d", 0)), max_run=2)

    assert len(out) == len(cands)
    categories = [c.category for c in out]
    if many <= 2 * (few + 1):
        assert longest_run(categories) <= 2, (
            f"a run of {longest_run(categories)} with {many} vs {few}: {categories}"
        )


def test_deck_with_three_categories_interleaves():
    cands = [candidate(i, "waterfall") for i in range(1, 7)]
    cands += [candidate(100 + i, "lake") for i in range(1, 7)]
    cands += [candidate(200 + i, "viewpoint") for i in range(1, 7)]
    out = diversify(score_candidates(cands, {}, NOW, deck_rng(4, "d", 0)), max_run=2)
    assert longest_run([c.category for c in out]) <= 2
    assert len(out) == 18


def test_deck_never_drops_a_card_even_when_all_one_category():
    cands = [candidate(i, "waterfall") for i in range(1, 9)]
    out = diversify(score_candidates(cands, {}, NOW, deck_rng(5, "d", 0)), max_run=2)
    assert len(out) == 8
