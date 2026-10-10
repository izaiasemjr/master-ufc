"""Configuration loading and compilation for declarative experiments.

The project deliberately uses a small YAML 1.2 subset so no third-party
package is required.  It supports the structures used by ``configs/``:
indentation-based mappings, scalar lists, strings, booleans, numbers, and
comments.  Keep complex values expanded over multiple lines rather than using
YAML anchors or inline mappings.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a dataset or experiment definition is invalid."""


_NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][-+]?\d+)?$")


def _clean_lines(source: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for number, raw in enumerate(source.splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ConfigError(f"Tabs are not allowed for YAML indentation (line {number}).")
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, text))
    return lines


def _split_flow(value: str) -> list[str]:
    items, current, quote = [], [], None
    for char in value:
        if char in "\"'":
            quote = None if quote == char else (char if quote is None else quote)
        if char == "," and quote is None:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    items.append("".join(current).strip())
    return [item for item in items if item]


def _scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return None
    if value.startswith("[") and value.endswith("]"):
        return [_scalar(item) for item in _split_flow(value[1:-1])]
    if value.startswith("{") or value.endswith("}"):
        raise ConfigError("Inline mappings are not supported; expand them over indented lines.")
    if (value.startswith('"') and value.endswith('"')):
        try:
            return json.loads(value)
        except json.JSONDecodeError as error:
            raise ConfigError(f"Invalid double-quoted string: {value}") from error
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "~"}:
        return None
    if _NUMBER.fullmatch(value):
        return float(value) if any(marker in value.lower() for marker in (".", "e")) else int(value)
    return value


