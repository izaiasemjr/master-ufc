#!/usr/bin/env python3
"""Plot sorted local-match distances for radial-grid probe x gallery pairs."""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


FIELDS = ("subject", "type", "expression", "sample")


def identity(row: dict[str, str], prefix: str) -> str:
    return "_".join(row[f"{prefix}_{field}"] for field in FIELDS)


def load_distances(path: Path) -> dict[tuple[str, str], list[float]]:
    groups: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            groups[(identity(row, "probe"), identity(row, "gallery"))].append(
                (int(row["pair_index"]), float(row["distance_l1"]))
            )
    if not groups:
        raise ValueError(f"No pair distances found in {path}")
    return {key: [value for _, value in sorted(values)] for key, values in groups.items()}


def thresholds(values: list[float], sigma: float) -> dict[str, float]:
    ordered = sorted(values)
    count = len(ordered)
    mean = sum(ordered) / count
    variance = sum((value - mean) ** 2 for value in ordered) / count
    median = (ordered[(count - 1) // 2] + ordered[count // 2]) / 2
    deviations = sorted(abs(value - median) for value in ordered)
    mad = (deviations[(count - 1) // 2] + deviations[count // 2]) / 2
    return {
        "mean_plus_sigma_sd": mean + sigma * math.sqrt(variance),
        "median_plus_sigma_mad": median + sigma * 1.4826 * mad,
    }


def retained(values: list[float], limit: float) -> int:
    return sum(value <= limit for value in values)


def plot_pair(probe: str, gallery: str, values: list[float], sigma: float, output: Path) -> None:
    cuts = thresholds(values, sigma)
    ranks = range(1, len(values) + 1)
    fig, (ax_distribution, ax_histogram) = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    ax_distribution.plot(ranks, values, color="#1f4e79", linewidth=1.8, label="L1 pair score (sorted)")
    styles = (("mean_plus_sigma_sd", "mean + SD", "#c00000"), ("median_plus_sigma_mad", "median + robust MAD", "#7030a0"))
    for key, label, color in styles:
        limit = cuts[key]
        count = retained(values, limit)
        ax_distribution.axhline(limit, color=color, linestyle="--", linewidth=1.3,
                                label=f"{label} x {sigma:g}: {limit:.3f} ({count}/{len(values)})")
        ax_histogram.axvline(limit, color=color, linestyle="--", linewidth=1.3)
    ax_distribution.set(xlabel="Pair rank after ascending sort", ylabel="L1 distance", title="Sorted local-pair scores")
    ax_distribution.grid(alpha=0.25)
    ax_distribution.legend(fontsize=8)
    ax_histogram.hist(values, bins="auto", color="#5b9bd5", edgecolor="white")
    ax_histogram.set(xlabel="L1 distance", ylabel="Number of local pairs", title="Distribution histogram")
    ax_histogram.grid(axis="y", alpha=0.25)
    fig.suptitle(f"Radial grid: probe {probe} x gallery {gallery}", fontsize=12)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot radial-grid local pair-score distributions.")
    parser.add_argument("--input", type=Path, required=True, help="sparse_15/pair_distances.csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--probe", help="Exact probe ID, e.g. bs000_O_EYE_0")
    parser.add_argument("--gallery", help="Exact gallery ID, e.g. bs000_N_N_0")
    parser.add_argument("--sigma", type=float, default=2.0, help="Multiplier for SD/MAD upper thresholds (default: 2)")
    parser.add_argument("--all", action="store_true", help="Render every selected probe x gallery pair; potentially many files")
    args = parser.parse_args()
    if args.sigma < 0:
        parser.error("--sigma must be non-negative")
    groups = load_distances(args.input)
    selected = [(probe, gallery, values) for (probe, gallery), values in groups.items()
                if (args.probe is None or probe == args.probe) and (args.gallery is None or gallery == args.gallery)]
    if not selected:
        parser.error("No pair matched --probe/--gallery")
    if len(selected) > 1 and not args.all:
        parser.error("Selection has multiple pairs; specify both --probe and --gallery, or pass --all")
    for probe, gallery, values in selected:
        plot_pair(probe, gallery, values, args.sigma, args.output_dir / probe / f"{gallery}.png")
    print(f"Wrote {len(selected)} plot(s) to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
