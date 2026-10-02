"""Phase 5 gate: land classification (see docs/Tasks.md). Runs on the real outputs (final run).

Run: pytest tests/gates/test_phase5.py
Build first: python -m src.classify.cluster; python -m src.classify.label;
             python -m src.classify.export; python -m src.classify.evaluate
Set GIS_SUIT_CONFIG to run the gate on another project (e.g. a synthetic one).
"""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import pytest
import rasterio

from src.classify import cluster as cl
from src.classify import evaluate as ev
from src.classify import export as ex
from src.config import load_config
from src.features import schema
from src.features.grid import lattice
from src.preprocess.raster import load_reference_grid

cfg = load_config(os.environ.get("GIS_SUIT_CONFIG"))
MIN_AGREEMENT = 0.80


@pytest.fixture(scope="module")
def c7() -> pd.DataFrame:
    p = schema.contract_path(cfg, "C7")
    if not p.exists():
        pytest.fail(f"{p} missing: run src.classify.label (P5.4)")
    return schema.read_contract(p, "C7")


def test_class_raster_aligned_and_valid(c7):
    p = ex.class_raster_path(cfg)
    assert p.exists(), f"{p} missing: run src.classify.export"
    lat, ref = lattice(cfg), load_reference_grid(cfg)
    with rasterio.open(p) as ds:
        img = ds.read(1)
        assert ds.crs == cfg.crs, f"CRS {ds.crs}"
        assert ds.res == (cfg.cell_size_m, cfg.cell_size_m), f"resolution {ds.res}"
        assert (ds.transform.c, ds.transform.f) == (
            ref.transform.c,
            ref.transform.f,
        ), "origin is not the reference grid's"
        assert img.shape == lat.shape, f"shape {img.shape} != lattice {lat.shape}"
        nodata = ds.nodata
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    inside = img[grid["row"], grid["col"]]
    extra = set(np.unique(inside).tolist()) - set(schema.CLASS_3_VALUES)
    assert not extra, f"values {sorted(extra)} inside the AOI; allowed {schema.CLASS_3_VALUES}"
    outside = np.ones(lat.shape, bool)
    outside[grid["row"], grid["col"]] = False
    assert (img[outside] == nodata).all(), "cells outside the AOI must be nodata"
    g = grid.merge(c7, on="cell_id")
    assert (img[g["row"], g["col"]] == g["class_3"]).all(), "GeoTIFF differs from C7"


def test_c7_covers_the_grid(c7):
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    assert set(c7["cell_id"]) == set(grid["cell_id"]), "C7 cells differ from the grid (C1)"


@pytest.mark.parametrize("cls", [schema.CLASS_BUILT, schema.CLASS_FOREST, schema.CLASS_USABLE])
def test_every_class_covers_one_percent(c7, cls):
    share = float((c7["class_3"] == cls).mean())
    assert share >= 0.01, f"{ev.NAMES[cls]} covers {share:.2%} of the AOI (< 1 %)"


def test_no_excluded_cell_is_usable(c7):
    p = schema.contract_path(cfg, "C5").parent / "exclusion_final.parquet"
    assert p.exists(), f"{p} missing: run src.features.labels"
    excl = pd.read_parquet(p)
    m = excl.loc[excl["excluded"], ["cell_id"]].merge(c7, on="cell_id")
    n = int((m["class_3"] == schema.CLASS_USABLE).sum())
    assert n == 0, f"{n} cells inside the exclusion mask are labelled usable"
    assert (m["class_3"] == schema.CLASS_EXCLUDED).all(), "excluded cells must be class 255"


def test_same_seed_same_cluster_labels(c7):
    saved = pd.read_parquet(cl.clusters_path(cfg, "final"))
    again = cl.cluster_run(cfg, "final", do_scan=False)["assignments"]
    assert again.equals(saved), "refit with the same seed changed the cluster labels"
    m = c7.loc[c7["cluster_id"] >= 0].merge(saved, on="cell_id", suffixes=("", "_fit"))
    assert (
        m["cluster_id"] == m["cluster_id_fit"]
    ).all(), "C7 cluster_id differs from clusters_final"


def test_agreement_with_esri(c7):
    year = cl.run_year(cfg, "final")
    res = ev.evaluate(cfg, c7, "final")
    for name, r in res.items():
        print(f"{name}: all {r['all']['agreement']:.1%}, land {r['land']['agreement']:.1%}")
    a = res[f"esri_{year}"]["land"]["agreement"]
    assert a >= MIN_AGREEMENT, (
        f"agreement with collapsed ESRI {year} is {a:.1%} (< {MIN_AGREEMENT:.0%}): "
        "explain it in the manual checklist"
    )


def test_silhouette_saved():
    p = cl.metrics_path(cfg)
    assert p.exists(), f"{p} missing: run src.classify.cluster"
    m = json.loads(p.read_text())
    chosen = m["final"]["chosen"]
    assert chosen["k"] == int(cfg["clustering"]["k"]), "clustering.json is from another k"
    assert -1 <= chosen["silhouette"] <= 1, f"silhouette {chosen['silhouette']}"
    assert any(r["k"] == chosen["k"] for r in m["final"]["scan"]), "the k scan is missing"
