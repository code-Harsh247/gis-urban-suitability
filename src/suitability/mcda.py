"""MCDA / AHP baseline: the classic weighted-overlay suitability (PRD FR-7.1, §9.7; Tasks P7.3).

Five criteria per cell, each rescaled to 0-1 (1 = most suitable), thresholds in
``config.yaml → mcda``:

- ``slope``: 1 on flat ground, falling linearly to 0 at ``slope_zero_deg`` (15°);
- ``road``: distance to the nearest major road, 1 on the road to 0 at ``road_max_m``;
- ``built``: distance to built-up outside the cell, 1 next to it to 0 at ``built_max_m``;
- ``water``: 0 within ``water_buffer_m`` of water, rising to 1 at twice the buffer;
- ``lulc``: own-cell land cover weighted by ``lulc_values`` (rangeland / bare easiest,
  then crops, trees). MCDA is not trained and validation scores only cells non-built in
  2018/19, so this is not the D4 leak; it is listed apart from ``features`` in the score
  metadata, and the variant ``mcda_no_lulc`` shows how much it matters.

Weights come from the AHP pairwise matrix ``mcda.ahp`` (principal eigenvector; Saaty
consistency ratio CR = CI / RI must be < 0.1). Score = weighted sum.

Outputs, like the random forests: C8 ``outputs/scores/mcda.parquet`` (validation run:
candidate cells, baseline-year features), ``outputs/final/scores/mcda.parquet`` (usable
cells, latest year), ``outputs/mcda_score.tif`` (final) and ``outputs/metrics/mcda.json``
(weights, CR, temporal preview vs distance-to-built, and each criterion's own AUC as a
diagnostic; the weights are never tuned on the test label).

Run: python -m src.suitability.mcda
"""

from __future__ import annotations

import argparse
import json
import logging
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from src.classify.cluster import run_year
from src.config import load_config
from src.features import schema
from src.io_utils import setup_logging
from src.similarity.rf_model import scores_path, usable_cells, write_probability_raster

log = logging.getLogger(__name__)

# Saaty's random consistency index for n = 1..10
RANDOM_INDEX = {
    1: 0.0,
    2: 0.0,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
}
CRITERION_FEATURES = {
    "slope": ["slope_mean"],
    "road": ["log_dist_major"],
    "built": ["log_dist_built"],
    "water": ["log_dist_water"],
    "lulc": [f"frac_{c}" for c in schema.OWN_FRACTION_CLASSES],
}
VARIANTS = {"mcda": True, "mcda_no_lulc": False}  # model name -> uses the lulc criterion


# ---------------------------------------------------------------- AHP


def parse_matrix(rows) -> np.ndarray:
    """Pairwise matrix from config (numbers or strings like '1/3')."""
    return np.array([[float(Fraction(str(v))) for v in row] for row in rows], dtype="float64")


