#!/usr/bin/env python3
"""Generate radial-grid, SIFT, and ISS keypoints from one JSON experiment config."""
from __future__ import annotations
import argparse, csv, json, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def resolve(value, root):
    value = Path(value); return value if value.is_absolute() else root / value

def main():
    parser = argparse.ArgumentParser(description="Generate configurable facial keypoints.")
    parser.add_argument("--config", required=True, type=Path); parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true"); parser.add_argument("--limit", type=int); parser.add_argument("--overwrite", action="store_true"); args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8")); root = args.project_root.resolve(); dataset, output = config["dataset"], config["output"]
        clouds, landmarks, output_root = resolve(dataset["cloud_root"], root), resolve(dataset["landmarks_root"], root), resolve(output["root"], root)
        if not clouds.is_dir() or not landmarks.is_dir(): raise ValueError("Registered clouds or transformed landmarks are missing.")
        pattern = re.compile(dataset["include_filename_regex"]); sources = [item for item in sorted(clouds.glob(dataset["include_glob"])) if item.is_file() and pattern.fullmatch(item.name)]
        if args.limit is not None: sources = sources[:args.limit]
        methods = [("grids", "radial_grid", values) for values in config["radial_grids"]] + [("detectors", "detectors", values) for values in config["detectors"]]
        print(f"Experiment: {config['name']}\nClouds: {len(sources)}\nMethods: {len(methods)}")
        if args.dry_run: print(f"Jobs: {len(sources) * len(methods)}"); return 0
        executables = {name: resolve(value, root) for name, value in config["commands"].items()}
        missing = [str(item) for item in executables.values() if not item.is_file()]
        if missing: raise ValueError("Executable(s) not found; build the C++ projects first: " + ", ".join(missing))
        records, failed, total, current = [], False, len(sources) * len(methods), 0
        for family, command_name, raw_values in methods:
            # YAML preserves numeric parameters as numbers.  Labels and the
            # C++ comma-separated option both require string values.
            values = [str(value) for value in raw_values]
            label = "_".join(values); timing_dir = output_root / "timings" / family / label; timing_dir.mkdir(parents=True, exist_ok=True)
            for source in sources:
                current += 1; relative = source.relative_to(clouds); destination = output_root / family / label / relative; landmark = landmarks / relative
                if destination.exists() and not (args.overwrite or output.get("overwrite", False)): records.append([str(relative), family, label, "skipped", 0, ""]); continue
                if not landmark.is_file(): records.append([str(relative), family, label, "failed", 0, "missing transformed landmark"]); failed = True; continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                command = [str(executables[command_name]), "-cloud", str(source), "-output", str(destination), "-debug", "0"]
                command += ["-grid", ",".join(values), "-keypoints", str(landmark)] if family == "grids" else ["-params", ",".join(values)]
                started = time.perf_counter(); result = subprocess.run(command, cwd=timing_dir, text=True, capture_output=True); seconds = round(time.perf_counter() - started, 6)
                status, message = ("processed", "") if result.returncode == 0 else ("failed", (result.stderr or result.stdout).strip().replace("\n", " "))
                records.append([str(relative), family, label, status, seconds, message]); failed |= status == "failed"; print(f"[{current}/{total}] [{status}] {family}/{label}/{relative}")
                if failed and config["execution"].get("fail_fast", False): break
            if failed and config["execution"].get("fail_fast", False): break
        output_root.mkdir(parents=True, exist_ok=True)
        with (output_root / "manifest.csv").open("w", newline="", encoding="utf-8") as handle: writer = csv.writer(handle); writer.writerow(["source", "family", "method", "status", "seconds", "message"]); writer.writerows(records)
        (output_root / "run.json").write_text(json.dumps({"experiment": config["name"], "jobs": len(records), "failed": sum(row[3] == "failed" for row in records)}, indent=2) + "\n", encoding="utf-8")
        return 1 if failed else 0
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"Configuration error: {error}", file=sys.stderr); return 2
if __name__ == "__main__": raise SystemExit(main())
