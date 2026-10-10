# Crop

This stage crops each registered face inside a sphere centered at a transformed
landmark. The supplied Bosphorus configuration uses landmark index `13` (the
nose tip), radius `80`, and offset `0,0,0`, preserving the dissertation setup.

Build the C++ executables under Linux/WSL with PCL installed:

```bash
cmake -S src/crop -B src/crop/build
cmake --build src/crop/build --parallel
```

After CP-ICP and landmark transformation, validate and run the experiment:

```bash
python3 src/crop/run_crop.py \
  --config data/configs/crop/bosphorus_registration_crop80.json --dry-run
python3 src/crop/run_crop.py \
  --config data/configs/crop/bosphorus_registration_crop80.json
```

To crop the preprocessed clouds before registration, use
`data/configs/crop/bosphorus_preprocessing_crop80.json`. It pairs the
preprocessed clouds with the original Bosphorus landmarks, which are still in
the same coordinate system at that point.

The cropped clouds are written to:

```text
data/results/BOSPHORUS/crop/bosphorus-registration-crop80/clouds/
```

Each execution produces `manifest.csv` and `run.json`. The terminal reports
the current cloud and the completed/remaining percentage. Copy the JSON config
to define another dataset, input variant, landmark index, crop radius, offset,
or output location.

`crop_nine-keypoints.cpp` and the historical scripts are retained for
provenance in `src/crop/`; the new `run_crop.py` is the supported batch runner.
