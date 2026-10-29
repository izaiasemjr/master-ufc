#!/usr/bin/env python3
"""Render publication-ready RR-by-k and CMC plots from evaluation CSVs."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # The pipeline must work on a headless WSL host.
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[3]

CATEGORY_ORDER = ("N", "O_EYE", "O_GLASSES", "O_MOUTH", "O_HAIR", "O_ALL", "ALL")
CATEGORY_LABELS = {
    "N": "Neutral",
    "O_EYE": "Eye",
    "O_GLASSES": "Glasses",
    "O_MOUTH": "Mouth",
    "O_HAIR": "Hair",
    "O_ALL": "O All",
    "ALL": "All",
}
CATEGORY_COLORS = {
    "N": "#0072B2", "O_EYE": "#D55E00", "O_GLASSES": "#009E73",
    "O_MOUTH": "#56B4E9", "O_HAIR": "#CC79A7", "O_ALL": "#E69F00", "ALL": "#000000",
}


def project_path(value: str, root: Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else root / candidate


def load_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid visualization configuration: {error}") from error


def read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Evaluation file has an invalid or empty header: {path}")
    return rows


def ordered_categories(values: set[str]) -> list[str]:
    return [category for category in CATEGORY_ORDER if category in values] + sorted(values.difference(CATEGORY_ORDER))


def category_label(category: str, settings: dict[str, Any]) -> str:
    labels = settings.get("category_labels", {})
    return str(labels.get(category, CATEGORY_LABELS.get(category, category.replace("_", " ").title())))


def variant_label(variant: str, settings: dict[str, Any]) -> str:
    labels = settings.get("variant_labels", {})
    return str(labels.get(variant, variant.replace("_", " ").upper()))


def k_label(value: int) -> str:
    return "ALL" if value >= 1_000_000 else f"{value:g}"


def selected_cmc_k(variant: str, available: set[int], settings: dict[str, Any]) -> int:
    axis = settings.get("_axis", "k")
    configured = settings.get(f"cmc_{axis}")
    if isinstance(configured, dict):
        configured = configured.get(variant)
    if configured is None:
        # A deterministic fallback keeps generic experiments runnable, but the
        # YAML should normally state the scientifically chosen value explicitly.
        return max(available)
    selected = float(configured) if axis != "k" else int(configured)
    if selected not in available:
        raise ValueError(f"visualization.cmc_{axis} for {variant} is {selected}, but available values are {sorted(available)}")
    return selected


def formats(settings: dict[str, Any]) -> list[str]:
    values = settings.get("formats", ["png"])
    values = values if isinstance(values, list) else [values]
    normalized = [str(value).lower().lstrip(".") for value in values]
    allowed = {"png", "pdf", "svg"}
    invalid = [value for value in normalized if value not in allowed]
    if invalid:
        raise ValueError("Unsupported visualization format(s): " + ", ".join(invalid))
    return list(dict.fromkeys(normalized))


def atomic_save(fig: plt.Figure, path: Path, dpi: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=path.suffix, dir=path.parent)
    os.close(descriptor)
    try:
        fig.savefig(temporary, format=path.suffix.lstrip("."), dpi=dpi, bbox_inches="tight")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def plot_rr_by_k(rows: list[dict[str, str]], variant: str, settings: dict[str, Any], output_base: Path, dpi: int) -> list[Path]:
    axis_name = settings.get("_axis", "k")
    axis_label = {"dp": "DP", "dp_threshold": "DPThreshold", "k": "k"}[axis_name]
    grouped: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append((float(row[axis_name]), float(row["accuracy_percent"])))
    fig, axis = plt.subplots(figsize=(10, 7), constrained_layout=True)
    for category in ordered_categories(set(grouped)):
        values = sorted(grouped[category])
        ks, accuracy = zip(*values)
        best_k, best_accuracy = max(values, key=lambda item: (item[1], -item[0]))
        axis.plot(ks if axis_name == "dp" else range(1, len(ks) + 1), accuracy, marker="o", linewidth=2.2,
                  color=CATEGORY_COLORS.get(category), label=f"{category_label(category, settings)} — {best_accuracy:.2f}% [{k_label(best_k)}]")
    all_k = sorted({float(row[axis_name]) for row in rows})
    axis.set_title(f"{variant_label(variant, settings)} — Recognition rate by {axis_label}", fontweight="bold")
    axis.set_xlabel(axis_label, fontweight="bold")
    axis.set_ylabel("RR (%)", fontweight="bold")
    if axis_name == "dp":
        axis.set_xscale("log")
    axis.set_xticks(all_k if axis_name == "dp" else range(1, len(all_k) + 1), [k_label(value) for value in all_k])
    if axis_name == "dp":
        axis.set_xlabel("DP (log scale)", fontweight="bold")
        axis.tick_params(axis="x", labelrotation=45)
    axis.set_ylim(0, 100)
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="best", fontsize=9, frameon=True)
    paths = [Path(str(output_base) + "." + extension) for extension in formats(settings)]
    for path in paths:
        atomic_save(fig, path, dpi)
    plt.close(fig)
    return paths


def plot_cmc(rows: list[dict[str, str]], variant: str, selected_k: int, settings: dict[str, Any], output_base: Path, dpi: int) -> list[Path]:
    axis_name = settings.get("_axis", "k")
    axis_label = {"dp": "DP", "dp_threshold": "DPThreshold", "k": "k"}[axis_name]
    grouped: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for row in rows:
        if float(row[axis_name]) == selected_k:
            grouped[row["category"]].append((int(row["rank"]), float(row["accuracy_percent"])))
    if not grouped:
        raise ValueError(f"No CMC rows found for {variant}, k={selected_k}")
    fig, axis = plt.subplots(figsize=(10, 7), constrained_layout=True)
    for category in ordered_categories(set(grouped)):
        values = sorted(grouped[category])
        ranks, accuracy = zip(*values)
        axis.plot(ranks, accuracy, marker="o", linewidth=2.2, color=CATEGORY_COLORS.get(category), label=category_label(category, settings))
    axis.set_title(f"{variant_label(variant, settings)} — CMC ({axis_label}={k_label(selected_k)})", fontweight="bold")
    axis.set_xlabel("Rank", fontweight="bold")
    axis.set_ylabel("RR (%)", fontweight="bold")
    axis.set_xticks(sorted({rank for values in grouped.values() for rank, _ in values}))
    axis.set_ylim(0, 100)
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="lower right", fontsize=9, frameon=True)
    paths = [Path(str(output_base) + "." + extension) for extension in formats(settings)]
    for path in paths:
        atomic_save(fig, path, dpi)
    plt.close(fig)
    return paths


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "status", "message", "output"])
        writer.writeheader(); writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render RR-by-k and CMC figures from evaluation results.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        config, root = load_config(args.config), args.project_root.resolve()
        evaluation_root = project_path(config["input"]["evaluation_root"], root)
        output_root = project_path(config["output"]["root"], root)
        settings = dict(config.get("visualization", {}))
        axis_name = "dp_threshold" if config["matching"].get("selection") == "auto_k_increment" else ("dp" if config["matching"].get("selection") == "auto_k" else "k")
        settings["_axis"] = axis_name
        dpi = int(settings.get("dpi", 300))
        if dpi < 72:
            raise ValueError("visualization.dpi must be at least 72")
        formats(settings)  # Validate before inspecting inputs.
        variants = config["matching"]["variants"]
        print(f"Experiment: {config['name']}\nVariants: {len(variants)}\nOutput: {output_root}")
        prepared: dict[str, tuple[list[dict[str, str]], list[dict[str, str]], int]] = {}
        for variant in variants:
            variant_root = evaluation_root / variant
            accuracy = read_csv(variant_root / f"accuracy_by_{axis_name}.csv", {"variant", axis_name, "category", "accuracy_percent"})
            cmc = read_csv(variant_root / "cmc.csv", {"variant", axis_name, "category", "rank", "accuracy_percent"})
            available_k = {float(row[axis_name]) for row in cmc}
            selected_k = selected_cmc_k(variant, available_k, settings)
            prepared[variant] = (accuracy, cmc, selected_k)
            print(f"  {variant}: RR by {axis_name}; CMC at {axis_name}={selected_k}")
        if args.dry_run:
            print("Dry run completed; evaluation tables were validated, no figures were written.")
            return 0
        manifest: list[dict[str, str]] = []
        for variant, (accuracy, cmc, selected_k) in prepared.items():
            variant_root = output_root / variant
            rr_paths = plot_rr_by_k(accuracy, variant, settings, variant_root / f"rr_by_{axis_name}", dpi)
            cmc_paths = plot_cmc(cmc, variant, selected_k, settings, variant_root / f"cmc_{axis_name}_{selected_k:g}", dpi)
            outputs = rr_paths + cmc_paths
            manifest.append({"source": variant, "status": "processed", "message": f"cmc_{axis_name}={selected_k}", "output": ";".join(str(path) for path in outputs)})
            print(f"[visualization] [processed] {variant}")
        write_manifest(output_root / "manifest.csv", manifest)
        (output_root / "run.json").write_text(json.dumps({"experiment": config["name"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "dpi": dpi, "formats": formats(settings), f"cmc_{axis_name}": settings.get(f"cmc_{axis_name}")}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    except (KeyError, OSError, ValueError, json.JSONDecodeError, csv.Error) as error:
        print(f"Visualization configuration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
