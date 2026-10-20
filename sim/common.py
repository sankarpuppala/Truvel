"""Shared plumbing for the simulations (SPEC §17).

Every simulation writes `results/<name>/<timestamp>/` containing the config it
ran with, the git commit, the seeds, `metrics.json` and a figure. The report
quotes those files rather than numbers retyped by hand (AC-24).

A simulation shows how a method behaves **under stated assumptions**. It is not
a user study, and the report says so. The assumptions are written into each
file's docstring so a reader can disagree with them specifically.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

# The simulations import the real functions, never copies of them (PLAN.md).
sys.path.insert(0, str(ROOT / "backend"))


def git_commit() -> str:
    """The commit the results were produced at, or 'unknown' outside a repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - a missing git is not a failure
        return "unknown"


def run_dir(name: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = RESULTS / name / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_results(
    name: str,
    metrics: dict[str, Any],
    *,
    seeds: list[int],
    assumptions: list[str],
    figure: str | None = None,
) -> Path:
    """Write metrics.json (plus config and commit) and return the directory."""
    import yaml

    path = run_dir(name)
    with (ROOT / "config.yaml").open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    payload = {
        "simulation": name,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "commit": git_commit(),
        "seeds": seeds,
        "seed_count": len(seeds),
        "assumptions": assumptions,
        "metrics": metrics,
    }
    (path / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (path / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    if figure:
        (path / "figure.svg").write_text(figure, encoding="utf-8")

    # A stable path the README can link to without knowing the timestamp.
    latest = RESULTS / name / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if figure:
        (latest / "figure.svg").write_text(figure, encoding="utf-8")

    return path


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #

def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: list[float]) -> float:
    """Sample standard deviation (n-1), which is what a CI over seeds wants."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def ci95(values: list[float]) -> tuple[float, float, float]:
    """(mean, low, high) for a 95 % confidence interval of the mean.

    Normal approximation: with 50-200 seeds the t correction is under 2 %, and
    stating the method matters more than the second decimal.
    """
    if not values:
        return (0.0, 0.0, 0.0)
    m = mean(values)
    half = 1.96 * stdev(values) / math.sqrt(len(values))
    return (m, m - half, m + half)


def summarise(values: list[float]) -> dict[str, float]:
    m, low, high = ci95(values)
    return {
        "mean": round(m, 6),
        "ci95_low": round(low, 6),
        "ci95_high": round(high, 6),
        "sd": round(stdev(values), 6),
        "n": len(values),
    }


def spearman(a: list[float], b: list[float]) -> float:
    """Spearman's rank correlation: Pearson on the ranks, ties averaged."""
    if len(a) != len(b) or len(a) < 2:
        return 0.0
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = mean(ra), mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0.0


def kendall_tau(a: list[float], b: list[float]) -> float:
    """Kendall's tau-b: the share of pairs the two orderings agree on."""
    n = len(a)
    if n < 2:
        return 0.0
    concordant = discordant = tied_a = tied_b = 0
    for i in range(n):
        for j in range(i + 1, n):
            da, db = a[i] - a[j], b[i] - b[j]
            if da == 0 and db == 0:
                continue
            if da == 0:
                tied_a += 1
            elif db == 0:
                tied_b += 1
            elif (da > 0) == (db > 0):
                concordant += 1
            else:
                discordant += 1
    denominator = math.sqrt(
        (concordant + discordant + tied_a) * (concordant + discordant + tied_b)
    )
    return (concordant - discordant) / denominator if denominator else 0.0


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def precision_at_k(ranked_ids: list[int], truth_ids: set[int], k: int) -> float:
    """How many of the top k the ranking got right."""
    if k <= 0:
        return 0.0
    top = ranked_ids[:k]
    return sum(1 for item in top if item in truth_ids) / k


# --------------------------------------------------------------------------- #
# Figures -- hand-written SVG, so the simulations need no plotting library
# --------------------------------------------------------------------------- #

PALETTE = ["#A8401C", "#25627F", "#2E6A4E", "#E9A21B", "#5A635D"]


def bar_figure(
    title: str,
    labels: list[str],
    values: list[float],
    lows: list[float] | None = None,
    highs: list[float] | None = None,
    y_label: str = "",
) -> str:
    """A bar chart with 95 % CI whiskers, as a standalone SVG."""
    width, height = 720, 380
    left, bottom, top, right = 70, 70, 56, 24
    plot_w = width - left - right
    plot_h = height - top - bottom

    top_value = max(highs or values) if (highs or values) else 1.0
    top_value = max(top_value, 1e-9) * 1.15
    bar_w = plot_w / max(1, len(values)) * 0.56

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Mukta, system-ui, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#F6F1E7"/>',
        f'<text x="{left}" y="32" font-size="19" font-weight="700" fill="#1D2420">{title}</text>',
    ]

    # Axis and gridlines.
    for step in range(5):
        value = top_value * step / 4
        y = top + plot_h - (value / top_value) * plot_h
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" '
            f'stroke="#E2D9C8" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" font-size="12" fill="#5A635D" '
            f'text-anchor="end">{value:.3g}</text>'
        )
    if y_label:
        parts.append(
            f'<text x="16" y="{top + plot_h / 2:.0f}" font-size="12" fill="#5A635D" '
            f'transform="rotate(-90 16 {top + plot_h / 2:.0f})" text-anchor="middle">{y_label}</text>'
        )

    for index, (label, value) in enumerate(zip(labels, values)):
        centre = left + plot_w * (index + 0.5) / len(values)
        x = centre - bar_w / 2
        bar_h = (value / top_value) * plot_h
        y = top + plot_h - bar_h
        colour = PALETTE[index % len(PALETTE)]
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'fill="{colour}" rx="4"/>'
        )
        parts.append(
            f'<text x="{centre:.1f}" y="{y - 8:.1f}" font-size="13" font-weight="600" '
            f'fill="#1D2420" text-anchor="middle">{value:.3g}</text>'
        )
        parts.append(
            f'<text x="{centre:.1f}" y="{top + plot_h + 22:.1f}" font-size="13" '
            f'fill="#1D2420" text-anchor="middle">{label}</text>'
        )
        if lows and highs:
            y_low = top + plot_h - (lows[index] / top_value) * plot_h
            y_high = top + plot_h - (highs[index] / top_value) * plot_h
            parts.append(
                f'<line x1="{centre:.1f}" y1="{y_low:.1f}" x2="{centre:.1f}" '
                f'y2="{y_high:.1f}" stroke="#1D2420" stroke-width="1.6"/>'
            )
            for yy in (y_low, y_high):
                parts.append(
                    f'<line x1="{centre - 7:.1f}" y1="{yy:.1f}" x2="{centre + 7:.1f}" '
                    f'y2="{yy:.1f}" stroke="#1D2420" stroke-width="1.6"/>'
                )

    parts.append(
        f'<text x="{left}" y="{height - 18}" font-size="11" fill="#5A635D">'
        f'Whiskers show the 95% confidence interval of the mean over seeds. '
        f'Simulation under stated assumptions, not a user study.</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def line_figure(
    title: str,
    series: dict[str, list[float]],
    x_label: str = "",
    y_label: str = "",
) -> str:
    """A line chart, one line per series."""
    width, height = 720, 380
    left, bottom, top, right = 70, 70, 56, 150
    plot_w = width - left - right
    plot_h = height - top - bottom

    all_values = [v for values in series.values() for v in values]
    top_value = max(all_values + [1e-9]) * 1.1
    length = max((len(v) for v in series.values()), default=1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Mukta, system-ui, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#F6F1E7"/>',
        f'<text x="{left}" y="32" font-size="19" font-weight="700" fill="#1D2420">{title}</text>',
    ]
    for step in range(5):
        value = top_value * step / 4
        y = top + plot_h - (value / top_value) * plot_h
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" '
            f'stroke="#E2D9C8" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" font-size="12" fill="#5A635D" '
            f'text-anchor="end">{value:.3g}</text>'
        )

    for index, (name, values) in enumerate(series.items()):
        colour = PALETTE[index % len(PALETTE)]
        points = " ".join(
            f"{left + plot_w * i / max(1, length - 1):.1f},"
            f"{top + plot_h - (v / top_value) * plot_h:.1f}"
            for i, v in enumerate(values)
        )
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{colour}" stroke-width="2.4" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        legend_y = top + 16 + index * 22
        parts.append(
            f'<line x1="{left + plot_w + 16}" y1="{legend_y}" x2="{left + plot_w + 38}" '
            f'y2="{legend_y}" stroke="{colour}" stroke-width="3"/>'
        )
        parts.append(
            f'<text x="{left + plot_w + 44}" y="{legend_y + 4}" font-size="12.5" '
            f'fill="#1D2420">{name}</text>'
        )

    if x_label:
        parts.append(
            f'<text x="{left + plot_w / 2:.0f}" y="{height - 34}" font-size="12" '
            f'fill="#5A635D" text-anchor="middle">{x_label}</text>'
        )
    if y_label:
        parts.append(
            f'<text x="16" y="{top + plot_h / 2:.0f}" font-size="12" fill="#5A635D" '
            f'transform="rotate(-90 16 {top + plot_h / 2:.0f})" text-anchor="middle">{y_label}</text>'
        )
    parts.append(
        f'<text x="{left}" y="{height - 16}" font-size="11" fill="#5A635D">'
        f'Simulation under stated assumptions, not a user study.</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def print_table(title: str, rows: list[tuple[str, dict[str, float]]]) -> None:
    """A readable summary on the terminal, so a run is useful without the files."""
    print(f"\n{title}")
    print(f"  {'method':<22} {'mean':>10} {'95% CI':>22}")
    for name, stats in rows:
        ci = f"[{stats['ci95_low']:.4f}, {stats['ci95_high']:.4f}]"
        print(f"  {name:<22} {stats['mean']:>10.4f} {ci:>22}")
