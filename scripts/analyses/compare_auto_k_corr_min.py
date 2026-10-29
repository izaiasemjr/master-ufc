#!/usr/bin/env python3
"""Compare completed absolute-DP runs with different correspondence floors."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
BASE = 'bosphorus-neutrals-occlusions-auto-k'
DEFAULT_IDS = [BASE] + [f'{BASE}-corr-min-{minimum}' for minimum in (7,9,12)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiments', nargs='+', default=DEFAULT_IDS)
    parser.add_argument('--results-root', type=Path,
                        default=ROOT / 'data/results/BOSPHORUS/experiments')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or args.results_root / BASE / 'evaluation/corr_min_comparison'
    combined = []
    protocol = None
    minima = set()
    for experiment in args.experiments:
        run_root = args.results_root / experiment
        run = json.loads((run_root / 'pipeline/pipeline-run.json').read_text())
        if run['failures'] or {stage['stage'] for stage in run['stages'] if stage['return_code'] == 0} != {
                'matching','classification','evaluation','visualization'}:
            raise ValueError(f'Experiment did not complete all recognition stages: {experiment}')
        config = json.loads((run_root / 'pipeline/matching.json').read_text())
        settings = config['matching']
        minimum = settings.get('corr_min', 1)
        if settings.get('selection') != 'auto_k' or minimum in minima:
            raise ValueError(f'Expected absolute-DP selection and distinct corr_min: {experiment}')
        minima.add(minimum)
        signature = {key: value for key, value in settings.items() if key != 'corr_min'}
        signature['descriptor_input'] = config['input']
        if protocol is None:
            protocol = signature
        elif signature != protocol:
            raise ValueError(f'Runs differ in settings beyond corr_min: {experiment}')
        for variant in settings['variants']:
            with (run_root / f'evaluation/{variant}/accuracy_by_dp.csv').open(newline='') as handle:
                combined.extend(dict(corr_min=minimum, **row) for row in csv.DictReader(handle))
    populations = {}
    for row in combined:
        key = (row['variant'], row['dp'], row['category'])
        populations.setdefault(key, set()).add(row['samples'])
    if any(len(values) != 1 for values in populations.values()):
        raise ValueError('Probe populations differ across runs')
    output.mkdir(parents=True, exist_ok=True)
    def save_csv(name, rows):
        with (output / name).open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    save_csv('accuracy_by_dp_corr_min.csv', combined)
    variants = list(settings['variants'])
    best = []
    for variant in variants:
        for minimum in sorted(minima):
            candidates = [row for row in combined if row['variant'] == variant and
                          row['corr_min'] == minimum and row['category'] == 'ALL']
            best.append(max(candidates, key=lambda row: (float(row['accuracy_percent']), -float(row['dp']))))
    save_csv('best_accuracy_by_corr_min.csv', best)
    fig, axes = plt.subplots(1, len(variants), figsize=(6*len(variants),5), squeeze=False, constrained_layout=True)
    labels = {'sparse_15': 'Radial Grid', 'sift': 'SIFT', 'iss': 'ISS'}
    for axis, variant in zip(axes[0], variants):
        for minimum in sorted(minima):
            rows = sorted((row for row in combined if row['variant'] == variant and
                           row['corr_min'] == minimum and row['category'] == 'ALL'), key=lambda row: float(row['dp']))
            axis.plot([float(row['dp']) for row in rows], [float(row['accuracy_percent']) for row in rows],
                      marker='o', label=f'corr_min = {minimum}')
        axis.set(title=labels.get(variant, variant), xlabel='DP (log scale)', ylabel='RR — All probes (%)', ylim=(0,100), xscale='log')
        dps = sorted({float(row['dp']) for row in combined})
        axis.set_xticks(dps, [f'{dp:g}' for dp in dps], rotation=45)
        axis.grid(axis='y', alpha=.25)
        axis.legend()
    fig.savefig(output / 'rr_by_dp_all_corr_min.png', dpi=200)
    plt.close(fig)
    print(output)
    for row in best:
        print(f"{row['variant']}: corr_min={row['corr_min']}, DP={row['dp']}, RR={row['accuracy_percent']}%")


if __name__ == '__main__':
    main()
