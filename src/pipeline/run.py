#!/usr/bin/env python3
"""Run an entire experiment, or an individual stage, from one YAML context."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import ConfigError, compile_experiment, read_yaml

ROOT = Path(__file__).resolve().parents[2]
STAGES = ("preprocessing", "reference_mask", "registration", "landmarks", "crop", "keypoints", "feature_extraction", "matching", "classification", "evaluation")
RUNNERS = {
    "preprocessing": "src/preprocessing/preprocess.py",
    "reference_mask": "src/registration/bosphorus_reference_mask.py",
    "registration": "src/registration/run_registration.py",
    "landmarks": "src/registration/transform_landmarks.py",
    "crop": "src/crop/run_crop.py",
    "keypoints": "src/keypoints/run_keypoints.py",
    "feature_extraction": "src/feature_extraction/run_feature_extraction.py",
    "matching": "src/matching/run_matching.py",
    "classification": "src/classification/run_classification.py",
    "evaluation": "src/evaluation/run_evaluation.py",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute configuration-defined 3D face-recognition experiments.")
    parser.add_argument("--experiment", required=True, help="Experiment filename/id in configs/experiments, without .yaml")
    parser.add_argument("--stage", action="append", choices=STAGES, help="Run only this stage; repeat to select multiple stages")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show the resolved run plan without writing files")
    parser.add_argument("--limit", type=int, help="Forward a cloud limit to cloud-processing stages")
    parser.add_argument("--overwrite", action="store_true", help="Forward overwrite authorization to selected stages")
    parser.add_argument("--print-config", action="store_true", help="Print the fully resolved configuration as JSON")
    return parser.parse_args()


def stage_command(stage: str, root: Path, config_path: Path, args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(root / RUNNERS[stage]), "--config", str(config_path), "--project-root", str(root)]
    # Recognition stages must receive a coherent descriptor population. A cloud
    # limit is useful for upstream smoke tests but would silently change that
    # population, so it is intentionally not forwarded to them.
    if args.limit is not None and stage not in {"reference_mask", "landmarks", "matching", "classification", "evaluation"}:
        command += ["--limit", str(args.limit)]
    if args.overwrite:
        command.append("--overwrite")
    return command


def stage_failures(stage: str, root: Path, resolved: dict) -> list[dict[str, str]]:
    """Read a completed stage manifest into one pipeline-level failure list."""
    stage_config = resolved["configs"]["registration"] if stage in {"reference_mask", "registration", "landmarks"} else resolved["configs"][stage]
    output_root = root / stage_config["output"]["root"]
    manifest = output_root / "reference_mask" / "alignment_manifest.csv" if stage == "reference_mask" else output_root / "manifest.csv"
    if not manifest.is_file():
        return []
    with manifest.open(newline="", encoding="utf-8") as handle:
        return [
            {"stage": stage, "cloud": row.get("source", "<unknown>"), "message": row.get("message", "")}
            for row in csv.DictReader(handle)
            if row.get("status") == "failed"
        ]


def print_failure_summary(failures: list[dict[str, str]]) -> None:
    if not failures:
        return
    print("\nResumo de falhas:")
    for failure in failures:
        message = failure["message"] or "sem diagnóstico fornecido pela etapa"
        print(f"- [{failure['stage']}] {failure['cloud']}: {message}")


def main() -> int:
    args = arguments()
    try:
        if args.limit is not None and args.limit < 1:
            raise ConfigError("--limit must be positive.")
        experiment_path = ROOT / "configs" / "experiments" / f"{args.experiment.removesuffix('.yaml')}.yaml"
        experiment = read_yaml(experiment_path)
        dataset_id = experiment.get("dataset")
        if not isinstance(dataset_id, str):
            raise ConfigError("experiment.dataset must name a file under configs/datasets.")
        dataset_path = ROOT / "configs" / "datasets" / f"{dataset_id}.yaml"
        resolved = compile_experiment(experiment, read_yaml(dataset_path))
        wanted = args.stage or resolved["stages"]
        invalid = [stage for stage in wanted if stage not in resolved["stages"]]
        if invalid:
            raise ConfigError("Stage(s) not enabled by this experiment: " + ", ".join(invalid))
        if args.print_config:
            print(json.dumps(resolved, indent=2, ensure_ascii=False))
        print(f"Experiment: {experiment['id']}")
        print(f"Dataset: {resolved['dataset']['id']}")
        print("Stages: " + ", ".join(wanted))
        if args.dry_run:
            for stage in wanted:
                print(f"[{stage}] input/output context prepared; runner: {RUNNERS[stage]}")
            print("Dry run completed; no files were written.")
            return 0
        config_dir = ROOT / resolved["paths"]["root"] / "pipeline"
        config_dir.mkdir(parents=True, exist_ok=True)
        context = {"experiment_config": str(experiment_path.relative_to(ROOT)), "dataset_config": str(dataset_path.relative_to(ROOT)), "source_sha256": hashlib.sha256(experiment_path.read_bytes() + dataset_path.read_bytes()).hexdigest(), "created_at_utc": datetime.now(timezone.utc).isoformat(), "resolved": resolved}
        (config_dir / "resolved-context.json").write_text(json.dumps(context, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        results, failures = [], []
        for stage in wanted:
            stage_config = resolved["configs"]["registration"] if stage in {"reference_mask", "registration", "landmarks"} else resolved["configs"][stage]
            config_path = config_dir / f"{stage}.json"
            config_path.write_text(json.dumps(stage_config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            command = stage_command(stage, ROOT, config_path, args)
            print("\n[run] " + " ".join(command))
            completed = subprocess.run(command, cwd=ROOT)
            results.append({"stage": stage, "return_code": completed.returncode})
            current_failures = stage_failures(stage, ROOT, resolved)
            if completed.returncode and not current_failures:
                current_failures = [{"stage": stage, "cloud": "<stage>", "message": f"runner exited with code {completed.returncode}; no per-cloud manifest was produced"}]
            failures.extend(current_failures)
            if completed.returncode:
                break
        print_failure_summary(failures)
        (config_dir / "pipeline-run.json").write_text(json.dumps({"experiment": experiment["id"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "stages": results, "failures": failures}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0 if results and results[-1]["return_code"] == 0 and len(results) == len(wanted) else 1
    except ConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
