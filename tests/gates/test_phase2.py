"""Phase 2 gate: data acquisition (see docs/Tasks.md). Runs on the real downloaded data.

Run: pytest tests/gates/test_phase2.py
Download first: python -m src.download.lulc; python -m src.download.dem; python -m src.download.osm
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.warp import transform_bounds

from src.config import load_config
from src.download import dem, lulc, osm
from src.download.stac import aoi_bounds_4326
from src.features.schema import ESRI_CLASSES, ESRI_NODATA
from src.io_utils import Manifest, manifest_key, needs_download, sha256

WORLDCOVER_CODES = {10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100}

cfg = load_config()

ESRI = {f"esri_{y}": lulc.esri_path(cfg, y) for y in lulc.esri_years(cfg)}
WORLDCOVER_YEAR = int(cfg["lulc"]["worldcover_check"])
RASTERS = {
    **ESRI,
    "worldcover": lulc.worldcover_path(cfg, WORLDCOVER_YEAR),
    "dem": dem.dem_path(cfg),
}
VECTORS = {
    f"osm_{snap}_{layer}": osm.osm_path(cfg, snap, layer)
    for snap in osm.snapshots(cfg)
    for layer in osm.layers_for(snap)
}
ALL_FILES = {**RASTERS, **VECTORS}


@pytest.fixture(scope="module")
def manifest() -> Manifest:
    return Manifest.for_config(cfg)


@pytest.mark.parametrize("name", list(ALL_FILES))
def test_file_exists(name):
    assert ALL_FILES[name].is_file(), f"Missing {ALL_FILES[name]}: run the downloaders"


@pytest.mark.parametrize("name", list(RASTERS))
def test_raster_readable_with_crs_nodata_and_covers_aoi(name):
    with rasterio.open(RASTERS[name]) as ds:
        assert ds.crs is not None
        assert ds.nodata is not None
        w, s, e, n = transform_bounds(4326, ds.crs, *cfg.aoi.total_bounds, densify_pts=21)
        b = ds.bounds
        tol = abs(ds.res[0])  # one pixel of slack for grid snapping
        assert b.left <= w + tol and b.bottom <= s + tol
        assert b.right >= e - tol and b.top >= n - tol


@pytest.mark.parametrize("name", list(ESRI))
def test_esri_class_codes_valid(name):
    with rasterio.open(ESRI[name]) as ds:
        values = set(np.unique(ds.read(1)).tolist())
    assert values <= set(ESRI_CLASSES) | {ESRI_NODATA}, f"unexpected codes {values}"


def test_worldcover_class_codes_valid():
    with rasterio.open(RASTERS["worldcover"]) as ds:
        values = set(np.unique(ds.read(1)).tolist())
    assert values <= WORLDCOVER_CODES | {0}, f"unexpected codes {values}"


def test_dem_values_plausible():
    with rasterio.open(RASTERS["dem"]) as ds:
        arr = ds.read(1, masked=True)
    assert arr.count() > 0
    assert 500 < float(arr.min()) and float(arr.max()) < 1500  # Bengaluru plateau, metres


@pytest.mark.parametrize("name", list(VECTORS))
def test_vector_readable_with_crs_and_not_empty(name):
    gdf = gpd.read_file(VECTORS[name])
    assert gdf.crs is not None
    assert len(gdf) > 0
    assert gdf.geometry.notna().all()


def test_osm_2018_snapshot_is_older_than_current():
    """The historical snapshot must really be historical (D8, D9)."""
    for layer in ("roads", "buildings"):
        old = len(gpd.read_file(osm.osm_path(cfg, "2018", layer)))
        new = len(gpd.read_file(osm.osm_path(cfg, "current", layer)))
        assert old < new, f"{layer}: 2018 has {old} features, current {new}"


@pytest.mark.parametrize("snap", list(osm.snapshots(cfg)))
def test_osm_counts_match_ohsome(snap):
    """No data silently lost to Overpass timeouts.

    The download covers AOI + buffer, so it should hold at least ~95 % of the
    features ohsome counted inside the AOI (docs/data_coverage.json, from P1.6).
    """
    coverage = json.loads((cfg.root / "docs" / "data_coverage.json").read_text("utf-8"))
    date = osm.snapshots(cfg)[snap]
    ohsome = coverage["osm"]["2018-01-01" if date else max(coverage["osm"])]
    bldg = gpd.read_file(osm.osm_path(cfg, snap, "buildings"))
    water = gpd.read_file(osm.osm_path(cfg, snap, "water"))
    n_lakes = int(
        ((water.get("natural") == "water") & water.geom_type.str.contains("Polygon")).sum()
    )
    assert len(bldg) >= 0.95 * ohsome["buildings"], f"{len(bldg)} vs ohsome {ohsome['buildings']}"
    assert n_lakes >= 0.95 * ohsome["water_polygons"], f"{n_lakes} vs {ohsome['water_polygons']}"


def test_bannerghatta_in_protected_areas():
    """H1.4: Bannerghatta NP must be present for the exclusion mask (A4.1b)."""
    gdf = gpd.read_file(osm.osm_path(cfg, "current", "protected"))
    names = gdf.get("name")
    assert names is not None and names.str.contains("Bannerghatta", case=False).any()


@pytest.mark.parametrize("name", list(ALL_FILES))
def test_manifest_entry_and_checksum(name, manifest):
    path: Path = ALL_FILES[name]
    entry = manifest.get(manifest_key(path, cfg.root))
    assert entry is not None, f"{path.name} is not in data/manifest.json"
    assert entry["sha256"] == sha256(path), f"{path.name} changed since download"


@pytest.mark.parametrize("name", list(ALL_FILES))
def test_download_covers_current_aoi_and_buffer(name, manifest):
    """A download made for a smaller AOI / buffer must be redone (e.g. buffer 1 → 3 km)."""
    entry = manifest.get(manifest_key(ALL_FILES[name], cfg.root)) or {}
    bbox = entry.get("source", {}).get("bbox_4326")
    assert bbox is not None, "no bbox_4326 recorded"
    w, s, e, n = aoi_bounds_4326(cfg)
    tol = 1e-6
    assert (
        bbox[0] <= w + tol and bbox[1] <= s + tol and bbox[2] >= e - tol and bbox[3] >= n - tol
    ), f"downloaded for {bbox}, needs {[w, s, e, n]}: rerun the downloader"


@pytest.mark.parametrize("name", list(ALL_FILES))
def test_rerun_would_not_download(name, manifest):
    assert not needs_download(ALL_FILES[name], manifest, cfg.root)
