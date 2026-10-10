# Keypoints

Two C++ methods were migrated:

- `radial_grid/`: radial-grid keypoints centred on Bosphorus landmark index 13
  (nose tip);
- `detectors/`: SIFT with normals and ISS detector keypoints.

Build both projects on Linux/WSL with PCL installed:

```bash
cmake -S src/keypoints/radial_grid -B src/keypoints/radial_grid/build
cmake --build src/keypoints/radial_grid/build --parallel
cmake -S src/keypoints/detectors -B src/keypoints/detectors/build
cmake --build src/keypoints/detectors/build --parallel
```

`run_keypoints.py` is the supported entry point. It consumes registered clouds
and transformed landmarks, then records each output and its runtime:

```bash
python3 src/keypoints/run_keypoints.py \
  --config data/configs/keypoints/bosphorus_n_o_keypoints.json --dry-run
python3 src/keypoints/run_keypoints.py \
  --config data/configs/keypoints/bosphorus_n_o_keypoints.json
```

The Bosphorus configuration reproduces the six radial grids and the final SIFT
and ISS configurations used in the dissertation. Outputs are separated by
`grids/<grid-label>` and `detectors/<method-label>` inside
`data/results/BOSPHORUS/keypoints/bosphorus-n-o-keypoints/`.

To test another dataset or method, copy the JSON configuration and change only
the input roots, filename selection, parameter lists, and output root. The
historical Python/shell scripts are retained under `legacy/` for provenance.
