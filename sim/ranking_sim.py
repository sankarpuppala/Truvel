"""Does Wilson's lower bound rank places better than raw likes or the ratio?

SPEC §17 item 1.

**The question.** Each place has a true like rate -- the share of people who,
having seen it, would like it. We never observe that; we observe `k` likes from
`n` viewers. Which statistic recovers the genuinely best places?

**The setup.** 500 places. True like rate ~ Beta(2, 5), which is a realistic
shape: most places are liked by a minority, a few by most. Exposure follows a
power law, because attention is never uniform -- a handful of places are seen
thousands of times and the long tail is seen by a dozen people. Likes are then
Binomial(n, p).

**The three contenders.**
  raw     rank by k            -- what a naive "most liked" list does
  ratio   rank by k / n        -- fairer, but 2 likes from 2 viewers scores 1.0
  wilson  rank by wilson_lb    -- SPEC §9.1

**What is measured.** Kendall's tau against the true ordering, and
precision@10: how many of the ten places the ranking puts on top are genuinely
in the true top ten. 200 seeds, 95 % confidence intervals.

**The assumption that matters.** Exposure is independent of quality. If good
places were systematically shown more, raw counts would look better than they
do here. That is stated rather than hidden.
"""
from __future__ import annotations

import argparse
import random

from common import (  # noqa: E402  (sys.path is set inside common)
    bar_figure,
    kendall_tau,
    precision_at_k,
    print_table,
    summarise,
    write_results,
)

from app.ranking.wilson import wilson_lb  # noqa: E402

PLACES = 500
BETA_A, BETA_B = 2.0, 5.0
MIN_VIEWERS, MAX_VIEWERS = 5, 4000
POWER_LAW_ALPHA = 1.6


def power_law_viewers(rng: random.Random) -> int:
    """Draw an audience size from a power law, clipped to a sane range."""
    u = rng.random()
    raw = MIN_VIEWERS * (1 - u) ** (-1 / (POWER_LAW_ALPHA - 1))
    return int(min(MAX_VIEWERS, max(MIN_VIEWERS, raw)))


def one_run(seed: int) -> dict[str, float]:
    rng = random.Random(seed)

    true_rates: list[float] = []
    likes: list[int] = []
    viewers: list[int] = []
    for _ in range(PLACES):
        p = rng.betavariate(BETA_A, BETA_B)
        n = power_law_viewers(rng)
        k = sum(1 for _ in range(n) if rng.random() < p) if n <= 2000 else round(
            # For very large n the exact sum is slow and the normal
            # approximation is indistinguishable at this scale.
            max(0, min(n, rng.gauss(n * p, (n * p * (1 - p)) ** 0.5)))
        )
        true_rates.append(p)
        viewers.append(n)
        likes.append(int(k))

    ids = list(range(PLACES))
    truth_order = sorted(ids, key=lambda i: -true_rates[i])
    truth_top10 = set(truth_order[:10])

    scores = {
        "raw": [float(likes[i]) for i in ids],
        "ratio": [likes[i] / viewers[i] if viewers[i] else 0.0 for i in ids],
        "wilson": [wilson_lb(likes[i], viewers[i]) for i in ids],
    }

    out: dict[str, float] = {}
    for name, score in scores.items():
        ranked = sorted(ids, key=lambda i: -score[i])
        out[f"{name}_tau"] = kendall_tau(score, true_rates)
        out[f"{name}_p10"] = precision_at_k(ranked, truth_top10, 10)
        # The mean true rate of what the method actually put on top -- the
        # plainest statement of "would a user have been well served".
        out[f"{name}_top10_true_rate"] = sum(true_rates[i] for i in ranked[:10]) / 10
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Ranking simulation (SPEC §17 item 1)")
    parser.add_argument("--seeds", type=int, default=200)
    args = parser.parse_args()

    seeds = list(range(args.seeds))
    runs = [one_run(seed) for seed in seeds]

    metrics: dict[str, object] = {}
    for key in runs[0]:
        metrics[key] = summarise([run[key] for run in runs])

    methods = ["raw", "ratio", "wilson"]
    print_table(
        "Kendall tau against the true ordering",
        [(m, metrics[f"{m}_tau"]) for m in methods],  # type: ignore[index]
    )
    print_table(
        "precision@10",
        [(m, metrics[f"{m}_p10"]) for m in methods],  # type: ignore[index]
    )
    print_table(
        "mean true like rate of the top 10",
        [(m, metrics[f"{m}_top10_true_rate"]) for m in methods],  # type: ignore[index]
    )

    figure = bar_figure(
        "precision@10 against the true top ten (500 places, 200 seeds)",
        ["raw likes", "like ratio", "Wilson lower bound"],
        [metrics[f"{m}_p10"]["mean"] for m in methods],  # type: ignore[index]
        [metrics[f"{m}_p10"]["ci95_low"] for m in methods],  # type: ignore[index]
        [metrics[f"{m}_p10"]["ci95_high"] for m in methods],  # type: ignore[index]
        y_label="precision@10",
    )

    path = write_results(
        "ranking",
        metrics,
        seeds=seeds,
        assumptions=[
            f"{PLACES} places per run; true like rate ~ Beta({BETA_A}, {BETA_B}).",
            f"Exposure is a power law (alpha={POWER_LAW_ALPHA}) between "
            f"{MIN_VIEWERS} and {MAX_VIEWERS} viewers, independent of quality.",
            "Likes are Binomial(viewers, true rate); no bots, no repeat likes.",
            "wilson_lb is the function the app uses (app.ranking.wilson), not a copy.",
        ],
        figure=figure,
    )
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
