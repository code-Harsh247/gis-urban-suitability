"""Unit tests for P6.6: held-out building check."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.features import schema
from src.preprocess import raster as pr
from src.similarity import holdout as ho
from src.similarity import reference as rs
from src.synthetic import make_synthetic_project


@pytest.fixture
def cfg(tmp_path):
    cfg = make_synthetic_project(tmp_path / "proj", n=30)
    ref = pr.build_reference_grid(cfg)
    pr.processed_dir(cfg).mkdir(parents=True, exist_ok=True)
    pr.reference_grid_path(cfg).write_text(json.dumps(ref.to_json()))
    c5 = pd.read_parquet(schema.contract_path(cfg, "C5"))
    for run in ("validation", "final"):
        c5[["cell_id", "excluded"]].to_parquet(
            schema.contract_path(cfg, "C5").parent / f"exclusion_{run}.parquet"
        )
    cfg["validation"]["spatial_block_m"] = 500
    cfg["rf"].update(n_estimators=20, n_folds=3)
    return cfg


def test_oracle_ranks_high_and_random_near_50(cfg):
    refs = set(rs.reference_cells(cfg, "validation")["cell_id"])
    oracle = ho.summarise(
        ho.holdout_ranks(
            cfg, "validation", lambda X, tr, ids: np.isin(ids, list(refs)).astype(float)
        )
    )
    rng = np.random.default_rng(0)
    rand = ho.summarise(
        ho.holdout_ranks(cfg, "validation", lambda X, tr, ids: rng.random(len(ids)))
    )
    assert oracle["median_percentile"] > 70 and oracle["n_held_out"] > 0
    assert 40 < rand["median_percentile"] < 60
    assert oracle["share_top30"] > rand["share_top30"]


def test_scorer_never_trains_on_the_scored_fold(cfg):
    seen = []

    def spy(X, train_ref, ids):
        seen.append(set(train_ref) & set(ids))
        return np.zeros(len(ids))

    ranks = ho.holdout_ranks(cfg, "validation", spy)
    assert len(seen) == cfg["rf"]["n_folds"] and not any(seen)
    assert ranks["cell_id"].is_unique  # every cell is held out exactly once
    excl = pd.read_parquet(schema.contract_path(cfg, "C5").parent / "exclusion_validation.parquet")
    assert not set(ranks["cell_id"]) & set(excl.loc[excl["excluded"], "cell_id"])


@pytest.mark.parametrize("name", ho.SCORERS)
def test_builtin_scorers_beat_chance(cfg, name):
    r = ho.summarise(ho.holdout_ranks(cfg, "validation", ho.scorers(cfg)[name]))
    assert r["auc"] > 0.55, r  # synthetic city: buildings sit in built-up surroundings


def test_summarise():
    ranks = pd.DataFrame(
        {
            "fold": [0, 0, 0, 1, 1, 1],
            "is_ref": [True, True, False, True, True, False],
            "percentile": [95.0, 50.0, 20.0, 80.0, 10.0, 60.0],
        }
    )
    r = ho.summarise(ranks)
    assert r["median_percentile"] == 65.0 and r["share_top10"] == 0.25 and r["share_top30"] == 0.5
    assert r["median_by_fold"] == [72.5, 45.0]
    assert r["reference_share"] == pytest.approx(4 / 6)
    assert r["best_possible_median"] == pytest.approx(100 * (1 - 2 / 6))
    assert r["auc"] == pytest.approx((1.0 + 0.5) / 2)  # fold 0: both refs above; fold 1: one of two


def test_oracle_reaches_the_best_possible_median(cfg):
    refs = set(rs.reference_cells(cfg, "validation")["cell_id"])
    r = ho.summarise(
        ho.holdout_ranks(
            cfg, "validation", lambda X, tr, ids: np.isin(ids, list(refs)).astype(float)
        )
    )
    assert r["auc"] == 1.0
    assert r["median_percentile"] == pytest.approx(r["best_possible_median"], abs=3)
