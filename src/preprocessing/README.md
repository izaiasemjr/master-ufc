# Preprocessing

This module removes isolated points using PCL's radius outlier filter and then
downsamples with PCL's voxel grid filter. It replaces the path-specific script
from the dissertation workspace with a configuration-driven runner.

## Run the Bosphorus experiments

From the repository root, first inspect the work without changing anything:

```powershell
python src/preprocessing/preprocess.py --config data/configs/preprocessing/bosphorus_n_o_radius5_voxel2.json --dry-run
```

For every available BOSPHORUS cloud, use the `all` configuration instead:

```powershell
python src/preprocessing/preprocess.py --config data/configs/preprocessing/bosphorus_all_radius5_voxel2.json --dry-run
```

To select only neutral, occluded, and expression clouds, create a configuration
whose filename pattern is `^bs\\d+_(N|O|E)_.*\\.pcd$`. The local
`bosphorus_subset_n_o_e_radius5_voxel2.json` is one example for a subset.

Run the complete experiment in an environment where PCL command-line tools are
available (Linux/WSL is the recommended environment):

```bash
python3 src/preprocessing/preprocess.py \
  --config data/configs/preprocessing/bosphorus_n_o_radius5_voxel2.json
```

Use `--limit 3` for a small execution test, `--workers 4` to override the
configured concurrency, and `--overwrite` only when intentionally regenerating
clouds. The process is resumable: by default, existing output clouds are
skipped.

## Input and output contract

Both Bosphorus configurations read from:

```text
data/bases/BOSPHORUS/BOSPHORUS_PCD/<subject>/<cloud>.pcd
```

`bosphorus_n_o_radius5_voxel2.json` selects the 680 neutral (`N`) and occluded
(`O`) clouds required by the dissertation protocol. The `all` configuration
selects all PCD files (4,666 in the supplied local dataset). Both preserve
subject subdirectories in:

```text
data/results/BOSPHORUS/preprocessing/<experiment-name>/clouds/
```

Each execution also writes `manifest.csv` (per-cloud status and duration) and
`run.json` (parameters and aggregate counts) beside `clouds`. These files make
an experiment traceable without hard-coding paths in source code.

## Create a new experiment

Copy `data/configs/preprocessing/bosphorus_n_o_radius5_voxel2.json`, give it a
new `name` and output root, then adjust:

- `dataset.input_root`, `include_glob`, and `include_filename_regex` for the dataset layout and selection;
- `processing.outlier_removal` and `processing.voxel_grid` for method parameters;
- `commands` if PCL executables are not on `PATH`;
- `execution.workers` and `fail_fast` for execution policy.

Relative paths are resolved from the repository root, not from the current
terminal directory. The runner never calls a shell, so paths with spaces are
handled safely.

## Historical scripts

The original scripts are retained under `legacy/` for provenance only. They
have fixed relative paths and viewer-oriented loops; use `preprocess.py` for
new experiments.
