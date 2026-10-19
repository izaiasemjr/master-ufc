# Analytical studies

This directory contains reproducible analyses that are outside the normal
pipeline. `analyses` is clearer and shorter than `study-analyses`.

## Radial-grid pair-score distributions

`plot_radial_pair_distributions.py` plots the full L1-score distribution of a
`probe x gallery` comparison for the `sparse_15` radial-grid variant. Each
image includes the sorted-score curve and a histogram, with two possible upper
cuts: `mean + c x standard deviation` and `median + c x 1.4826 x MAD`. The MAD
cut is robust to long tails. A `c=2` cut means two standard deviations; adding
two times the variance to a distance would have incompatible units.

The matcher must first export raw local scores. The experiment configuration
already enables this only for `sparse_15` via `export_pair_distances: true`.
Rebuild the matcher, run the matching stage with overwrite, then plot a pair:

```bash
cmake -S src/matching -B src/matching/build
cmake --build src/matching/build -j
python scripts/analyses/plot_radial_pair_distributions.py \
  --input data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions/matching/sparse_15/pair_distances.csv \
  --output-dir data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions/analyses/radial-pair-distributions \
  --probe bs000_N_N_1 --gallery bs000_N_N_0
```

Use `--gallery <id> --all` to create one plot for every probe against a gallery
subject, or `--probe <id> --all` to inspect a probe against every gallery
subject. The complete protocol can produce tens of thousands of images.

## Radial-grid distribution for every gallery of one probe

`plot_radial_probe_distributions.py` creates one combined image per probe. It
shows the percentile bands of sorted local L1 distances across all its gallery
comparisons, a histogram split between the gallery of the same subject and
other subjects, and the final gallery ranking obtained from the mean of the
`k` smallest local distances. The final panel is the one that directly tests
identification: the genuine gallery should rank near 1.

```bash
python scripts/analyses/plot_radial_probe_distributions.py \
  --input data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions/matching/sparse_15/pair_distances.csv \
  --output-dir data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions/analyses/radial-probe-distributions \
  --probe bs000_N_N_1 --k 30
```

Use `--all` to produce the figure for every probe. The default `k=30` matches
the experiment configuration.

## Radial-grid distributions for misclassified probes

`plot_radial_misclassified_probe_distributions.py` reuses the same three panels
but writes images only when the best gallery belongs to a different subject
(incorrect rank-1 identification). Scores are recomputed from `pair_distances.csv`
using the mean of the `min(k, number of local distances)` smallest L1 distances.
Equal scores are ordered by gallery ID, following the classification stage's
tie-breaking rule. This analyzes the chosen `k`, independently of any previously
saved predictions; `k` does not have to appear in `matching.k_values`.

```bash
python scripts/analyses/plot_radial_misclassified_probe_distributions.py \
  --input data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions/matching/sparse_15/pair_distances.csv \
  --output-dir data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions/analyses/radial-probe-distributions-misclassified-k107 \
  --all --k 107
```

All probes are analyzed by default; `--all` is optional. Use `--probe <id>` to
check a single probe. Correct probes produce no image. The script reports the
predicted subject and genuine rank for each error, and the total number of
errors. A missing genuine gallery is reported as an invalid protocol.
Use a separate output directory for each `k` to keep results from different
runs separate; existing images are not removed.
