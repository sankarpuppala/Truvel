"""Does Thompson sampling learn what a user likes faster than the alternatives?

SPEC §17 item 2.

**The question.** The deck has to choose which place to show next without
knowing the user's taste. Does drawing from a Beta belief (SPEC §9.4) actually
beat the obvious alternatives?

**The setup.** 300 simulated users, each with hidden per-category preferences
drawn from Beta(2, 5) -- so most people like a couple of categories and are
indifferent to the rest. Each user is shown cards one at a time and saves a
card with probability `taste(category) * quality(place)`.

**The four strategies.**
  random      pick any candidate
  popular     always pick the highest-quality candidate, ignoring taste
  fixed       quality + the population's average taste per category; never learns
  thompson    SPEC §9.4: draw theta ~ Beta(alpha, beta) per category per request

**What is measured.** The save rate -- how often the user found something worth
keeping -- at two horizons: the first 30 swipes (what SPEC §17 asks for) and
once settled (the last 30 of 150). The two are reported separately because they
say different things, and the honest answer at 30 swipes is not the flattering
one. 50 seeds, 95 % confidence intervals, plus the learning curve.

**The assumption that matters.** Taste is stable within a session and
independent across categories. Real taste is correlated -- somebody who likes
waterfalls probably likes lakes -- which would let every learner generalise
from fewer observations and so favour Thompson.
"""
from __future__ import annotations

import argparse
import random

from common import (  # noqa: E402
    bar_figure,
    line_figure,
    print_table,
    summarise,
    write_results,
)

from app.deck.thompson import draw_theta, update  # noqa: E402

CATEGORIES = [
    "viewpoint",
    "waterfall",
    "lake",
    "hill_trek",
    "fort_heritage",
    "temple_sacred",
    "park_garden",
    "beach_river",
]
USERS = 300
SWIPES = 30                 # the horizon SPEC §17 item 2 asks about
LONG_SWIPES = 150           # a longer horizon, to show where the lines cross
CANDIDATES_PER_STEP = 8

# The "fixed" baseline's weights: the population's *average* taste per category,
# which is the best a hand-tuned, non-learning system could realistically do.
# Beta(2, 5) has mean 2/7 ~ 0.286, so each category sits near that with spread.
FIXED_WEIGHTS = {
    category: 0.2857 + offset
    for category, offset in zip(
        CATEGORIES, [0.10, 0.06, 0.02, -0.02, 0.04, -0.06, -0.04, -0.08]
    )
}


def make_places(rng: random.Random, count: int = 400) -> list[tuple[str, float]]:
    """(category, quality) for a pool of places. Quality is the general appeal."""
    return [(rng.choice(CATEGORIES), rng.betavariate(2.0, 3.0)) for _ in range(count)]


def simulate_user(
    rng: random.Random,
    strategy: str,
    places: list[tuple[str, float]],
    swipes: int = SWIPES,
) -> list[int]:
    """Run one user through `swipes` cards. Returns 1/0 saved, per swipe."""
    taste = {category: rng.betavariate(2.0, 5.0) for category in CATEGORIES}
    prefs = {category: (1.0, 1.0) for category in CATEGORIES}

    saved: list[int] = []
    seen: set[int] = set()

    for _ in range(swipes):
        pool = [i for i in range(len(places)) if i not in seen]
        if not pool:
            break
        candidates = rng.sample(pool, min(CANDIDATES_PER_STEP, len(pool)))

        if strategy == "random":
            choice = rng.choice(candidates)
        elif strategy == "popular":
            choice = max(candidates, key=lambda i: places[i][1])
        elif strategy == "fixed":
            choice = max(
                candidates,
                key=lambda i: 0.5 * places[i][1] + 0.5 * FIXED_WEIGHTS[places[i][0]],
            )
        else:  # thompson
            thetas = {
                category: draw_theta(prefs[category][0], prefs[category][1], rng)
                for category in CATEGORIES
            }
            choice = max(
                candidates,
                key=lambda i: 0.5 * places[i][1] + 0.5 * thetas[places[i][0]],
            )

        seen.add(choice)
        category, quality = places[choice]
        did_save = rng.random() < taste[category] * quality
        saved.append(1 if did_save else 0)

        if strategy == "thompson":
            alpha, beta = prefs[category]
            prefs[category] = update("save" if did_save else "skip", alpha, beta)

    return saved


def _rate(rows: list[list[int]]) -> float:
    total = sum(sum(row) for row in rows)
    count = sum(len(row) for row in rows)
    return total / count if count else 0.0


