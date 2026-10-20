"""Re-ranking so no group repeats too many times in a row (SPEC §9.4, §9.5).

The deck limits how many cards of one category appear consecutively, and Watch
limits both creator and category. Both are the same problem: reorder a ranked
list so that no "group" appears more than `k` times in a row, while staying as
close to the ranking as possible.

**Why the obvious greedy is wrong.** "Take the best item that is currently
allowed" looks right and fails in a very ordinary case: with 6 items from one
creator and 3 from another, it spends the scarce creator early and leaves a run
of five at the end. A feed that looks varied for four items and then shows five
videos from the same person has not done its job.

**The rule used here.** Walk the ranking in order and take the first item that
is both allowed *and* leaves the rest still arrangeable. Arrangeability has a
closed form: a multiset can be laid out with runs of at most `k` exactly when

    largest_group <= k * (total - largest_group + 1)

because the other items make `total - largest_group + 1` gaps, and each gap can
hold `k` of the largest group. When no item satisfies both, take from the
largest remaining group, which is the choice that keeps the final run shortest.

So the ranking is followed unless following it would strand a run -- which is
the smallest departure from the ranking that still delivers the promise.
"""
from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import TypeVar

T = TypeVar("T")


def feasible(counts: dict[Hashable, int], max_run: int) -> bool:
    """Whether a multiset can be arranged with no more than `max_run` in a row."""
    total = sum(counts.values())
    if total <= 0:
        return True
    largest = max(counts.values())
    return largest <= max_run * (total - largest + 1)


def rearrange(
    ranked: list[T],
    key: Callable[[T], Hashable],
    max_run: int,
    blocked: Callable[[T, list[T]], bool] | None = None,
) -> list[T]:
    """Reorder `ranked` so no `key` repeats more than `max_run` times in a row.

    `ranked` is best-first and is followed wherever possible. `blocked` lets a
    caller add a second constraint (Watch limits creators *and* categories);
    it is called with the candidate and the output so far, so it can look at
    what has just been placed. The feasibility test only guards the `key`
    constraint, which is the one that strands runs in practice.

    Nothing is ever dropped: when a list cannot be arranged -- twenty videos
    from one creator and two from another -- the run is made as short as the
    items allow and every item is still returned.
    """
    pool = list(ranked)
    out: list[T] = []
    counts: dict[Hashable, int] = {}
    for item in pool:
        counts[key(item)] = counts.get(key(item), 0) + 1

    current: Hashable | None = None
    run = 0

    while pool:
        pick: int | None = None

        for index, item in enumerate(pool):
            group = key(item)
            if current == group and run >= max_run:
                continue
            if blocked is not None and blocked(item, out):
                continue
            # Would taking this leave the remainder arrangeable?
            counts[group] -= 1
            rest = {g: c for g, c in counts.items() if c > 0}
            ok = feasible(rest, max_run)
            counts[group] += 1
            if ok:
                pick = index
                break

        if pick is None:
            # Nothing both allowed and safe. Take from the largest remaining
            # group: that is what keeps the unavoidable run shortest.
            pick = max(
                range(len(pool)),
                key=lambda i: (counts[key(pool[i])], -i),
            )

        chosen = pool.pop(pick)
        group = key(chosen)
        counts[group] -= 1
        if counts[group] <= 0:
            counts.pop(group, None)
        run = run + 1 if group == current else 1
        current = group
        out.append(chosen)

    return out


def longest_run(values: list[Hashable]) -> int:
    """The longest consecutive repeat in a list. Used by the tests."""
    if not values:
        return 0
    best = run = 1
    for a, b in zip(values, values[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best
