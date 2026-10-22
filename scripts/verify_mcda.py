"""Done check for P7.3 (MCDA / AHP baseline).

1. AHP weights recomputed by power iteration (not numpy's eigen-solver); lambda_max and
   CR = (lambda_max - n) / (n - 1) / RI equal the stored ones; CR < 0.1;
2. 200 random candidate cells: the score recomputed by hand from the raw C4 values
   (plain Python, one cell at a time) equals the stored validation score;
3. final scores cover the usable cells of C7; ``mcda_score.tif`` equals them;
4. temporal AUC recomputed from ranks (Mann-Whitney U).

Run: python scripts/verify_mcda.py
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np
import pandas as pd
import rasterio
from scipy.stats import rankdata

from src.classify.label import c7_path
from src.config import load_config
from src.features import schema
from src.similarity.rf_model import scores_path
from src.suitability import mcda

failures: list[str] = []
RI = {3: 0.58, 4: 0.90, 5: 1.12}


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def power_iteration(A: np.ndarray, it: int = 1000) -> tuple[np.ndarray, float]:
    w = np.ones(len(A)) / len(A)
    for _ in range(it):
        v = A @ w
        w = v / v.sum()
    return w, float((A @ w / w).mean())


def by_hand(row: pd.Series, m: dict, w: dict) -> float:
    def down(d, dmax):
        return min(1.0, max(0.0, 1.0 - d / dmax))

    dw = math.expm1(row["log_dist_water"])
    crit = {
        "slope": down(row["slope_mean"], m["slope_zero_deg"]),
        "road": down(math.expm1(row["log_dist_major"]), m["road_max_m"]),
        "built": down(math.expm1(row["log_dist_built"]), m["built_max_m"]),
        "water": min(1.0, max(0.0, (dw - m["water_buffer_m"]) / m["water_buffer_m"])),
        "lulc": sum(m["lulc_values"][c] * row[f"frac_{c}"] for c in schema.OWN_FRACTION_CLASSES),
    }
    return sum(w[c] * crit[c] for c in w)


def main() -> int:
    cfg = load_config()
    m = cfg["mcda"]
    rep = json.loads(mcda.metrics_path(cfg).read_text())

    print("== 1. AHP")
    A = mcda.parse_matrix(m["ahp"])
    for model, keep in (
        ("mcda", list(range(len(A)))),
        ("mcda_no_lulc", [i for i, c in enumerate(m["criteria"]) if c != "lulc"]),
    ):
        sub = A[np.ix_(keep, keep)]
        w, lam = power_iteration(sub)
        n = len(sub)
        cr = (lam - n) / (n - 1) / RI[n]
        names = [m["criteria"][i] for i in keep]
        stored = rep[model]["weights"]
        ok = (
            np.allclose(w, [stored[c] for c in names], atol=1e-4)
            and abs(cr - rep[model]["consistency_ratio"]) < 1e-6
        )
        check(
            ok and cr < 0.1, f"{model}: power-iteration weights and CR {cr:.4f} = stored; CR < 0.1"
        )

    print("== 2. scores by hand")
    base = cfg["years"]["baseline"]
    c4 = pd.read_parquet(schema.contract_path(cfg, "C4", year=base)).set_index("cell_id")
    val = pd.read_parquet(scores_path(cfg, "mcda", "validation")).set_index("cell_id")
    ids = np.random.default_rng(3).choice(val.index.to_numpy(), 200, replace=False)
    w = rep["mcda"]["weights"]
    mine = np.array([by_hand(c4.loc[i], m, w) for i in ids])
    err = float(np.abs(mine - val.loc[ids, "score"].to_numpy()).max())
    check(
        err < 1e-3,
        f"200 cells recomputed by hand, max difference {err:.1e} (weights stored to 4 d.p.)",
    )

    print("== 3. final scores and GeoTIFF")
    c7 = pd.read_parquet(c7_path(cfg, "final"))
    usable = set(c7.loc[c7["class_3"] == schema.CLASS_USABLE, "cell_id"])
    fin = pd.read_parquet(scores_path(cfg, "mcda", "final"))
    check(set(fin["cell_id"]) == usable, f"final mcda scores the {len(usable)} usable cells")
    grid = pd.read_parquet(schema.contract_path(cfg, "C1")).set_index("cell_id").loc[fin["cell_id"]]
    with rasterio.open(mcda.mcda_tif_path(cfg)) as ds:
        img = ds.read(1)
    same = np.allclose(img[grid["row"], grid["col"]], fin["score"])
    check(
        bool(same) and int(np.isfinite(img).sum()) == len(fin),
        "mcda_score.tif = final scores, NaN elsewhere",
    )

    print("== 4. temporal AUC from ranks")
    lab = pd.read_parquet(schema.contract_path(cfg, "C5")).set_index("cell_id")
    cand = lab.index[lab["candidate"] & ~lab["ambiguous"]]
    y = lab.loc[cand, "grew"].to_numpy().astype(int)
    r = rankdata(val.loc[cand, "score"].to_numpy())
    auc = (r[y == 1].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (1 - y).sum())
    check(
        abs(auc - rep["mcda"]["temporal_preview"]["auc_grew"]) < 1e-9,
        f"AUC on grew {auc:.3f} = stored",
    )

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
