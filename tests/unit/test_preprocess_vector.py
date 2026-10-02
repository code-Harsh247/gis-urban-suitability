"""Unit tests for vector preprocessing (P3.4–P3.6): roads, water, buildings, C6."""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, MultiPolygon, Polygon, box

from src.features import schema
from src.features.grid import build_grid, lattice
from src.preprocess import raster as pr
from src.preprocess import vector as pv
from src.synthetic import make_synthetic_project


@pytest.fixture
def cfg(tmp_path):
    cfg = make_synthetic_project(tmp_path / "proj", n=10)
    ref = pr.build_reference_grid(cfg)
    pr.processed_dir(cfg).mkdir(parents=True, exist_ok=True)
    pr.reference_grid_path(cfg).write_text(json.dumps(ref.to_json()))
    return cfg


def _to_ll(cfg, geom):
    t = Transformer.from_crs(cfg.crs, 4326, always_xy=True).transform
    return shapely.ops.transform(t, geom)


def _aoi_xy(cfg, dx=0.0, dy=0.0):
    """A point dx, dy metres from the AOI's south-west corner (project CRS)."""
    x0, y0, _, _ = cfg.aoi_projected.total_bounds
    return x0 + dx, y0 + dy


# ---------------------------------------------------------------- roads


@pytest.mark.parametrize(
    ("tag", "keep_tracks", "expected"),
    [
        ("motorway", False, "major"),
        ("trunk_link", False, "major"),
        ("secondary", False, "major"),
        ("primary;secondary", False, "major"),
        ("tertiary", False, "minor"),
        ("residential", False, "minor"),
        ("service", False, "minor"),
        ("track", False, None),
        ("track", True, "minor"),
        ("footway", False, None),
        ("construction", False, None),
    ],
)
def test_road_classes(tag, keep_tracks, expected):
    got = pv.classify_roads(pd.Series([tag]), keep_tracks).iloc[0]
    assert got == expected


def test_clean_roads_clips_reprojects_and_drops_paths(cfg):
    x, y = _aoi_xy(cfg, 200, 200)
    ext = pv.reference_extent(cfg)
    far = ext.bounds[2] + 5000
    lines = [
        LineString([(x, y), (x + 500, y)]),  # inside
        LineString([(x, y + 100), (far, y + 100)]),  # crosses the extent edge
        LineString([(far, y), (far + 100, y)]),  # outside
        LineString([(x, y + 200), (x + 300, y + 200)]),  # footway
    ]
    raw = gpd.GeoDataFrame(
        {
            "osm_type": "way",
            "osm_id": [1, 2, 3, 4],
            "highway": ["primary", "residential", "residential", "footway"],
        },
        geometry=[_to_ll(cfg, g) for g in lines],
        crs=4326,
    )
    out, stats = pv.clean_roads(cfg, raw, ext)
    assert out.crs == cfg.crs
    assert set(out["osm_id"]) == {1, 2}
    assert set(out["road_class"]) == {"major", "minor"}
    assert stats["outside_extent"] == 1 and stats["not_drivable"] == 1
    assert out.geometry.within(ext.buffer(1e-6)).all()  # clipped
    assert (out.geom_type == "LineString").all()
    assert out.loc[out["osm_id"] == 1].length.iloc[0] == pytest.approx(500, rel=1e-3)


# ---------------------------------------------------------------- generic cleaning


def test_invalid_polygon_is_made_valid(cfg):
    x, y = _aoi_xy(cfg, 300, 300)
    bowtie = Polygon([(x, y), (x + 20, y + 20), (x + 20, y), (x, y + 20), (x, y)])
    assert not bowtie.is_valid
    raw = gpd.GeoDataFrame({"osm_id": [1]}, geometry=[_to_ll(cfg, bowtie)], crs=4326)
    out, stats = pv.clean_geometries(raw, cfg.crs, pv.reference_extent(cfg), pv.POLY_TYPES)
    assert stats["made_valid"] == 1
    assert out.geometry.is_valid.all() and len(out) == 1
    assert out.area.iloc[0] == pytest.approx(200, rel=1e-2)  # two 10 m² × 20 m triangles


def test_non_matching_parts_are_dropped(cfg):
    x, y = _aoi_xy(cfg, 300, 300)
    raw = gpd.GeoDataFrame(
        {"osm_id": [1]}, geometry=[_to_ll(cfg, LineString([(x, y), (x + 9, y)]))], crs=4326
    )
    out, stats = pv.clean_geometries(raw, cfg.crs, pv.reference_extent(cfg), pv.POLY_TYPES)
    assert len(out) == 0 and stats["empty_after_clip"] == 1


