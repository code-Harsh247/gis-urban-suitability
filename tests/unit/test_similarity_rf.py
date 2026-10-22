"""Unit tests for P6.2 (reference set) and P6.5 (random forests, spatial CV) - P6.9."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import rasterio

from src.classify.label import c7_path
from src.features import schema
from src.features.grid import lattice
from src.preprocess import raster as pr
from src.similarity import reference as rs
from src.similarity import rf_model as rm
from src.synthetic import make_synthetic_project


@pytest.fixture
def cfg(tmp_path):
    cfg = make_synthetic_project(tmp_path / "proj", n=30)
    ref = pr.build_reference_grid(cfg)
    pr.processed_dir(cfg).mkdir(parents=True, exist_ok=True)
    pr.reference_grid_path(cfg).write_text(json.dumps(ref.to_json()))
    cfg["validation"]["spatial_block_m"] = 500  # 3 km synthetic AOI -> 36 blocks
    cfg["rf"].update(
        n_estimators=30, n_folds=3, permutation_repeats=2, param_grid={"min_samples_leaf": [1, 5]}
    )
    return cfg


# ---------------------------------------------------------------- folds


def test_blocks_are_squares_of_the_configured_size(cfg):
    grid = pd.read_parquet(schema.contract_path(cfg, "C1"))
    b = rm.spatial_blocks(cfg, grid["cell_id"])
    per = 5  # 500 m / 100 m
    key = (grid["row"] // per).astype(str) + "_" + (grid["col"] // per).astype(str)
    assert pd.Series(b).groupby(key.to_numpy()).nunique().eq(1).all()  # one block per square
    assert pd.Series(key.to_numpy()).groupby(b).nunique().eq(1).all()  # one square per block


def test_folds_never_split_a_block(cfg):
    blocks = np.repeat(np.arange(40), 7)
    folds = rm.assign_folds(blocks, 5, seed=1)
    assert pd.Series(folds).groupby(blocks).nunique().eq(1).all()
    assert set(folds) == set(range(5))
    assert (rm.assign_folds(blocks, 5, seed=1) == folds).all()  # seeded
    assert not (rm.assign_folds(blocks, 5, seed=2) == folds).all()


def test_cv_trains_without_the_test_blocks(cfg, monkeypatch):
    """Each out-of-fold score comes from a model that never saw the cell's block."""
    rng = np.random.default_rng(0)
    blocks = np.repeat(np.arange(30), 20)
    folds = rm.assign_folds(blocks, 3, seed=0)
    X = rng.normal(size=(len(blocks), 4))
    y = (X[:, 0] > 0).astype(int)
    seen = []
    real = rm.make_rf

    class Spy:
        def __init__(self, rf):
            self.rf = rf

        def fit(self, Xt, yt):
            seen.append({tuple(r) for r in Xt})
            self.rf.fit(Xt, yt)
            return self

        def predict_proba(self, Xs):
            return self.rf.predict_proba(Xs)

    monkeypatch.setattr(rm, "make_rf", lambda c, p, s: Spy(real(c, p, s)))
    r = rm.cross_validate(cfg, X, y, folds, {"min_samples_leaf": 1}, seed=0)
    assert not np.isnan(r["oof"]).any()
    for f, train_rows in zip(np.unique(folds), seen, strict=True):
        test_blocks = set(blocks[folds == f])
        train_blocks = {blocks[i] for i in range(len(X)) if tuple(X[i]) in train_rows}
        assert not test_blocks & train_blocks
    assert r["mean_auc"] > 0.9  # the signal is learnable across blocks


# ---------------------------------------------------------------- features and labels


def test_float_noise_becomes_ties():
    """Regression: values equal up to float noise must get the same percentile."""
    v = pd.Series([0.1 + 0.2, 0.3, 0.5, 0.30000001])
    r = v.round(rm.ROUND_DECIMALS).rank(pct=True)
    assert r[0] == r[1] and r[3] == r[0]  # 0.30000000000000004, 0.3, 0.30000001
    assert r[2] > r[0]


def test_features_are_model_inputs_only(cfg):
    X = rm.model_features(cfg, cfg["years"]["baseline"])
    assert list(X.columns) == list(schema.MODEL_INPUTS)
    assert not set(X.columns) & set(schema.LEAKY_FEATURES)
    assert X.min().min() > 0 and X.max().max() <= 1  # percentiles


