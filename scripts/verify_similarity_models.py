"""Done check for P6.2, P6.5, P6.6 (reference set, random forests, held-out check).

1. reference set: OSM cells = C6 cells of the run's snapshot (read directly), ESRI fills =
   C4 built cells without an OSM building;
2. spatial blocks recomputed from the cell coordinates (2 km squares from the grid
   origin): the same partition as ``rf_model.spatial_blocks``; folds never split a block;
3. out of fold: refitting one fold with plain scikit-learn reproduces the stored scores
   of that fold's cells exactly, and in-sample scores would have a higher AUC;
4. temporal AUC preview recomputed by hand (Mann-Whitney U from ranks);
5. final scores cover exactly the usable cells of C7; ``rf_probability.tif`` equals them
   cell by cell and is NaN elsewhere;
6. held-out kNN scorer: brute-force numpy distances for 50 cells match;
7. quick-look ``outputs/figures/verify_similarity_models.png``.

Run: python scripts/verify_similarity_models.py
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import json
import sys

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from scipy.stats import rankdata  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402

from src.classify.label import c7_path  # noqa: E402
from src.config import load_config  # noqa: E402
from src.features import schema  # noqa: E402
from src.features.grid import lattice  # noqa: E402
from src.preprocess.raster import load_reference_grid  # noqa: E402
from src.similarity import holdout as ho  # noqa: E402
from src.similarity import reference as rs  # noqa: E402
from src.similarity import rf_model as rm  # noqa: E402

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def auc_by_hand(y: np.ndarray, s: np.ndarray) -> float:
    r = rankdata(s)
    n1, n0 = int(y.sum()), int((1 - y).sum())
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main() -> int:
    cfg = load_config()
    seed = int(cfg["project"]["random_seed"])
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1").set_index("cell_id")
    labels = schema.read_contract(schema.contract_path(cfg, "C5"), "C5").set_index("cell_id")
    metrics = json.loads(rm.metrics_path(cfg).read_text())

    print("== 1. reference set")
    for run, snap, year in (
        ("validation", "2018", cfg["years"]["baseline"]),
        ("final", "current", cfg["years"]["latest"]),
    ):
        ref = pd.read_parquet(rs.reference_path(cfg, run)).set_index("cell_id")
        b = gpd.read_file(schema.contract_path(cfg, "C6", snapshot=snap), ignore_geometry=True)
        c4 = pd.read_parquet(schema.contract_path(cfg, "C4", year=year)).set_index("cell_id")
        built = set(c4.index[c4["frac_built"] >= cfg["growth"]["built_min"]])
        osm = set(ref.index[ref["source"].isin(["osm", "both"])])
        esri = set(ref.index[ref["source"] == "esri"])
        ok = osm == set(b["cell_id"]) and esri == built - set(b["cell_id"])
        check(
            ok,
            f"{run}: {len(osm)} OSM cells = C6 {snap}; "
            f"{len(esri)} ESRI fills = built cells without OSM",
        )

    print("== 2. spatial blocks and folds")
    lat = lattice(cfg)
    ref_grid = load_reference_grid(cfg)
    blk = float(cfg["validation"]["spatial_block_m"])
    for model in rm.MODELS:
        ids, y = rm.training_set(labels.reset_index(), model)
        g = grid.loc[ids]
        bx = np.floor((g["x"] - ref_grid.transform.c) / blk).astype(int).astype(str)
        by = np.floor((ref_grid.transform.f - g["y"]) / blk).astype(int).astype(str)
        mine = (bx + "_" + by).to_numpy()
        theirs = rm.spatial_blocks(cfg, ids)
        same = (
            pd.Series(theirs).groupby(mine).nunique().eq(1).all()
            and pd.Series(mine).groupby(theirs).nunique().eq(1).all()
        )
        folds = rm.assign_folds(theirs, int(cfg["rf"]["n_folds"]), seed)
        split = pd.Series(folds).groupby(theirs).nunique().max()
        check(
            bool(same) and split == 1,
            f"{model}: blocks = 2 km squares from coordinates; no block in two folds",
        )

    print("== 3. out of fold")
    feats = rm.model_features(cfg, cfg["years"]["baseline"])
    for model in rm.MODELS:
        ids, y = rm.training_set(labels.reset_index(), model)
        folds = rm.assign_folds(rm.spatial_blocks(cfg, ids), int(cfg["rf"]["n_folds"]), seed)
        p = metrics[model]["best_params"]
        test = folds == 0
        X = feats.loc[ids].to_numpy()
        rf = RandomForestClassifier(
            n_estimators=int(cfg["rf"]["n_estimators"]), class_weight=cfg["rf"]["class_weight"],
            random_state=seed, n_jobs=-1, **p,
        ).fit(X[~test], y[~test])  # fmt: skip
        mine = rf.predict_proba(X[test])[:, 1]
        val = pd.read_parquet(rm.scores_path(cfg, model, "validation")).set_index("cell_id")
        cand = np.isin(ids[test], val.index)
        stored = val.loc[ids[test][cand], "score"].to_numpy()
        check(
            bool(np.allclose(mine[cand], stored)),
            f"{model}: fold 0 refit reproduces {cand.sum()} stored scores",
        )
        full = RandomForestClassifier(
            n_estimators=int(cfg["rf"]["n_estimators"]), class_weight=cfg["rf"]["class_weight"],
            random_state=seed, n_jobs=-1, **p,
        ).fit(X, y)  # fmt: skip
        ins = auc_by_hand(y, full.predict_proba(X)[:, 1])
        oof = metrics[model]["spatial_cv_auc"]["mean"]
        check(
            ins > oof,
            f"{model}: in-sample AUC {ins:.3f} > spatial-CV AUC {oof:.3f} (OOF is honest)",
        )

    print("== 4. temporal preview by hand")
    cand = labels.index[labels["candidate"] & ~labels["ambiguous"]]
    grew = labels.loc[cand, "grew"].to_numpy().astype(int)
    for model in rm.MODELS:
        s = (
            pd.read_parquet(rm.scores_path(cfg, model, "validation"))
            .set_index("cell_id")
            .loc[cand, "score"]
        )
        a = auc_by_hand(grew, s.to_numpy())
        st = metrics[model]["temporal_preview"]["auc_grew_oof"]
        check(abs(a - st) < 1e-9, f"{model}: AUC on grew {a:.3f} = stored {st:.3f}")

    print("== 5. final scores and GeoTIFF")
    c7 = pd.read_parquet(c7_path(cfg, "final"))
    usable = set(c7.loc[c7["class_3"] == schema.CLASS_USABLE, "cell_id"])
    fin = pd.read_parquet(rm.scores_path(cfg, "rf_change", "final"))
    check(
        set(fin["cell_id"]) == usable,
        f"final rf_change scores exactly the {len(usable)} usable cells",
    )
    with rasterio.open(rm.rf_probability_path(cfg)) as ds:
        img = ds.read(1)
        ok_grid = (
            ds.crs == cfg.crs and ds.res == (lat.cell_m, lat.cell_m) and img.shape == lat.shape
        )
    g = grid.loc[fin["cell_id"]]
    vals = img[g["row"], g["col"]]
    check(
        bool(ok_grid and np.allclose(vals, fin["score"])),
        "rf_probability.tif = final scores, on the cell lattice",
    )
    check(int(np.isfinite(img).sum()) == len(fin), "rf_probability.tif is NaN outside usable cells")
    check(bool(((vals >= 0) & (vals <= 1)).all()), "probabilities in [0, 1]")

    print("== 6. held-out kNN scorer by brute force")
    c4 = pd.read_parquet(schema.contract_path(cfg, "C4", year=cfg["years"]["baseline"])).set_index(
        "cell_id"
    )
    X = c4[list(schema.MODEL_INPUTS)]
    rng = np.random.default_rng(1)
    ref_ids = rng.choice(X.index.to_numpy(), 500, replace=False)
    q = rng.choice(X.index.to_numpy(), 50, replace=False)
    got = ho.scorers(cfg)["knn"](X, ref_ids, q)
    Z = ((X - X.mean()) / X.std(ddof=0)).to_numpy()
    pos = {c: i for i, c in enumerate(X.index)}
    R = Z[[pos[c] for c in ref_ids]]
    k = int(cfg["similarity"]["knn_k"])
    want = [-np.sort(np.linalg.norm(R - Z[pos[c]], axis=1))[:k].mean() for c in q]
    check(
        bool(np.allclose(got, want)),
        f"kNN score = mean distance to the {k} nearest references (50 cells)",
    )

    print("== 7. quick-look")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    for ax, (title, ids_, v) in zip(
        axes,
        [
            (
                "rf_change validation (OOF), candidates",
                *(lambda d: (d["cell_id"], d["score"]))(
                    pd.read_parquet(rm.scores_path(cfg, "rf_change", "validation"))
                ),
            ),
            ("grew 2022/23 (validation label)", cand, grew.astype(float)),
            ("rf_change final, usable cells", fin["cell_id"], fin["score"]),
        ],
        strict=True,
    ):
        im = np.full(lat.shape, np.nan)
        gg = grid.loc[np.asarray(ids_)]
        im[gg["row"], gg["col"]] = np.asarray(v)
        h = ax.imshow(im, cmap="magma", vmin=0, vmax=1)
        ax.set_title(title)
        ax.set_axis_off()
        fig.colorbar(h, ax=ax, shrink=0.7)
    out = cfg.paths["figures"] / "verify_similarity_models.png"
    fig.savefig(out, dpi=80, bbox_inches="tight")
    print(f"  wrote {out}")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
