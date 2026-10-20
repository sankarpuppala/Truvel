"""Do the invalid-traffic rules catch fraud, and what does fraud still earn?

SPEC §17 item 4.

**The question.** The Partner pool is divided by score, so a fraudster does not
need to break anything -- they only need to inflate their own numbers faster
than everyone else. Do the SPEC §9.10 rules catch them, and how much money does
a fraudster still walk away with?

**The setup.** Honest creators get organic views from aged accounts at a human
pace. Three kinds of fraud are injected:

  bot burst     one item gets thousands of views in a couple of hours
  sock puppets  a farm of accounts under 24 h old, all viewing the same creator
  self views    the creator watching their own content on repeat

**The rules under test** (all from the app, not copies): self-view, new
account, repeat-within-24 h, and the velocity hold, which keeps the excess over
`mean + 4*sd` of an item's own trailing hourly counts when that hour also
exceeds 50 views.

**What is measured.** Precision and recall over individual views, and the thing
that actually matters: the share of the simulated pool a fraudster takes, with
the rules on and off.

**The assumption that matters.** Fraud here is unsubtle, which is what cheap
fraud looks like. A patient attacker -- aged accounts, human pacing, one view
each -- would evade all four rules, and the honest conclusion is that these
rules raise the cost of fraud rather than ending it. That is why visits, which
need a body in a place, are weighted 25x views.
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

from common import (  # noqa: E402
    bar_figure,
    print_table,
    summarise,
    write_results,
)

from app.partner.invalid import velocity_hold  # noqa: E402
from app.partner.split import CreatorMonth, score_creator, split_pool  # noqa: E402
from app.watch.views import invalid_reason  # noqa: E402

NOW = datetime(2026, 10, 31, 23, 0)
MONTH_START = datetime(2026, 10, 1)
HONEST_CREATORS = 8
POOL_PAISE = 250_000 * 100


class View:
    """One view, with the truth about whether it was fraudulent."""

    __slots__ = ("creator", "viewer", "viewer_age_h", "at", "item", "is_fraud")

    def __init__(self, creator: int, viewer: int, viewer_age_h: float, at: datetime, item: int, is_fraud: bool):
        self.creator = creator
        self.viewer = viewer
        self.viewer_age_h = viewer_age_h
        self.at = at
        self.item = item
        self.is_fraud = is_fraud


def generate(rng: random.Random, fraudsters: int = 2) -> list[View]:
    """Organic traffic for honest creators, plus three kinds of injected fraud."""
    views: list[View] = []
    viewer_id = 100_000

    # --- honest traffic ---------------------------------------------------- #
    for creator in range(HONEST_CREATORS):
        items = [creator * 10 + i for i in range(3)]
        for day in range(30):
            for _ in range(rng.randint(8, 30)):
                viewer_id += 1
                at = MONTH_START + timedelta(days=day, hours=rng.uniform(6, 23))
                views.append(
                    View(creator, viewer_id, rng.uniform(48, 8000), at, rng.choice(items), False)
                )

    # --- fraud ------------------------------------------------------------- #
    for index in range(fraudsters):
        creator = HONEST_CREATORS + index
        item = creator * 10
        kind = ["bot_burst", "sock_puppets", "self_views"][index % 3]

        # Every fraudster also posts a little real-looking traffic, so the
        # rules cannot simply flag "the account with no organic views".
        for day in range(30):
            for _ in range(rng.randint(3, 10)):
                viewer_id += 1
                at = MONTH_START + timedelta(days=day, hours=rng.uniform(6, 23))
                views.append(View(creator, viewer_id, rng.uniform(48, 8000), at, item, False))

        if kind == "bot_burst":
            # 4,000 views in two hours, from aged accounts, one view each.
            burst_at = MONTH_START + timedelta(days=rng.randint(10, 25), hours=14)
            for i in range(4000):
                viewer_id += 1
                at = burst_at + timedelta(seconds=rng.uniform(0, 7200))
                views.append(View(creator, viewer_id, rng.uniform(48, 5000), at, item, True))
        elif kind == "sock_puppets":
            # 300 fresh accounts, each watching 8 times over a few days.
            for _ in range(300):
                viewer_id += 1
                age = rng.uniform(1, 20)          # under 24 h: the rule's target
                for _ in range(8):
                    at = MONTH_START + timedelta(days=rng.randint(5, 28), hours=rng.uniform(0, 23))
                    views.append(View(creator, viewer_id, age, at, item, True))
        else:
            # The creator watching themselves 1,200 times.
            for _ in range(1200):
                at = MONTH_START + timedelta(days=rng.randint(1, 29), hours=rng.uniform(0, 23))
                views.append(View(creator, creator, 9000, at, item, True))

    return views


def apply_rules(views: list[View]) -> tuple[set[int], dict[int, int]]:
    """Return (indices flagged invalid, held views per creator).

    The per-view rules come from `app.watch.views.invalid_reason`; the velocity
    hold is applied afterwards per item per hour, because it can only be judged
    against an item's own history.
    """
    flagged: set[int] = set()
    last_seen: dict[tuple[int, int], datetime] = {}

    for index, view in enumerate(sorted(range(len(views)), key=lambda i: views[i].at)):
        v = views[view]
        key = (v.viewer, v.item)
        reason = invalid_reason(
            viewer_id=v.viewer,
            creator_id=v.creator,
            viewer_created_at=v.at - timedelta(hours=v.viewer_age_h),
            now=v.at,
            previous_view_at=last_seen.get(key),
        )
        if reason:
            flagged.add(view)
        last_seen[key] = v.at
        del index

    # Velocity hold, per item per hour against its own trailing 7 days.
    surviving = [i for i in range(len(views)) if i not in flagged]
    by_item_hour: dict[tuple[int, datetime], list[int]] = {}
    for i in surviving:
        v = views[i]
        hour = v.at.replace(minute=0, second=0, microsecond=0)
        by_item_hour.setdefault((v.item, hour), []).append(i)

    held: dict[int, int] = {}
    for (item, hour), indices in sorted(by_item_hour.items(), key=lambda kv: kv[0][1]):
        trailing = [
            float(len(other))
            for (other_item, other_hour), other in by_item_hour.items()
            if other_item == item and hour - timedelta(days=7) <= other_hour < hour
        ]
        verdict = velocity_hold(len(indices), trailing)
        if verdict.held > 0:
            creator = views[indices[0]].creator
            held[creator] = held.get(creator, 0) + verdict.held
            # Hold the excess: the last N of that hour.
            for i in indices[verdict.counted :]:
                flagged.add(i)
    return flagged, held


def one_run(seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    views = generate(rng)
    flagged, _held = apply_rules(views)

    truth_fraud = {i for i, v in enumerate(views) if v.is_fraud}
    true_positive = len(flagged & truth_fraud)
    false_positive = len(flagged - truth_fraud)
    false_negative = len(truth_fraud - flagged)

    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 1.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 1.0

    # What the money does, with the rules on and off.
    def payout(use_rules: bool) -> dict[int, int]:
        counted: dict[int, int] = {}
        for i, v in enumerate(views):
            if use_rules and i in flagged:
                continue
            counted[v.creator] = counted.get(v.creator, 0) + 1
        rows = [
            CreatorMonth(creator_id=creator, engaged_views=count, eligible=True)
            for creator, count in counted.items()
        ]
        split_pool(rows, POOL_PAISE)
        return {row.creator_id: row.amount_paise for row in rows}

    with_rules = payout(True)
    without_rules = payout(False)
    fraud_creators = [c for c in range(HONEST_CREATORS, HONEST_CREATORS + 3) if c in without_rules]

    fraud_with = sum(with_rules.get(c, 0) for c in fraud_creators) / POOL_PAISE
    fraud_without = sum(without_rules.get(c, 0) for c in fraud_creators) / POOL_PAISE

    return {
        "precision": precision,
        "recall": recall,
        "fraud_pool_share_rules_off": fraud_without,
        "fraud_pool_share_rules_on": fraud_with,
        "fraud_share_reduction": (
            1 - fraud_with / fraud_without if fraud_without else 0.0
        ),
        "views_total": float(len(views)),
        "views_flagged": float(len(flagged)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Invalid-traffic simulation (SPEC §17 item 4)")
    parser.add_argument("--seeds", type=int, default=50)
    args = parser.parse_args()

    seeds = list(range(args.seeds))
    runs = [one_run(seed) for seed in seeds]

    metrics: dict[str, object] = {}
    for key in runs[0]:
        metrics[key] = summarise([run[key] for run in runs])

    print_table(
        "SPEC §9.10 rules over individual views",
        [("precision", metrics["precision"]), ("recall", metrics["recall"])],  # type: ignore[index]
    )
    print_table(
        "share of the simulated pool taken by fraudsters",
        [
            ("rules off", metrics["fraud_pool_share_rules_off"]),  # type: ignore[index]
            ("rules on", metrics["fraud_pool_share_rules_on"]),  # type: ignore[index]
        ],
    )
    reduction = metrics["fraud_share_reduction"]["mean"] * 100  # type: ignore[index]
    print(f"\n  The rules remove {reduction:.1f}% of what fraud would have earned.")

    figure = bar_figure(
        f"Share of the simulated pool taken by fraud ({args.seeds} seeds)",
        ["rules off", "rules on"],
        [
            metrics["fraud_pool_share_rules_off"]["mean"],  # type: ignore[index]
            metrics["fraud_pool_share_rules_on"]["mean"],  # type: ignore[index]
        ],
        [
            metrics["fraud_pool_share_rules_off"]["ci95_low"],  # type: ignore[index]
            metrics["fraud_pool_share_rules_on"]["ci95_low"],  # type: ignore[index]
        ],
        [
            metrics["fraud_pool_share_rules_off"]["ci95_high"],  # type: ignore[index]
            metrics["fraud_pool_share_rules_on"]["ci95_high"],  # type: ignore[index]
        ],
        y_label="share of the pool",
    )

    path = write_results(
        "fraud",
        metrics,
        seeds=seeds,
        assumptions=[
            f"{HONEST_CREATORS} honest creators with organic traffic over one month; "
            "3 fraudsters, one per attack type.",
            "bot burst = 4,000 views in 2 hours from aged accounts, one view each.",
            "sock puppets = 300 accounts under 24 h old, 8 views each.",
            "self views = the creator watching their own item 1,200 times.",
            "Each fraudster also posts organic-looking traffic, so 'no organic "
            "views' is not the giveaway.",
            "Earnings are views-only here, to isolate the view rules; in the app "
            "a visit is worth 25 views, which is the real defence.",
            "Fraud is unsubtle. A patient attacker with aged accounts viewing once "
            "each at human pace would evade all four rules.",
            "The rules are the app's own functions (app.watch.views, app.partner.invalid).",
        ],
        figure=figure,
    )
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