def parse_yaml(source: str) -> dict[str, Any]:
    """Parse the project-supported, dependency-free YAML subset."""
    lines = _clean_lines(source)
    if not lines:
        raise ConfigError("Configuration is empty.")
    index = 0

    def block(indent: int) -> Any:
        nonlocal index
        if index >= len(lines) or lines[index][0] < indent:
            return None
        is_list = lines[index][0] == indent and lines[index][1].startswith("- ")
        value: Any = [] if is_list else {}
        while index < len(lines) and lines[index][0] == indent:
            _, text = lines[index]
            if is_list:
                if not text.startswith("- "):
                    raise ConfigError("A list cannot mix entries with mapping keys.")
                entry = text[2:].strip()
                index += 1
                if entry:
                    value.append(_scalar(entry))
                else:
                    if index >= len(lines) or lines[index][0] <= indent:
                        raise ConfigError("List entry requires an indented value.")
                    value.append(block(lines[index][0]))
                continue
            if text.startswith("- "):
                raise ConfigError("A mapping cannot mix entries with list items.")
            if ":" not in text:
                raise ConfigError(f"Expected 'key: value', found: {text}")
            key, raw_value = text.split(":", 1)
            key, raw_value = key.strip(), raw_value.strip()
            if not key:
                raise ConfigError("Configuration contains an empty key.")
            index += 1
            if raw_value:
                value[key] = _scalar(raw_value)
            elif index < len(lines) and lines[index][0] > indent:
                value[key] = block(lines[index][0])
            else:
                value[key] = None
        return value

    root = block(lines[0][0])
    if index != len(lines) or not isinstance(root, dict):
        raise ConfigError("The root YAML value must be a mapping.")
    return root


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        return parse_yaml(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigError(f"Configuration file not found: {path}") from error


def _require(mapping: dict[str, Any], key: str, label: str) -> Any:
    value = mapping.get(key)
    if value is None:
        raise ConfigError(f"Missing required setting '{label}.{key}'.")
    return value


def _paths(experiment: dict[str, Any], dataset: dict[str, Any]) -> dict[str, str]:
    dataset_id = _require(dataset, "id", "dataset")
    experiment_id = _require(experiment, "id", "experiment")
    if not isinstance(dataset_id, str) or not isinstance(experiment_id, str):
        raise ConfigError("Dataset and experiment identifiers must be strings.")
    root = f"data/results/{dataset_id}/experiments/{experiment_id}"
    return {
        "root": root,
        "preprocessing": f"{root}/preprocessing",
        "registration": f"{root}/registration",
        "crop": f"{root}/crop",
        "keypoints": f"{root}/keypoints",
        "feature_extraction": f"{root}/feature_extraction",
        "matching": f"{root}/matching",
        "classification": f"{root}/classification",
        "evaluation": f"{root}/evaluation",
    }


def _sample_pattern(experiment: dict[str, Any], dataset: dict[str, Any]) -> str:
    samples = _require(experiment, "samples", "experiment")
    groups = _require(samples, "groups", "experiment.samples")
    available = _require(_require(dataset, "selection", "dataset"), "groups", "dataset.selection")
    if not isinstance(groups, list) or not groups:
        raise ConfigError("experiment.samples.groups must contain at least one group.")
    patterns = []
    for group in groups:
        pattern = available.get(group)
        if not isinstance(pattern, str):
            raise ConfigError(f"Unknown sample group '{group}' for dataset '{dataset['id']}'.")
        patterns.append(f"(?:{pattern})")
    return "(?:" + "|".join(patterns) + ")"


def compile_experiment(experiment: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    """Compile one generic experiment into runner-specific stage configs."""
    paths = _paths(experiment, dataset)
    dataset_paths = _require(dataset, "paths", "dataset")
    commands = _require(dataset, "commands", "dataset")
    selection = _require(dataset, "selection", "dataset")
    stages = _require(_require(experiment, "pipeline", "experiment"), "stages", "experiment.pipeline")
    if not isinstance(stages, list) or not stages:
        raise ConfigError("experiment.pipeline.stages must be a non-empty list.")
    pattern = _sample_pattern(experiment, dataset)
    glob = _require(selection, "glob", "dataset.selection")
    name, dataset_id = experiment["id"], dataset["id"]
    registration_settings = _require(experiment, "registration", "experiment")
    preprocessing_settings = _require(experiment, "preprocessing", "experiment")
    crop_settings = _require(experiment, "crop", "experiment")
    keypoint_settings = _require(experiment, "keypoints", "experiment")
    feature_settings = _require(experiment, "feature_extraction", "experiment")
    execution = experiment.get("execution", {"workers": 1, "fail_fast": False})
    preprocess = {
        "name": name, "dataset": {"name": dataset_id, "input_root": dataset_paths["raw_clouds"], "include_glob": glob, "include_filename_regex": pattern},
        "output": {"root": paths["preprocessing"], "overwrite": False}, "commands": commands["preprocessing"],
        "processing": preprocessing_settings, "execution": execution,
    }
    reference = dataset["reference"]
    registration = {
        "name": name,
        "dataset": {"input_root": paths["preprocessing"] + "/clouds", "landmarks_root": dataset_paths["landmarks"], "include_glob": glob, "include_filename_regex": pattern, "target_suffix": registration_settings["target_suffix"]},
        "reference": {
            "gallery_root": paths["preprocessing"] + "/clouds", "gallery_filename_regex": reference["gallery_filename_regex"],
            "alignment": {"base_relative_path": reference["base_relative_path"], "aligned_gallery_root": paths["registration"] + "/reference_mask/aligned_gallery", "pcl_icp_options": reference["pcl_icp_options"]},
            "concatenated_cloud": paths["registration"] + "/reference_mask/gallery_concatenated.pcd", "global_cloud": paths["registration"] + "/reference_mask/mask_mls.pcd", "mls_radius": reference["mls_radius"],
        },
        "output": {"root": paths["registration"], "overwrite": False}, "commands": commands["registration"],
        "processing": registration_settings["processing"], "execution": {"fail_fast": execution.get("fail_fast", False)},
    }
    crop = {
        "name": name,
        "dataset": {"cloud_root": paths["registration"] + "/registrations", "landmarks_root": paths["registration"] + "/landmarks_transformed", "include_glob": glob, "include_filename_regex": pattern},
        "output": {"root": paths["crop"], "overwrite": False}, "commands": commands["crop"], "processing": crop_settings,
        "execution": {"fail_fast": execution.get("fail_fast", False)},
    }
    keypoints = {
        "name": name,
        "dataset": {"cloud_root": paths["crop"] + "/clouds", "landmarks_root": paths["registration"] + "/landmarks_transformed", "include_glob": glob, "include_filename_regex": pattern},
        "output": {"root": paths["keypoints"], "overwrite": False}, "commands": commands["keypoints"],
        "radial_grids": keypoint_settings["radial_grids"], "detectors": keypoint_settings["detectors"], "execution": {"fail_fast": execution.get("fail_fast", False)},
    }
    feature_extraction = {
        "name": name,
        "dataset": {"cloud_root": paths["crop"] + "/clouds", "keypoints_root": paths["keypoints"], "include_glob": glob, "include_filename_regex": pattern},
        "output": {"root": paths["feature_extraction"], "overwrite": False},
        "commands": commands["feature_extraction"], "variants": feature_settings["variants"],
        "execution": {"workers": execution.get("workers", 1), "fail_fast": execution.get("fail_fast", False)},
    }
    configs = {"preprocessing": preprocess, "registration": registration, "crop": crop, "keypoints": keypoints, "feature_extraction": feature_extraction}
    recognition_stages = {"matching", "classification", "evaluation"}
    if recognition_stages.intersection(stages):
        matching_settings = _require(experiment, "matching", "experiment")
        matching_commands = _require(commands, "matching", "dataset")
        matching = {
            "name": name,
            "input": {"descriptor_root": paths["feature_extraction"]},
            "output": {"root": paths["matching"], "overwrite": False},
            "commands": matching_commands,
            "matching": matching_settings,
        }
        configs["matching"] = matching
        configs["classification"] = {
            "name": name,
            "input": {"matching_root": paths["matching"]},
            "output": {"root": paths["classification"], "overwrite": False},
            "matching": matching_settings,
        }
        configs["evaluation"] = {
            "name": name,
            "input": {"classification_root": paths["classification"]},
            "output": {"root": paths["evaluation"], "overwrite": False},
            "matching": matching_settings,
        }
    return {"experiment": experiment, "dataset": dataset, "paths": paths, "stages": stages, "configs": configs}
