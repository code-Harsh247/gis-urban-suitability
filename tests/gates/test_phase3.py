"""Phase 3 gate: preprocessing (see docs/Tasks.md). Runs on the real processed data.

Run: pytest tests/gates/test_phase3.py
Build first: python -m src.preprocess.raster; python -m src.preprocess.vector
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
import shapely
from rasterio.features import geometry_mask

from src.config import load_config
from src.download.osm import layers_for, snapshots
from src.features import schema
from src.preprocess.raster import ESRI_VALID, load_reference_grid, processed_dir
from src.preprocess.vector import processed_osm_path

WORLDCOVER_CODES = {10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100}

cfg = load_config()


def _rasters(c=None) -> dict[str, Path]:
    c = c or cfg
    out = processed_dir(c)
    files = {p.name: p for p in sorted(out.glob("*.tif"))}
    return files


def _vectors(c=None) -> dict[str, Path]:
    c = c or cfg
    return {
        f"{s}/{layer}": processed_osm_path(c, s, layer)
        for s in snapshots(c)
        for layer in layers_for(s)
    }


RASTERS = _rasters()
VECTORS = _vectors()
EXPECTED_RASTERS = {
    *(f"lulc_esri_{y}.tif" for y in range(cfg["years"]["baseline"], cfg["years"]["latest"] + 1)),
    f"worldcover_{cfg['lulc']['worldcover_check']}.tif",
    "elevation.tif",
    "slope.tif",
}


def test_all_processed_layers_exist():
    missing = sorted(EXPECTED_RASTERS - set(RASTERS))
    missing += [k for k, p in VECTORS.items() if not p.exists()]
    assert not missing, f"missing processed layers: {missing}"


@pytest.mark.parametrize("name", sorted(EXPECTED_RASTERS))
def test_rasters_share_the_reference_grid(name):
    """Identical CRS, transform, width and height for every processed raster."""
    ref = load_reference_grid(cfg)
    with rasterio.open(RASTERS[name]) as ds:
        assert ds.crs == ref.crs, f"{name}: CRS {ds.crs}"
        assert ds.transform == ref.transform, f"{name}: transform differs"
        assert (ds.height, ds.width) == ref.shape, f"{name}: shape {ds.shape}"


def test_reference_grid_is_project_crs_and_whole_cells():
    ref = load_reference_grid(cfg)
    assert ref.crs == cfg.crs, f"reference grid CRS {ref.crs} != project CRS {cfg.crs}"
    cell = cfg.cell_size_m
    assert all(
        abs(v / cell - round(v / cell)) < 1e-9 for v in ref.bounds
    ), "grid edges not on whole cells"


@pytest.mark.parametrize("name", sorted(VECTORS))
def test_vectors_project_crs_valid_non_empty_inside_grid(name):
    g = gpd.read_file(VECTORS[name])
    assert len(g) > 0, f"{name}: empty layer"
    assert g.crs == cfg.crs, f"{name}: CRS {g.crs}"
    assert g.is_valid.all(), f"{name}: {int((~g.is_valid).sum())} invalid geometries"
    assert not g.is_empty.any(), f"{name}: empty geometries"
    # clipped to the reference grid (same 1 cm tolerance as scripts/verify_vectors.py)
    extent = shapely.box(*load_reference_grid(cfg).bounds).buffer(0.01)
    outside = int((~g.within(extent)).sum())
    assert outside == 0, f"{name}: {outside} geometries outside the reference-grid extent"


@pytest.mark.parametrize("name", sorted(n for n in VECTORS if n.endswith(("/roads", "/water"))))
def test_lines_are_single_part(name):
    """P3.4: multi-part lines are exploded (roads and waterways)."""
    g = gpd.read_file(VECTORS[name])
    multi = int((g.geom_type == "MultiLineString").sum())
    assert multi == 0, f"{name}: {multi} MultiLineString features"


@pytest.mark.parametrize("snapshot", sorted(snapshots(cfg)))
def test_roads_have_major_minor_class(snapshot):
    g = gpd.read_file(processed_osm_path(cfg, snapshot, "roads"))
    assert "road_class" in g.columns, f"{snapshot}: roads have no road_class column"
    assert set(g["road_class"]) == {
        "major",
        "minor",
    }, f"{snapshot}: road_class {sorted(set(g['road_class']))}"


@pytest.mark.parametrize(
    "name", sorted(n for n in EXPECTED_RASTERS if n.startswith(("lulc_esri", "worldcover")))
)
def test_lulc_only_valid_codes(name):
    """Resampling must not create new class values."""
    with rasterio.open(RASTERS[name]) as ds:
        codes = set(np.unique(ds.read(1)).tolist())
    valid = set(ESRI_VALID) if name.startswith("lulc_esri") else WORLDCOVER_CODES
    extra = codes - valid - {0}
    assert not extra, f"{name}: unexpected codes {sorted(extra)}"


def test_slope_range():
    with rasterio.open(RASTERS["slope.tif"]) as ds:
        s = ds.read(1)
        s = s[s != ds.nodata]
    assert s.min() >= 0 and s.max() <= 90, f"slope {s.min()}..{s.max()}"


def test_elevation_plausible():
    lo, hi = cfg["qa"]["elevation_range_m"]
    with rasterio.open(RASTERS["elevation.tif"]) as ds:
        z = ds.read(1)
        z = z[z != ds.nodata]
    assert (
        lo <= z.min() and z.max() <= hi
    ), f"elevation {z.min():.0f}..{z.max():.0f} outside [{lo}, {hi}]"


@pytest.mark.parametrize("name", sorted(EXPECTED_RASTERS))
def test_nodata_inside_aoi_below_5_percent(name):
    with rasterio.open(RASTERS[name]) as ds:
        a = ds.read(1)
        inside = ~geometry_mask(cfg.aoi_projected.geometry, a.shape, ds.transform)
        share = float((a[inside] == ds.nodata).mean())
    assert share < 0.05, f"{name}: {share:.1%} nodata inside the AOI"


@pytest.mark.parametrize("snapshot", sorted(snapshots(cfg)))
def test_c6_buildings_contract(snapshot):
    """FR-3.6: buildings joined to grid cells form contract C6."""
    path = schema.contract_path(cfg, "C6", snapshot=snapshot)
    assert path.exists(), f"{path} missing"
    c6 = schema.read_contract(path, "C6")
    assert c6.crs == cfg.crs, f"{snapshot}: C6 CRS {c6.crs}"
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    bad = int((~c6["cell_id"].isin(grid["cell_id"])).sum())
    assert bad == 0, f"{snapshot}: {bad} C6 buildings are not in an analysis grid cell"
