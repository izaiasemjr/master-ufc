#!/usr/bin/env python3
"""Turn all probe x gallery scores into deterministic identification results."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import tempfile
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
        raise ValueError(f"Invalid classification configuration: {error}") from error


def identity(row: dict[str, str], prefix: str) -> str:
    return "_".join(row[f"{prefix}_{field}"] for field in ("subject", "type", "expression", "sample"))


def matches_selector(row: dict[str, str], prefix: str, rule: dict[str, Any]) -> bool:
    for field in ("subject", "type", "expression", "sample"):
        value = row[f"{prefix}_{field}"]
        if field in rule:
            selected = rule[field]
            values = selected if isinstance(selected, list) else [selected]
            if value not in {str(item) for item in values}:
                return False
        regex = rule.get(f"{field}_regex")
        if regex is not None and re.fullmatch(str(regex), value) is None:
            return False
    return True


def optional_count(rule: dict[str, Any], location: str) -> int | None:
    value = rule.get("expected_count")
    if value is None:
        return None
    count = int(value)
    if count < 1:
        raise ValueError(f"{location}.expected_count must be positive when declared")
    return count


def category_for(row: dict[str, str], categories: dict[str, Any]) -> str:
    matching = [
        name for name, rule in categories.items()
        if matches_selector(row, "probe", rule)
    ]
    if len(matching) != 1:
        raise ValueError(f"Probe {identity(row, 'probe')} must match exactly one configured category; found {matching}")
    return matching[0]


def read_predictions(scores: Path, settings: dict[str, Any], variant: str) -> list[dict[str, Any]]:
    with scores.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "k", "probe_subject", "probe_type", "probe_expression", "probe_sample",
        "gallery_subject", "gallery_type", "gallery_expression", "gallery_sample",
        "distance_mean_l1", "correspondence_count", "selected_count", "time_match_ms",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Matching score file has an invalid header: {scores}")
    groups: dict[tuple[str, int], list[dict[str, str]]] = {}
    for row in rows:
        try:
            k_value = int(row["k"])
            score = float(row["distance_mean_l1"])
        except ValueError as error:
            raise ValueError(f"Invalid numeric score in {scores}: {error}") from error
        if k_value < 1 or not math.isfinite(score):
            raise ValueError(f"Invalid k or non-finite score in {scores}")
        groups.setdefault((identity(row, "probe"), k_value), []).append(row)

    k_values = {int(value) for value in settings["k_values"]}
    category_rules = settings["probes"]["categories"]
    predictions: list[dict[str, Any]] = []
    canonical_gallery: set[str] | None = None
    probe_k_values: dict[str, set[int]] = {}
    expected_gallery_count = optional_count(settings["gallery"], "matching.gallery")
    for (probe_id, k_value), candidates in sorted(groups.items()):
        if k_value not in k_values:
            raise ValueError(f"Unexpected k={k_value} in {scores}")
        gallery_ids = [identity(row, "gallery") for row in candidates]
        gallery_set = set(gallery_ids)
        if len(candidates) != len(gallery_set):
            raise ValueError(f"{variant}: incomplete or duplicate gallery for probe={probe_id}, k={k_value}")
        if expected_gallery_count is not None and len(gallery_set) != expected_gallery_count:
            raise ValueError(f"{variant}: gallery has {len(gallery_set)} entries; expected {expected_gallery_count}")
        if canonical_gallery is None:
            canonical_gallery = gallery_set
        elif gallery_set != canonical_gallery:
            raise ValueError(f"{variant}: gallery differs between probe/k groups")
        probe_k_values.setdefault(probe_id, set()).add(k_value)
        ordered = sorted(candidates, key=lambda row: (float(row["distance_mean_l1"]), identity(row, "gallery")))
        probe_subject = ordered[0]["probe_subject"]
        true_rows = [index for index, row in enumerate(ordered, 1) if row["gallery_subject"] == probe_subject]
        if len(true_rows) != 1:
            raise ValueError(f"{variant}: probe {probe_id} has {len(true_rows)} gallery entries for its true subject")
        best_score = float(ordered[0]["distance_mean_l1"])
        category = category_for(ordered[0], category_rules)
        predictions.append({
            "variant": variant, "k": k_value, "category": category,
            "probe_subject": ordered[0]["probe_subject"], "probe_type": ordered[0]["probe_type"],
            "probe_expression": ordered[0]["probe_expression"], "probe_sample": ordered[0]["probe_sample"],
            "predicted_subject": ordered[0]["gallery_subject"], "predicted_distance_mean_l1": f"{best_score:.9f}",
            "true_rank": true_rows[0], "correct_rank_1": int(ordered[0]["gallery_subject"] == probe_subject),
            "tie_count_at_best": sum(float(row["distance_mean_l1"]) == best_score for row in ordered),
        })
    if not canonical_gallery:
        raise ValueError(f"{variant}: no gallery results were found")
    for probe_id, values in probe_k_values.items():
        if values != k_values:
            raise ValueError(f"{variant}: probe {probe_id} is missing one or more configured k values")
    expected_probes = optional_count(settings["probes"], "matching.probes")
    if expected_probes is not None and len(probe_k_values) != expected_probes:
        raise ValueError(f"{variant}: produced {len(probe_k_values)} probes; expected {expected_probes}")
    for category, rule in category_rules.items():
        expected = optional_count(rule, f"matching.probes.categories.{category}")
        if expected is not None:
            for k_value in k_values:
                found = sum(prediction["category"] == category and prediction["k"] == k_value for prediction in predictions)
                if found != expected:
                    raise ValueError(f"{variant}: category {category}, k={k_value}, has {found} probes; expected {expected}")
    return predictions


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify strict FPFH matching scores.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        config, root = load_config(args.config), args.project_root.resolve()
        settings = config["matching"]
        if settings.get("mode") != "paper":
            raise ValueError("Classification currently requires matching.mode: paper")
        matching_root = project_path(config["input"]["matching_root"], root)
        output_root = project_path(config["output"]["root"], root)
        variants = settings["variants"]
        print(f"Experiment: {config['name']}\nVariants: {len(variants)}")
        prepared: dict[str, list[dict[str, Any]]] = {}
        for variant in variants:
            prepared[variant] = read_predictions(matching_root / variant / "pair_scores.csv", settings, variant)
            print(f"  {variant}: {len(prepared[variant])} predictions validated")
        if args.dry_run:
            print("Dry run completed; score tables were validated, no files were written.")
            return 0
        manifest: list[dict[str, str]] = []
        fields = ["variant", "k", "category", "probe_subject", "probe_type", "probe_expression", "probe_sample", "predicted_subject", "predicted_distance_mean_l1", "true_rank", "correct_rank_1", "tie_count_at_best"]
        for variant, rows in prepared.items():
            path = output_root / variant / "predictions.csv"
            atomic_csv(path, fields, rows)
            manifest.append({"source": variant, "status": "processed", "message": "", "output": str(path)})
            print(f"[classification] [processed] {variant}")
        atomic_csv(output_root / "manifest.csv", ["source", "status", "message", "output"], manifest)
        (output_root / "run.json").write_text(json.dumps({"experiment": config["name"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "mode": settings["mode"], "variants": list(variants)}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    except (KeyError, OSError, ValueError, json.JSONDecodeError, csv.Error) as error:
        print(f"Classification configuration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