def test_percentile_scaling_keeps_the_partition(cfg):
    """Config claim: a per-feature monotone transform keeps each tree's partition of its
    training sample. Without bootstrap every cell is in-sample, so predictions are equal."""
    cfg["rf"]["feature_scaling"] = "none"
    raw = rm.model_features(cfg, cfg["years"]["baseline"]).round(rm.ROUND_DECIMALS)
    cfg["rf"]["feature_scaling"] = "percentile"
    pct = rm.model_features(cfg, cfg["years"]["baseline"])
    y = (raw["ring250_built"] > raw["ring250_built"].median()).to_numpy().astype(int)
    p = {"min_samples_leaf": 5, "bootstrap": False, "max_features": "sqrt"}
    a = rm.make_rf(cfg, p, 0).fit(raw.to_numpy(), y).predict_proba(raw.to_numpy())[:, 1]
    b = rm.make_rf(cfg, p, 0).fit(pct.to_numpy(), y).predict_proba(pct.to_numpy())[:, 1]
    np.testing.assert_allclose(a, b)


def test_training_sets():
    lab = pd.DataFrame(
        {
            "cell_id": [1, 2, 3, 4, 5],
            "candidate": [True, True, False, False, True],
            "chg_train_pos": [True, False, False, False, False],
            "built_baseline": [False, False, True, True, False],
            "excluded": [False, False, False, True, False],
        }
    )
    ids, y = rm.training_set(lab, "rf_change")
    assert ids.tolist() == [1, 2, 5] and y.tolist() == [1, 0, 0]
    ids, y = rm.training_set(lab, "rf_state")
    assert ids.tolist() == [1, 2, 3, 5] and y.tolist() == [0, 0, 1, 0]  # excluded built cell 4 out
    with pytest.raises(ValueError):
        rm.training_set(lab, "other")


# ---------------------------------------------------------------- end to end on stubs


def test_write_models(cfg):
    out = rm.write_models(cfg, ["rf_change"])
    lab = pd.read_parquet(schema.contract_path(cfg, "C5"))
    val = schema.read_contract(rm.scores_path(cfg, "rf_change", "validation"), "C8")
    assert set(val["cell_id"]) == set(lab.loc[lab["candidate"], "cell_id"])  # FR-6.7
    assert val["score"].between(0, 1).all()
    meta = schema.validate_score_meta(
        rm.scores_path(cfg, "rf_change", "validation").with_suffix(".json")
    )
    assert meta["out_of_fold"] is True
    fin = pd.read_parquet(rm.scores_path(cfg, "rf_change", "final"))
    c7 = pd.read_parquet(c7_path(cfg, "final"))
    assert set(fin["cell_id"]) == set(c7.loc[c7["class_3"] == schema.CLASS_USABLE, "cell_id"])
    with rasterio.open(rm.rf_probability_path(cfg)) as ds:
        img = ds.read(1)
        assert img.shape == lattice(cfg).shape
    finite = img[np.isfinite(img)]
    assert len(finite) == len(fin) and ((finite >= 0) & (finite <= 1)).all()
    m = json.loads(rm.metrics_path(cfg).read_text())["rf_change"]
    assert 0 <= m["spatial_cv_auc"]["mean"] <= 1
    assert {r["feature"] for r in m["importance"]} == set(schema.MODEL_INPUTS)
    assert out["rf_change"]["metrics"]["best_params"]["min_samples_leaf"] in (1, 5)


# ---------------------------------------------------------------- reference set (P6.2)


def test_type_groups():
    t = pd.Series(["apartments", "yes", None, "warehouse", "temple", "garage"])
    assert rs.type_group(t).tolist() == [
        "residential",
        "unknown",
        "unknown",
        "industrial",
        "institutional",
        "other",
    ]


@pytest.mark.parametrize("source", rs.SOURCES)
def test_reference_cells(cfg, source):
    cfg["similarity"]["reference_source"] = source
    ref = rs.reference_cells(cfg, "final")
    b = rs.buildings(cfg, "final")
    assert ref["cell_id"].is_unique
    osm = ref.loc[ref["source"].isin(["osm", "both"])]
    assert set(osm["cell_id"]) == set(b["cell_id"])
    assert osm["n_buildings"].sum() == len(b)
    if source == "osm":
        assert set(ref["source"]) <= {"osm"}
    else:
        c4 = pd.read_parquet(schema.contract_path(cfg, "C4", year=cfg["years"]["latest"]))
        built = set(c4.loc[c4["frac_built"] >= cfg["growth"]["built_min"], "cell_id"])
        assert set(ref.loc[ref["source"].isin(["esri", "both"]), "cell_id"]) == built
        assert (ref.loc[ref["source"] == "esri", "n_buildings"] == 0).all()


def test_reference_uses_the_run_snapshot(cfg, monkeypatch):
    asked = []
    real = schema.contract_path
    monkeypatch.setattr(
        schema, "contract_path", lambda c, cid, **kw: asked.append((cid, kw)) or real(c, cid, **kw)
    )
    rs.reference_cells(cfg, "validation")
    assert ("C6", {"snapshot": "2018"}) in asked  # time-travel rule
    assert ("C4", {"year": cfg["years"]["baseline"]}) in asked
