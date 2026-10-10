#!/usr/bin/env python3
"""Apply CP-ICP matrices to the landmark clouds selected by a registration config."""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def resolve(value, root):
    value = Path(value); return value if value.is_absolute() else root / value

def main():
    parser = argparse.ArgumentParser(description="Transform landmark PCDs with registration matrices.")
    parser.add_argument("--config", required=True, type=Path); parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true"); parser.add_argument("--overwrite", action="store_true"); args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8")); root = args.project_root.resolve(); dataset = config["dataset"]
        matrices = resolve(config["output"]["root"], root) / "transforms"; landmarks = resolve(dataset["landmarks_root"], root); output = resolve(config["output"]["root"], root) / "landmarks_transformed"; executable = config["commands"]["transform_landmarks"]
        if not matrices.is_dir() or not landmarks.is_dir(): raise ValueError("Registration matrices or input landmarks are missing.")
        items = list(matrices.rglob("*.mat")); print(f"Matrices: {len(items)}\nOutput: {output}")
        if args.dry_run: return 0
        if shutil.which(executable) is None: raise ValueError(f"PCL command not on PATH: {executable}")
        failed = 0
        for matrix in items:
            relative = matrix.relative_to(matrices).with_suffix(".pcd"); source, destination = landmarks / relative, output / relative
            if destination.exists() and not (args.overwrite or config["output"].get("overwrite", False)): continue
            if not source.is_file(): print(f"[failed] missing landmark: {relative}"); failed += 1; continue
            values = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", matrix.read_text(encoding="utf-8"))
            if len(values) != 16: print(f"[failed] invalid 4x4 matrix: {matrix}"); failed += 1; continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run([executable, str(source), str(destination), "-matrix", ",".join(values)], text=True, capture_output=True)
            failed += result.returncode != 0; print(f"[{'processed' if result.returncode == 0 else 'failed'}] {relative}")
        return 1 if failed else 0
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"Configuration error: {error}", file=sys.stderr); return 2
if __name__ == "__main__": raise SystemExit(main())
