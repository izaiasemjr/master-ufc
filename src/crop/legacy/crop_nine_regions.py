#!/usr/bin/env python3
"""Generate the nine Bosphorus facial crops for one hardcoded face."""

import subprocess
import sys
import struct
import tempfile
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
pathOut = SCRIPT_DIR / "key-nine-regions"
cropExecutable = SCRIPT_DIR.parent / "build" / "Crop"
offset = "0,0,0"


# keypoints-rays.conf numbers landmarks from 1. Crop uses zero-based PCL
# indices, therefore each index below is the configuration number minus one.
REGIONS = (
    ("nose_tip", 13, 25, (255, 0, 0)),
    ("mouth_cd", 20, 45, (0, 255, 0)),
    ("mouth_cu", 16, 35, (0, 0, 255)),
    ("mouth_l", 15, 45, (255, 255, 0)),
    ("mouth_r", 17, 45, (255, 0, 255)),
    ("eye_li", 7, 45, (0, 255, 255)),
    ("eye_le", 6, 45, (255, 128, 0)),
    ("eye_ri", 8, 45, (128, 0, 255)),
    ("eye_re", 9, 45, (0, 128, 255)),
)
FACE_COLOR = (128, 128, 128)


def require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{description} nao encontrado: {path}")


def read_xyz_pcd(path: Path):
    """Read x/y/z points from an ASCII PCD file."""
    fields = None
    xyz_indices = None
    reading_points = False
    points = []

    with path.open("r", encoding="utf-8") as pcd_file:
        for raw_line in pcd_file:
            line = raw_line.strip()
            if not reading_points:
                tokens = line.split()
                if tokens and tokens[0] == "FIELDS":
                    fields = tokens[1:]
                elif tokens and tokens[0] == "DATA":
                    if len(tokens) != 2 or tokens[1].lower() != "ascii":
                        raise ValueError(f"PCD deve usar DATA ascii: {path}")
                    if fields is None or not {"x", "y", "z"}.issubset(fields):
                        raise ValueError(f"PCD sem campos x, y e z: {path}")
                    xyz_indices = tuple(fields.index(axis) for axis in ("x", "y", "z"))
                    reading_points = True
                continue

            if not line:
                continue
            values = line.split()
            if len(values) <= max(xyz_indices):
                raise ValueError(f"Linha PCD incompleta em: {path}")
            points.append(tuple(float(values[index]) for index in xyz_indices))

    if not reading_points:
        raise ValueError(f"Cabecalho PCD invalido: {path}")
    return points


def pcl_rgb_value(color):
    """Pack RGB bytes into the float representation expected by PCL."""
    red, green, blue = color
    packed_rgb = (red << 16) | (green << 8) | blue
    return struct.unpack("<f", struct.pack("<I", packed_rgb))[0]


def write_colored_cloud(output: Path, face_points, crop_points, crop_color) -> None:
    """Write face points in gray followed by the crop points in its color."""
    face_rgb = pcl_rgb_value(FACE_COLOR)
    crop_rgb = pcl_rgb_value(crop_color)
    point_count = len(face_points) + len(crop_points)

    with output.open("w", encoding="utf-8", newline="\n") as pcd_file:
        pcd_file.write("# .PCD v0.7 - Point Cloud Data file format\n")
        pcd_file.write("VERSION 0.7\n")
        pcd_file.write("FIELDS x y z rgb\n")
        pcd_file.write("SIZE 4 4 4 4\n")
        pcd_file.write("TYPE F F F F\n")
        pcd_file.write("COUNT 1 1 1 1\n")
        pcd_file.write(f"WIDTH {point_count}\n")
        pcd_file.write("HEIGHT 1\n")
        pcd_file.write("VIEWPOINT 0 0 0 1 0 0 0\n")
        pcd_file.write(f"POINTS {point_count}\n")
        pcd_file.write("DATA ascii\n")

        for point in face_points:
            pcd_file.write("{:.9g} {:.9g} {:.9g} {:.9g}\n".format(*point, face_rgb))
        for point in crop_points:
            pcd_file.write("{:.9g} {:.9g} {:.9g} {:.9g}\n".format(*point, crop_rgb))


def main() -> int:
    try:
        require_file(pathPeople, "Arquivo da face")
        require_file(keypointsPath, "Arquivo de keypoints")
        require_file(cropExecutable, "Executavel Crop")
        pathOut.mkdir(parents=True, exist_ok=True)
        face_points = read_xyz_pcd(pathPeople)
    except (FileNotFoundError, OSError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="crop-nine-regions-") as temporary_dir:
        temporary_dir = Path(temporary_dir)
        for position, (region, landmark_index, radius, color) in enumerate(
                REGIONS, start=1):
            crop_output = temporary_dir / f"{region}.pcd"
            output = pathOut / f"{region}.pcd"
            command = [
                str(cropExecutable),
                "-cloud", str(pathPeople),
                "-keypoints", f"{keypointsPath},{landmark_index}",
                "-crop_radius", str(radius),
                "-output", str(crop_output),
                "-offset", offset,
            ]

            print(f"[{position}/{len(REGIONS)}] {region} (raio {radius})")
            try:
                subprocess.run(command, check=True)
                crop_points = read_xyz_pcd(crop_output)
                write_colored_cloud(output, face_points, crop_points, color)
            except subprocess.CalledProcessError as error:
                print(f"Erro ao gerar {region}.pcd: {error}", file=sys.stderr)
                return error.returncode or 1
            except (OSError, ValueError) as error:
                print(f"Erro ao colorir {region}.pcd: {error}", file=sys.stderr)
                return 1

    print(f"9 regioes coloridas salvas em: {pathOut}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
