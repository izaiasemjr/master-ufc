#!/usr/bin/env python3
"""Plot radial-grid distributions only for probes misclassified at rank 1."""
from __future__ import annotations

import argparse
from pathlib import Path

from plot_radial_probe_distributions import load_distances, plot_probe, rank_galleries, subject


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot radial-grid distributions only for probes misclassified at rank 1 for the chosen k."
    )
    parser.add_argument("--input", type=Path, required=True, help="sparse_15/pair_distances.csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--probe", help="Restrict analysis to one exact probe ID, e.g. bs000_N_N_1")
    parser.add_argument("--k", type=int, default=30, help="Number of smallest local L1 values averaged for final score")
    parser.add_argument("--all", action="store_true", help="Analyze every probe (the default when --probe is omitted)")
    args = parser.parse_args()
    if args.k < 1:
        parser.error("--k must be positive")
    if not args.input.is_file():
        parser.error(f"Input file not found: {args.input}. Run matching with export_pair_distances: true first.")
    groups = load_distances(args.input)
    selected = {probe: galleries for probe, galleries in groups.items() if args.probe is None or probe == args.probe}
    if not selected:
        parser.error("No pair matched --probe")
    # A missing genuine gallery indicates an invalid protocol, not a rank-1 error.
    for probe, galleries in selected.items():
        if not any(subject(gallery) == subject(probe) for gallery in galleries):
            parser.error(f"No gallery entry for the true subject of probe {probe}")
    written = 0
    for probe, galleries in selected.items():
        ranking = rank_galleries(galleries, args.k)
        predicted_gallery = ranking[0][1]
        if subject(predicted_gallery) == subject(probe):
            continue
        true_rank = next(rank for rank, (_, gallery) in enumerate(ranking, 1) if subject(gallery) == subject(probe))
        plot_probe(probe, galleries, args.k, args.output_dir / f"{probe}.png",
                   show_extreme_galleries=True)
        written += 1
        print(f"[misclassified] {probe}: predicted={subject(predicted_gallery)}, true_rank={true_rank}")
    print(f"Analyzed {len(selected)} probe(s) at k={args.k}; misclassified: {written}.")
    print(f"Wrote {written} combined probe plot(s) to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
