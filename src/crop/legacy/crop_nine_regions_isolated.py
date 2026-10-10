#!/usr/bin/env python3
"""Generate the nine Bosphorus facial crops for one hardcoded face."""

import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

# Paths for the face used in this example. Change these values when selecting
# another face; keypointsPath must be the landmark PCD of pathPeople.
pathPeople = (
    SCRIPT_DIR
    / "../../DATA/RESULTS_REGISTRO/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/"
    "CP-ICP/mask_mls_th8/registrations/bs000/bs000_N_N_0.pcd"
).resolve()
keypointsPath = (
    SCRIPT_DIR
    / "../../DATA/RESULTS_REGISTRO/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/"
    "CP-ICP/mask_mls_th8/landmarks_transformed/bs000/bs000_N_N_0.pcd"
).resolve()
pathOut = SCRIPT_DIR / "key-nine-regions/isolated_regions"
cropExecutable = SCRIPT_DIR.parent / "build" / "Crop"
offset = "0,0,0"


# keypoints-rays.conf numbers landmarks from 1. Crop uses zero-based PCL
# indices, therefore each index below is the configuration number minus one.
REGIONS = (
    ("nose_tip", 13, 25),
    ("mouth_cd", 20, 45),
    ("mouth_cu", 16, 35),
    ("mouth_l", 15, 45),
    ("mouth_r", 17, 45),
    ("eye_li", 7, 45),
    ("eye_le", 6, 45),
    ("eye_ri", 8, 45),
    ("eye_re", 9, 45),
)


def require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{description} nao encontrado: {path}")


def main() -> int:
    try:
        require_file(pathPeople, "Arquivo da face")
        require_file(keypointsPath, "Arquivo de keypoints")
        require_file(cropExecutable, "Executavel Crop")
        pathOut.mkdir(parents=True, exist_ok=True)
    except (FileNotFoundError, OSError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    for position, (region, landmark_index, radius) in enumerate(REGIONS, start=1):
        output = pathOut / f"{region}.pcd"
        command = [
            str(cropExecutable),
            "-cloud", str(pathPeople),
            "-keypoints", f"{keypointsPath},{landmark_index}",
            "-crop_radius", str(radius),
            "-output", str(output),
            "-offset", offset,
        ]

        print(f"[{position}/{len(REGIONS)}] {region} (raio {radius})")
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as error:
            print(f"Erro ao gerar {region}.pcd: {error}", file=sys.stderr)
            return error.returncode or 1

    print(f"9 regioes isoladas salvas em: {pathOut}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
