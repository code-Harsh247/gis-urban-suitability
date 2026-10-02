"""Unit tests for P5.1-P5.3: clustering inputs, K-Means / GMM, scan, ordering, outputs."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import adjusted_rand_score

from src.classify import cluster as cl
from src.features import schema
from src.synthetic import make_synthetic_project


@pytest.fixture
def cfg(tmp_path):
    cfg = make_synthetic_project(tmp_path / "proj", n=20)
    cfg["clustering"].update(k=4, k_min=3, k_max=5)
    return cfg


def _blobs(n=300, seed=0):
    """Three well-separated land-cover groups: built, crop, tree."""
    rng = np.random.default_rng(seed)
    rows, truth = [], []
    for g, (b, c, t) in enumerate([(0.95, 0.03, 0.02), (0.05, 0.9, 0.05), (0.02, 0.08, 0.9)]):
        for _ in range(n):
            rows.append([b, c, t] + rng.normal(0, 0.01, 3).tolist())
            truth.append(g)
    X = pd.DataFrame(
        np.array(rows)[:, :3] + np.array(rows)[:, 3:],
        columns=["frac_built", "frac_crop", "frac_tree"],
    )
    return X, np.array(truth)


def test_run_year_follows_time_travel_rule(cfg):
    assert cl.run_year(cfg, "validation") == cfg["years"]["baseline"]
    assert cl.run_year(cfg, "final") == cfg["years"]["latest"]
    with pytest.raises(ValueError):
        cl.run_year(cfg, "other")


def test_unknown_input_rejected(cfg):
    cfg["clustering"]["inputs"] = ["frac_built", "not_a_feature"]
    with pytest.raises(ValueError, match="not_a_feature"):
        cl.cluster_inputs(cfg)


def test_inputs_default_to_cluster_inputs(cfg):
    cfg["clustering"]["inputs"] = None
    assert cl.cluster_inputs(cfg) == list(schema.CLUSTER_INPUTS)


@pytest.mark.parametrize("method", cl.METHODS)
def test_separated_groups_are_recovered(cfg, method):
    X, truth = _blobs()
    Z, _ = cl.prepare(cfg, X)
    _, labels = cl.fit(Z, method, 3, seed=0)
    assert adjusted_rand_score(truth, labels) == pytest.approx(1.0)


def test_order_clusters_by_built_then_tree():
    X, truth = _blobs()
    shuffled = np.array([2, 0, 1])[truth]  # arbitrary solver ids
    ordered = cl.order_clusters(X, shuffled)
    assert (ordered == truth).all()  # by mean frac_built: built 0.95, crop 0.05, tree 0.02
    c = cl.centroids(X, ordered)
    assert c["frac_built"].is_monotonic_decreasing
    assert c["n_cells"].sum() == len(X) and c["share"].sum() == pytest.approx(1.0)


def test_pca_option_reduces_dimensions(cfg):
    X, _ = _blobs()
    Z, info = cl.prepare(cfg, X)
    assert Z.shape[1] == 3 and not info["use_pca"]
    cfg["clustering"].update(use_pca=True, pca_variance=0.5)
    Z2, info2 = cl.prepare(cfg, X)
    assert Z2.shape[1] == info2["pca_components_for_target"] < 3
    assert sum(info2["pca_explained_variance"]) == pytest.approx(1.0, abs=1e-3)


def test_same_seed_same_labels(cfg):
    a = cl.cluster_run(cfg, "final", do_scan=False)["assignments"]
    b = cl.cluster_run(cfg, "final", do_scan=False)["assignments"]
    assert a.equals(b)


def test_write_clusters_outputs(cfg):
    out = cl.write_clusters(cfg)
    grid = pd.read_parquet(schema.contract_path(cfg, "C4", year=cfg["years"]["latest"]))
    for run in cl.RUNS:
        a = pd.read_parquet(cl.clusters_path(cfg, run))
        assert a["cell_id"].is_unique
        assert set(a["cluster_id"]) == set(range(cfg["clustering"]["k"]))
        assert len(a) == len(out[run]["assignments"])
    assert len(pd.read_parquet(cl.clusters_path(cfg, "final"))) == len(grid)

    def no_nan(x):
        raise ValueError(f"invalid JSON constant {x}")

    m = json.loads(cl.metrics_path(cfg).read_text(), parse_constant=no_nan)  # strict JSON
    assert set(m) == set(cl.RUNS)
    ks = {(r["method"], r["k"]) for r in m["final"]["scan"]}
    assert ks == {(meth, k) for meth in cl.METHODS for k in range(3, 6)}
    assert -1 <= m["final"]["chosen"]["silhouette"] <= 1