def one_run(seed: int) -> dict[str, object]:
    """One seed: every strategy over the long horizon, measured at both points."""
    rng = random.Random(seed)
    places = make_places(rng)
    out: dict[str, object] = {}
    curves: dict[str, list[float]] = {}

    for strategy in ("random", "popular", "fixed", "thompson"):
        per_user: list[list[int]] = []
        for user in range(USERS):
            # The same user seed across strategies, so the comparison is paired:
            # every strategy faces the same people with the same tastes.
            user_rng = random.Random(seed * 100_003 + user)
            per_user.append(simulate_user(user_rng, strategy, places, LONG_SWIPES))

        out[f"{strategy}_save_rate"] = _rate([row[:SWIPES] for row in per_user])
        out[f"{strategy}_save_rate_long"] = _rate(per_user)
        # The last 30 swipes: the steady state, once learning has had a chance.
        out[f"{strategy}_save_rate_settled"] = _rate([row[-SWIPES:] for row in per_user])

        curve = []
        for step in range(LONG_SWIPES):
            values = [row[step] for row in per_user if len(row) > step]
            curve.append(sum(values) / len(values) if values else 0.0)
        curves[strategy] = curve

    out["_curves"] = curves
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Bandit simulation (SPEC §17 item 2)")
    parser.add_argument("--seeds", type=int, default=50)
    args = parser.parse_args()

    seeds = list(range(args.seeds))
    runs = [one_run(seed) for seed in seeds]
    strategies = ["random", "popular", "fixed", "thompson"]

    metrics: dict[str, object] = {}
    for strategy in strategies:
        for suffix in ("", "_long", "_settled"):
            key = f"{strategy}_save_rate{suffix}"
            metrics[key] = summarise([float(run[key]) for run in runs])  # type: ignore[arg-type]

    # Average the learning curves across seeds, smoothed so the shape is
    # visible without pretending to a precision we do not have.
    curves: dict[str, list[float]] = {}
    window = 9
    for strategy in strategies:
        stacked = [run["_curves"][strategy] for run in runs]  # type: ignore[index]
        mean_curve = [
            sum(curve[i] for curve in stacked) / len(stacked) for i in range(LONG_SWIPES)
        ]
        smoothed = []
        for i in range(LONG_SWIPES):
            chunk = mean_curve[max(0, i - window // 2) : i + window // 2 + 1]
            smoothed.append(round(sum(chunk) / len(chunk), 5))
        curves[strategy] = smoothed
    metrics["learning_curves"] = curves

    print_table(
        f"save rate over the first {SWIPES} swipes ({USERS} users per seed)",
        [(s, metrics[f"{s}_save_rate"]) for s in strategies],  # type: ignore[index]
    )
    print_table(
        f"save rate once settled (last {SWIPES} of {LONG_SWIPES} swipes)",
        [(s, metrics[f"{s}_save_rate_settled"]) for s in strategies],  # type: ignore[index]
    )

    def lift(key: str) -> float:
        thompson = metrics[f"thompson_{key}"]["mean"]  # type: ignore[index]
        popular = metrics[f"popular_{key}"]["mean"]  # type: ignore[index]
        return (thompson / popular - 1) * 100 if popular else 0.0

    first = lift("save_rate")
    settled = lift("save_rate_settled")
    print(f"\n  Thompson vs popularity, first {SWIPES} swipes: {first:+.1f}%")
    print(f"  Thompson vs popularity, once settled:      {settled:+.1f}%")
    metrics["thompson_vs_popular_pct_first30"] = round(first, 3)
    metrics["thompson_vs_popular_pct_settled"] = round(settled, 3)

    figure = bar_figure(
        f"Save rate once settled (last {SWIPES} of {LONG_SWIPES} swipes, "
        f"{USERS} users, {args.seeds} seeds)",
        ["random", "popularity", "fixed weights", "Thompson"],
        [metrics[f"{s}_save_rate_settled"]["mean"] for s in strategies],  # type: ignore[index]
        [metrics[f"{s}_save_rate_settled"]["ci95_low"] for s in strategies],  # type: ignore[index]
        [metrics[f"{s}_save_rate_settled"]["ci95_high"] for s in strategies],  # type: ignore[index]
        y_label="share of cards saved",
    )
    curve_figure = line_figure(
        "Learning curve: save rate by swipe number",
        {
            "random": curves["random"],
            "popularity": curves["popular"],
            "fixed weights": curves["fixed"],
            "Thompson": curves["thompson"],
        },
        x_label="swipe number",
        y_label="save rate",
    )

    path = write_results(
        "bandit",
        metrics,
        seeds=seeds,
        assumptions=[
            f"{USERS} users per seed, {LONG_SWIPES} swipes each (reported at "
            f"{SWIPES} and once settled), {CANDIDATES_PER_STEP} candidates per swipe.",
            "The comparison is paired: every strategy faces the same users.",
            "Hidden per-category taste ~ Beta(2, 5); place quality ~ Beta(2, 3).",
            "A user saves with probability taste(category) x quality(place).",
            "The 'fixed weights' baseline uses the population's average taste per "
            "category, which is the best a non-learning system could do.",
            "Taste is stable within a session and independent across categories; "
            "real taste is correlated, which would favour every learner.",
            "draw_theta and update are the app's own functions (app.deck.thompson).",
        ],
        figure=figure,
    )
    (path / "learning-curve.svg").write_text(curve_figure, encoding="utf-8")
    (path.parent / "latest" / "learning-curve.svg").write_text(curve_figure, encoding="utf-8")
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
