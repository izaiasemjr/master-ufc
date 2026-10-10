#!/usr/bin/env python3
"""Preprocess point clouds with PCL from a declarative experiment config.

The module intentionally depends only on the Python standard library.  PCL
executables must be installed separately and available on PATH (or declared
with absolute paths in the configuration).
"""

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


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(ValueError):
    """Raised when an experiment config cannot be used safely."""


@dataclass(frozen=True)
class Job:
    source: Path
    destination: Path
    relative_path: Path


def load_config(config_path: Path) -> dict[str, Any]:
    try:
        with config_path.open(encoding="utf-8") as handle:
            config = json.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {config_path}: {exc}") from exc

    for key in ("name", "dataset", "output", "commands", "processing", "execution"):
        if key not in config:
            raise ConfigError(f"Missing required key: {key}")
    return config


def project_path(value: str, project_root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def validate_config(config: dict[str, Any], project_root: Path) -> tuple[Path, Path, re.Pattern[str]]:
    dataset = config["dataset"]
    output = config["output"]
    processing = config["processing"]
    commands = config["commands"]

    for key in ("name", "input_root", "include_glob", "include_filename_regex"):
        if key == "name":
            value = config[key]
        else:
            value = dataset.get(key)
        if not isinstance(value, str) or not value:
            raise ConfigError(f"'{key}' must be a non-empty string")

    if not isinstance(output.get("root"), str) or not output["root"]:
        raise ConfigError("'output.root' must be a non-empty directory path")
    input_root = project_path(dataset["input_root"], project_root)
    output_root = project_path(output["root"], project_root)
    if not input_root.is_dir():
        raise ConfigError(f"Input directory does not exist: {input_root}")
    try:
        filename_pattern = re.compile(dataset["include_filename_regex"])
    except re.error as exc:
        raise ConfigError(f"Invalid dataset.include_filename_regex: {exc}") from exc

    try:
        radius = float(processing["outlier_removal"]["radius"])
        min_points = int(processing["outlier_removal"]["min_points"])
        leaf_size = processing["voxel_grid"]["leaf_size"]
        leaf_values = [float(value) for value in leaf_size]
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError("Invalid processing parameters") from exc
    if radius <= 0 or min_points < 1 or len(leaf_values) != 3 or any(value <= 0 for value in leaf_values):
        raise ConfigError("Outlier radius/min_points and all three voxel leaf sizes must be positive")

    workers = config["execution"].get("workers", 1)
    if not isinstance(workers, int) or workers < 1:
        raise ConfigError("execution.workers must be a positive integer")
    for name in ("outlier_removal", "voxel_grid"):
        if not isinstance(commands.get(name), str) or not commands[name]:
            raise ConfigError(f"commands.{name} must be a non-empty command")

    if input_root.resolve() == output_root.resolve():
        raise ConfigError("Input and output directories must be different")
    return input_root, output_root, filename_pattern


def discover_jobs(config: dict[str, Any], input_root: Path, output_root: Path, pattern: re.Pattern[str]) -> list[Job]:
    glob_pattern = config["dataset"]["include_glob"]
    jobs: list[Job] = []
    for source in sorted(input_root.glob(glob_pattern)):
        if source.is_file() and pattern.fullmatch(source.name):
            relative_path = source.relative_to(input_root)
            jobs.append(Job(source, output_root / "clouds" / relative_path, relative_path))
    return jobs


def command_available(command: str) -> bool:
    return Path(command).is_file() if Path(command).is_absolute() else shutil.which(command) is not None


def run_job(job: Job, config: dict[str, Any], overwrite: bool) -> dict[str, Any]:
    started = time.perf_counter()
    if job.destination.exists() and not overwrite:
        return {"source": str(job.relative_path), "output": str(job.destination), "status": "skipped", "seconds": 0.0, "message": "output already exists"}

    job.destination.parent.mkdir(parents=True, exist_ok=True)
    outlier_temporary = job.destination.with_name(job.destination.stem + ".outlier-tmp.pcd")
    output_temporary = job.destination.with_name(job.destination.stem + ".preprocess-tmp.pcd")
    outlier_temporary.unlink(missing_ok=True)
    output_temporary.unlink(missing_ok=True)
    parameters = config["processing"]
    outlier = parameters["outlier_removal"]
    leaf = parameters["voxel_grid"]["leaf_size"]
    commands = config["commands"]
    try:
        subprocess.run(
            [commands["outlier_removal"], str(job.source), str(outlier_temporary), "-radius", str(outlier["radius"]), "-min_pts", str(outlier["min_points"]), "-negative", "0"],
            check=True,
            text=True,
            capture_output=True,
        )
        subprocess.run(
            [commands["voxel_grid"], str(outlier_temporary), str(output_temporary), "-leaf", ",".join(str(value) for value in leaf)],
            check=True,
            text=True,
            capture_output=True,
        )
        output_temporary.replace(job.destination)
        return {"source": str(job.relative_path), "output": str(job.destination), "status": "processed", "seconds": round(time.perf_counter() - started, 6), "message": ""}
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip().replace("\n", " ")
        return {"source": str(job.relative_path), "output": str(job.destination), "status": "failed", "seconds": round(time.perf_counter() - started, 6), "message": message}
    except OSError as exc:
        return {"source": str(job.relative_path), "output": str(job.destination), "status": "failed", "seconds": round(time.perf_counter() - started, 6), "message": str(exc)}
    finally:
        outlier_temporary.unlink(missing_ok=True)
        output_temporary.unlink(missing_ok=True)


def write_metadata(output_root: Path, config_path: Path, config: dict[str, Any], records: list[dict[str, Any]], elapsed: float) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "output", "status", "seconds", "message"])
        writer.writeheader()
        writer.writerows(records)
    counts = {status: sum(record["status"] == status for record in records) for status in ("processed", "skipped", "failed")}
    metadata = {
        "experiment": config["name"],
        "config_file": str(config_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 6),
        "summary": {"discovered": len(records), **counts},
        "parameters": config["processing"],
    }
    (output_root / "run.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply configurable PCL preprocessing to point clouds.")
    parser.add_argument("--config", required=True, type=Path, help="JSON experiment configuration")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT, help="Base used to resolve relative config paths")
    parser.add_argument("--dry-run", action="store_true", help="Validate and list work without calling PCL or writing files")
    parser.add_argument("--limit", type=int, help="Process only the first N selected clouds (useful for smoke tests)")
    parser.add_argument("--workers", type=int, help="Override execution.workers")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output clouds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config_path = args.config.resolve()
        project_root = args.project_root.resolve()
        config = load_config(config_path)
        input_root, output_root, pattern = validate_config(config, project_root)
        jobs = discover_jobs(config, input_root, output_root, pattern)
        if args.limit is not None:
            if args.limit < 1:
                raise ConfigError("--limit must be positive")
            jobs = jobs[:args.limit]
        if not jobs:
            raise ConfigError("No input clouds matched the configured selection")
        if args.workers is not None:
            if args.workers < 1:
                raise ConfigError("--workers must be positive")
            config["execution"]["workers"] = args.workers

        print(f"Experiment: {config['name']}")
        print(f"Selected clouds: {len(jobs)}")
        print(f"Input: {input_root}")
        print(f"Output: {output_root}")
        if args.dry_run:
            for job in jobs[:10]:
                print(f"  {job.relative_path}")
            if len(jobs) > 10:
                print(f"  ... and {len(jobs) - 10} more")
            print("Dry run completed; no files were written.")
            return 0

        missing = [name for name in config["commands"].values() if not command_available(name)]
        if missing:
            raise ConfigError("PCL command(s) not available on PATH: " + ", ".join(missing))
        started = time.perf_counter()
        overwrite = args.overwrite or bool(config["output"].get("overwrite", False))
        records: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=config["execution"]["workers"]) as executor:
            futures = [executor.submit(run_job, job, config, overwrite) for job in jobs]
            for future in as_completed(futures):
                record = future.result()
                records.append(record)
                print(f"[{record['status']}] {record['source']}")
                if record["status"] == "failed" and config["execution"].get("fail_fast", False):
                    for pending in futures:
                        pending.cancel()
                    break
        records.sort(key=lambda record: record["source"])
        write_metadata(output_root, config_path, config, records, time.perf_counter() - started)
        failed = sum(record["status"] == "failed" for record in records)
        print(f"Completed: processed={sum(r['status'] == 'processed' for r in records)}, skipped={sum(r['status'] == 'skipped' for r in records)}, failed={failed}")
        return 1 if failed else 0
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
