#!/usr/bin/env python3
"""Run CP-ICP for every selected cloud in a configuration-defined dataset."""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def path(value: str, root: Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else root / candidate


def report_progress(index: int, total: int, status: str, cloud: Path) -> None:
    completed = 100 * index / total
    remaining = 100 * (total - index) / total
    print(f"[CP-ICP {index}/{total} | {completed:6.2f}% concluido | {remaining:6.2f}% restante] [{status}] {cloud}")


def failure_details(command: list[str], result: subprocess.CompletedProcess[str], log_path: Path) -> str:
    """Persist every diagnostic emitted by CP-ICP for a failed cloud."""
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "Command:\n"
        + " ".join(command)
        + f"\n\nExit code: {result.returncode}\n\nSTDOUT:\n{stdout or '(empty)'}\n\nSTDERR:\n{stderr or '(empty)'}\n",
        encoding="utf-8",
    )
    fragments = [f"exit_code={result.returncode}", f"log={log_path}"]
    if stdout:
        fragments.append("stdout=" + stdout.replace("\n", " | "))
    if stderr:
        fragments.append("stderr=" + stderr.replace("\n", " | "))
    return "; ".join(fragments)


def main() -> int:
    parser = argparse.ArgumentParser(description="Register clouds with CP-ICP.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--project-root", default=ROOT, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        root = args.project_root.resolve()
        dataset, output, processing = config["dataset"], config["output"], config["processing"]
        cloud_root, output_root = path(dataset["input_root"], root), path(output["root"], root)
        reference, executable = path(config["reference"]["global_cloud"], root), path(config["commands"]["cp_icp"], root)
        if not cloud_root.is_dir() or not reference.is_file():
            raise ValueError("Input clouds or global reference are missing; run preprocessing and provide the reference mask first.")
        pattern = re.compile(dataset["include_filename_regex"])
        sources = [item for item in sorted(cloud_root.glob(dataset["include_glob"])) if item.is_file() and pattern.fullmatch(item.name)]
        if args.limit is not None:
            sources = sources[:args.limit]
        if not sources:
            raise ValueError("No clouds matched the dataset selection.")
        print(f"Experiment: {config['name']}\nSelected clouds: {len(sources)}\nOutput: {output_root}")
        if args.dry_run:
            for source in sources[:10]: print("  " + str(source.relative_to(cloud_root)))
            print("Dry run completed; no files were written.")
            return 0
        if not executable.is_file():
            raise ValueError(f"CP-ICP executable not found: {executable}. Build src/registration/cp_icp first.")
        output_root.mkdir(parents=True, exist_ok=True)
        metrics = output_root / "metrics.csv"
        if not metrics.exists(): metrics.write_text("person source algorithm penalty TP FN FP TN RMSE_global lambda1 lambda2 time\n", encoding="utf-8")
        records, failed = [], False
        for index, source in enumerate(sources, 1):
            relative, person, suffix = source.relative_to(cloud_root), source.parent.name, source.stem.split("_", 1)[1]
            registration = output_root / "registrations" / relative
            if registration.exists() and not (args.overwrite or output.get("overwrite", False)):
                records.append([str(relative), "skipped", "0", "output already exists"])
                report_progress(index, len(sources), "skipped", relative)
                continue
            target = cloud_root / person / f"{person}_{dataset['target_suffix']}.pcd"
            if not target.is_file():
                records.append([str(relative), "failed", "0", f"missing target: {target.name}"])
                report_progress(index, len(sources), "failed", relative)
                failed = True
                continue
            occlusion = output_root / "occlusions" / relative
            removed = output_root / "occlusions_removed" / relative
            restored_inverse = output_root / "occlusions_restored_inverse" / relative
            restored = output_root / "occlusions_restored" / relative
            matrix = output_root / "transforms" / relative.with_suffix(".mat")
            train_test = output_root / "data_train_test" / person / source.stem.rsplit("_", 1)[0]
            for destination in (registration, occlusion, removed, restored_inverse, restored, matrix, train_test): destination.parent.mkdir(parents=True, exist_ok=True)
            command = [str(executable), "-path", str(cloud_root) + "/", "-person", person, "-source", suffix, "-target", dataset["target_suffix"], "-target_special", str(reference), "-field", ",".join(processing["fields"]), "-k", str(processing["partitions"]), "-icp", f"{processing['icp']['transformation_epsilon']},{processing['icp']['max_iterations']}", "-th", str(processing["occlusion"]["threshold"]), "-th_rest", str(processing["occlusion"]["restoration_threshold"]), "-penality", str(processing["occlusion"]["penalty"]), "-occlusion", "1" if processing["occlusion"]["enabled"] else "0", "-debug", "1" if processing["debug"] else "0", "-GT", "null", "-outputs", ",".join(map(str, [registration, occlusion, metrics, matrix, removed, restored_inverse, restored, train_test]))]
            started = time.perf_counter(); result = subprocess.run(command, text=True, capture_output=True); seconds = round(time.perf_counter() - started, 6)
            if result.returncode == 0:
                status, message = "processed", ""
            else:
                error_log = output_root / "errors" / relative.with_suffix(".log")
                status, message = "failed", failure_details(command, result, error_log)
            records.append([str(relative), status, seconds, message]); failed |= status == "failed"
            report_progress(index, len(sources), status, relative)
            if failed and config["execution"].get("fail_fast", False): break
        with (output_root / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle); writer.writerow(["source", "status", "seconds", "message"]); writer.writerows(records)
        (output_root / "run.json").write_text(json.dumps({"experiment": config["name"], "config": str(args.config), "records": len(records), "failed": sum(row[1] == "failed" for row in records)}, indent=2) + "\n", encoding="utf-8")
        return 1 if failed else 0
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"Configuration error: {error}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
