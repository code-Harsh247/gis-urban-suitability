"""Random forests on cell surroundings (PRD FR-6.5, FR-6.6, FR-6.8, §9.7; Tasks P6.5).

Two models, both on ``schema.MODEL_INPUTS`` of ``years.baseline`` (2018) only:

- ``rf_change`` [D6]: candidate cells (C5); positives ``chg_train_pos`` (non-built in
  2018/19, built in 2020/21), negatives the other candidates;
- ``rf_state``: built (``built_baseline``) vs candidate cells in 2018, kept as a comparison.

Spatial cross-validation: cells are grouped in ``validation.spatial_block_m`` blocks
(2 km), blocks are dealt to ``rf.n_folds`` folds in a seeded random order, so no block is
ever in both train and test. The ``rf.param_grid`` is tuned by spatial-CV ROC-AUC on the
**training label** only (never on the 2022/23 ``grew`` label used by the validation).

Validation run (contract C8, ``outputs/scores/{model}.parquet``): every candidate cell
gets its **out-of-fold** probability, from a model that never saw its block [D11].
Final run (``outputs/final/scores/{model}.parquet``): one model fitted on all training
cells scores the usable cells of the final 3-class map (C7 ``class_3 = 3``) with the
``years.latest`` features. ``outputs/rf_probability.tif`` is the final ``rf_change`` score
on the 100 m cell lattice (NaN outside usable land).

With ``rf.feature_scaling: percentile`` each feature is replaced by its percentile among
all grid cells of the same year (see config; within a year it keeps each tree's partition
of its training sample, so the model barely changes). Importance: impurity (final model) and
permutation (ROC-AUC drop on each test fold, averaged). Metrics, including a preview of
the temporal AUC on ``grew`` against the distance-to-built baseline, go to
``outputs/metrics/similarity.json`` under the model name.

Run: python -m src.similarity.rf_model [--model rf_change|rf_state]
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

from src.classify.export import lattice_transform
from src.classify.label import c7_path
from src.config import load_config
from src.features import schema
from src.features.grid import lattice
from src.io_utils import setup_logging

log = logging.getLogger(__name__)

MODELS = ("rf_change", "rf_state")
ROUND_DECIMALS = 6  # before ranking; real differences are >= ~1e-4 (pixel shares)
DESCRIPTION = {
    "rf_change": "RF: 2018 surroundings of cells that became built in 2020/21 (D6)",
    "rf_state": "RF: built vs non-built cells in 2018 (comparison only)",
}


# ---------------------------------------------------------------- spatial folds


def spatial_blocks(cfg, cell_ids) -> np.ndarray:
    """Block id of each cell (``validation.spatial_block_m`` squares from the grid origin)."""
    lat = lattice(cfg)
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1").set_index("cell_id")
    g = grid.loc[np.asarray(cell_ids)]
    per = max(1, int(round(float(cfg["validation"]["spatial_block_m"]) / lat.cell_m)))
    n_bcols = -(-lat.shape[1] // per)
    return ((g["row"].to_numpy() // per) * n_bcols + g["col"].to_numpy() // per).astype("int64")


def assign_folds(blocks: np.ndarray, n_folds: int, seed: int) -> np.ndarray:
    """Fold of each cell: unique blocks in a seeded random order, dealt round-robin."""
    uniq = np.unique(blocks)
    order = np.random.default_rng(seed).permutation(len(uniq))
    fold_of_block = dict(zip(uniq[order], np.arange(len(uniq)) % n_folds, strict=True))
    return np.array([fold_of_block[b] for b in blocks], dtype="int64")


# ---------------------------------------------------------------- data


def model_features(cfg, year: int) -> pd.DataFrame:
    """MODEL_INPUTS of every grid cell of ``year``, indexed by cell_id (scaled per config)."""
    cols = list(schema.MODEL_INPUTS)
    schema.check_model_inputs(cols)
    c4 = schema.read_contract(schema.contract_path(cfg, "C4", year=year), "C4")
    X = c4.set_index("cell_id")[cols].astype("float64")
    scaling = cfg["rf"].get("feature_scaling", "none")
    if scaling == "percentile":
        # round first: ring fractions carry float noise from the convolution sums (~250,000
        # pairs < 1e-7 apart in 2018), which the forest treats as ties but ranks would order
        X = X.round(ROUND_DECIMALS).rank(pct=True)
    elif scaling != "none":
        raise ValueError(f"rf.feature_scaling must be percentile or none, got {scaling!r}")
    return X


def training_set(labels: pd.DataFrame, model: str) -> tuple[np.ndarray, np.ndarray]:
    """cell_ids and 0/1 target of a model's training cells (C5)."""
    lab = labels.set_index("cell_id")
    if model == "rf_change":
        keep = lab["candidate"]
        y = lab["chg_train_pos"]
    elif model == "rf_state":
        keep = (lab["candidate"] | lab["built_baseline"]) & ~lab["excluded"]
        y = lab["built_baseline"]
    else:
        raise ValueError(f"model must be one of {MODELS}, got {model!r}")
    ids = lab.index[keep].to_numpy()
    return ids, y.loc[ids].to_numpy().astype("int64")


