"""Unit tests for P5.4 / P5.5 (cluster -> class rules, exclusion applied last) and P5.8."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import rasterio

from src.classify import cluster as cl
from src.classify import label as lb
from src.features import schema
from src.features.grid import lattice
from src.preprocess import raster as pr
from src.synthetic import make_synthetic_project

B, F, U, X = lb.B, lb.F, lb.U, lb.X
RULES = {
    "water_threshold": 0.5,
    "built_threshold": 0.3,
    "forest_threshold": 0.5,
    "steep_natural_slope_deg": 8,
    "cropland_usable": True,
}


def _c(slope=3.0, **fr):
    row = {f"frac_{c}": 0.0 for c in schema.OWN_FRACTION_CLASSES}
    row.update({f"frac_{k}": v for k, v in fr.items()})
    row["slope_mean"] = slope
    return pd.Series(row)


@pytest.mark.parametrize(
    ("centroid", "expected", "flag"),
    [
        (_c(built=0.96), B, ""),
        (_c(water=0.8, built=0.1), X, ""),
        (_c(water=0.3, flooded=0.3), X, ""),  # water + flooded
        (_c(tree=0.87, range=0.08), F, ""),
        (_c(range=0.75, tree=0.13, slope=13.2), F, ""),  # steep rangeland: Bannerghatta hills
        (_c(range=0.88, slope=3.8), U, ""),  # flat rangeland
        (_c(crop=0.88, built=0.08), U, "agricultural"),
        (_c(crop=0.5, built=0.31, range=0.13), U, "agricultural"),  # mixed valley
        (_c(tree=0.4, range=0.2, crop=0.4, slope=12.0), F, ""),  # tree + range on slope
    ],
)
def test_cluster_rules(centroid, expected, flag):
    cls, _, f = lb.classify_cluster(centroid, RULES)
    assert cls == expected and f == flag


def test_built_needs_to_be_the_largest_land_group():
    """A share above the threshold alone must not make a crop-dominated cluster built-up."""
    assert lb.classify_cluster(_c(built=0.35, crop=0.55), RULES)[0] == U
    assert lb.classify_cluster(_c(built=0.55, crop=0.35), RULES)[0] == B


def test_cropland_can_be_excluded_by_config():
    rules = {**RULES, "cropland_usable": False}
    assert lb.classify_cluster(_c(crop=0.9), rules)[0] == X
    assert lb.classify_cluster(_c(range=0.9), rules)[0] == U  # only cropland is affected


@pytest.fixture
def cfg(tmp_path):
    cfg = make_synthetic_project(tmp_path / "proj", n=20)
    ref = pr.build_reference_grid(cfg)
    pr.processed_dir(cfg).mkdir(parents=True, exist_ok=True)
    pr.reference_grid_path(cfg).write_text(json.dumps(ref.to_json()))
    return cfg


def _cluster(cfg, run):
    res = cl.cluster_run(cfg, run, do_scan=False)
    p = cl.clusters_path(cfg, run)
    p.parent.mkdir(parents=True, exist_ok=True)
    res["assignments"].to_parquet(p, index=False)
    return res["assignments"]


def test_same_seed_same_labels(cfg):
    a = cl.cluster_run(cfg, "final", do_scan=False)["assignments"]
    b = cl.cluster_run(cfg, "final", do_scan=False)["assignments"]
    assert a.equals(b)


def test_exclusion_is_applied_last_and_unclustered_cells_are_excluded(cfg, monkeypatch):
    assign = _cluster(cfg, "final")
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    rules = lb.rule_table(cfg, "final", assign)
    usable_clusters = rules.index[rules["class_3"] == U]
    assert len(usable_clusters), "synthetic city should have usable land"
    usable_cells = assign.loc[assign["cluster_id"].isin(usable_clusters), "cell_id"]
    masked = set(usable_cells.iloc[:5]) | set(grid["cell_id"].iloc[:3])
    monkeypatch.setattr(
        lb,
        "exclusion_table",
        lambda cfg, run: pd.DataFrame(
            {"cell_id": grid["cell_id"], "excluded": grid["cell_id"].isin(masked)}
        ),
    )
    dropped = int(assign["cell_id"].iloc[-1])  # e.g. dropped for nodata
    assign.iloc[:-1].to_parquet(cl.clusters_path(cfg, "final"), index=False)

    c7, _, _ = lb.label_run(cfg, "final")
    schema.validate_frame(c7, "C7")
    assert set(c7["cell_id"]) == set(grid["cell_id"])
    assert (c7.loc[c7["cell_id"].isin(masked), "class_3"] == X).all()
    row = c7.set_index("cell_id").loc[dropped]
    assert row["cluster_id"] == -1 and row["class_3"] == X
    kept = c7.loc[~c7["cell_id"].isin(masked | {dropped})].merge(
        assign, on="cell_id", suffixes=("", "_fit")
    )
    assert (kept["cluster_id"] == kept["cluster_id_fit"]).all()
    assert (kept["class_3"] == kept["cluster_id"].map(rules["class_3"])).all()


def test_exclusion_mask_raster(cfg):
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    excl = pd.DataFrame({"cell_id": grid["cell_id"], "excluded": False})
    excl.loc[excl.index[:4], "excluded"] = True
    p = lb.write_exclusion_mask(cfg, excl, cfg.root / "outputs" / "mask.tif")
    lat = lattice(cfg)
    with rasterio.open(p) as ds:
        img = ds.read(1)
        assert img.shape == lat.shape and ds.crs == cfg.crs and ds.nodata == 255
    inside = img[grid["row"], grid["col"]]
    assert inside.sum() == 4 and set(np.unique(inside)) <= {0, 1}
    outside = np.ones(lat.shape, bool)
    outside[grid["row"], grid["col"]] = False
    assert (img[outside] == 255).all()


def test_validation_c7_has_its_own_path(cfg):
    assert lb.c7_path(cfg, "final") == schema.contract_path(cfg, "C7")
    assert lb.c7_path(cfg, "validation").name == "lulc_3class_validation.parquet"
    assert lb.mask_path(cfg, "validation").name == "exclusion_mask_validation.tif"
