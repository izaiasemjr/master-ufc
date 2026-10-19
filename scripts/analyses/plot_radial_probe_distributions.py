#!/usr/bin/env python3
"""Summarise all radial-grid gallery comparisons for each probe.

The figure deliberately keeps local L1 distances and final comparison scores
separate: a local cut is applied inside a probe x gallery comparison, while
identity is decided by comparing the final scores across galleries.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


FIELDS = ("subject", "type", "expression", "sample")


def identity(row: dict[str, str], prefix: str) -> str:
    return "_".join(row[f"{prefix}_{field}"] for field in FIELDS)


def subject(identifier: str) -> str:
    return identifier.split("_", 1)[0]


def load_distances(path: Path) -> dict[str, dict[str, list[float]]]:
    grouped: dict[str, dict[str, list[tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            grouped[identity(row, "probe")][identity(row, "gallery")].append(
                (int(row["pair_index"]), float(row["distance_l1"]))
            )
    if not grouped:
        raise ValueError(f"No pair distances found in {path}")
    return {
        probe: {gallery: [value for _, value in sorted(rows)] for gallery, rows in galleries.items()}
        for probe, galleries in grouped.items()
    }


def local_quantiles(galleries: dict[str, list[float]], ranks: np.ndarray) -> tuple[np.ndarray, ...]:
    """Return percentile bands at normalized ranks, tolerating unequal counts."""
    curves = []
    for values in galleries.values():
        ordered = np.sort(np.asarray(values, dtype=float))
        source_ranks = np.linspace(0.0, 1.0, len(ordered))
        curves.append(np.interp(ranks, source_ranks, ordered))
    return tuple(np.percentile(np.asarray(curves), q, axis=0) for q in (10, 25, 50, 75, 90))


def rank_galleries(galleries: dict[str, list[float]], k: int) -> list[tuple[float, str]]:
    """Rank by mean of the k smallest distances, breaking ties by gallery ID."""
    if k < 1:
        raise ValueError("k must be positive")
    return sorted(
        (sum(sorted(values)[:min(k, len(values))]) / min(k, len(values)), gallery)
        for gallery, values in galleries.items()
    )


def plot_probe(probe: str, galleries: dict[str, list[float]], k: int, output: Path) -> None:
    ranks = np.linspace(0.0, 1.0, 106)
    q10, q25, q50, q75, q90 = local_quantiles(galleries, ranks)
    genuine = {gallery: values for gallery, values in galleries.items() if subject(gallery) == subject(probe)}
    impostor = {gallery: values for gallery, values in galleries.items() if gallery not in genuine}
    final_scores = rank_galleries(galleries, k)

    fig, (ax_local, ax_hist, ax_final) = plt.subplots(1, 3, figsize=(16, 4.8), constrained_layout=True)
    ax_local.fill_between(ranks * 100, q10, q90, color="#5b9bd5", alpha=0.18, label="10–90% das galleries")
    ax_local.fill_between(ranks * 100, q25, q75, color="#5b9bd5", alpha=0.34, label="25–75% das galleries")
    ax_local.plot(ranks * 100, q50, color="#1f4e79", linewidth=1.8, label="mediana entre galleries")
    for values in genuine.values():
        source_ranks = np.linspace(0.0, 1.0, len(values))
        ax_local.plot(ranks * 100, np.interp(ranks, source_ranks, np.sort(values)), color="#c00000", linewidth=1.5,
                      label="gallery do mesmo sujeito")
    ax_local.set(xlabel="Percentil da distância local ordenada", ylabel="Distância L1",
                 title="Distribuição local por comparação")
    ax_local.grid(alpha=0.25)
    handles, labels = ax_local.get_legend_handles_labels()
    ax_local.legend(dict(zip(labels, handles)).values(), dict(zip(labels, handles)).keys(), fontsize=8)

    impostor_values = [value for values in impostor.values() for value in values]
    genuine_values = [value for values in genuine.values() for value in values]
    # Both groups need identical bin edges; otherwise overlapping bars cannot
    # be compared as frequencies in the same L1 interval.
    bin_edges = np.histogram_bin_edges(impostor_values + genuine_values, bins="auto")
    if impostor_values:
        ax_hist.hist(impostor_values, bins=bin_edges, color="#5b9bd5", alpha=0.60, label="outros sujeitos")
    if genuine_values:
        ax_hist.hist(genuine_values, bins=bin_edges, color="#c00000", alpha=0.55, label="mesmo sujeito")
    ax_hist.set(xlabel="Distância L1 local", ylabel="Número de pares locais", title="Todas as correspondências locais")
    ax_hist.grid(axis="y", alpha=0.25)
    ax_hist.legend(fontsize=8)

    for rank, (score, gallery) in enumerate(final_scores, start=1):
        color = "#c00000" if gallery in genuine else "#5b9bd5"
        ax_final.scatter(rank, score, color=color, s=20)
    true_ranks = [rank for rank, (_, gallery) in enumerate(final_scores, start=1) if gallery in genuine]
    ax_final.set(xlabel="Rank da gallery após ordenar o score final", ylabel=f"Média das {k} menores L1",
                 title="Score usado para decisão de identidade")
    ax_final.grid(alpha=0.25)
    ax_final.scatter([], [], color="#c00000", label="mesmo sujeito")
    ax_final.scatter([], [], color="#5b9bd5", label="outro sujeito")
    ax_final.legend(fontsize=8)
    if true_ranks:
        ax_final.text(0.98, 0.02, "rank genuíno: " + ", ".join(map(str, true_ranks)), transform=ax_final.transAxes,
                      horizontalalignment="right", verticalalignment="bottom", fontsize=8,
                      bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"})

    fig.suptitle(f"Radial grid — probe {probe}: {len(galleries)} galleries; score final com k={k}", fontsize=12)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot all gallery comparisons jointly for each radial-grid probe.")
    parser.add_argument("--input", type=Path, required=True, help="sparse_15/pair_distances.csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--probe", help="Exact probe ID, e.g. bs000_N_N_1")
    parser.add_argument("--k", type=int, default=30, help="Number of smallest local L1 values averaged for final score")
    parser.add_argument("--all", action="store_true", help="Render one combined figure for every probe")
    args = parser.parse_args()
    if args.k < 1:
        parser.error("--k must be positive")
    groups = load_distances(args.input)
    selected = {probe: galleries for probe, galleries in groups.items() if args.probe is None or probe == args.probe}
    if not selected:
        parser.error("No pair matched --probe")
    if len(selected) > 1 and not args.all:
        parser.error("Selection has multiple probes; specify --probe or pass --all")
    for probe, galleries in selected.items():
        plot_probe(probe, galleries, args.k, args.output_dir / f"{probe}.png")
    print(f"Wrote {len(selected)} combined probe plot(s) to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
