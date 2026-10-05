"""Phase 4 gate: grid and feature engineering (see docs/Tasks.md). Runs on the real data.

Checks contracts C1-C4 and, independently of the feature code, a few facts that must
hold if the features are right: the grid tiles the AOI, own-cell fractions sum to 1,
road distances match shapely, cells crossed by a major road are near it, the baseline
table uses the 2018 OSM snapshot (time-travel rule), and no own-cell or leaky column
can reach a model (D4).

Run: pytest tests/gates/test_phase4.py
Build first: python -m src.features.raster_features; python -m src.features.distance;
             python -m src.features.build
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely

from src.config import load_config
from src.download.osm import snapshots
from src.features import schema
from src.features.raster_features import features_years
from src.preprocess.vector import processed_osm_path

cfg = load_config()
YEARS = features_years(cfg)
SNAPSHOTS = list(snapshots(cfg))
BASELINE = int(cfg["years"]["baseline"])
CELL = float(cfg.cell_size_m)
CAP = float(cfg["features"]["distance_cap_m"])
MAX_NODATA = float(cfg["features"]["max_nodata_fraction"])


@pytest.fixture(scope="module")
def grid() -> pd.DataFrame:
    return schema.read_contract(schema.contract_path(cfg, "C1"), "C1")


@pytest.fixture(scope="module")
def c2() -> dict[int, pd.DataFrame]:
    return {y: schema.read_contract(schema.contract_path(cfg, "C2", year=y), "C2") for y in YEARS}


@pytest.fixture(scope="module")
def c3() -> dict[str, pd.DataFrame]:
    return {
        s: schema.read_contract(schema.contract_path(cfg, "C3", snapshot=s), "C3")
        for s in SNAPSHOTS
    }


@pytest.fixture(scope="module")
def c4() -> dict[int, pd.DataFrame]:
    return {y: schema.read_contract(schema.contract_path(cfg, "C4", year=y), "C4") for y in YEARS}


# ---------------------------------------------------------------- files and contracts


def test_feature_years_cover_both_runs():
    assert BASELINE in YEARS and int(cfg["years"]["latest"]) in YEARS


def test_all_contract_files_exist():
    paths = [schema.contract_path(cfg, "C1")]
    paths += [schema.contract_path(cfg, "C2", year=y) for y in YEARS]
    paths += [schema.contract_path(cfg, "C3", snapshot=s) for s in SNAPSHOTS]
    paths += [schema.contract_path(cfg, "C4", year=y) for y in YEARS]
    paths += [schema.contract_path(cfg, "C4", year=y).with_suffix(".gpkg") for y in YEARS]
    missing = [str(p) for p in paths if not p.exists()]
    assert not missing, f"missing: {missing}"


# ---------------------------------------------------------------- grid (C1)


def test_grid_ids_unique_and_spacing(grid):
    assert grid["cell_id"].is_unique
    assert np.allclose(np.diff(np.sort(grid["x"].unique())), CELL)
    assert np.allclose(np.diff(np.sort(grid["y"].unique())), CELL)


def test_grid_tiles_the_aoi(grid):
    """Cells whose centre is inside the AOI cover its area to within half a cell ring."""
    aoi = cfg.aoi_projected.geometry.iloc[0]
    assert shapely.contains_xy(aoi, grid["x"], grid["y"]).all()
    expected = aoi.area / CELL**2
    assert abs(len(grid) - expected) <= aoi.length / CELL, f"{len(grid)} vs {expected:.0f}"


# ---------------------------------------------------------------- feature table (C4)


@pytest.mark.parametrize("year", YEARS)
def test_rows_are_grid_minus_logged_drops(year, grid, c2, c4):
    df = c4[year]
    assert df["cell_id"].is_unique
    dropped = c2[year].loc[c2[year]["nodata_frac"] > MAX_NODATA, "cell_id"]
    assert len(df) == len(grid) - len(dropped)
    assert set(df["cell_id"]) == set(grid["cell_id"]) - set(dropped)


@pytest.mark.parametrize("year", YEARS)
def test_all_core_columns_present(year, c4):
    missing = set(schema.RASTER_FEATURES + schema.VECTOR_FEATURES) - set(c4[year].columns)
    assert not missing, f"missing columns: {sorted(missing)}"


@pytest.mark.parametrize("year", YEARS)
def test_own_fractions_sum_to_one(year, c4):
    df = c4[year]
    total = df[list(schema.OWN_FRACTIONS)].sum(axis=1)
    has_data = df["nodata_frac"] < 1.0
    assert np.allclose(total[has_data], 1.0, atol=0.01)


@pytest.mark.parametrize("year", YEARS)
def test_values_finite_in_range_and_rarely_missing(year, c4):
    df = c4[year]
    num = df.select_dtypes("number")
    assert np.isfinite(num.fillna(0).to_numpy()).all(), "infinite values"
    nan_share = num.isna().mean()
    assert (nan_share < 0.01).all(), f"NaN share >= 1 %: {nan_share[nan_share >= 0.01].to_dict()}"
    logs = [c for c in df.columns if c.startswith("log_dist_")]
    assert (df[logs] >= 0).all().all()
    assert (df[logs] <= np.log1p(CAP) + 1e-9).all().all(), "distance above features.distance_cap_m"
    assert df["slope_mean"].between(0, 90).all() and df["slope_max"].between(0, 90).all()
    assert (df["slope_mean"] <= df["slope_max"] + 1e-9).all()


# ---------------------------------------------------------------- leakage guards (D4)


def test_leaky_features_listed_and_never_model_inputs():
    assert {"frac_built", "bldg_count", "bldg_area_frac"} <= set(schema.LEAKY_FEATURES)
    banned = set(schema.LEAKY_FEATURES) | set(schema.OWN_CELL_FEATURES)
    assert not banned & set(schema.MODEL_INPUTS)
    schema.check_model_inputs(schema.MODEL_INPUTS)
    with pytest.raises(schema.ContractError):
        schema.check_model_inputs(["frac_built"])


def test_baseline_table_uses_2018_osm_snapshot(c3, c4):
    """Time-travel rule (D8): baseline-year road / building columns come from 2018 OSM."""
    snap = schema.vector_snapshot_for(cfg, BASELINE)
    assert snap != "current"
    merged = c4[BASELINE][["cell_id", *schema.VECTOR_FEATURES]].merge(
        c3[snap], on="cell_id", suffixes=("", "_c3")
    )
    for col in schema.VECTOR_FEATURES:
        assert np.allclose(merged[col], merged[f"{col}_c3"]), col
    # and it is genuinely different from today's OSM
    cur = c4[BASELINE].merge(c3["current"], on="cell_id", suffixes=("", "_cur"))
    assert not np.allclose(cur["log_dist_any"], cur["log_dist_any_cur"])


# ---------------------------------------------------------------- spot checks vs shapely


@pytest.mark.parametrize("snap", SNAPSHOTS)
def test_road_distances_match_shapely(snap, grid, c3):
    roads = gpd.read_file(processed_osm_path(cfg, snap, "roads"))
    assert roads.crs == cfg.crs
    major = shapely.union_all(roads.loc[roads["road_class"] == "major"].geometry.values)
    sample = grid.sample(300, random_state=1).merge(c3[snap], on="cell_id")
    pts = shapely.points(sample["x"], sample["y"])
    expected = np.minimum(shapely.distance(pts, major), CAP)
    got = np.expm1(sample["log_dist_major"].to_numpy())
    assert np.allclose(got, expected, atol=0.5), np.abs(got - expected).max()


@pytest.mark.parametrize("snap", SNAPSHOTS)
def test_cells_crossed_by_major_road_are_near_it(snap, grid, c3):
    roads = gpd.read_file(processed_osm_path(cfg, snap, "roads"))
    major = roads.loc[roads["road_class"] == "major"].geometry.values
    h = CELL / 2
    boxes = shapely.box(grid["x"] - h, grid["y"] - h, grid["x"] + h, grid["y"] + h)
    tree = shapely.STRtree(major)
    hit_idx = np.unique(tree.query(boxes, predicate="intersects")[0])
    assert len(hit_idx) > 100, "expected many cells on major roads"
    hits = grid.iloc[hit_idx][["cell_id"]].merge(c3[snap], on="cell_id")
    dist = np.expm1(hits["log_dist_major"].to_numpy())
    assert (dist <= CELL).all(), f"max {dist.max():.1f} m"


def test_osm_buildings_agree_with_esri_built(c4):
    """Two independent sources: cells full of OSM buildings are mostly ESRI built-up."""
    df = c4[int(cfg["years"]["latest"])]
    dense = df.loc[df["bldg_count"] >= 10, "frac_built"].mean()
    empty = df.loc[df["bldg_count"] == 0, "frac_built"].mean()
    assert dense > 0.8 and dense > empty + 0.3, (dense, empty)
