#!/usr/bin/env python3
"""Extract validated FPFH descriptors from YAML-compiled experiment context."""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Task:
    index: int
    variant: str
    cloud: Path
    keypoints: Path
    output: Path
    relative: Path
    expected_points: int


def project_path(value: str, root: Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else root / candidate


def pcd_point_count(path: Path) -> int:
    """Read the PCD header only, avoiding an expensive duplicate cloud load."""
    header: dict[str, list[str]] = {}
    with path.open("rb") as handle:
        for raw_line in handle:
            try:
                line = raw_line.decode("ascii").strip()
            except UnicodeDecodeError as error:
                raise ValueError(f"Invalid ASCII PCD header: {path}") from error
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            header[fields[0].upper()] = fields[1:]
            if fields[0].upper() == "DATA":
                break
    if "POINTS" in header:
        return int(header["POINTS"][0])
    if "WIDTH" in header and "HEIGHT" in header:
        return int(header["WIDTH"][0]) * int(header["HEIGHT"][0])
    raise ValueError(f"PCD has no POINTS or WIDTH/HEIGHT field: {path}")


def load_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid feature-extraction configuration: {error}") from error


def collect_tasks(config: dict[str, Any], root: Path, limit: int | None) -> tuple[list[Task], Path, Path]:
    dataset, output = config["dataset"], config["output"]
    clouds_root = project_path(dataset["cloud_root"], root)
    keypoints_root = project_path(dataset["keypoints_root"], root)
    output_root = project_path(output["root"], root)
    if not clouds_root.is_dir():
        raise ValueError(f"Cropped-cloud directory does not exist: {clouds_root}")
    if not keypoints_root.is_dir():
        raise ValueError(f"Keypoint directory does not exist: {keypoints_root}")
    pattern = re.compile(dataset["include_filename_regex"])
    clouds = [item for item in sorted(clouds_root.glob(dataset["include_glob"])) if item.is_file() and pattern.fullmatch(item.name)]
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be positive")
        clouds = clouds[:limit]
    if not clouds:
        raise ValueError("No clouds matched the configured selection")
    variants = config["variants"]
    if not isinstance(variants, dict) or not variants:
        raise ValueError("At least one feature-extraction variant is required")
    tasks: list[Task] = []
    for variant, settings in variants.items():
        family, method = settings["keypoint_family"], settings["keypoint_method"]
        for cloud in clouds:
            relative = cloud.relative_to(clouds_root)
            keypoints = keypoints_root / family / method / relative
            if not keypoints.is_file():
                raise ValueError(f"Missing keypoints for {variant}: {keypoints}")
            expected = pcd_point_count(keypoints)
            if expected < 1:
                raise ValueError(f"Keypoint file has no points for {variant}: {keypoints}")
            tasks.append(Task(len(tasks) + 1, variant, cloud, keypoints, output_root / variant / "descriptors" / relative.with_name(relative.stem + "-desc.pcd"), relative, expected))
    return tasks, output_root, project_path(config["commands"]["feature_extraction"], root)


def task_result(task: Task, config: dict[str, Any], executable: Path, output_root: Path, overwrite: bool) -> dict[str, Any]:
    started = time.perf_counter()
    if task.output.exists() and not overwrite:
        return {"variant": task.variant, "source": str(task.relative), "keypoints": str(task.keypoints), "output": str(task.output), "status": "skipped", "seconds": 0.0, "message": "output already exists"}
    settings = config["variants"][task.variant]
    temporary = task.output.with_name(task.output.stem + ".tmp.pcd")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.unlink(missing_ok=True)
    command = [str(executable), "-cloud", str(task.cloud), "-normal", str(settings["normal_radius"]), "-keypoints", f"from_file,{task.keypoints}", "-features", f"fpfh,{settings['feature_radius']}", "-output", str(temporary)]
    completed = subprocess.run(command, text=True, capture_output=True)
    seconds = round(time.perf_counter() - started, 6)
    if completed.returncode == 0 and temporary.is_file() and temporary.stat().st_size:
        try:
            descriptor_points = pcd_point_count(temporary)
            if descriptor_points != task.expected_points:
                raise ValueError(f"descriptor count {descriptor_points}; expected {task.expected_points}")
            temporary.replace(task.output)
            return {"variant": task.variant, "source": str(task.relative), "keypoints": str(task.keypoints), "output": str(task.output), "status": "processed", "seconds": seconds, "message": ""}
        except (OSError, ValueError) as error:
            diagnostic = str(error)
    else:
        diagnostic = " | ".join(part for part in ((completed.stdout or "").strip(), (completed.stderr or "").strip()) if part) or f"extractor exit code {completed.returncode}"
    temporary.unlink(missing_ok=True)
    error_log = output_root / "errors" / task.variant / task.relative.with_suffix(".log")
    error_log.parent.mkdir(parents=True, exist_ok=True)
    error_log.write_text("Command:\n" + " ".join(command) + f"\n\nExit code: {completed.returncode}\n\nSTDOUT:\n{completed.stdout or '(empty)'}\n\nSTDERR:\n{completed.stderr or '(empty)'}\n\nValidation:\n{diagnostic}\n", encoding="utf-8")
    return {"variant": task.variant, "source": str(task.relative), "keypoints": str(task.keypoints), "output": str(task.output), "status": "failed", "seconds": seconds, "message": f"{diagnostic.replace(chr(10), ' | ')}; log={error_log}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract FPFH descriptors for config-selected keypoint sets.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        config, root = load_config(args.config), args.project_root.resolve()
        tasks, output_root, executable = collect_tasks(config, root, args.limit)
        workers = args.workers if args.workers is not None else int(config["execution"].get("workers", 1))
        if workers < 1:
            raise ValueError("workers must be positive")
        print(f"Experiment: {config['name']}\nTasks: {len(tasks)}\nVariants: {len(config['variants'])}\nOutput: {output_root}")
        if args.dry_run:
            for task in tasks[:10]:
                print(f"  {task.variant}: {task.relative}")
            if len(tasks) > 10:
                print(f"  ... and {len(tasks) - 10} more")
            print("Dry run completed; no files were written.")
            return 0
        if not executable.is_file():
            raise ValueError(f"Feature-extraction executable not found: {executable}. Build src/feature_extraction first.")
        output_root.mkdir(parents=True, exist_ok=True)
        overwrite = args.overwrite or bool(config["output"].get("overwrite", False))
        records: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(workers, len(tasks))) as executor:
            futures = [executor.submit(task_result, task, config, executable, output_root, overwrite) for task in tasks]
            for index, future in enumerate(as_completed(futures), 1):
                record = future.result()
                records.append(record)
                print(f"[Feature extraction {index}/{len(tasks)}] [{record['status']}] {record['variant']}/{record['source']}")
        records.sort(key=lambda item: (item["variant"], item["source"]))
        with (output_root / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["variant", "source", "keypoints", "output", "status", "seconds", "message"])
            writer.writeheader(); writer.writerows(records)
        failed = [record for record in records if record["status"] == "failed"]
        (output_root / "run.json").write_text(json.dumps({"experiment": config["name"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "tasks": len(records), "processed": sum(record["status"] == "processed" for record in records), "skipped": sum(record["status"] == "skipped" for record in records), "failed": len(failed), "variants": config["variants"]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 1 if failed else 0
    except (KeyError, OSError, ValueError, json.JSONDecodeError, re.error) as error:
        print(f"Feature-extraction configuration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
