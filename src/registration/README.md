# Registration (CP-ICP)

`cp_icp/` contains the C++ CP-ICP implementation migrated from the dissertation
workspace. Build it on Linux/WSL with PCL installed:

```bash
cmake -S src/registration/cp_icp -B src/registration/cp_icp/build
cmake --build src/registration/cp_icp/build --parallel
```

## Create the reference mask first

CP-ICP uses one global reference mask. This Bosphorus-specific script selects
all `*_N_N_0.pcd` clouds available in the configured gallery, aligns each to
`bs000_N_N_0.pcd` using `pcl_icp`, concatenates the aligned clouds with
`pcl_concatenate_points_pcd`, then applies `pcl_mls_smoothing` with radius
`0.2`. The original base cloud is copied unchanged into the aligned gallery.

Run this stage after preprocessing and before CP-ICP:

```bash
python3 src/registration/bosphorus_reference_mask.py \
  --config data/configs/registration/bosphorus_cp_icp_mask_mls_th8.json --dry-run
python3 src/registration/bosphorus_reference_mask.py \
  --config data/configs/registration/bosphorus_cp_icp_mask_mls_th8.json
```

It writes the aligned gallery, its `alignment_manifest.csv`, the concatenated
gallery cloud, and the final `mask_mls.pcd` to
`data/results/BOSPHORUS/registration/cp-icp-mask-mls-th8/reference_mask/`,
plus `reference_mask_run.json` with the exact selection, base face, ICP
options, and MLS radius. The current configuration supplies `-d 20 -r 10 -i 50`
to `pcl_icp`; tune
`reference.alignment.pcl_icp_options` for a specific experiment.

The gallery size is dynamic: the script uses the number of files selected by
`reference.gallery_filename_regex`; it does not require 105 subjects.

During both reference-mask alignment and CP-ICP registration, the terminal
shows the current cloud, completed/total count, percentage completed, and
percentage remaining.

The experiment runner then reads every path and parameter from the same JSON
configuration:

```bash
python3 src/registration/run_registration.py \
  --config data/configs/registration/bosphorus_cp_icp_mask_mls_th8.json --dry-run
python3 src/registration/run_registration.py \
  --config data/configs/registration/bosphorus_cp_icp_mask_mls_th8.json
```

The supplied configuration depends on the `bosphorus-n-o-radius5-voxel2`
preprocessing output and its generated reference mask, and reproduces CP-ICP
parameters `k=2`, ICP
`0.0001,200`, threshold `8`, penalty `1`, and restoration threshold `1.0`.

Outputs are isolated under `data/results/BOSPHORUS/registration/`:
`registrations`, `transforms`, occlusion variants, `data_train_test`,
`metrics.csv`, `manifest.csv`, and `run.json`.

## Transform landmarks

The keypoint grid requires landmarks in the same coordinate system as the
registered faces. After registration, run:

```bash
python3 src/registration/transform_landmarks.py \
  --config data/configs/registration/bosphorus_cp_icp_mask_mls_th8.json
```

It reads registration matrices and writes to `landmarks_transformed`. It needs
`pcl_transform_point_cloud` on `PATH`.

`legacy/` holds unchanged historic shell orchestration scripts. They retain
their old hard-coded paths and are not the supported entry point.
