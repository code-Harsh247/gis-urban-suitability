"""Done check for P5.1-P5.3 (clustering): are the cluster outputs correct?

Checks ``outputs/clusters_{run}.parquet`` and ``outputs/metrics/`` against independent
computations:

1. one row per feature-table cell (C4 of the run's year), ids 0..k-1, all used;
2. K-Means fixed point, recomputed with numpy: every cell is assigned to its nearest
   centroid (in z-scores), and every centroid is the mean of its cells;
3. centroid CSV = groupby mean of the raw C4 inputs;
4. silhouette recomputed on a different random sample is within 0.02 of the stored one;
   Davies-Bouldin recomputed by hand (numpy) equals the stored one;
5. reproducible: refitting with the same seed gives identical assignments;
6. landmarks from OSM: the largest named lake falls in the water cluster; cells in
   Bannerghatta NP fall in the tree or rangeland clusters;
7. quick-look map ``outputs/figures/verify_clustering.png``.

Run: python scripts/verify_clustering.py
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
from sklearn.metrics import silhouette_score  # noqa: E402

from src.classify import cluster as cl  # noqa: E402
from src.config import load_config  # noqa: E402
from src.features import schema  # noqa: E402
from src.features.grid import lattice, xy_to_cell_id  # noqa: E402
from src.preprocess.vector import processed_osm_path  # noqa: E402

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def davies_bouldin(Z: np.ndarray, labels: np.ndarray) -> float:
    ks = np.unique(labels)
    cen = np.array([Z[labels == k].mean(axis=0) for k in ks])
    s = np.array([np.linalg.norm(Z[labels == k] - cen[i], axis=1).mean() for i, k in enumerate(ks)])
    d = np.linalg.norm(cen[:, None] - cen[None], axis=2)
    np.fill_diagonal(d, np.inf)
    return float(np.mean(np.max((s[:, None] + s[None]) / d, axis=1)))


def main() -> int:
    cfg = load_config()
    k = int(cfg["clustering"]["k"])
    seed = int(cfg["project"]["random_seed"])
    metrics = json.loads(cl.metrics_path(cfg).read_text())
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1").set_index("cell_id")
    lat = lattice(cfg)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5))

    for ax, run in zip(axes, cl.RUNS, strict=True):
        year = cl.run_year(cfg, run)
        print(f"== {run} ({year})")
        a = pd.read_parquet(cl.clusters_path(cfg, run))
        c4 = schema.read_contract(schema.contract_path(cfg, "C4", year=year), "C4")
        check(
            a["cell_id"].tolist() == c4["cell_id"].tolist(),
            f"1. {len(a)} rows, same cells and order as C4 {year}",
        )
        check(set(a["cluster_id"]) == set(range(k)), f"1. cluster ids 0..{k - 1}, all used")

        X = c4[metrics[run]["inputs"]].to_numpy(float)
        Z = (X - X.mean(axis=0)) / X.std(axis=0)  # population std, as StandardScaler
        lab = a["cluster_id"].to_numpy()
        if cfg["clustering"]["method"] == "kmeans" and not cfg["clustering"].get("use_pca"):
            cen = np.array([Z[lab == i].mean(axis=0) for i in range(k)])
            nearest = np.argmin(((Z[:, None, :] - cen[None]) ** 2).sum(axis=2), axis=1)
            share = float((nearest == lab).mean())
            check(
                share > 0.999,
                f"2. K-Means fixed point: {share:.4%} of cells are nearest to their own centroid",
            )

        csv = pd.read_csv(cl.metrics_path(cfg).parent / f"cluster_centroids_{run}.csv", index_col=0)
        mine = c4[metrics[run]["inputs"]].groupby(lab).mean()
        check(
            bool(np.allclose(csv[mine.columns].to_numpy(), mine.to_numpy(), atol=1e-3)),
            "3. centroid CSV = groupby mean of C4",
        )
        check(
            bool((csv["n_cells"].to_numpy() == np.bincount(lab, minlength=k)).all()),
            "3. n_cells per cluster",
        )

        stored = metrics[run]["chosen"]
        sil = float(silhouette_score(Z, lab, sample_size=10000, random_state=seed + 1))
        check(
            abs(sil - stored["silhouette"]) < 0.02,
            f"4. silhouette {stored['silhouette']:.3f} (other sample: {sil:.3f})",
        )
        db = davies_bouldin(Z, lab)
        check(
            abs(db - stored["davies_bouldin"]) < 1e-6,
            f"4. Davies-Bouldin {stored['davies_bouldin']:.3f} = by hand {db:.3f}",
        )

        again = cl.cluster_run(cfg, run, do_scan=False)["assignments"]
        check(again.equals(a), "5. refit with the same seed gives identical assignments")

        # 6. landmarks
        water_c = int(csv["frac_water"].idxmax())
        water = gpd.read_file(
            processed_osm_path(cfg, schema.vector_snapshot_for(cfg, year), "water")
        )
        lakes = water.loc[(water["kind"] == "water_body") & water["name"].notna()]
        lake = lakes.loc[lakes.area.idxmax()]
        pt = lake.geometry.representative_point()
        cid = int(xy_to_cell_id(cfg, np.array([pt.x]), np.array([pt.y]))[0])
        got = int(a.set_index("cell_id").at[cid, "cluster_id"])
        check(got == water_c, f"6. {lake['name']} is in the water cluster {water_c} (got {got})")
        park = gpd.read_file(processed_osm_path(cfg, "current", "protected")).union_all()
        xy = grid.loc[a["cell_id"]]
        inside = gpd.points_from_xy(xy["x"], xy["y"]).within(park)
        veg_c = set(csv.index[(csv["frac_tree"] + csv["frac_range"]) > 0.5])
        share = float(np.isin(lab[inside], list(veg_c)).mean())
        check(
            share > 0.9,
            f"6. {share:.1%} of {int(inside.sum())} Bannerghatta cells "
            f"in tree/rangeland clusters {sorted(veg_c)}",
        )

        img = np.full(lat.shape, np.nan)
        img[xy["row"], xy["col"]] = lab
        im = ax.imshow(img, cmap="tab10", vmin=-0.5, vmax=9.5, interpolation="nearest")
        ax.set_title(f"clusters {run} ({year}), k = {k}")
        ax.set_axis_off()
    fig.colorbar(im, ax=axes, ticks=range(k), shrink=0.7)
    out = cfg.paths["figures"] / "verify_clustering.png"
    fig.savefig(out, dpi=80, bbox_inches="tight")
    print(f"== 7. wrote {out}")
    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