def param_combos(cfg) -> list[dict]:
    """Every combination of ``rf.param_grid``."""
    grid = cfg["rf"]["param_grid"]
    keys = sorted(grid)
    return [dict(zip(keys, v, strict=True)) for v in itertools.product(*(grid[k] for k in keys))]


def make_rf(cfg, params: dict, seed: int) -> RandomForestClassifier:
    """Class-balanced random forest with the configured size and the given parameters."""
    return RandomForestClassifier(
        n_estimators=int(cfg["rf"]["n_estimators"]),
        class_weight=cfg["rf"]["class_weight"],
        random_state=seed,
        n_jobs=-1,
        **params,
    )


# ---------------------------------------------------------------- CV


def cross_validate(
    cfg,
    X: np.ndarray,
    y: np.ndarray,
    folds: np.ndarray,
    params: dict,
    seed: int,
    importance: bool = False,
) -> dict:  # noqa: E501
    """Out-of-fold probabilities, per-fold AUC, optionally permutation importance."""
    oof = np.full(len(y), np.nan)
    aucs, perm = [], []
    for f in np.unique(folds):
        test = folds == f
        train = ~test
        if len(np.unique(y[train])) < 2:
            raise ValueError(f"fold {f}: training part has one class only")
        rf = make_rf(cfg, params, seed).fit(X[train], y[train])
        oof[test] = rf.predict_proba(X[test])[:, 1]
        if len(np.unique(y[test])) == 2:
            aucs.append(float(roc_auc_score(y[test], oof[test])))
            if importance:
                pi = permutation_importance(
                    rf, X[test], y[test], scoring="roc_auc",
                    n_repeats=int(cfg["rf"]["permutation_repeats"]), random_state=seed, n_jobs=-1,
                )  # fmt: skip
                perm.append(pi.importances_mean)
    out = {"oof": oof, "fold_auc": aucs, "mean_auc": float(np.mean(aucs)) if aucs else float("nan")}
    if importance and perm:
        out["permutation"] = np.mean(perm, axis=0)
    return out


def tune(cfg, X, y, folds, seed) -> tuple[dict, list[dict]]:
    """Pick the ``rf.param_grid`` combination with the best spatial-CV AUC (training label only)."""
    table = []
    for params in param_combos(cfg):
        r = cross_validate(cfg, X, y, folds, params, seed)
        table.append({**params, "cv_auc": round(r["mean_auc"], 4)})
        log.info("tune %s: spatial-CV AUC %.3f", params, r["mean_auc"])
    best = max(table, key=lambda row: row["cv_auc"])
    return {k: v for k, v in best.items() if k != "cv_auc"}, table


# ---------------------------------------------------------------- run


def scores_path(cfg, model: str, run: str) -> Path:
    p = schema.contract_path(cfg, "C8", model=model)
    return p if run == "validation" else p.parent.parent / "final" / "scores" / p.name


def rf_probability_path(cfg) -> Path:
    return Path(cfg.paths["outputs"]) / "rf_probability.tif"


def metrics_path(cfg) -> Path:
    return Path(cfg.paths["metrics"]) / "similarity.json"


def usable_cells(cfg) -> np.ndarray:
    """Usable cells of the final 3-class map (C7 ``class_3 = 3``)."""
    c7 = schema.read_contract(c7_path(cfg, "final"), "C7")
    return c7.loc[c7["class_3"] == schema.CLASS_USABLE, "cell_id"].to_numpy()


