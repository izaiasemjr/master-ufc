"""Exercise coordinate preservation through the real Python stage runners."""
from __future__ import annotations

import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/pipeline"))
from config import ConfigError, compile_experiment, read_yaml
sys.path.insert(0, str(ROOT / "src/matching"))
from run_matching import collect_variant


class RegistrationAblationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.names = ["bs000_N_N_0.pcd", "bs000_N_N_1.pcd", "bs000_O_EYE_0.pcd"]
        for name in self.names:
            for folder in ("inputs", "landmarks"):
                item = self.root / folder / "bs000" / name
                item.parent.mkdir(parents=True, exist_ok=True)
                item.write_bytes(f"{folder}: unchanged bytes for {name}\n".encode())
        self.config = {
            "name": "test", "mode": "none", "gallery_filename_regex": r"bs\d+_N_N_0\.pcd",
            "dataset": {"input_root": "inputs", "landmarks_root": "landmarks", "include_glob": "**/*.pcd",
                        "include_filename_regex": r"bs\d+_(N_N|O_EYE)_\d+\.pcd", "target_suffix": "N_N_0"},
            "output": {"root": "output"}, "reference": {"global_cloud": "missing-mask.pcd"},
            "processing": {}, "commands": {"cp_icp": "missing-cp-icp", "transform_landmarks": "missing-pcl-transform"},
            "execution": {},
        }

    def run_stage(self, script, *extra):
        config_path = self.root / "config.json"
        config_path.write_text(json.dumps(self.config))
        return subprocess.run([sys.executable, str(ROOT / "src/registration" / script),
                               "--config", str(config_path), "--project-root", str(self.root), *extra],
                              capture_output=True, text=True)

    def test_no_registration_preserves_clouds_and_landmarks_without_pcl(self):
        result = self.run_stage("run_registration.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_stage("transform_landmarks.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in self.names:
            relative = Path("bs000") / name
            self.assertEqual((self.root / "inputs" / relative).read_bytes(),
                             (self.root / "output/registrations" / relative).read_bytes())
            self.assertEqual((self.root / "landmarks" / relative).read_bytes(),
                             (self.root / "output/landmarks_transformed" / relative).read_bytes())
            values = (self.root / "output/transforms" / relative.with_suffix(".mat")).read_text().split()
            self.assertEqual([int(v) for v in values], [int(i == j) for i in range(4) for j in range(4)])
        # Resume also repairs an incomplete cloud/matrix pair.
        matrix = self.root / "output/transforms/bs000/bs000_N_N_0.mat"
        matrix.unlink()
        self.assertEqual(self.run_stage("run_registration.py").returncode, 0)
        self.assertTrue(matrix.is_file())

    def frozen_gallery(self):
        self.config.update(mode="gallery_only", reuse_gallery_root="baseline")
        relative = Path("bs000/bs000_N_N_0.pcd")
        for folder in ("registrations", "landmarks_transformed", "transforms"):
            destination = self.root / "baseline" / folder / (relative.with_suffix(".mat") if folder == "transforms" else relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(f"frozen {folder}\n".encode())

    def test_only_gallery_is_reused_and_probes_keep_original_coordinates(self):
        self.frozen_gallery()
        for script in ("run_registration.py", "transform_landmarks.py"):
            result = self.run_stage(script)
            self.assertEqual(result.returncode, 0, result.stderr)
        for name in self.names:
            relative = Path("bs000") / name
            for folder, original in (("registrations", "inputs"), ("landmarks_transformed", "landmarks")):
                expected = self.root / ("baseline" if name == self.names[0] else original)
                expected = expected / folder / relative if name == self.names[0] else expected / relative
                self.assertEqual(expected.read_bytes(), (self.root / "output" / folder / relative).read_bytes())
        with (self.root / "output/manifest.csv").open() as handle:
            self.assertEqual([row["action"] for row in csv.DictReader(handle)], ["reused", "bypassed", "bypassed"])

    def test_missing_frozen_gallery_fails_before_writing_outputs(self):
        self.frozen_gallery()
        (self.root / "baseline/landmarks_transformed/bs000/bs000_N_N_0.pcd").unlink()
        result = self.run_stage("run_registration.py")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Frozen gallery artifact is missing", result.stderr)
        self.assertFalse((self.root / "output").exists())

    def test_dry_run_writes_nothing_and_default_still_requires_mask(self):
        self.assertEqual(self.run_stage("run_registration.py", "--dry-run").returncode, 0)
        self.assertFalse((self.root / "output").exists())
        del self.config["mode"]
        result = self.run_stage("run_registration.py")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Global reference is missing", result.stderr)

    def test_ablation_configs_preserve_all_other_parameters(self):
        baseline = read_yaml(ROOT / "configs/experiments/bosphorus_neutrals_occlusions.yaml")
        dataset = read_yaml(ROOT / "configs/datasets/bosphorus.yaml")
        self.assertEqual(compile_experiment(baseline, dataset)["configs"]["registration"]["mode"], "all")
        for suffix, mode in (("gallery_only_registration", "gallery_only"), ("no_registration", "none")):
            ablation = read_yaml(ROOT / f"configs/experiments/bosphorus_neutrals_occlusions_{suffix}.yaml")
            self.assertEqual(compile_experiment(ablation, dataset)["configs"]["registration"]["mode"], mode)
            comparable = copy.deepcopy(ablation)
            comparable["id"] = baseline["id"]
            comparable["registration"].pop("mode")
            comparable["registration"].pop("reuse_gallery_from", None)
            comparable["pipeline"] = baseline["pipeline"]
            self.assertEqual(comparable, baseline)
            invalid = copy.deepcopy(ablation)
            invalid["registration"]["mode"] = "typo"
            with self.assertRaises(ConfigError):
                compile_experiment(invalid, dataset)

    def test_matching_freezes_only_gallery_descriptors(self):
        local, frozen = self.root / "features", self.root / "frozen-features"
        for name in self.names:
            descriptor = local / "iss/descriptors/bs000" / (Path(name).stem + "-desc.pcd")
            descriptor.parent.mkdir(parents=True, exist_ok=True)
            descriptor.write_text("local descriptor")
        original = frozen / "iss/descriptors/bs000/bs000_N_N_0-desc.pcd"
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text("baseline descriptor")
        settings = {"gallery": {"type": "N", "expression": "N", "sample": 0},
                    "probes": {"categories": {"N": {"type": "N", "sample": 1}, "EYE": {"type": "O"}}}}
        gallery, probes = collect_variant("iss", local, settings, frozen)
        self.assertEqual(gallery[0]["path"], str(original.resolve()))
        self.assertTrue(all(Path(record["path"]).is_relative_to(local) for record in probes))
        original.unlink()
        with self.assertRaisesRegex(ValueError, "Frozen gallery descriptor is missing"):
            collect_variant("iss", local, settings, frozen)


if __name__ == "__main__":
    unittest.main()
