"""Unit tests for src/config.py using synthetic config + AOI files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.config import ConfigError, load_config, utm_epsg_for

# ~10 km x 10 km square near Pune, India (UTM 43N)
SQUARE = [[73.80, 18.50], [73.895, 18.50], [73.895, 18.59], [73.80, 18.59], [73.80, 18.50]]


def _write_project(tmp_path: Path, *, coords=None, features: int = 1, **overrides) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    feature = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [coords or SQUARE]},
    }
    geojson = {"type": "FeatureCollection", "features": [feature] * features}
    (config_dir / "aoi.geojson").write_text(json.dumps(geojson), encoding="utf-8")

    cfg = {
        "project": {"name": "test", "random_seed": 7},
        "aoi": {"path": "config/aoi.geojson"},
        "crs": {"epsg": "auto"},
        "grid": {"cell_size_m": 100},
        "years": {"baseline": 2017, "latest": 2023},
        "paths": {"data_raw": "data/raw", "outputs": "outputs"},
    }
    for section, values in overrides.items():
        cfg[section] = {**cfg.get(section, {}), **values}
    path = config_dir / "config.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("lon", "lat", "expected"),
    [
        (73.85, 18.52, 32643),  # Pune, north
        (-0.12, 51.5, 32630),  # London
        (151.2, -33.87, 32756),  # Sydney, south
        (180.0, 0.0, 32660),  # antimeridian clamps to zone 60
    ],
)
def test_utm_epsg_for(lon, lat, expected):
    assert utm_epsg_for(lon, lat) == expected


def test_utm_epsg_rejects_bad_coords():
    with pytest.raises(ConfigError):
        utm_epsg_for(200, 0)


def test_load_valid_config(tmp_path):
    cfg = load_config(_write_project(tmp_path))
    assert cfg.crs.to_epsg() == 32643
    assert cfg.cell_size_m == 100
    assert cfg.seed == 7
    assert cfg["years"]["baseline"] == 2017
    assert 90 < cfg.aoi_area_km2 < 110
    assert cfg.paths["data_raw"] == tmp_path / "data" / "raw"


def test_ensure_dirs_creates_paths(tmp_path):
    cfg = load_config(_write_project(tmp_path))
    cfg.ensure_dirs()
    assert (tmp_path / "data" / "raw").is_dir()
    assert (tmp_path / "outputs").is_dir()


def test_explicit_epsg(tmp_path):
    cfg = load_config(_write_project(tmp_path, crs={"epsg": 32644}))
    assert cfg.crs.to_epsg() == 32644


def test_geographic_crs_rejected(tmp_path):
    with pytest.raises(ConfigError, match="not projected"):
        load_config(_write_project(tmp_path, crs={"epsg": 4326}))


@pytest.mark.parametrize("size", [0, -5])
def test_bad_cell_size_rejected(tmp_path, size):
    with pytest.raises(ConfigError, match="cell_size_m"):
        load_config(_write_project(tmp_path, grid={"cell_size_m": size}))


def test_missing_aoi_file(tmp_path):
    path = _write_project(tmp_path)
    (tmp_path / "config" / "aoi.geojson").unlink()
    with pytest.raises(ConfigError, match="P0.10"):
        load_config(path)


def test_multiple_features_rejected(tmp_path):
    with pytest.raises(ConfigError, match="exactly one feature"):
        load_config(_write_project(tmp_path, features=2))


def test_invalid_polygon_rejected(tmp_path):
    bowtie = [[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]
    with pytest.raises(ConfigError, match="invalid"):
        load_config(_write_project(tmp_path, coords=bowtie))


def test_missing_section_rejected(tmp_path):
    path = _write_project(tmp_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["grid"]
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="grid"):
        load_config(path)
