"""Unit tests for P5.6 (evaluation vs land-cover references) and the P5.7 exports."""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio

from src.classify import evaluate as ev
from src.classify import export as ex
from src.features import schema
from src.features.grid import lattice
from src.preprocess import raster as pr
from src.synthetic import make_synthetic_project

B, F, U, X = ev.B, ev.F, ev.U, ev.X


@pytest.fixture
def cfg(tmp_path):
    cfg = make_synthetic_project(tmp_path / "proj", n=20)
    ref = pr.build_reference_grid(cfg)
    pr.processed_dir(cfg).mkdir(parents=True, exist_ok=True)
    pr.reference_grid_path(cfg).write_text(json.dumps(ref.to_json()))
    wc = np.full(ref.shape, 50, dtype=np.uint8)  # WorldCover built-up everywhere
    wc[:, : ref.shape[1] // 2] = 10  # west half: tree cover
    pr.write(ev.worldcover_path(cfg), wc, ref, 0)
    return cfg


def _fr(**kw):
    row = {f"frac_{c}": 0.0 for c in schema.OWN_FRACTION_CLASSES}
    row.update({f"frac_{k}": v for k, v in kw.items()})
    return row


def test_collapse_follows_prd_table():
    fr = pd.DataFrame(
        [
            _fr(built=0.6, tree=0.4),
            _fr(crop=0.3, range=0.3, tree=0.4),  # usable 0.6 beats forest 0.4
            _fr(water=0.3, flooded=0.3, built=0.4),  # excluded 0.6
            _fr(bare=1.0),
            _fr(built=0.5, tree=0.5),  # tie -> built-up first
        ]
    )
    assert ev.collapse_fractions(fr).tolist() == [B, U, X, U, B]


def test_compare_counts_and_rates():
    ref = np.array([B, B, B, F, U, U])
    pred = np.array([B, B, U, F, U, B])
    r = ev.compare(pred, ref, classes=(B, F, U))
    assert r["n_cells"] == 6 and r["agreement"] == pytest.approx(4 / 6)
    assert r["confusion"]["built-up"] == {"built-up": 2, "forest": 0, "usable": 1}
    assert r["per_class"]["built-up"]["recall"] == pytest.approx(2 / 3)
    assert r["per_class"]["built-up"]["precision"] == pytest.approx(2 / 3)
    assert r["per_class"]["forest"]["precision"] == 1.0


def test_perfect_map_agrees_with_esri(cfg):
    year = cfg["years"]["latest"]
    ref = ev.esri_reference(cfg, year)
    c7 = ref.rename(columns={"ref": "class_3"}).assign(cluster_id=0)
    res = ev.evaluate(cfg, c7, "final")
    assert res[f"esri_{year}"]["all"]["agreement"] == 1.0
    assert res[f"esri_{year}"]["land"]["agreement"] == 1.0


def test_worldcover_reference_and_land_comparison(cfg):
    wc = ev.worldcover_reference(cfg)
    grid = pd.read_parquet(schema.contract_path(cfg, "C1"))
    half = lattice(cfg).shape[1] // 2
    want = np.where(grid["col"].to_numpy() < half, F, B)
    assert (wc["ref"].to_numpy() == want).all()
    c7 = grid[["cell_id"]].assign(cluster_id=0, class_3=np.full(len(grid), B, dtype="uint8"))
    c7.loc[c7.index[:5], "class_3"] = X  # excluded cells drop out of the land comparison
    land = ev.evaluate(cfg, c7, "final")[f"worldcover_{cfg['lulc']['worldcover_check']}"]["land"]
    keep = c7["class_3"].to_numpy() != X
    assert land["n_cells"] == keep.sum()
    assert land["agreement"] == pytest.approx((want[keep] == B).mean())


def test_write_evaluation_is_strict_json(cfg):
    ev.write_evaluation(cfg, "final")

    def no_nan(x):
        raise ValueError(x)

    m = json.loads(ev.eval_path(cfg).read_text(), parse_constant=no_nan)
    assert set(m["final"]) == {
        f"esri_{cfg['years']['latest']}",
        f"worldcover_{cfg['lulc']['worldcover_check']}",
    }


# ---------------------------------------------------------------- exports (P5.7)


def test_class_raster_on_the_cell_lattice(cfg):
    c7 = pd.read_parquet(schema.contract_path(cfg, "C7"))
    p = ex.write_class_raster(cfg, c7)
    lat = lattice(cfg)
    ref = pr.load_reference_grid(cfg)
    grid = pd.read_parquet(schema.contract_path(cfg, "C1")).merge(c7, on="cell_id")
    with rasterio.open(p) as ds:
        img = ds.read(1)
        assert ds.crs == cfg.crs and ds.nodata == ex.NODATA
        assert ds.res == (cfg.cell_size_m, cfg.cell_size_m)
        assert (ds.transform.c, ds.transform.f) == (ref.transform.c, ref.transform.f)  # same origin
        assert img.shape == lat.shape
    assert (img[grid["row"], grid["col"]] == grid["class_3"]).all()
    inside = np.zeros(lat.shape, bool)
    inside[grid["row"], grid["col"]] = True
    assert (img[~inside] == ex.NODATA).all()
    assert set(np.unique(img[inside])) <= set(schema.CLASS_3_VALUES)


def test_class_raster_needs_every_cell(cfg):
    c7 = pd.read_parquet(schema.contract_path(cfg, "C7")).iloc[1:]
    with pytest.raises(ValueError, match="no class"):
        ex.class_image(cfg, c7)


def test_clusters_gpkg(cfg):
    c7 = pd.read_parquet(schema.contract_path(cfg, "C7"))
    g = gpd.read_file(ex.write_clusters_gpkg(cfg, c7))
    assert len(g) == len(c7) and g.crs == cfg.crs
    assert set(g["class_name"]) <= set(ev.NAMES.values())
    assert np.allclose(g.area, cfg.cell_size_m**2)
