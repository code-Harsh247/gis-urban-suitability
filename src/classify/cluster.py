"""Cluster grid cells on land cover and terrain (PRD FR-5.1-5.3, §9.4; Tasks P5.1-P5.3).

For each run (``validation``: baseline-year features; ``final``: latest-year features):

1. inputs: ``clustering.inputs`` from the feature table (C4), standardised (z-scores);
   PCA is computed and reported, and used only if ``clustering.use_pca``;
2. scan k = ``k_min`` ... ``k_max`` with K-Means (k-means++, n_init = 10) and GMM (full
   covariance): inertia, BIC, silhouette (on a seeded sample) and Davies-Bouldin;
3. fit the chosen ``clustering.method`` with ``clustering.k``. Cluster ids are renumbered
   by descending mean ``frac_built`` (ties: ``frac_tree``), so they don't depend on the
   solver's arbitrary order.

Outputs (``outputs/``): ``clusters_{run}.parquet`` (cell_id, cluster_id),
``metrics/cluster_centroids_{run}.csv`` (mean inputs per cluster, in original units, and
share of cells) and ``metrics/clustering.json`` (scan, chosen model, silhouette).
Mapping clusters to built-up / forest / usable is ``src/classify/label.py`` (P5.4).

Run: python -m src.classify.cluster [--run validation|final] [--no-scan]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from src.config import load_config
from src.features import schema
from src.io_utils import setup_logging

log = logging.getLogger(__name__)

RUNS = ("validation", "final")
METHODS = ("kmeans", "gmm")


def run_year(cfg, run: str) -> int:
    """Feature year a run clusters: baseline for validation (time-travel rule), else latest."""
    if run == "validation":
        return int(cfg["years"]["baseline"])
    if run == "final":
        return int(cfg["years"]["latest"])
    raise ValueError(f"run must be one of {RUNS}, got {run!r}")


def cluster_inputs(cfg) -> list[str]:
    cols = list(cfg["clustering"].get("inputs") or schema.CLUSTER_INPUTS)
    unknown = set(cols) - set(schema.CONTRACTS["C4"].columns)
    if unknown:
        raise ValueError(f"clustering.inputs not in the feature table (C4): {sorted(unknown)}")
    return cols


def load_inputs(cfg, run: str) -> pd.DataFrame:
    """cell_id + clustering inputs for the run's feature year."""
    year = run_year(cfg, run)
    df = schema.read_contract(schema.contract_path(cfg, "C4", year=year), "C4")
    return df[["cell_id", *cluster_inputs(cfg)]].reset_index(drop=True)


def prepare(cfg, X: pd.DataFrame) -> tuple[np.ndarray, dict]:
    """Standardise; optionally project on the PCs that explain ``pca_variance``."""
    Z = StandardScaler().fit_transform(X.to_numpy(dtype="float64"))
    pca = PCA(random_state=int(cfg["project"]["random_seed"])).fit(Z)
    cum = np.cumsum(pca.explained_variance_ratio_)
    n_pc = int(np.searchsorted(cum, float(cfg["clustering"]["pca_variance"])) + 1)
    info = {
        "pca_explained_variance": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "pca_components_for_target": n_pc,
        "use_pca": bool(cfg["clustering"].get("use_pca", False)),
    }
    if info["use_pca"]:
        Z = pca.transform(Z)[:, :n_pc]
    return Z, info


def fit(Z: np.ndarray, method: str, k: int, seed: int):
    """Fitted model and labels."""
    if method == "kmeans":
        model = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=seed).fit(Z)
        return model, model.labels_
    if method == "gmm":
        model = GaussianMixture(k, covariance_type="full", n_init=2, random_state=seed).fit(Z)
        return model, model.predict(Z)
    raise ValueError(f"clustering.method must be one of {METHODS}, got {method!r}")


def scores(Z: np.ndarray, labels: np.ndarray, sample: int, seed: int) -> dict[str, float]:
    if len(np.unique(labels)) < 2:
        return {"silhouette": float("nan"), "davies_bouldin": float("nan")}
    n = min(sample, len(Z))
    return {
        "silhouette": float(silhouette_score(Z, labels, sample_size=n, random_state=seed)),
        "davies_bouldin": float(davies_bouldin_score(Z, labels)),
    }


