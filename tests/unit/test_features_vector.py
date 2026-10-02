"""Unit tests for P4.4–P4.5: road distances, road density, building metrics (C3)."""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, box

from src.features import distance as fd
from src.features import schema
from src.features.grid import Lattice, build_grid, lattice
from src.preprocess import raster as pr
from src.preprocess.vector import processed_osm_path
from src.synthetic import make_synthetic_project

# ---------------------------------------------------------------- pure functions


def test_nearest_line_distance_exact_and_capped():
    lines = [LineString([(0, 0), (1000, 0)])]
    xs = np.array([500.0, 500.0, 1300.0, 500.0])
    ys = np.array([0.0, 120.0, 400.0, 5000.0])
    d = fd.nearest_line_distance(lines, xs, ys, cap_m=3000.0)
    np.testing.assert_allclose(d, [0.0, 120.0, 500.0, 3000.0])


def test_nearest_line_distance_no_lines():
    d = fd.nearest_line_distance([], np.array([1.0]), np.array([2.0]), cap_m=3000.0)
    assert d[0] == 3000.0


def _toy_lattice(n=21, cell=100.0):
    from affine import Affine

    ref = pr.ReferenceGrid(
        None, Affine(10.0, 0, 0.0, 0, -10.0, n * cell), int(n * cell / 10), int(n * cell / 10), cell
    )
    return Lattice(ref, cell)


def test_road_length_per_cell_conserves_length():
    lat = _toy_lattice()
    road = LineString([(55.0, 1050.0), (2045.0, 1050.0)])  # along row 10
    per = fd.road_length_per_cell([road], lat)
    assert per.sum() == pytest.approx(road.length, rel=1e-9)
    assert per[10].sum() == pytest.approx(road.length, rel=1e-9)  # all in row 10
    assert per[10, 1:20] == pytest.approx(100.0, rel=1e-6)  # full cells get exactly 100 m


def test_road_density_straight_road():
    """A road along a full row: the centre cell's 500 m disk holds 11 cells of that row."""
    lat = _toy_lattice()
    per = fd.road_length_per_cell([LineString([(0.0, 1050.0), (2100.0, 1050.0)])], lat)
    dens = fd.road_density(per, 500.0, 100.0)
    k = fd.disk_kernel(500.0, 100.0)
    assert k.sum() == 81  # cells whose centres are within 500 m
    assert dens[10, 10] == pytest.approx(1.1 / (81 * 0.01), rel=1e-6)  # 1.1 km / 0.81 km²
    assert dens[0, 10] == 0.0  # > 500 m from the road


def test_road_density_edge_normalised_by_cells_on_lattice():
    lat = _toy_lattice()
    per = np.full(lat.shape, 100.0)  # 100 m of road in every cell
    dens = fd.road_density(per, 500.0, 100.0)
    np.testing.assert_allclose(dens, 10.0)  # 0.1 km per 0.01 km² everywhere, edges included


# ---------------------------------------------------------------- C3 on a synthetic project


@pytest.fixture
def cfg(tmp_path):
    cfg = make_synthetic_project(tmp_path / "proj", n=10)
    ref = pr.build_reference_grid(cfg)
    pr.processed_dir(cfg).mkdir(parents=True, exist_ok=True)
    pr.reference_grid_path(cfg).write_text(json.dumps(ref.to_json()))
    lat = lattice(cfg)
    grid = build_grid(cfg)
    g0 = grid.iloc[0]  # first AOI cell
    cx, cy = g0.x, g0.y
    roads = gpd.GeoDataFrame(
        {"road_class": ["major", "minor"]},
        geometry=[
            LineString([(cx - 3000, cy), (cx + 3000, cy)]),  # major through the cell centre row
            LineString([(cx + 250, cy - 3000), (cx + 250, cy + 3000)]),  # minor 250 m east
        ],
        crs=cfg.crs,
    )
    bld = gpd.GeoDataFrame(
        {"cell_id": [int(g0.cell_id)] * 3, "area_m2": [1000.0, 2000.0, 9500.0]},
        geometry=[box(cx, cy, cx + 1, cy + 1)] * 3,
        crs=cfg.crs,
    )
    for snap in ("2018", "current"):
        for layer, gdf in (("roads", roads), ("buildings", bld)):
            p = processed_osm_path(cfg, snap, layer)
            p.parent.mkdir(parents=True, exist_ok=True)
            gdf.to_file(p, driver="GPKG")
    return cfg, lat, grid


def test_c3_values(cfg):
    cfg, lat, grid = cfg
    df = fd.vector_features(cfg, "2018").set_index("cell_id")
    schema.validate_frame(df.reset_index(), "C3")
    g0 = grid.iloc[0]
    row = df.loc[g0.cell_id]
    assert np.expm1(row["log_dist_major"]) == pytest.approx(0.0, abs=1e-9)  # on the major road
    assert np.expm1(row["log_dist_any"]) == pytest.approx(0.0, abs=1e-9)
    assert row["bldg_count"] == 3
    assert row["bldg_area_frac"] == 1.0  # 12,500 m² > one cell, capped
    other = df.drop(index=g0.cell_id)
    assert (other["bldg_count"] == 0).all()
    # the cell 3 rows south (300 m) of the major road, in the same column: 300 m to the
    # major road, 250 m to the minor road running north-south 250 m east
    south = grid[(grid["col"] == g0.col) & (grid["row"] == g0.row + 3)]
    assert len(south) == 1, "test cell must be inside the AOI"
    assert np.expm1(df.loc[south.cell_id.iloc[0], "log_dist_major"]) == pytest.approx(300.0)
    assert np.expm1(df.loc[south.cell_id.iloc[0], "log_dist_any"]) == pytest.approx(250.0)


def test_c3_written_for_both_snapshots(cfg):
    cfg, _, _ = cfg
    out = fd.write_vector_features(cfg)
    assert set(out) == {"2018", "current"}
    for snap in out:
        assert schema.contract_path(cfg, "C3", snapshot=snap).exists()


def test_leaky_building_columns_are_flagged():
    assert {"bldg_count", "bldg_area_frac"} <= set(schema.LEAKY_FEATURES)
    assert not {"bldg_count", "bldg_area_frac"} & set(schema.MODEL_INPUTS)
