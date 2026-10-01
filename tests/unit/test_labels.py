"""Unit tests for A4: exclusion mask, growth labels (C5), LEI growth type."""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from shapely.geometry import box

from src.download.osm import osm_path
from src.features import labels, schema
from src.features.grid import lattice
from src.preprocess import raster as pr
from src.synthetic import make_synthetic_project

YEARS = range(2018, 2024)


def _write(path, arr, ref, nodata):
    with rasterio.open(path, "w", **ref.profile(str(arr.dtype), nodata)) as dst:
        dst.write(arr, 1)


class Stack:
    """6-year synthetic LULC on the reference grid, with planted cases (cell = 10 px)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.ref = pr.build_reference_grid(cfg)
        self.lat_c0 = int(cfg["aoi"]["buffer_m"] // cfg.cell_size_m)  # first AOI cell
        self.lulc = {y: np.full(self.ref.shape, 11, dtype=np.uint8) for y in YEARS}
        self.slope = np.full(self.ref.shape, 2.0, dtype="float32")

    def px(self, r, c):
        """Pixel slice of AOI-relative cell (r, c)."""
        r0, c0 = (self.lat_c0 + r) * 10, (self.lat_c0 + c) * 10
        return slice(r0, r0 + 10), slice(c0, c0 + 10)

    def set(self, r, c, code, years, frac=1.0):
        rs, cs = self.px(r, c)
        n = int(round(frac * 10))
        for y in years:
            self.lulc[y][rs.start : rs.start + n, cs] = code

    def cell_id(self, r, c):
        lat = lattice(self.cfg)
        return (self.lat_c0 + r) * lat.shape[1] + (self.lat_c0 + c)

    def box_4326(self, r, c):
        left = self.ref.transform.c + (self.lat_c0 + c) * 100
        top = self.ref.transform.f - (self.lat_c0 + r) * 100
        g = gpd.GeoSeries([box(left + 1, top - 99, left + 99, top - 1)], crs=self.ref.crs)
        return g.to_crs(4326).iloc[0]

    def write(self):
        out = pr.processed_dir(self.cfg)
        out.mkdir(parents=True, exist_ok=True)
        pr.reference_grid_path(self.cfg).write_text(json.dumps(self.ref.to_json()))
        for y, arr in self.lulc.items():
            _write(out / f"lulc_esri_{y}.tif", arr, self.ref, 0)
        _write(out / "slope.tif", self.slope, self.ref, -9999.0)


def _osm(cfg, snapshot, layer, geoms, **cols):
    p = osm_path(cfg, snapshot, layer)
    p.parent.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame(cols, geometry=geoms, crs=4326).to_file(p, driver="GPKG")


@pytest.fixture
def stack(tmp_path):
    cfg = make_synthetic_project(tmp_path / "proj", n=10)
    s = Stack(cfg)
    for r in range(4):
        for c in range(4):
            s.set(r, c, 7, YEARS)  # old built block
    s.set(4, 1, 7, range(2020, 2024))  # adjacent growth from 2020 (change-train positive)
    s.set(8, 8, 7, range(2022, 2024))  # outlying growth
    s.set(6, 2, 7, [2019])  # built only in 2019 -> not a candidate
    s.set(6, 4, 7, [2023])  # built only in 2023 -> ambiguous
    s.set(6, 6, 7, [2022, 2023], frac=0.3)  # partly built -> ambiguous
    s.set(2, 8, 1, [2018])  # water in 2018 only
    s.set(3, 8, 1, [2023])  # water in 2023 only
    rs, cs = s.px(5, 8)
    s.slope[rs, cs] = 20.0  # steep
    s.write()
    _osm(cfg, "2018", "water", [s.box_4326(7, 0)], natural=["water"])
    _osm(cfg, "current", "water", [s.box_4326(7, 0), s.box_4326(7, 1)], natural=["water", "water"])
    _osm(cfg, "current", "protected", [s.box_4326(9, 0)], boundary=["national_park"])
    return s


def _row(df, s, r, c):
    return df.set_index("cell_id").loc[s.cell_id(r, c)]


def test_labels_contract_and_invariants(stack):
    df = labels.build_labels(stack.cfg)
    schema.validate_frame(df, "C5")
    assert not (df["candidate"] & df["excluded"]).any()
    assert not (df["grew"] & ~df["candidate"]).any()
    assert not (df["ambiguous"] & (df["grew"] | ~df["candidate"])).any()
    assert not (df["chg_train_pos"] & ~df["candidate"]).any()
    assert (df.loc[df["grew"], "lei_type"] != "none").all()
    assert (df.loc[~df["grew"], "lei_type"] == "none").all()


def test_growth_cases(stack):
    df = labels.build_labels(stack.cfg)
    s = stack
    assert _row(df, s, 1, 1)["built_baseline"] and not _row(df, s, 1, 1)["candidate"]
    adj = _row(df, s, 4, 1)
    assert adj["grew"] and adj["chg_train_pos"] and adj["lei_type"] == "adjacent"
    out = _row(df, s, 8, 8)
    assert out["grew"] and not out["chg_train_pos"] and out["lei_type"] == "outlying"
    assert not _row(df, s, 6, 2)["candidate"]  # built in 2019 -> not non-built at start
    for r, c in ((6, 4), (6, 6)):
        row = _row(df, s, r, c)
        assert row["candidate"] and not row["grew"] and row["ambiguous"]
    plain = _row(df, s, 9, 9)
    assert plain["candidate"] and not plain["grew"] and not plain["ambiguous"]


def test_validation_mask_never_uses_later_data(stack):
    """Time-travel rule: 2023 water and current-only OSM water don't exclude in validation."""
    val = labels.exclusion_table(stack.cfg, "validation").set_index("cell_id")
    fin = labels.exclusion_table(stack.cfg, "final").set_index("cell_id")
    s = stack
    assert val.loc[s.cell_id(2, 8), "excl_wet"] and not fin.loc[s.cell_id(2, 8), "excl_wet"]
    assert not val.loc[s.cell_id(3, 8), "excl_wet"] and fin.loc[s.cell_id(3, 8), "excl_wet"]
    assert (
        val.loc[s.cell_id(7, 0), "excl_wet"] and fin.loc[s.cell_id(7, 0), "excl_wet"]
    )  # OSM 2018 lake
    assert (
        not val.loc[s.cell_id(7, 1), "excl_wet"] and fin.loc[s.cell_id(7, 1), "excl_wet"]
    )  # current only
    for t in (val, fin):  # static layers apply to both runs
        assert t.loc[s.cell_id(5, 8), "excl_slope"]
        assert t.loc[s.cell_id(9, 0), "excl_protected"]
    assert val.attrs["sources"] == {
        "lulc_years": [2018, 2019],
        "osm_water": "2018",
        "protected": "current",
    }
    assert fin.attrs["sources"]["lulc_years"] == [2022, 2023]


