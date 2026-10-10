#!/usr/bin/env python3
"""Crop registered point clouds around a configurable landmark."""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def project_path(value: str, project_root: Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else project_root / candidate


def report_progress(index: int, total: int, status: str, cloud: Path) -> None:
    completed = 100 * index / total
    remaining = 100 * (total - index) / total
    print(f"[Crop {index}/{total} | {completed:6.2f}% concluido | {remaining:6.2f}% restante] [{status}] {cloud}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Crop clouds around a configured landmark.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--project-root", default=PROJECT_ROOT, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        root = args.project_root.resolve()
        dataset, output, processing = config["dataset"], config["output"], config["processing"]
        cloud_root = project_path(dataset["cloud_root"], root)
        landmarks_root = project_path(dataset["landmarks_root"], root)
        output_root = project_path(output["root"], root)
        executable = project_path(config["commands"]["crop"], root)
        if not cloud_root.is_dir() or not landmarks_root.is_dir():
            raise ValueError("Registered clouds or transformed landmarks are missing.")
        pattern = re.compile(dataset["include_filename_regex"])
        clouds = [cloud for cloud in sorted(cloud_root.glob(dataset["include_glob"])) if cloud.is_file() and pattern.fullmatch(cloud.name)]
        if args.limit is not None:
            if args.limit < 1: raise ValueError("--limit must be positive")
            clouds = clouds[:args.limit]
        if not clouds: raise ValueError("No clouds matched the configured selection.")
        landmark_index, radius, offset = int(processing["landmark_index"]), float(processing["crop_radius"]), processing["offset"]
        if landmark_index < 0 or radius <= 0 or len(offset) != 3: raise ValueError("Invalid landmark index, crop radius, or offset.")
        print(f"Experiment: {config['name']}\nClouds: {len(clouds)}\nRadius: {radius}\nOutput: {output_root}")
        if args.dry_run:
            for cloud in clouds[:10]: print("  " + str(cloud.relative_to(cloud_root)))
            if len(clouds) > 10: print(f"  ... and {len(clouds) - 10} more")
            print("Dry run completed; no files were written.")
            return 0
        if not executable.is_file(): raise ValueError(f"Crop executable not found: {executable}. Build src/crop first.")
        overwrite = args.overwrite or bool(output.get("overwrite", False))
        records, failed = [], False
        for index, cloud in enumerate(clouds, 1):
            relative = cloud.relative_to(cloud_root)
            landmark = landmarks_root / relative
            destination = output_root / "clouds" / relative
            if destination.exists() and not overwrite:
                records.append([str(relative), "skipped", 0, "output already exists"]); report_progress(index, len(clouds), "skipped", relative); continue
            if not landmark.is_file():
                records.append([str(relative), "failed", 0, "missing transformed landmark"]); report_progress(index, len(clouds), "failed", relative); failed = True
                if config["execution"].get("fail_fast", False): break
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.stem + ".tmp.pcd")
            temporary.unlink(missing_ok=True)
            command = [str(executable), "-cloud", str(cloud), "-keypoints", f"{landmark},{landmark_index}", "-crop_radius", str(radius), "-output", str(temporary), "-offset", ",".join(str(value) for value in offset)]
            started = time.perf_counter(); result = subprocess.run(command, text=True, capture_output=True); seconds = round(time.perf_counter() - started, 6)
            if result.returncode == 0 and temporary.is_file():
                temporary.replace(destination); status, message = "processed", ""
            else:
                temporary.unlink(missing_ok=True); status, message = "failed", (result.stderr or result.stdout or "Crop did not create an output file").strip().replace("\n", " "); failed = True
            records.append([str(relative), status, seconds, message]); report_progress(index, len(clouds), status, relative)
            if failed and config["execution"].get("fail_fast", False): break
        output_root.mkdir(parents=True, exist_ok=True)
        with (output_root / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle); writer.writerow(["source", "status", "seconds", "message"]); writer.writerows(records)
        metadata = {"experiment": config["name"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "selected_clouds": len(clouds), "processed": sum(row[1] == "processed" for row in records), "failed": sum(row[1] == "failed" for row in records), "parameters": processing}
        (output_root / "run.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 1 if failed else 0
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"Crop configuration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
