"""Unit tests for A3: grid (C1), fractions, rings, distances, raster features (C2), merge (C4)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import rasterio

from src.features import build, schema
from src.features.context import ring_mean
from src.features.grid import build_grid, grid_geodataframe, lattice, write_grid, xy_to_cell_id
from src.features.lulc_features import class_fractions
from src.features.proximity import dist_to_class, dist_to_class_outside_cell
from src.features.raster_features import raster_features, write_raster_features
from src.preprocess import raster as pr
from src.synthetic import make_synthetic_project

# ---------------------------------------------------------------- fixtures


def _write_on_grid(path, arr, ref, nodata):
    with rasterio.open(path, "w", **ref.profile(str(arr.dtype), nodata)) as dst:
        dst.write(arr, 1)


@pytest.fixture
def raster_project(tmp_path):
    """Synthetic project + processed rasters on its reference grid.

    LULC: rangeland everywhere, a built square in the north-west, a water square
    in the south-east. Elevation rises to the east (slope known).
    """
    cfg = make_synthetic_project(tmp_path / "proj", n=10)
    ref = pr.build_reference_grid(cfg)
    out = pr.processed_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    pr.reference_grid_path(cfg).write_text(json.dumps(ref.to_json()))
    lulc = np.full(ref.shape, 11, dtype=np.uint8)
    a0 = int(cfg["aoi"]["buffer_m"] // 10)  # first AOI pixel row/col (grid edge = buffer)
    lulc[a0 + 30 : a0 + 90, a0 + 30 : a0 + 90] = 7  # built block: whole cells, inside the AOI
    lulc[-90:-50, -90:-50] = 1  # water block
    for y in (cfg["years"]["baseline"], cfg["years"]["latest"]):
        _write_on_grid(out / f"lulc_esri_{y}.tif", lulc, ref, 0)
    cols = np.indices(ref.shape)[1]
    _write_on_grid(out / "elevation.tif", (800 + 0.1 * cols * 10.0).astype("float32"), ref, -9999.0)
    _write_on_grid(out / "slope.tif", np.full(ref.shape, 5.71, dtype="float32"), ref, -9999.0)
    return cfg, ref, lulc


# ---------------------------------------------------------------- grid (C1)


def test_grid_cells_have_centres_in_aoi_and_unique_ids(raster_project):
    cfg, _, _ = raster_project
    grid = build_grid(cfg)
    schema.validate_frame(grid, "C1")
    assert grid["cell_id"].is_unique
    import shapely

    aoi = cfg.aoi_projected.geometry.iloc[0]
    assert shapely.contains_xy(aoi, grid["x"], grid["y"]).all()
    assert len(grid) == pytest.approx(cfg.aoi_area_km2 * 100, rel=0.05)  # 1 ha cells


def test_grid_polygons_are_whole_cells_on_the_reference_grid(raster_project):
    cfg, ref, _ = raster_project
    gdf = grid_geodataframe(build_grid(cfg), cfg)
    assert np.allclose(gdf.area, cfg.cell_size_m**2)
    b = gdf.bounds
    assert np.allclose(((b["minx"] - ref.transform.c) / cfg.cell_size_m) % 1, 0)
    assert np.allclose(((ref.transform.f - b["maxy"]) / cfg.cell_size_m) % 1, 0)


def test_xy_to_cell_id_round_trip(raster_project):
    cfg, _, _ = raster_project
    grid = build_grid(cfg)
    ids = xy_to_cell_id(cfg, grid["x"] + 49.0, grid["y"] - 49.0)  # anywhere inside the cell
    np.testing.assert_array_equal(ids, grid["cell_id"])
    assert xy_to_cell_id(cfg, [0.0], [0.0])[0] == -1


# ---------------------------------------------------------------- fractions


def test_class_fractions_sum_to_one_and_ignore_nodata_and_cloud():
    lulc = np.zeros((20, 20), dtype=np.uint8)
    lulc[:10, :10] = 7  # cell (0,0): all built
    lulc[:10, 10:] = 2
    lulc[:10, 10:15] = 10  # cell (0,1): half cloud, half trees
    lulc[10:, :] = 0  # cells (1,*): nodata
    f = class_fractions(lulc, 10)
    assert f["frac_built"][0, 0] == 1.0
    assert f["frac_tree"][0, 1] == 1.0 and f["nodata_frac"][0, 1] == 0.5
    assert (f["nodata_frac"][1] == 1.0).all()
    total = sum(v for k, v in f.items() if k.startswith("frac_"))
    assert np.allclose(total[0], 1.0) and np.allclose(total[1], 0.0)


# ---------------------------------------------------------------- rings


def test_ring_excludes_centre_cell():
    v = np.zeros((11, 11))
    v[5, 5] = 1.0
    r = ring_mean(v, 100, 100)  # 3x3 window
    assert r[5, 5] == 0.0  # own value never counts
    assert r[4, 4] == pytest.approx(1 / 8) and r[5, 6] == pytest.approx(1 / 8)
    assert r[2, 2] == 0.0


def test_ring_of_constant_field_and_edges():
    v = np.full((8, 8), 0.3)
    np.testing.assert_allclose(ring_mean(v, 200, 100), 0.3)  # edges average only real cells


def test_ring_radius_must_cover_a_cell():
    with pytest.raises(ValueError):
        ring_mean(np.zeros((3, 3)), 40, 100)


# ---------------------------------------------------------------- distances


def _brute_outside(mask, rows, cols, cell_m=100.0, px=10.0, cap=5000.0):
    r, c = np.nonzero(mask)
    xs, ys = (c + 0.5) * px, -(r + 0.5) * px
    pr_, pc_ = (r * px) // cell_m, (c * px) // cell_m
    out = []
    for row, col in zip(rows, cols, strict=True):
        cx, cy = (col + 0.5) * cell_m, -(row + 0.5) * cell_m
        keep = (pr_ != row) | (pc_ != col)
        d = np.hypot(xs[keep] - cx, ys[keep] - cy)
        out.append(min(d.min(), cap) if d.size else cap)
    return np.array(out)


def test_outside_cell_distance_ignores_own_pixels():
    mask = np.zeros((50, 50), bool)
    mask[0:10, 0:10] = True  # cell (0,0) fully built
    mask[0, 25] = True  # one pixel in cell (0,2), centre at (255, -5)
    d = dist_to_class_outside_cell(
        mask, 0.0, 0.0, 10.0, 100.0, np.array([0, 0, 4]), np.array([0, 2, 4]), 5000.0
    )
    # cell (0,0): own pixels ignored -> nearest is the pixel at (255,-5): hypot(205, 45)
    assert d[0] == pytest.approx(np.hypot(205, 45))
    # cell (0,2), centre (250,-50): own pixel ignored -> nearest outside is (95,-45)
    # in cell (0,0): hypot(155, 5)
    assert d[1] == pytest.approx(np.hypot(155, 5))
    assert d[2] == pytest.approx(np.hypot(450 - 255, 450 - 5))


def test_outside_cell_distance_matches_brute_force():
    rng = np.random.default_rng(3)
    mask = rng.random((60, 60)) < 0.03
    rows, cols = np.indices((6, 6))
    rows, cols = rows.ravel(), cols.ravel()
    got = dist_to_class_outside_cell(mask, 0.0, 0.0, 10.0, 100.0, rows, cols, 5000.0)
    np.testing.assert_allclose(got, _brute_outside(mask, rows, cols))


def test_only_own_pixels_gives_cap():
    mask = np.zeros((30, 30), bool)
    mask[10:20, 10:20] = True
    d = dist_to_class_outside_cell(
        mask, 0.0, 0.0, 10.0, 100.0, np.array([1]), np.array([1]), 5000.0
    )
    assert d[0] == 5000.0


def test_dist_to_class_plain():
    mask = np.zeros((10, 10), bool)
    mask[0, 0] = True  # centre (5, -5)
    d = dist_to_class(mask, 0.0, 0.0, 10.0, np.array([5.0, 35.0]), np.array([-5.0, -45.0]), 5000.0)
    np.testing.assert_allclose(d, [0.0, 50.0])


# ---------------------------------------------------------------- raster features (C2)


def test_raster_features_contract_and_values(raster_project):
    cfg, ref, lulc = raster_project
    year = cfg["years"]["baseline"]
    df = raster_features(cfg, year)
    schema.validate_frame(df, "C2")
    grid = build_grid(cfg)
    assert df["cell_id"].equals(grid["cell_id"])
    fr = df[list(schema.OWN_FRACTIONS)].sum(axis=1)
    assert np.allclose(fr, 1.0)
    assert np.allclose(df["slope_mean"], 5.71, atol=1e-4)
    # elevation rises 1 m per 10 m eastward -> cell mean = elevation at the cell centre
    lat = lattice(cfg)
    exp = 800 + 0.1 * (grid["col"] * 10 + 4.5) * 10.0
    np.testing.assert_allclose(df["elev_mean"], exp, atol=1e-3)
    assert lat.px_per_cell == 10


def test_built_cell_distance_is_outside_cell(raster_project):
    """Inside a solid built block, the nearest *outside* built pixel is in the next cell."""
    cfg, _, lulc = raster_project
    df = raster_features(cfg, cfg["years"]["baseline"]).set_index("cell_id")
    lat = lattice(cfg)
    # built block covers whole cells c0+3 .. c0+8 (c0 = first AOI cell) in both directions
    c0 = int(cfg["aoi"]["buffer_m"] // cfg.cell_size_m)
    for r, c in ((c0 + 5, c0 + 5), (c0 + 6, c0 + 4)):
        cid = r * lat.shape[1] + c
        assert cid in df.index, "test cell must be inside the AOI"
        assert df.loc[cid, "frac_built"] == 1.0
        # nearest outside pixel centre: 5 m beyond the cell edge (55 m) and, since the cell
        # centre lies between pixel centres, 5 m off-axis -> hypot(55, 5)
        assert np.expm1(df.loc[cid, "log_dist_built"]) == pytest.approx(np.hypot(55, 5))
    # a cell far from any built pixel: distance >= its offset from the block
    far = df["frac_built"] == 0
    assert (np.expm1(df.loc[far, "log_dist_built"]) > 0).all()


def test_distance_cap_cannot_exceed_buffer(raster_project):
    from dataclasses import replace

    from src.features.raster_features import check_distance_cap

    cfg, _, _ = raster_project
    raw = {**cfg.raw, "features": {**cfg["features"], "distance_cap_m": cfg["aoi"]["buffer_m"] + 1}}
    with pytest.raises(ValueError, match="distance_cap_m"):
        check_distance_cap(replace(cfg, raw=raw))
    assert check_distance_cap(cfg) <= cfg["aoi"]["buffer_m"]


def test_write_raster_features_writes_c1_and_c2(raster_project):
    cfg, _, _ = raster_project
    # the synthetic stubs use their own 0..99 ids; drop them so only real C1/C2 are checked
    for d in ("data_features", "data_processed", "outputs"):
        for f in cfg.paths[d].rglob("*"):
            if f.suffix in (".parquet", ".gpkg", ".json") and f.name != "reference_grid.json":
                f.unlink()
    out = write_raster_features(cfg)
    assert set(out) == {cfg["years"]["baseline"], cfg["years"]["latest"]}
    checked = schema.validate_project(cfg)
    assert {"C1", "C2"} <= set(checked)
    assert schema.contract_path(cfg, "C1").with_suffix(".gpkg").exists()


# ---------------------------------------------------------------- merge (C4)


def test_build_merges_c2_and_c3_on_stubs(synthetic_project):
    year = synthetic_project["years"]["baseline"]
    df = build.build_feature_table(synthetic_project, year)
    schema.validate_frame(df, "C4")
    c2 = pd.read_parquet(schema.contract_path(synthetic_project, "C2", year=year))
    assert len(df) == len(c2)


def test_build_needs_c3(raster_project):
    cfg, _, _ = raster_project
    write_raster_features(cfg)
    for p in schema.contract_path(cfg, "C3", snapshot="x").parent.glob("vector_features_*.parquet"):
        p.unlink()
    with pytest.raises(FileNotFoundError, match="H3.3"):
        build.build_feature_table(cfg, cfg["years"]["baseline"])


def test_build_drops_high_nodata_cells(tmp_path):
    cfg = make_synthetic_project(tmp_path / "p", n=10)
    year = cfg["years"]["baseline"]
    p = schema.contract_path(cfg, "C2", year=year)
    c2 = pd.read_parquet(p)
    c2.loc[:4, "nodata_frac"] = 0.9
    c2.to_parquet(p, index=False)
    df = build.build_feature_table(cfg, year)
    assert len(df) == len(c2) - 5


def test_write_grid_matches_contract(raster_project):
    cfg, _, _ = raster_project
    grid = write_grid(cfg)
    assert schema.read_contract(schema.contract_path(cfg, "C1"), "C1").equals(grid)