def test_changing_2023_does_not_change_validation_labels_inputs(stack):
    """Overwriting the 2020-2023 maps must not change the validation mask."""
    before = labels.exclusion_table(stack.cfg, "validation")
    for y in (2020, 2021, 2022, 2023):
        stack.lulc[y][:] = 1  # everything water
    stack.write()
    after = labels.exclusion_table(stack.cfg, "validation")
    assert before["excluded"].equals(after["excluded"])


def test_missing_osm_layers_are_skipped(stack, caplog):
    for snap, layer in (("2018", "water"), ("current", "water"), ("current", "protected")):
        osm_path(stack.cfg, snap, layer).unlink()
    with caplog.at_level("WARNING"):
        t = labels.exclusion_table(stack.cfg, "validation").set_index("cell_id")
    assert not t.loc[stack.cell_id(9, 0), "excl_protected"]
    assert not t.loc[stack.cell_id(7, 0), "excl_wet"]
    assert "protected areas missing" in caplog.text
    assert t.attrs["sources"]["osm_water"] is None


def test_lei_patch_ring_logic(stack):
    """A patch is adjacent only if its 20 m ring touches baseline built-up."""
    types = labels.lei_cell_types(stack.cfg, {y: a == 7 for y, a in stack.lulc.items()})
    c0 = stack.lat_c0
    assert types[c0 + 4, c0 + 1] == "adjacent"
    assert types[c0 + 8, c0 + 8] == "outlying"
    assert types[c0 + 9, c0 + 9] == "none"


def test_write_labels_outputs(stack):
    df = labels.write_labels(stack.cfg)
    assert schema.contract_path(stack.cfg, "C5").exists()
    for run in labels.RUNS:
        assert (schema.contract_path(stack.cfg, "C5").parent / f"exclusion_{run}.parquet").exists()
    c = df.attrs["counts"]
    assert c["grew"] == 2 and c["ambiguous"] == 2 and c["chg_train_pos"] == 1
    assert c["lei_adjacent"] == 1 and c["lei_outlying"] == 1


def test_run_name_is_checked(stack):
    with pytest.raises(ValueError, match="run must be"):
        labels.exclusion_table(stack.cfg, "future")