# ---------------------------------------------------------------- water


def test_water_kinds(cfg):
    x, y = _aoi_xy(cfg, 400, 400)
    raw = gpd.GeoDataFrame(
        {
            "osm_id": [1, 2, 3],
            "natural": ["water", None, "wood"],
            "waterway": [None, "stream", None],
        },
        geometry=[
            _to_ll(cfg, box(x, y, x + 50, y + 50)),
            _to_ll(cfg, LineString([(x, y), (x, y + 300)])),
            _to_ll(cfg, box(x + 100, y, x + 150, y + 50)),  # not water
        ],
        crs=4326,
    )
    out, stats = pv.clean_water(cfg, raw, pv.reference_extent(cfg))
    assert sorted(out["kind"]) == ["water_body", "waterway"]
    lake = out.loc[out["kind"] == "water_body"]
    assert lake.area.iloc[0] == pytest.approx(2500, rel=1e-3)
    assert "km2_water_bodies" in stats


# ---------------------------------------------------------------- buildings + C6


def _buildings(cfg):
    x, y = _aoi_xy(cfg, 250, 250)
    geoms = [
        MultiPolygon([box(x, y, x + 10, y + 10)]),  # 100 m², single-part multipolygon
        MultiPolygon([box(x + 30, y, x + 33, y + 3)]),  # 9 m²: too small
        MultiPolygon([box(x + 50, y, x + 60, y + 10), box(x + 70, y, x + 80, y + 10)]),  # 2 parts
        MultiPolygon([box(x - 2000, y - 2000, x - 1990, y - 1990)]),  # in the buffer, not the AOI
    ]
    return gpd.GeoDataFrame(
        {"osm_type": "way", "osm_id": [10, 11, 12, 13], "building": ["house", "yes", None, "yes"]},
        geometry=[_to_ll(cfg, g) for g in geoms],
        crs=4326,
    )


def test_clean_buildings(cfg):
    out, stats = pv.clean_buildings(cfg, _buildings(cfg), pv.reference_extent(cfg))
    assert stats["too_small"] == 1 and set(out["osm_id"]) == {10, 12, 13}
    house = out.loc[out["osm_id"] == 10].iloc[0]
    assert house.geometry.geom_type == "Polygon"  # single-part multipolygon unwrapped
    assert house["area_m2"] == pytest.approx(100, rel=1e-3)
    assert out.loc[out["osm_id"] == 12, "geometry"].iloc[0].geom_type == "MultiPolygon"
    assert out.loc[out["osm_id"] == 12, "building_type"].iloc[0] == "yes"  # missing tag -> yes
    lat = lattice(cfg)
    r, c = lat.xy_to_rowcol(house["cx"], house["cy"])
    assert house["cell_id"] == r * lat.shape[1] + c
    assert list(out["bldg_id"]) == list(range(len(out)))


def test_building_area_limits_from_config(cfg):
    from dataclasses import replace

    raw = {**cfg.raw, "vector": {**cfg["vector"], "building_max_area_m2": 150}}
    out, stats = pv.clean_buildings(
        replace(cfg, raw=raw), _buildings(cfg), pv.reference_extent(cfg)
    )
    assert stats["too_large"] == 1  # the 200 m² two-part building
    assert 12 not in set(out["osm_id"])


def test_c6_keeps_only_grid_cells(cfg):
    out, _ = pv.clean_buildings(cfg, _buildings(cfg), pv.reference_extent(cfg))
    grid_ids = set(build_grid(cfg)["cell_id"])
    c6 = pv.write_c6(cfg, out, "2018", grid_ids)
    schema.validate_frame(c6, "C6")
    assert set(c6["osm_id"]) == {10, 12}  # the buffer building is not in an AOI cell
    back = gpd.read_file(schema.contract_path(cfg, "C6", snapshot="2018"))
    assert len(back) == 2 and back.crs == cfg.crs


def test_buildings_sorted_deterministically(cfg):
    raw = _buildings(cfg)
    a, _ = pv.clean_buildings(cfg, raw, pv.reference_extent(cfg))
    b, _ = pv.clean_buildings(cfg, raw.sample(frac=1, random_state=3), pv.reference_extent(cfg))
    assert a["osm_id"].tolist() == b["osm_id"].tolist()
    assert np.allclose(a["area_m2"], b["area_m2"])
