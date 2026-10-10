# Project memory

## 2026-10-06 - preprocessing migration

### Scope completed

- Migrated the reusable preprocessing workflow from
  `MESTRADO-CODIGOS-IZAIAS/preproceessing/` into
  `src/preprocessing/preprocess.py`.
- Preserved the three original Python scripts under `src/preprocessing/legacy/`
  as an unchanged provenance snapshot; their generated visualizations and PCL
  camera/timing files were deliberately not migrated.
- Added the dissertation Bosphorus experiment configuration at
  `data/configs/preprocessing/bosphorus_n_o_radius5_voxel2.json`.
- Added `data/configs/preprocessing/bosphorus_all_radius5_voxel2.json` for a
  complete pass over every available BOSPHORUS PCD file.
- Added `data/configs/preprocessing/bosphorus_n_o_e_radius5_voxel2.json` for
  neutral, occluded, and expression (`E`) clouds.
- Added `src/preprocessing/README.md` and data/git ignore rules.

### Established project conventions

- **Source code:** `src/<stage>/`.
- **Input datasets:** `data/bases/<DATASET>/`; they are ignored by default so
  non-public data is not accidentally committed.
- **Experiment configuration:** `data/configs/<stage>/<experiment>.json`; one
  file defines a dataset selection, output location, commands, parameters and
  execution policy.
- **Generated outputs:** `data/results/<DATASET>/<stage>/<experiment>/`; they
  are ignored by default. Every successful run writes `manifest.csv` and
  `run.json` beside the outputs.

### Bosphorus preprocessing protocol

Input layout: `data/bases/BOSPHORUS/BOSPHORUS_PCD/<subject>/*.pcd`.

Selection: filenames matching `^bs\\d+_(N|O)_.*\\.pcd$`. In the supplied local
dataset this selects 680 clouds: 299 neutral, 105 eye, 104 glasses, 105 mouth,
and 67 hair occlusions. The full directory contains 4,666 clouds.

Use `bosphorus_all_radius5_voxel2.json` when the intended experiment covers
all 4,666 clouds; use `bosphorus_n_o_radius5_voxel2.json` to reproduce the
dissertation subset.

Method parameters preserved from the original script and dissertation:

1. `pcl_outlier_removal -radius 5 -min_pts 10 -negative 0`
2. `pcl_voxel_grid -leaf 2,2,2`

The implementation uses intermediate `*.outlier-tmp.pcd` and
`*.preprocess-tmp.pcd` files, then atomically places the final output rather
than overwriting a cloud in place. It retains each source's relative path in
the output tree, reports failures per cloud, and can resume by skipping output
files that already exist.

### How to use it

```powershell
# Validate paths and selection; writes nothing.
python src/preprocessing/preprocess.py --config data/configs/preprocessing/bosphorus_n_o_radius5_voxel2.json --dry-run
```

```bash
# Run under Linux/WSL after installing pcl-tools.
python3 src/preprocessing/preprocess.py \
  --config data/configs/preprocessing/bosphorus_n_o_radius5_voxel2.json
```

The original workspace documentation recommends Linux/WSL and `pcl-tools`.
Windows PowerShell can run the dry run, but the actual stage needs
`pcl_outlier_removal` and `pcl_voxel_grid` available on `PATH` (or absolute
command paths defined in the config).

### Sources consulted

- `disssertação.pdf`: preprocessing is radius-based outlier removal followed
  by voxel-grid density reduction; reports roughly 0.33 seconds per cloud.
- `face-recognition-oclusion.pdf`: describes denoising/downsampling before
  registration and feature extraction.
- `MESTRADO-CODIGOS-IZAIAS/preproceessing/preprocessing.py`: supplied the
  exact original selection and PCL parameters.

## 2026-10-06 - registration and keypoints migration

### Migrated source

- CP-ICP C++ source: `src/registration/cp_icp/`.
- Radial-grid C++ source: `src/keypoints/radial_grid/`.
- SIFT/ISS C++ source: `src/keypoints/detectors/`.
- The historical shell/Python orchestrators are preserved in each module's
  `legacy/` directory. Build directories, ELF executables, historical output
  PCDs, and generated result tables were not migrated.
- Global references `mask_mls.pcd` and `mask_vg.pcd` were copied to
  `data/bases/BOSPHORUS/references/`; they remain ignored with other data.

### New experiment chain

1. Run preprocessing configuration `bosphorus_n_o_radius5_voxel2`.
2. Create the MLS global reference mask with
   `src/registration/bosphorus_reference_mask.py` and the registration config.
   It aligns each `N_N_0` gallery cloud to `bs000_N_N_0.pcd` with `pcl_icp`,
   concatenates all aligned gallery clouds selected by the configuration, and
   runs MLS with radius `0.2`. The gallery count is dynamic rather than fixed.
3. Build CP-ICP and run
   `data/configs/registration/bosphorus_cp_icp_mask_mls_th8.json` with
   `src/registration/run_registration.py`.
4. Run `src/registration/transform_landmarks.py` using that same config.
5. Build `src/crop/` and run
   `data/configs/crop/bosphorus_registration_crop80.json` with
   `src/crop/run_crop.py`. It uses landmark index 13, radius 80, and offset
   `0,0,0` for the Bosphorus protocol.
6. Build both keypoint C++ projects and run
   `data/configs/keypoints/bosphorus_n_o_keypoints.json` with
   `src/keypoints/run_keypoints.py`.

The registration config records the gallery selection, MLS mask construction,
and CP-ICP parameters; the keypoint config declares all grid/SIFT/ISS variants.
All generated clouds and metadata stay under `data/results`, keeping source
free of dataset paths.

## 2026-10-06 - crop migration

- Migrated the `Crop` and `crop_nine-keypoints` C++ sources from
  `MESTRADO-CODIGOS-IZAIAS/crop_cloud_bosphorus/` into `src/crop/`.
- Added the configuration-driven batch runner `src/crop/run_crop.py` and
  `data/configs/crop/bosphorus_registration_crop80.json`.
- Added `data/configs/crop/bosphorus_preprocessing_crop80.json` to crop the
  preprocessing output with the original landmarks, before registration.
- The runner consumes registered clouds and transformed landmarks, writes
  crops to `data/results/BOSPHORUS/crop/bosphorus-registration-crop80/clouds`,
  uses atomic temporary output, supports resuming, and records per-cloud
  progress, manifest, and metadata.
- Updated the Bosphorus keypoint configuration to consume that crop output.
- Historical crop scripts were kept under `src/crop/legacy/`; nine-region PCD
  visualizations and build artifacts were not migrated.

### Terminal progress

The reference-mask ICP loop and the CP-ICP registration loop report the cloud,
completed count, completed percentage, and remaining percentage after each
cloud. This includes skipped files when a resumable execution finds existing
output.

## 2026-10-06 - local Linux builds

The following PCL-dependent executables were built and link successfully in
the Ubuntu 22.04 WSL environment. Their `build/` directories are intentionally
ignored by Git:

- `src/registration/cp_icp/build/icp-cp`
- `src/crop/build/Crop`
- `src/crop/build/crop_nine-keypoints`
- `src/keypoints/radial_grid/build/keypoints_grid`
- `src/keypoints/detectors/build/keypoints`

They are ELF Linux executables and must be run from WSL/Linux, not native
Windows PowerShell.
