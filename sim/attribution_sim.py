"""Which attribution rule credits the creator who actually caused the visit?

SPEC §17 item 3. This is the simulation that justifies SPEC §9.9, and therefore
how the Partner Program divides money.

**The question.** A user sees several creators' posts about a place and then
goes. Who caused the visit? We cannot know, so we need a rule -- and the rule
decides who gets paid. Which rule comes closest to the truth?

**The ground truth.** Each creator has a hidden *influence* -- how much one
piece of their content raises the chance that a viewer goes. A touch at time t
contributes `influence * exp(-(age)/tau)` to the visit probability, with a
decay the rules do not get told about. A visit happens with the summed
probability, and the creator responsible for *that* visit is drawn in
proportion to each creator's contribution at that moment. So there is a true
answer per visit, and a true total per creator.

**The three rules.**
  last_touch   all credit to the most recent touch (the industry default)
  linear       split evenly across touches, ignoring when they happened
  time_decay   SPEC §9.9: weight 2^(-age/7 days), normalise to 1

**What is measured.** Spearman's rho between credited visits and true influence
(does the rule rank creators correctly?) and the mean absolute error of each
creator's share of all credit (does it get the magnitudes right?). 100 seeds.

**The assumption that matters.** The ground-truth decay (tau) is *not* the
rule's 7-day half-life. If it were, time-decay would win by construction. The
simulation sweeps tau so the result shows where each rule wins and where it
does not.
"""
from __future__ import annotations

import argparse
import math
import random

from common import (  # noqa: E402
    bar_figure,
    line_figure,
    print_table,
    spearman,
    summarise,
    write_results,
)

from app.partner.attribution import (  # noqa: E402
    TouchRow,
    attribute,
    attribute_last_touch,
    attribute_linear,
)

from datetime import datetime, timedelta  # noqa: E402

CREATORS = 12
USERS = 900
PLACES = 40
LOOKBACK_DAYS = 30
VISIT_AT = datetime(2026, 10, 20, 12, 0)

RULES = {
    "last_touch": attribute_last_touch,
    "linear": attribute_linear,
    "time_decay": attribute,
}


