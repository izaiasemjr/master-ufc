#!/usr/bin/env python3
"""Create the CP-ICP global reference mask from Bosphorus gallery faces.

PCL's ``pcl_concatenate_points_pcd`` always creates ``output.pcd`` in its
working directory. This runner isolates that implementation detail in a
temporary directory and writes stable, configuration-defined result paths.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def project_path(value: str, project_root: Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else project_root / candidate


def report_progress(index: int, total: int, status: str, cloud: Path) -> None:
    completed = 100 * index / total
    remaining = 100 * (total - index) / total
    print(f"[ICP mascara {index}/{total} | {completed:6.2f}% concluido | {remaining:6.2f}% restante] [{status}] {cloud}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Bosphorus MLS reference mask for CP-ICP.")
    parser.add_argument("--config", required=True, type=Path, help="Registration JSON configuration")
    parser.add_argument("--project-root", default=PROJECT_ROOT, type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Validate and list the selected gallery clouds")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate an existing concatenation and mask")
    args = parser.parse_args()

    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        root = args.project_root.resolve()
        reference, commands, output = config["reference"], config["commands"], config["output"]
        gallery_root = project_path(reference["gallery_root"], root)
        concatenated = project_path(reference["concatenated_cloud"], root)
        mask = project_path(reference["global_cloud"], root)
        alignment = reference["alignment"]
        base_cloud = gallery_root / alignment["base_relative_path"]
        aligned_gallery = project_path(alignment["aligned_gallery_root"], root)
        pattern = re.compile(reference["gallery_filename_regex"])
        if not gallery_root.is_dir():
            raise ValueError(f"Gallery directory does not exist: {gallery_root}. Run preprocessing first.")
        clouds = [cloud for cloud in sorted(gallery_root.rglob("*.pcd")) if pattern.fullmatch(cloud.name)]
        expected = reference.get("expected_gallery_clouds")
        if expected is not None and len(clouds) != expected:
            raise ValueError(f"Expected {expected} gallery clouds, found {len(clouds)}.")
        if not clouds:
            raise ValueError("No gallery clouds matched the configured selection.")
        if not base_cloud.is_file() or base_cloud not in clouds:
            raise ValueError(f"Configured base cloud is not in the selected gallery: {base_cloud}")
        print(f"Experiment: {config['name']}\nGallery clouds: {len(clouds)}\nBase cloud: {base_cloud.relative_to(gallery_root)}\nMask: {mask}")
        if args.dry_run:
            for cloud in clouds[:10]: print("  " + str(cloud.relative_to(gallery_root)))
            if len(clouds) > 10: print(f"  ... and {len(clouds) - 10} more")
            print("Dry run completed; no files were written.")
            return 0
        overwrite = args.overwrite or bool(output.get("overwrite", False))
        if mask.exists() and not overwrite:
            print("Mask already exists; use --overwrite to regenerate it.")
            return 0
        concatenate_command, smoothing_command, icp_command = commands["concatenate_points"], commands["mls_smoothing"], commands["icp"]
        missing = [command for command in (concatenate_command, smoothing_command, icp_command) if shutil.which(command) is None]
        if missing:
            raise ValueError("PCL command(s) not available on PATH: " + ", ".join(missing))
        concatenated.parent.mkdir(parents=True, exist_ok=True); mask.parent.mkdir(parents=True, exist_ok=True); aligned_gallery.mkdir(parents=True, exist_ok=True)
        working_directory = mask.parent / ".reference-mask-work"
        working_directory.mkdir(parents=True, exist_ok=True)
        pcl_default_output = working_directory / "output.pcd"
        pcl_default_output.unlink(missing_ok=True)
        concatenated_temporary = concatenated.with_name(concatenated.stem + ".tmp.pcd")
        mask_temporary = mask.with_name(mask.stem + ".tmp.pcd")
        concatenated_temporary.unlink(missing_ok=True); mask_temporary.unlink(missing_ok=True)
        try:
            aligned_clouds, alignment_records = [], []
            for index, cloud in enumerate(clouds, 1):
                relative = cloud.relative_to(gallery_root)
                destination = aligned_gallery / relative
                if destination.exists() and not overwrite:
                    aligned_clouds.append(destination); alignment_records.append([str(relative), "skipped", "output already exists"])
                    report_progress(index, len(clouds), "skipped", relative)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.unlink(missing_ok=True)
                if cloud == base_cloud:
                    shutil.copy2(cloud, destination)
                    aligned_clouds.append(destination); alignment_records.append([str(relative), "copied", "base reference"])
                    report_progress(index, len(clouds), "base copiada", relative)
                    continue
                cloud_working_directory = working_directory / "icp" / relative.parent / cloud.stem
                cloud_working_directory.mkdir(parents=True, exist_ok=True)
                aligned_from_pcl = cloud_working_directory / cloud.name
                aligned_from_pcl.unlink(missing_ok=True)
                # YAML keeps numeric options as numbers, whereas subprocess
                # requires every command argument to be a string/path object.
                icp_options = [str(option) for option in alignment.get("pcl_icp_options", [])]
                subprocess.run([icp_command, str(base_cloud), str(cloud), *icp_options], cwd=cloud_working_directory, check=True, text=True, capture_output=True)
                if not aligned_from_pcl.is_file():
                    raise ValueError(f"pcl_icp completed but did not create aligned cloud: {aligned_from_pcl}")
                shutil.move(str(aligned_from_pcl), str(destination))
                aligned_clouds.append(destination); alignment_records.append([str(relative), "aligned", ""])
                report_progress(index, len(clouds), "aligned", relative)
            with (mask.parent / "alignment_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle); writer.writerow(["source", "status", "message"]); writer.writerows(alignment_records)
            subprocess.run([concatenate_command, *(str(cloud) for cloud in aligned_clouds)], cwd=working_directory, check=True, text=True, capture_output=True)
            if not pcl_default_output.is_file():
                raise ValueError("pcl_concatenate_points_pcd completed but did not create output.pcd")
            shutil.move(str(pcl_default_output), str(concatenated_temporary))
            subprocess.run([smoothing_command, str(concatenated_temporary), str(mask_temporary), "-radius", str(reference["mls_radius"])], check=True, text=True, capture_output=True)
            if not mask_temporary.is_file():
                raise ValueError("pcl_mls_smoothing completed but did not create the mask")
            concatenated_temporary.replace(concatenated); mask_temporary.replace(mask)
        finally:
            pcl_default_output.unlink(missing_ok=True); concatenated_temporary.unlink(missing_ok=True); mask_temporary.unlink(missing_ok=True)
        metadata = {"experiment": config["name"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "gallery_clouds": len(clouds), "gallery_pattern": reference["gallery_filename_regex"], "base_cloud": str(base_cloud), "aligned_gallery_root": str(aligned_gallery), "pcl_icp_options": alignment.get("pcl_icp_options", []), "mls_radius": reference["mls_radius"], "concatenated_cloud": str(concatenated), "global_cloud": str(mask)}
        (mask.parent / "reference_mask_run.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("Reference mask created successfully.")
        return 0
    except (KeyError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"Reference-mask error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
