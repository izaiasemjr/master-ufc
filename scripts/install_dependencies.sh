#!/usr/bin/env bash
# Install the supported Linux/WSL toolchain and compile every native stage.
# Usage: bash scripts/install_dependencies.sh [--skip-system-packages] [--skip-build]

set -Eeuo pipefail

SKIP_SYSTEM_PACKAGES=false
SKIP_BUILD=false

for argument in "$@"; do
  case "$argument" in
    --skip-system-packages) SKIP_SYSTEM_PACKAGES=true ;;
    --skip-build) SKIP_BUILD=true ;;
    -h|--help)
      sed -n '1,3p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $argument" >&2
      exit 2
      ;;
  esac
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "Administrative privileges are required to install system packages." >&2
    exit 1
  fi
}

if [[ "$SKIP_SYSTEM_PACKAGES" == false ]]; then
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "This installer supports Ubuntu/Debian (including WSL) via apt-get." >&2
    echo "Install an equivalent C++17/CMake/PCL toolchain, then rerun with --skip-system-packages." >&2
    exit 1
  fi

  run_as_root apt-get update
  run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    ca-certificates \
    cmake \
    libpcl-dev \
    pcl-tools \
    python3 \
    python3-matplotlib
fi

for command in cmake python3 pcl_icp pcl_voxel_grid pcl_outlier_removal \
  pcl_transform_point_cloud pcl_concatenate_points_pcd pcl_mls_smoothing; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command was not found: $command" >&2
    exit 1
  fi
done

if [[ "$SKIP_BUILD" == false ]]; then
  build_target() {
    local source_directory="$1"
    local build_directory="$source_directory/build"
    cmake -S "$PROJECT_ROOT/$source_directory" -B "$PROJECT_ROOT/$build_directory"
    cmake --build "$PROJECT_ROOT/$build_directory" --parallel
  }

  build_target src/registration/cp_icp
  build_target src/crop
  build_target src/keypoints/radial_grid
  build_target src/keypoints/detectors
  build_target src/feature_extraction
  build_target src/matching
fi

echo "Dependencies are available and the native pipeline stages are ready."