def one_run(seed: int, truth_tau_days: float) -> dict[str, float]:
    rng = random.Random(seed)

    # Hidden influence per creator: a few are genuinely persuasive.
    influence = {c: rng.betavariate(2.0, 5.0) for c in range(CREATORS)}

    credited: dict[str, dict[int, float]] = {rule: {c: 0.0 for c in range(CREATORS)} for rule in RULES}
    true_credit = {c: 0.0 for c in range(CREATORS)}
    visits = 0

    for user in range(USERS):
        place = rng.randrange(PLACES)
        # Each user sees 0-5 pieces of content about the place.
        touch_count = rng.choices([0, 1, 2, 3, 4, 5], weights=[12, 30, 26, 18, 9, 5])[0]
        touches: list[TouchRow] = []
        contributions: list[tuple[int, float]] = []

        for _ in range(touch_count):
            creator = rng.randrange(CREATORS)
            age_days = rng.uniform(0.0, LOOKBACK_DAYS)
            at = VISIT_AT - timedelta(days=age_days)
            touches.append(TouchRow(creator_id=creator, at=at))
            # The ground truth the rules are not told about.
            contributions.append((creator, influence[creator] * math.exp(-age_days / truth_tau_days)))

        total = sum(weight for _, weight in contributions)
        probability = 1.0 - math.exp(-total)      # saturating, so many touches do not exceed 1
        if rng.random() >= probability or not contributions:
            continue

        visits += 1
        # Which creator actually caused *this* visit.
        pick = rng.random() * total
        running = 0.0
        for creator, weight in contributions:
            running += weight
            if running >= pick:
                true_credit[creator] += 1.0
                break

        visitor_id = 10_000 + user       # never one of the creators
        for rule, function in RULES.items():
            shares = function(touches, visitor_id, VISIT_AT)
            for creator, share in shares.items():
                credited[rule][creator] += share

    out: dict[str, float] = {"visits": float(visits)}
    truth_vector = [true_credit[c] for c in range(CREATORS)]
    influence_vector = [influence[c] for c in range(CREATORS)]
    truth_total = sum(truth_vector) or 1.0

    for rule in RULES:
        vector = [credited[rule][c] for c in range(CREATORS)]
        total_credit = sum(vector) or 1.0
        out[f"{rule}_rho_vs_truth"] = spearman(vector, truth_vector)
        out[f"{rule}_rho_vs_influence"] = spearman(vector, influence_vector)
        out[f"{rule}_share_mae"] = sum(
            abs(vector[c] / total_credit - truth_vector[c] / truth_total) for c in range(CREATORS)
        ) / CREATORS
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Attribution simulation (SPEC §17 item 3)")
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument(
        "--truth-tau",
        type=float,
        default=10.0,
        help="the ground truth's decay constant in days (the rules do not know it)",
    )
    args = parser.parse_args()

    seeds = list(range(args.seeds))
    runs = [one_run(seed, args.truth_tau) for seed in seeds]
    rules = list(RULES)

    metrics: dict[str, object] = {"truth_tau_days": args.truth_tau}
    for key in runs[0]:
        metrics[key] = summarise([run[key] for run in runs])

    print_table(
        f"Spearman rho vs the true per-visit credit (truth tau = {args.truth_tau} d)",
        [(r, metrics[f"{r}_rho_vs_truth"]) for r in rules],  # type: ignore[index]
    )
    print_table(
        "mean absolute error of each creator's share",
        [(r, metrics[f"{r}_share_mae"]) for r in rules],  # type: ignore[index]
    )

    # Sweep the ground truth's decay, so the result is not an artefact of one
    # lucky choice of tau. Fewer seeds per point, since this is a shape.
    sweep_taus = [2, 4, 7, 10, 14, 21, 30]
    sweep_seeds = max(10, args.seeds // 8)
    sweep: dict[str, list[float]] = {rule: [] for rule in rules}
    for tau in sweep_taus:
        tau_runs = [one_run(seed, float(tau)) for seed in range(sweep_seeds)]
        for rule in rules:
            values = [run[f"{rule}_rho_vs_truth"] for run in tau_runs]
            sweep[rule].append(round(sum(values) / len(values), 5))
    metrics["tau_sweep_days"] = sweep_taus
    metrics["tau_sweep_rho"] = sweep

    print(f"\n  rho as the truth's decay changes (seeds={sweep_seeds})")
    print(f"    {'tau (days)':<14}" + "".join(f"{t:>9}" for t in sweep_taus))
    for rule in rules:
        print(f"    {rule:<14}" + "".join(f"{v:>9.3f}" for v in sweep[rule]))

    figure = bar_figure(
        f"Spearman rho against the true credit (truth decay {args.truth_tau} d, "
        f"{args.seeds} seeds)",
        ["last touch", "linear", "time decay (SPEC §9.9)"],
        [metrics[f"{r}_rho_vs_truth"]["mean"] for r in rules],  # type: ignore[index]
        [metrics[f"{r}_rho_vs_truth"]["ci95_low"] for r in rules],  # type: ignore[index]
        [metrics[f"{r}_rho_vs_truth"]["ci95_high"] for r in rules],  # type: ignore[index]
        y_label="Spearman rho",
    )
    sweep_figure = line_figure(
        "Does the rule still work when the truth decays differently?",
        {
            "last touch": sweep["last_touch"],
            "linear": sweep["linear"],
            "time decay": sweep["time_decay"],
        },
        x_label=f"ground-truth decay constant, days: {sweep_taus}",
        y_label="Spearman rho vs true credit",
    )

    path = write_results(
        "attribution",
        metrics,
        seeds=seeds,
        assumptions=[
            f"{CREATORS} creators, {USERS} users, {PLACES} places per seed.",
            f"Hidden influence per creator ~ Beta(2, 5); lookback {LOOKBACK_DAYS} days.",
            f"A touch raises the visit probability by influence x exp(-age/{args.truth_tau}d); "
            "the visit probability is 1 - exp(-sum), so it saturates below 1.",
            "The creator credited by the ground truth is drawn in proportion to each "
            "creator's contribution at the moment of the visit.",
            "The ground truth's decay is deliberately NOT the rule's 7-day half-life, "
            "and is swept from 2 to 30 days so the result is not an artefact of it.",
            "The three rules are the app's own functions (app.partner.attribution).",
        ],
        figure=figure,
    )
    (path / "tau-sweep.svg").write_text(sweep_figure, encoding="utf-8")
    (path.parent / "latest" / "tau-sweep.svg").write_text(sweep_figure, encoding="utf-8")
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
