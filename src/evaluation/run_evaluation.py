#!/usr/bin/env python3
"""Publish RR and CMC tables from configuration-defined identification output."""
from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def project_path(value: str, root: Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else root / candidate


def load_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid evaluation configuration: {error}") from error


def atomic_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    try:
        with Path(temporary).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader(); writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def aggregate_categories(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)
        grouped["ALL"].append(row)
        if row["probe_type"] == "O":
            grouped["O_ALL"].append(row)
    return grouped


def optional_count(rule: dict[str, Any], location: str) -> int | None:
    value = rule.get("expected_count")
    if value is None:
        return None
    count = int(value)
    if count < 1:
        raise ValueError(f"{location}.expected_count must be positive when declared")
    return count


def evaluate_variant(path: Path, variant: str, settings: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Prediction file is empty: {path}")
    required = {"k", "category", "probe_type", "true_rank", "correct_rank_1"}
    if not required.issubset(rows[0]):
        raise ValueError(f"Prediction file has invalid columns: {path}")
    k_values = sorted({int(value) for value in settings["k_values"]})
    rank_max = int(settings.get("rank_max", 20))
    if rank_max < 1:
        raise ValueError("evaluation.rank_max must be positive")
    category_rules = settings["probes"]["categories"]
    expected_by_category = {
        name: optional_count(rule, f"matching.probes.categories.{name}") for name, rule in category_rules.items()
    }
    occlusion_counts = [count for name, count in expected_by_category.items() if str(category_rules[name].get("type")) == "O"]
    expected_by_category["O_ALL"] = sum(occlusion_counts) if occlusion_counts and all(count is not None for count in occlusion_counts) else None
    expected_by_category["ALL"] = optional_count(settings["probes"], "matching.probes")
    accuracy_rows: list[dict[str, Any]] = []
    cmc_rows: list[dict[str, Any]] = []
    by_k: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        k_value = int(row["k"])
        if k_value not in k_values:
            raise ValueError(f"Unexpected k={k_value} in {path}")
        by_k[k_value].append(row)
    if set(by_k) != set(k_values):
        raise ValueError(f"Missing one or more configured k values in {path}")
    reference_counts: dict[str, int] | None = None
    for k_value, k_rows in sorted(by_k.items()):
        grouped = aggregate_categories(k_rows)
        for category, expected in expected_by_category.items():
            if expected is not None and len(grouped.get(category, [])) != expected:
                raise ValueError(f"{variant}, k={k_value}, {category}: found {len(grouped.get(category, []))} samples; expected {expected}")
        counts = {category: len(entries) for category, entries in grouped.items()}
        if reference_counts is None:
            reference_counts = counts
        elif counts != reference_counts:
            raise ValueError(f"{variant}, k={k_value}: the probe/category population differs from the other k values")
        for category, entries in sorted(grouped.items()):
            expected = expected_by_category.get(category)
            if expected is not None and len(entries) != expected:
                raise ValueError(f"{variant}, k={k_value}, {category}: found {len(entries)} samples; expected {expected}")
            rank_one = sum(int(row["correct_rank_1"]) for row in entries)
            accuracy_rows.append({"variant": variant, "k": k_value, "category": category, "samples": len(entries), "recognized": rank_one, "accuracy_percent": f"{100.0 * rank_one / len(entries):.6f}"})
            for rank in range(1, rank_max + 1):
                recognized = sum(int(row["true_rank"]) <= rank for row in entries)
                cmc_rows.append({"variant": variant, "k": k_value, "category": category, "rank": rank, "samples": len(entries), "recognized": recognized, "accuracy_percent": f"{100.0 * recognized / len(entries):.6f}"})
    return accuracy_rows, cmc_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Produce accuracy-by-k and CMC tables.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        config, root = load_config(args.config), args.project_root.resolve()
        settings = config["matching"]
        classification_root = project_path(config["input"]["classification_root"], root)
        output_root = project_path(config["output"]["root"], root)
        print(f"Experiment: {config['name']}\nVariants: {len(settings['variants'])}")
        prepared: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}
        for variant in settings["variants"]:
            prepared[variant] = evaluate_variant(classification_root / variant / "predictions.csv", variant, settings)
            print(f"  {variant}: validated")
        if args.dry_run:
            print("Dry run completed; predictions were validated, no files were written.")
            return 0
        manifest: list[dict[str, str]] = []
        for variant, (accuracy, cmc) in prepared.items():
            variant_root = output_root / variant
            accuracy_path, cmc_path = variant_root / "accuracy_by_k.csv", variant_root / "cmc.csv"
            atomic_csv(accuracy_path, ["variant", "k", "category", "samples", "recognized", "accuracy_percent"], accuracy)
            atomic_csv(cmc_path, ["variant", "k", "category", "rank", "samples", "recognized", "accuracy_percent"], cmc)
            manifest.append({"source": variant, "status": "processed", "message": "", "output": str(accuracy_path)})
            print(f"[evaluation] [processed] {variant}")
        atomic_csv(output_root / "manifest.csv", ["source", "status", "message", "output"], manifest)
        (output_root / "run.json").write_text(json.dumps({"experiment": config["name"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "rank_max": int(settings.get("rank_max", 20)), "k_values": settings["k_values"]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    except (KeyError, OSError, ValueError, json.JSONDecodeError, csv.Error) as error:
        print(f"Evaluation configuration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
