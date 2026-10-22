"""Unit tests for P7.3 (MCDA / AHP baseline) - part of P7.9."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.features import schema
from src.preprocess import raster as pr
from src.similarity.rf_model import scores_path
from src.suitability import mcda
from src.synthetic import make_synthetic_project

# ---------------------------------------------------------------- AHP


def test_ahp_textbook_example():
    """Saaty's 3-criterion example: w ~ (0.637, 0.258, 0.105), lambda_max ~ 3.039, CR ~ 0.033."""
    A = mcda.parse_matrix([[1, 3, 5], ["1/3", 1, 3], ["1/5", "1/3", 1]])
    w, lam, cr = mcda.ahp_weights(A)
    np.testing.assert_allclose(w, [0.637, 0.258, 0.105], atol=2e-3)
    assert lam == pytest.approx(3.039, abs=2e-3)
    assert cr == pytest.approx(0.033, abs=2e-3)


def test_consistent_matrix_recovers_weights_exactly():
    w0 = np.array([0.5, 0.3, 0.15, 0.05])
    w, lam, cr = mcda.ahp_weights(w0[:, None] / w0[None, :])
    np.testing.assert_allclose(w, w0)
    assert lam == pytest.approx(4.0) and cr == pytest.approx(0.0, abs=1e-12)


def test_cyclic_preferences_are_inconsistent():
    A = mcda.parse_matrix([[1, 9, "1/9"], ["1/9", 1, 9], [9, "1/9", 1]])  # a > b > c > a
    assert mcda.ahp_weights(A)[2] > 0.1


def test_non_reciprocal_matrix_rejected():
    with pytest.raises(ValueError, match="reciprocal"):
        mcda.ahp_weights(np.array([[1.0, 2.0], [2.0, 1.0]]))


def test_config_matrix_is_consistent_and_without_lulc_too():
    cfg_like = {"mcda": __import__("src.config", fromlist=["load_config"]).load_config()["mcda"]}
    for use in (True, False):
        w, cons = mcda.weights(cfg_like, use)
        assert cons["consistency_ratio"] < 0.1 and w.sum() == pytest.approx(1.0)
        assert ("lulc" in w.index) == use


# ---------------------------------------------------------------- criteria


def _row(**kw):
    base = {f"frac_{c}": 0.0 for c in schema.OWN_FRACTION_CLASSES}
    base.update(
        frac_range=1.0,
        slope_mean=0.0,
        log_dist_major=0.0,
        log_dist_built=np.log1p(55.0),
        log_dist_water=np.log1p(5000.0),
    )
    base.update(kw)
    return base


def test_criteria_rescaling():
    from src.config import load_config

    cfg = load_config()
    m = cfg["mcda"]
    df = pd.DataFrame(
        [
            _row(),  # best case
            _row(slope_mean=m["slope_zero_deg"], log_dist_major=np.log1p(m["road_max_m"]),
                 log_dist_built=np.log1p(m["built_max_m"] + 1), log_dist_water=np.log1p(10.0),
                 frac_range=0.0, frac_tree=1.0),  # worst-ish
            _row(slope_mean=m["slope_zero_deg"] / 2,
                 log_dist_water=np.log1p(1.5 * m["water_buffer_m"]),
                 frac_range=0.5, frac_crop=0.5),
        ]
    )  # fmt: skip
    c = mcda.criteria(cfg, df)
    assert list(c.columns) == m["criteria"]
    assert ((c >= 0) & (c <= 1)).all().all()
    assert (
        c.loc[0, "slope"] == 1
        and c.loc[0, "road"] == 1
        and c.loc[0, "water"] == 1
        and c.loc[0, "lulc"] == 1
    )
    np.testing.assert_allclose(
        c.loc[1, ["slope", "road", "built", "water"]].to_numpy(float), 0, atol=1e-12
    )
    assert c.loc[1, "lulc"] == pytest.approx(m["lulc_values"]["tree"])
    assert c.loc[2, "slope"] == pytest.approx(0.5) and c.loc[2, "water"] == pytest.approx(0.5)
    assert c.loc[2, "lulc"] == pytest.approx(
        0.5 * (m["lulc_values"]["range"] + m["lulc_values"]["crop"])
    )


# ---------------------------------------------------------------- end to end


@pytest.fixture
def cfg(tmp_path):
    cfg = make_synthetic_project(tmp_path / "proj", n=20)
    ref = pr.build_reference_grid(cfg)
    pr.processed_dir(cfg).mkdir(parents=True, exist_ok=True)
    pr.reference_grid_path(cfg).write_text(json.dumps(ref.to_json()))
    return cfg


def test_write_mcda(cfg):
    rep = mcda.write_mcda(cfg)
    lab = pd.read_parquet(schema.contract_path(cfg, "C5"))
    for model in mcda.VARIANTS:
        val = schema.read_contract(scores_path(cfg, model, "validation"), "C8")
        assert set(val["cell_id"]) == set(lab.loc[lab["candidate"], "cell_id"])
        assert val["score"].between(0, 1).all()
        meta = schema.validate_score_meta(
            scores_path(cfg, model, "validation").with_suffix(".json")
        )
        schema.check_model_inputs(meta["features"])  # own-cell inputs listed apart
        assert bool(meta["own_cell_inputs"]) == mcda.VARIANTS[model]
        assert rep[model]["consistency_ratio"] < 0.1
    assert mcda.mcda_tif_path(cfg).exists()
    assert set(rep["criterion_auc"]) == set(cfg["mcda"]["criteria"])


def test_inconsistent_config_is_refused(cfg):
    cfg["mcda"]["ahp"] = [
        [1, 9, "1/9", 1, 1],
        ["1/9", 1, 9, 1, 1],
        [9, "1/9", 1, 1, 1],
        [1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1],
    ]
    with pytest.raises(ValueError, match="consistency ratio"):
        mcda.write_mcda(cfg)