def ahp_weights(A: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Principal-eigenvector weights (sum 1), lambda_max and consistency ratio."""
    A = np.asarray(A, dtype="float64")
    n = A.shape[0]
    if A.shape != (n, n) or (A <= 0).any():
        raise ValueError("AHP matrix must be square and positive")
    if not np.allclose(A * A.T, 1.0):
        raise ValueError("AHP matrix must be reciprocal (a_ji = 1 / a_ij)")
    vals, vecs = np.linalg.eig(A)
    i = int(np.argmax(vals.real))
    lam = float(vals[i].real)
    w = np.abs(vecs[:, i].real)
    w = w / w.sum()
    ci = (lam - n) / (n - 1) if n > 2 else 0.0
    ri = RANDOM_INDEX.get(n)
    if ri is None:
        raise ValueError(f"no random index for n = {n}")
    cr = ci / ri if ri > 0 else 0.0
    return w, lam, float(cr)


# ---------------------------------------------------------------- criteria


def _linear_down(d: np.ndarray, d_max: float) -> np.ndarray:
    return np.clip(1.0 - d / d_max, 0.0, 1.0)


def criteria(cfg, df: pd.DataFrame) -> pd.DataFrame:
    """0-1 criterion scores for each row of a C4 frame."""
    m = cfg["mcda"]
    buf = float(m["water_buffer_m"])
    d_water = np.expm1(df["log_dist_water"].to_numpy())
    lulc = sum(
        float(m["lulc_values"][c]) * df[f"frac_{c}"].to_numpy() for c in schema.OWN_FRACTION_CLASSES
    )
    out = pd.DataFrame(
        {
            "slope": _linear_down(df["slope_mean"].to_numpy(), float(m["slope_zero_deg"])),
            "road": _linear_down(np.expm1(df["log_dist_major"].to_numpy()), float(m["road_max_m"])),
            "built": _linear_down(
                np.expm1(df["log_dist_built"].to_numpy()), float(m["built_max_m"])
            ),
            "water": np.clip((d_water - buf) / buf, 0.0, 1.0),
            "lulc": np.clip(lulc, 0.0, 1.0),
        },
        index=df.index,
    )
    return out[list(m["criteria"])]


def weights(cfg, use_lulc: bool = True) -> tuple[pd.Series, dict]:
    """AHP weights of the criteria (optionally without land cover) and their consistency."""
    names = list(cfg["mcda"]["criteria"])
    A = parse_matrix(cfg["mcda"]["ahp"])
    if A.shape != (len(names), len(names)):
        raise ValueError(f"mcda.ahp is {A.shape}, expected {len(names)} x {len(names)}")
    if not use_lulc and "lulc" in names:
        keep = [i for i, n in enumerate(names) if n != "lulc"]
        A, names = A[np.ix_(keep, keep)], [names[i] for i in keep]
    w, lam, cr = ahp_weights(A)
    return pd.Series(w, index=names), {"lambda_max": lam, "consistency_ratio": cr, "n": len(names)}


def mcda_scores(cfg, year: int, cell_ids, use_lulc: bool = True) -> pd.DataFrame:
    """Weighted-overlay score of ``cell_ids`` from the ``year`` feature table."""
    c4 = schema.read_contract(schema.contract_path(cfg, "C4", year=year), "C4").set_index("cell_id")
    w, _ = weights(cfg, use_lulc)
    crit = criteria(cfg, c4.loc[np.asarray(cell_ids)])
    score = crit[w.index].to_numpy() @ w.to_numpy()
    return pd.DataFrame({"cell_id": np.asarray(cell_ids), "score": score})


# ---------------------------------------------------------------- run


def mcda_tif_path(cfg) -> Path:
    return Path(cfg.paths["outputs"]) / "mcda_score.tif"


def metrics_path(cfg) -> Path:
    return Path(cfg.paths["metrics"]) / "mcda.json"


def write_mcda(cfg) -> dict:
    """Score both MCDA variants for both runs; write C8 files, the GeoTIFF and ``mcda.json``."""
    labels = schema.read_contract(schema.contract_path(cfg, "C5"), "C5").set_index("cell_id")
    cand = labels.index[labels["candidate"]].to_numpy()
    use = usable_cells(cfg)
    base, latest = run_year(cfg, "validation"), run_year(cfg, "final")
    c4 = schema.read_contract(schema.contract_path(cfg, "C4", year=base), "C4").set_index("cell_id")
    ev = labels.loc[cand]
    keep = ~ev["ambiguous"].to_numpy()
    grew = ev["grew"].to_numpy()[keep]
    report: dict = {}
    for model, use_lulc in VARIANTS.items():
        w, cons = weights(cfg, use_lulc)
        if cons["consistency_ratio"] >= 0.1:
            raise ValueError(
                f"AHP consistency ratio {cons['consistency_ratio']:.3f} >= 0.1: revise mcda.ahp"
            )
        own = CRITERION_FEATURES["lulc"] if use_lulc else []
        feats = [f for c in w.index if c != "lulc" for f in CRITERION_FEATURES[c]]
        meta = {
            "model": model,
            "features": feats,
            "own_cell_inputs": own,
            "train_years": [],
            "description": "MCDA/AHP weighted overlay"
            + ("" if use_lulc else " without the land-cover criterion"),
            "weights": {k: round(float(v), 4) for k, v in w.items()},
            "consistency_ratio": cons["consistency_ratio"],
        }
        for run, year, ids in (("validation", base, cand), ("final", latest, use)):
            sc = mcda_scores(cfg, year, ids, use_lulc)
            schema.validate_frame(sc, "C8")
            p = scores_path(cfg, model, run)
            p.parent.mkdir(parents=True, exist_ok=True)
            sc.to_parquet(p, index=False)
            p.with_suffix(".json").write_text(json.dumps({**meta, "run": run}, indent=1))
            if run == "validation":
                schema.validate_score_meta(p.with_suffix(".json"))
                s = sc.set_index("cell_id").loc[cand, "score"].to_numpy()[keep]
                auc = float(roc_auc_score(grew, s))
            elif model == "mcda":
                write_probability_raster(cfg, sc, mcda_tif_path(cfg))
        report[model] = {**meta, **cons, "temporal_preview": {"auc_grew": auc}}
        log.info(
            "%s: weights %s, CR %.3f, AUC on grew %.3f",
            model,
            meta["weights"],
            cons["consistency_ratio"],
            auc,
        )
    # diagnostic only (weights are never tuned on the test label): each criterion alone
    crit = criteria(cfg, c4.loc[cand]).to_numpy()[keep]
    report["criterion_auc"] = {
        c: float(roc_auc_score(grew, crit[:, i])) for i, c in enumerate(cfg["mcda"]["criteria"])
    }
    d2b = float(roc_auc_score(grew, -c4.loc[cand, "log_dist_built"].to_numpy()[keep]))
    report["baseline_dist_to_built_auc"] = d2b
    report["n_cells"], report["n_grew"] = int(keep.sum()), int(grew.sum())
    p = metrics_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=1, allow_nan=False))
    return report


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    cfg = load_config()
    setup_logging(cfg, "suitability")
    write_mcda(cfg)


if __name__ == "__main__":
    main()
