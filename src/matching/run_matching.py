#!/usr/bin/env python3
"""Run strict, in-memory batch FPFH matching from an experiment context.

Python owns selection, protocol validation and provenance.  The C++ core owns
only descriptor loading and numerical matching.  Consequently, output scores
are auditable without embedding dataset-specific rules in the executable.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LABEL = re.compile(r"^(?P<subject>[^_]+)_(?P<type>[^_]+)_(?P<expression>[^_]+)_(?P<sample>[^_]+)-desc\.pcd$")


def project_path(value: str, root: Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else root / candidate


def load_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid matching configuration: {error}") from error


def descriptor_record(path: Path, descriptor_root: Path) -> dict[str, str]:
    match = LABEL.fullmatch(path.name)
    if not match:
        raise ValueError(f"Descriptor name must encode subject_type_expression_sample: {path}")
    record = match.groupdict()
    record["path"] = str(path.resolve())
    record["source"] = str(path.relative_to(descriptor_root))
    return record


def label(record: dict[str, str]) -> str:
    return "_".join(record[name] for name in ("subject", "type", "expression", "sample"))


def matches_selector(record: dict[str, str], rule: dict[str, Any]) -> bool:
    """Match optional exact/list/regex selectors without dataset-specific IDs."""
    for field in ("subject", "type", "expression", "sample"):
        if field in rule:
            selected = rule[field]
            values = selected if isinstance(selected, list) else [selected]
            if record[field] not in {str(value) for value in values}:
                return False
        regex = rule.get(f"{field}_regex")
        if regex is not None and re.fullmatch(str(regex), record[field]) is None:
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


def category_for(record: dict[str, str], categories: dict[str, Any]) -> str | None:
    matches = [
        name for name, rule in categories.items()
        if matches_selector(record, rule)
    ]
    if len(matches) > 1:
        raise ValueError(f"Probe {label(record)} matches more than one configured category: {', '.join(matches)}")
    return matches[0] if matches else None


def validate_protocol(records: list[dict[str, str]], settings: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    gallery_rule = settings["gallery"]
    categories = settings["probes"]["categories"]
    if not isinstance(categories, dict) or not categories:
        raise ValueError("matching.probes.categories must be a non-empty mapping")
    gallery = [record for record in records if matches_selector(record, gallery_rule)]
    if not gallery:
        raise ValueError("Gallery selection found no descriptors")
    expected_gallery = optional_count(gallery_rule, "matching.gallery")
    if expected_gallery is not None and len(gallery) != expected_gallery:
        raise ValueError(f"Gallery protocol requires exactly {expected_gallery} descriptors; found {len(gallery)}")
    duplicate_gallery_subjects = sorted({record["subject"] for record in gallery if sum(other["subject"] == record["subject"] for other in gallery) != 1})
    if duplicate_gallery_subjects:
        raise ValueError("Gallery has duplicate subjects: " + ", ".join(duplicate_gallery_subjects))

    gallery_paths = {record["path"] for record in gallery}
    probes: list[dict[str, str]] = []
    counts = {name: 0 for name in categories}
    for record in records:
        if record["path"] in gallery_paths:
            continue
        category = category_for(record, categories)
        if category is None:
            raise ValueError(f"Probe {label(record)} does not belong to a configured protocol category")
        record = dict(record)
        record["category"] = category
        probes.append(record)
        counts[category] += 1
    for name, rule in categories.items():
        expected = optional_count(rule, f"matching.probes.categories.{name}")
        if expected is not None and counts[name] != expected:
            raise ValueError(f"Probe category {name} requires exactly {expected} descriptors; found {counts[name]}")
    if not probes:
        raise ValueError("Probe selection found no descriptors")
    expected_probes = optional_count(settings["probes"], "matching.probes")
    if expected_probes is not None and len(probes) != expected_probes:
        raise ValueError(f"Protocol requires exactly {expected_probes} probes; found {len(probes)}")
    return sorted(gallery, key=label), sorted(probes, key=label)


def collect_variant(variant: str, descriptor_root: Path, settings: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    root = descriptor_root / variant / "descriptors"
    if not root.is_dir():
        raise ValueError(f"Missing descriptor directory for {variant}: {root}")
    records = [descriptor_record(path, root) for path in sorted(root.rglob("*-desc.pcd")) if path.is_file()]
    if not records:
        raise ValueError(f"No descriptors found for {variant}: {root}")
    identities = [label(record) for record in records]
    duplicates = sorted({identity for identity in identities if identities.count(identity) > 1})
    if duplicates:
        raise ValueError(f"Duplicate descriptor identity in {variant}: {', '.join(duplicates)}")
    return validate_protocol(records, settings)


def write_input_manifest(path: Path, gallery: list[dict[str, str]], probes: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for role, records in (("gallery", gallery), ("probe", probes)):
            for record in records:
                handle.write("\t".join([role, record["subject"], record["type"], record["expression"], record["sample"], record["path"]]) + "\n")


def validate_scores(path: Path, probes: list[dict[str, str]], gallery: list[dict[str, str]], k_values: list[int]) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_rows = len(probes) * len(gallery) * len(k_values)
    if len(rows) != expected_rows:
        raise ValueError(f"Matching produced {len(rows)} rows; expected {expected_rows}")
    expected_gallery = {label(record) for record in gallery}
    groups: dict[tuple[str, int], set[str]] = {}
    for row in rows:
        key = ("_".join(row[f"probe_{field}"] for field in ("subject", "type", "expression", "sample")), int(row["k"]))
        gallery_id = "_".join(row[f"gallery_{field}"] for field in ("subject", "type", "expression", "sample"))
        groups.setdefault(key, set()).add(gallery_id)
        if int(row["correspondence_count"]) < 1 or int(row["selected_count"]) < 1:
            raise ValueError(f"Matching returned an empty correspondence result for {key[0]}")
    expected_probe = {label(record) for record in probes}
    if set(probe for probe, _ in groups) != expected_probe:
        raise ValueError("Matching output has missing or unexpected probes")
    for probe in expected_probe:
        for k_value in k_values:
            if groups.get((probe, k_value)) != expected_gallery:
                raise ValueError(f"Matching output has an incomplete gallery for probe={probe}, k={k_value}")


def write_error(path: Path, command: list[str], completed: subprocess.CompletedProcess[str] | None, diagnostic: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stdout = completed.stdout if completed else "(not started)"
    stderr = completed.stderr if completed else "(not started)"
    code = completed.returncode if completed else "(not started)"
    path.write_text("Command:\n" + " ".join(command) + f"\n\nExit code: {code}\n\nSTDOUT:\n{stdout or '(empty)'}\n\nSTDERR:\n{stderr or '(empty)'}\n\nValidation:\n{diagnostic}\n", encoding="utf-8")


def write_setup_failure(output_root: Path, diagnostic: str) -> None:
    """Expose validation failures to the pipeline-level failure summary."""
    output_root.mkdir(parents=True, exist_ok=True)
    error_path = output_root / "errors" / "configuration.log"
    error_path.parent.mkdir(parents=True, exist_ok=True)
    error_path.write_text(diagnostic + "\n", encoding="utf-8")
    with (output_root / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "status", "message", "output"])
        writer.writeheader()
        writer.writerow({"source": "<configuration>", "status": "failed", "message": f"{diagnostic}; log={error_path}", "output": ""})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run strict batch FPFH matching for one experiment.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    records: list[dict[str, Any]] = []
    output_root: Path | None = None
    try:
        config, root = load_config(args.config), args.project_root.resolve()
        settings = config["matching"]
        if settings.get("mode") != "paper":
            raise ValueError("Only matching.mode: paper is supported; it uses documented L1 matching and scoring")
        descriptor_root = project_path(config["input"]["descriptor_root"], root)
        output_root = project_path(config["output"]["root"], root)
        executable = project_path(config["commands"]["matching_batch"], root)
        k_values = sorted({int(value) for value in settings["k_values"]})
        if not k_values or any(value < 1 for value in k_values):
            raise ValueError("matching.k_values must contain positive integers")
        variants = settings["variants"]
        if not isinstance(variants, dict) or not variants:
            raise ValueError("matching.variants must be a non-empty mapping")
        print(f"Experiment: {config['name']}\nMode: paper (L1)\nVariants: {len(variants)}\nK: {', '.join(map(str, k_values))}")
        prepared: dict[str, tuple[list[dict[str, str]], list[dict[str, str]]]] = {}
        for variant, variant_settings in variants.items():
            correspondence = variant_settings.get("correspondence")
            if correspondence not in {"fixed", "dynamic"}:
                raise ValueError(f"matching variant {variant} must set correspondence: fixed or dynamic")
            prepared[variant] = collect_variant(variant, descriptor_root, settings)
            gallery, probes = prepared[variant]
            print(f"  {variant}: {len(probes)} probes x {len(gallery)} gallery ({correspondence})")
        if args.dry_run:
            print("Dry run completed; descriptors and protocol were validated, no files were written.")
            return 0
        if not executable.is_file():
            raise ValueError(f"Matching executable not found: {executable}. Build src/matching first.")
        output_root.mkdir(parents=True, exist_ok=True)
        for variant, variant_settings in variants.items():
            gallery, probes = prepared[variant]
            variant_root = output_root / variant
            manifest = variant_root / "descriptor-manifest.tsv"
            scores = variant_root / "pair_scores.csv"
            timing = variant_root / "timing.csv"
            if scores.is_file() and timing.is_file() and not args.overwrite:
                validate_scores(scores, probes, gallery, k_values)
                records.append({"source": variant, "status": "skipped", "message": "validated existing score and timing files", "output": str(scores)})
                print(f"[matching] [skipped] {variant}")
                continue
            write_input_manifest(manifest, gallery, probes)
            command = [str(executable), "--input", str(manifest), "--output", str(scores), "--timing-output", str(timing), "--correspondence", str(variant_settings["correspondence"]), "--ks", ",".join(map(str, k_values))]
            completed = subprocess.run(command, text=True, capture_output=True)
            if completed.returncode == 0:
                try:
                    validate_scores(scores, probes, gallery, k_values)
                    records.append({"source": variant, "status": "processed", "message": "", "output": str(scores)})
                    print(f"[matching] [processed] {variant}")
                    continue
                except (OSError, ValueError, csv.Error) as error:
                    diagnostic = str(error)
            else:
                diagnostic = " | ".join(part for part in ((completed.stdout or "").strip(), (completed.stderr or "").strip()) if part) or f"matching core exited with code {completed.returncode}"
            error_path = output_root / "errors" / f"{variant}.log"
            write_error(error_path, command, completed, diagnostic)
            records.append({"source": variant, "status": "failed", "message": f"{diagnostic}; log={error_path}", "output": str(scores)})
            print(f"[matching] [failed] {variant}", file=sys.stderr)
        with (output_root / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["source", "status", "message", "output"])
            writer.writeheader(); writer.writerows(records)
        failures = [record for record in records if record["status"] == "failed"]
        (output_root / "run.json").write_text(json.dumps({"experiment": config["name"], "mode": settings["mode"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "k_values": k_values, "variants": settings["variants"], "failed": len(failures)}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 1 if failures else 0
    except (KeyError, OSError, ValueError, json.JSONDecodeError, re.error, csv.Error) as error:
        diagnostic = str(error)
        print(f"Matching configuration error: {diagnostic}", file=sys.stderr)
        if output_root is not None:
            try:
                write_setup_failure(output_root, diagnostic)
            except OSError as manifest_error:
                print(f"Matching could not write failure manifest: {manifest_error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
