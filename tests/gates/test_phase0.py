"""Phase 0 gate: setup and planning (see docs/Tasks.md).

Run: pytest tests/gates/test_phase0.py
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from src.config import PROJECT_ROOT, load_config

AOI_MIN_KM2 = 50
AOI_MAX_KM2 = 1500

# Folders tracked in git (PRD section 11). data/, outputs/, logs/ are git-ignored
# and created on demand by Config.ensure_dirs().
REQUIRED_DIRS = [
    "config",
    "docs",
    "notebooks",
    "report",
    "scripts",
    "src",
    "src/download",
    "src/preprocess",
    "src/features",
    "src/classify",
    "src/similarity",
    "src/suitability",
    "src/viz",
    "tests/unit",
    "tests/gates",
]

REQUIRED_FILES = [
    "environment.yml",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    "config/config.yaml",
    "docs/PRD.md",
    "docs/Tasks.md",
]


def test_environment_complete():
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "check_env.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("rel", REQUIRED_DIRS)
def test_folder_exists(rel):
    assert (PROJECT_ROOT / rel).is_dir(), f"Missing folder: {rel}"


@pytest.mark.parametrize("rel", REQUIRED_FILES)
def test_file_exists(rel):
    assert (PROJECT_ROOT / rel).is_file(), f"Missing file: {rel}"


@pytest.mark.parametrize("pkg", [d for d in REQUIRED_DIRS if d.startswith("src")])
def test_src_packages_importable(pkg):
    assert (PROJECT_ROOT / pkg / "__init__.py").is_file(), f"{pkg} has no __init__.py"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_config_loads(cfg):
    assert cfg.cell_size_m > 0


def test_aoi_single_valid_polygon(cfg):
    assert len(cfg.aoi) == 1
    geom = cfg.aoi.geometry.iloc[0]
    assert geom.is_valid and not geom.is_empty
    assert geom.geom_type in ("Polygon", "MultiPolygon")


def test_aoi_area_in_range(cfg):
    area = cfg.aoi_area_km2
    assert AOI_MIN_KM2 <= area <= AOI_MAX_KM2, f"AOI area {area:.0f} km² outside range"


def test_crs_projected_in_metres(cfg):
    assert cfg.crs.is_projected
    assert {axis.unit_name for axis in cfg.crs.axis_info} == {"metre"}


def test_study_area_named(cfg):
    assert cfg["aoi"].get("name") not in (None, "", "TBD"), "Set aoi.name in config.yaml"