def scan(cfg, Z: np.ndarray) -> pd.DataFrame:
    """Metrics for every k and method (FR-5.3)."""
    c = cfg["clustering"]
    seed, sample = int(cfg["project"]["random_seed"]), int(c["silhouette_sample"])
    rows = []
    for k in range(int(c["k_min"]), int(c["k_max"]) + 1):
        for method in METHODS:
            model, labels = fit(Z, method, k, seed)
            row = {"method": method, "k": k, **scores(Z, labels, sample, seed)}
            row["inertia"] = float(model.inertia_) if method == "kmeans" else None
            row["bic"] = float(model.bic(Z)) if method == "gmm" else None
            rows.append(row)
            log.info(
                "scan %s k=%d: silhouette %.3f, DB %.3f",
                method,
                k,
                row["silhouette"],
                row["davies_bouldin"],
            )
    return pd.DataFrame(rows)


def order_clusters(X: pd.DataFrame, labels: np.ndarray) -> np.ndarray:
    """Renumber clusters 0..k-1 by descending mean frac_built, then frac_tree."""
    keys = [c for c in ("frac_built", "frac_tree") if c in X.columns]
    if not keys:
        return labels
    means = X.groupby(labels)[keys].mean().sort_values(keys, ascending=False)
    new = {old: i for i, old in enumerate(means.index)}
    return np.vectorize(new.get)(labels).astype("int64")


def centroids(X: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Mean of each input per cluster (original units) and the share of cells."""
    c = X.groupby(labels).mean()
    c.insert(0, "n_cells", pd.Series(labels).value_counts().sort_index())
    c.insert(1, "share", c["n_cells"] / len(labels))
    c.index.name = "cluster_id"
    return c


def cluster_run(cfg, run: str, do_scan: bool = True) -> dict:
    """Cluster one run; return assignments, centroids and metrics (nothing written)."""
    c = cfg["clustering"]
    seed = int(cfg["project"]["random_seed"])
    df = load_inputs(cfg, run)
    X = df.drop(columns="cell_id")
    Z, info = prepare(cfg, X)
    _, labels = fit(Z, c["method"], int(c["k"]), seed)
    labels = order_clusters(X, labels)
    chosen = {
        "method": c["method"],
        "k": int(c["k"]),
        **scores(Z, labels, int(c["silhouette_sample"]), seed),
    }
    return {
        "run": run,
        "year": run_year(cfg, run),
        "inputs": list(X.columns),
        "assignments": pd.DataFrame({"cell_id": df["cell_id"], "cluster_id": labels}),
        "centroids": centroids(X, labels),
        "chosen": chosen,
        "scan": scan(cfg, Z) if do_scan else None,
        **info,
    }


def clusters_path(cfg, run: str) -> Path:
    return Path(cfg.paths["outputs"]) / f"clusters_{run}.parquet"


def metrics_path(cfg) -> Path:
    return Path(cfg.paths["metrics"]) / "clustering.json"


def write_clusters(cfg, runs: list[str] | None = None, do_scan: bool = True) -> dict[str, dict]:
    out = {}
    mpath = metrics_path(cfg)
    metrics = json.loads(mpath.read_text()) if mpath.exists() else {}
    for run in runs or list(RUNS):
        res = cluster_run(cfg, run, do_scan)
        p = clusters_path(cfg, run)
        p.parent.mkdir(parents=True, exist_ok=True)
        res["assignments"].to_parquet(p, index=False)
        mpath.parent.mkdir(parents=True, exist_ok=True)
        res["centroids"].round(4).to_csv(mpath.parent / f"cluster_centroids_{run}.csv")
        entry = {
            k: res[k]
            for k in (
                "year",
                "inputs",
                "chosen",
                "pca_explained_variance",
                "pca_components_for_target",
                "use_pca",
            )
        }
        if res["scan"] is not None:
            sc = res["scan"].round(4).astype(object)
            entry["scan"] = sc.where(sc.notna(), None).to_dict(orient="records")  # NaN -> null
        elif "scan" in metrics.get(run, {}):
            entry["scan"] = metrics[run]["scan"]
        metrics[run] = entry
        log.info(
            "%s (%d): %s k=%d, silhouette %.3f, DB %.3f -> %s",
            run, res["year"], res["chosen"]["method"], res["chosen"]["k"],
            res["chosen"]["silhouette"], res["chosen"]["davies_bouldin"], p.name,
        )  # fmt: skip
        out[run] = res
    mpath.write_text(json.dumps(metrics, indent=1, allow_nan=False))
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", choices=RUNS, help="default: both")
    parser.add_argument("--no-scan", action="store_true", help="skip the k scan")
    args = parser.parse_args(argv)
    cfg = load_config()
    setup_logging(cfg, "classify")
    write_clusters(cfg, args.run, do_scan=not args.no_scan)


if __name__ == "__main__":
    main()