def run_model(cfg, model: str) -> dict:
    """Fit, cross-validate and score one model; nothing written."""
    seed = int(cfg["project"]["random_seed"])
    base, latest = int(cfg["years"]["baseline"]), int(cfg["years"]["latest"])
    labels = schema.read_contract(schema.contract_path(cfg, "C5"), "C5")
    feats = model_features(cfg, base)
    ids, y = training_set(labels, model)
    X = feats.loc[ids].to_numpy()
    blocks = spatial_blocks(cfg, ids)
    folds = assign_folds(blocks, int(cfg["rf"]["n_folds"]), seed)
    best, table = tune(cfg, X, y, folds, seed)
    cv = cross_validate(cfg, X, y, folds, best, seed, importance=True)
    final_rf = make_rf(cfg, best, seed).fit(X, y)

    # validation run: out-of-fold scores of the candidate cells
    lab = labels.set_index("cell_id")
    oof = pd.Series(cv["oof"], index=ids)
    cand = lab.index[lab["candidate"]]
    val = pd.DataFrame({"cell_id": cand, "score": oof.loc[cand].to_numpy()})

    # preview of the temporal validation (Phase 7 does it properly)
    ev = lab.loc[cand]
    keep = ~ev["ambiguous"].to_numpy()
    grew = ev["grew"].to_numpy()[keep]
    preview = {
        "auc_grew_oof": float(roc_auc_score(grew, val["score"].to_numpy()[keep])),
        "auc_grew_dist_to_built": float(
            roc_auc_score(grew, -feats.loc[cand, "log_dist_built"].to_numpy()[keep])
        ),
        "n_cells": int(keep.sum()),
        "n_grew": int(grew.sum()),
    }

    # final run: all-blocks model on the usable cells, latest-year features
    use = usable_cells(cfg)
    Xf = model_features(cfg, latest).loc[use].to_numpy()
    fin = pd.DataFrame({"cell_id": use, "score": final_rf.predict_proba(Xf)[:, 1]})

    cols = list(schema.MODEL_INPUTS)
    imp = pd.DataFrame(
        {"impurity": final_rf.feature_importances_, "permutation_auc_drop": cv["permutation"]},
        index=cols,
    ).sort_values("permutation_auc_drop", ascending=False)
    fold_sizes = pd.Series(folds).value_counts().sort_index()
    metrics = {
        "training": {
            "label": "chg_train_pos" if model == "rf_change" else "built_baseline",
            "n_cells": int(len(y)), "n_positive": int(y.sum()),
            "n_blocks": int(len(np.unique(blocks))), "fold_sizes": fold_sizes.astype(int).tolist(),
        },
        "feature_scaling": cfg["rf"].get("feature_scaling", "none"),
        "tuning": table,
        "best_params": best,
        "spatial_cv_auc": {"mean": cv["mean_auc"], "folds": cv["fold_auc"]},
        "temporal_preview": preview,
        "importance": imp.round(5).reset_index(names="feature").to_dict(orient="records"),
    }  # fmt: skip
    return {
        "model": model,
        "validation": val,
        "final": fin,
        "metrics": metrics,
        "folds": folds,
        "ids": ids,
    }


def write_scores(cfg, model: str, run: str, df: pd.DataFrame, meta_extra: dict) -> Path:
    """Write one model's scores for a run (C8 layout) with its metadata JSON."""
    schema.validate_frame(df, "C8")
    p = scores_path(cfg, model, run)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    base = int(cfg["years"]["baseline"])
    meta = {
        "model": model,
        "features": list(schema.MODEL_INPUTS),
        "train_years": (
            [base, *cfg["years"]["change_train_end"]] if model == "rf_change" else [base]
        ),
        "description": DESCRIPTION[model],
        "run": run,
        **meta_extra,
    }
    p.with_suffix(".json").write_text(json.dumps(meta, indent=1))
    if run == "validation":
        schema.validate_score_meta(p.with_suffix(".json"))
    return p


def write_probability_raster(cfg, scores: pd.DataFrame, path: Path) -> Path:
    """Write scores as a float32 GeoTIFF on the cell lattice (NaN elsewhere)."""
    lat = lattice(cfg)
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1").set_index("cell_id")
    g = grid.loc[scores["cell_id"]]
    img = np.full(lat.shape, np.nan, dtype="float32")
    img[g["row"].to_numpy(), g["col"].to_numpy()] = scores["score"].to_numpy()
    profile = {
        "driver": "GTiff", "height": img.shape[0], "width": img.shape[1], "count": 1,
        "dtype": "float32", "crs": cfg.crs, "transform": lattice_transform(lat),
        "nodata": np.nan, "compress": "deflate",
    }  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(img, 1)
    return path


def write_models(cfg, models: list[str] | None = None) -> dict[str, dict]:
    """Run, score and write each model; merge its metrics into ``similarity.json``."""
    out = {}
    mpath = metrics_path(cfg)
    allm = json.loads(mpath.read_text()) if mpath.exists() else {}
    for model in models or list(MODELS):
        r = run_model(cfg, model)
        m = r["metrics"]
        write_scores(
            cfg,
            model,
            "validation",
            r["validation"],
            {"out_of_fold": True, "params": m["best_params"]},
        )
        write_scores(
            cfg, model, "final", r["final"], {"out_of_fold": False, "params": m["best_params"]}
        )
        if model == "rf_change":
            write_probability_raster(cfg, r["final"], rf_probability_path(cfg))
        allm[model] = m
        log.info(
            "%s: spatial-CV AUC %.3f (%s), temporal preview AUC %.3f vs distance-to-built %.3f",
            model, m["spatial_cv_auc"]["mean"], m["training"]["label"],
            m["temporal_preview"]["auc_grew_oof"], m["temporal_preview"]["auc_grew_dist_to_built"],
        )  # fmt: skip
        out[model] = r
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(allm, indent=1, allow_nan=False))
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", choices=MODELS, help="default: both")
    args = parser.parse_args(argv)
    cfg = load_config()
    setup_logging(cfg, "similarity")
    write_models(cfg, args.model)


if __name__ == "__main__":
    main()
