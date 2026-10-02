"""Done check for P4.4–P4.5 (vector features, contract C3): are they correct?

Checks ``data/features/vector_features_*.parquet`` against independent computations:

1. C3 passes its contract and has exactly the grid cells (C1);
2. road distances recomputed with ``shapely.distance`` to the union of the roads
   (a different code path from the STRtree nearest-neighbour) for random cells;
3. spot check: every cell holding a major-road point is <= 70.7 m (half a cell
   diagonal) from a major road;
4. road density vs the exact road length inside a true 500 m circle;
5. building count / area fraction recomputed by a spatial join of footprint
   centroids with the cell squares;
6. snapshots: 2018 median density <= today's; where 2018 has a road > 50 m closer
   than today, that road has left today's drivable network (retagged 'track' or deleted);
7. quick-look maps ``outputs/figures/verify_vector_features.png``.

Run: python scripts/verify_vector_features.py
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import shapely  # noqa: E402

from src.config import load_config  # noqa: E402
from src.download.osm import osm_path, snapshots  # noqa: E402
from src.features import schema  # noqa: E402
from src.features.grid import lattice  # noqa: E402
from src.preprocess.vector import processed_osm_path  # noqa: E402

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def main() -> int:
    cfg = load_config()
    lat = lattice(cfg)
    cell = lat.cell_m
    cap = float(cfg["features"]["distance_cap_m"])
    radius = float(cfg["features"]["road_density_radius_m"])
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1").set_index("cell_id")
    snaps = list(snapshots(cfg))
    C3 = {
        s: schema.read_contract(schema.contract_path(cfg, "C3", snapshot=s), "C3").set_index(
            "cell_id"
        )
        for s in snaps
    }
    rng = np.random.default_rng(4)
    sample = rng.choice(grid.index.to_numpy(), 400, replace=False)

    for s in snaps:
        print(f"== snapshot {s}")
        df = C3[s]
        check(df.index.equals(grid.index), "1. same cells as the grid (C1)")
        roads = gpd.read_file(processed_osm_path(cfg, s, "roads"))
        major_u = shapely.union_all(roads.loc[roads["road_class"] == "major"].geometry.values)
        any_u = shapely.union_all(roads.geometry.values)
        pts = shapely.points(grid.loc[sample, "x"], grid.loc[sample, "y"])
        for name, u, col in (("major", major_u, "log_dist_major"), ("any", any_u, "log_dist_any")):
            want = np.minimum(shapely.distance(pts, u), cap)
            got = np.expm1(df.loc[sample, col].to_numpy())
            err = float(np.abs(got - want).max())
            check(
                err < 1e-6,
                f"2. dist to {name} road = shapely.distance to the union "
                f"(max err {err:.1e} m, 400 cells)",
            )

        # 3. cells holding a major-road point
        coords = shapely.get_coordinates(roads.loc[roads["road_class"] == "major"].geometry.values)
        coords = coords[rng.choice(len(coords), min(3000, len(coords)), replace=False)]
        row, col = lat.xy_to_rowcol(coords[:, 0], coords[:, 1])
        cid = row * lat.shape[1] + col
        cid = cid[np.isin(cid, grid.index)]
        dmax = float(np.expm1(df.loc[cid, "log_dist_major"]).max())
        check(
            dmax <= cell / np.sqrt(2) + 1e-6,
            f"3. {len(cid)} cells holding a major-road point: "
            f"max dist {dmax:.1f} m (<= {cell / np.sqrt(2):.1f})",
        )

        # 4. density vs an exact circle
        sub = sample[:250]
        circles = shapely.buffer(
            shapely.points(grid.loc[sub, "x"], grid.loc[sub, "y"]), radius, quad_segs=32
        )
        tree = shapely.STRtree(roads.geometry.values)
        exact = []
        for c in circles:
            idx = tree.query(c)
            km = shapely.length(shapely.intersection(roads.geometry.values[idx], c)).sum() / 1000
            exact.append(km / (np.pi * (radius / 1000) ** 2))
        exact = np.array(exact)
        got = df.loc[sub, "road_density"].to_numpy()
        r = float(np.corrcoef(exact, got)[0, 1])
        rel = np.median(np.abs(got - exact) / np.maximum(exact, 0.5))
        check(
            r > 0.97 and rel < 0.10,
            f"4. density vs exact 500 m circle: r = {r:.3f}, median rel. error {rel:.1%} "
            "(disk-of-cells approximation)",
        )

        # 5. buildings via spatial join with cell squares
        b = gpd.read_file(processed_osm_path(cfg, s, "buildings"), columns=["area_m2"])
        cents = gpd.GeoDataFrame(b[["area_m2"]], geometry=b.geometry.centroid, crs=b.crs)
        sq = gpd.GeoDataFrame(
            {"cell_id": sub},
            # plain arrays: a pandas Series here would be aligned on cell_id and give None
            geometry=shapely.box(
                grid.loc[sub, "x"].to_numpy() - cell / 2,
                grid.loc[sub, "y"].to_numpy() - cell / 2,
                grid.loc[sub, "x"].to_numpy() + cell / 2,
                grid.loc[sub, "y"].to_numpy() + cell / 2,
            ),
            crs=cfg.crs,
        )
        j = (
            gpd.sjoin(cents, sq, predicate="within")
            .groupby("cell_id")["area_m2"]
            .agg(["count", "sum"])
        )
        want_n = j["count"].reindex(sub).fillna(0).to_numpy()
        want_f = np.clip(j["sum"].reindex(sub).fillna(0).to_numpy() / cell**2, 0, 1)
        check(
            bool((want_n == df.loc[sub, "bldg_count"].to_numpy()).all()),
            "5. bldg_count = spatial join count (250 cells)",
        )
        check(
            bool(np.allclose(want_f, df.loc[sub, "bldg_area_frac"].to_numpy())),
            "5. bldg_area_frac = spatial join area / cell area",
        )

    if len(snaps) == 2:
        print("== 6. 2018 vs current")
        a, b = C3[snaps[0]], C3[snaps[1]]
        check(
            a["road_density"].median() <= b["road_density"].median(),
            f"median density 2018 {a['road_density'].median():.1f} "
            f"<= current {b['road_density'].median():.1f} km/km²",
        )
        # Roads are mostly added, but OSM also retags ways (many 2018 'unclassified' /
        # 'residential' ways are 'track' today, which cleaning drops) and deletes them.
        # So where 2018 has a much closer road, that 2018 road must be gone from today's
        # cleaned network: retagged non-drivable, or deleted/merged.
        closer = (np.expm1(a["log_dist_any"]) < np.expm1(b["log_dist_any"]) - 50).to_numpy()
        print(f"  2018 has a road > 50 m closer than today in {closer.mean():.1%} of cells")
        ids = a.index[closer]
        r18 = gpd.read_file(processed_osm_path(cfg, snaps[0], "roads"))
        cur = gpd.read_file(
            processed_osm_path(cfg, snaps[1], "roads"), columns=["osm_id"], ignore_geometry=True
        )
        raw = gpd.read_file(
            osm_path(cfg, snaps[1], "roads"), columns=["osm_id", "highway"], ignore_geometry=True
        )
        pts = shapely.points(grid.loc[ids, "x"].to_numpy(), grid.loc[ids, "y"].to_numpy())
        near = r18["osm_id"].to_numpy()[
            shapely.STRtree(r18.geometry.values).query_nearest(pts, all_matches=False)[1]
        ]
        still = np.isin(near, cur["osm_id"])
        retag = ~still & np.isin(near, raw["osm_id"])
        tags = (
            raw.drop_duplicates("osm_id")
            .set_index("osm_id")
            .loc[near[retag], "highway"]
            .value_counts()
        )
        print(
            f"  their nearest 2018 road today: drivable {still.mean():.1%}, "
            f"retagged {retag.mean():.1%} "
            f"({dict(tags.head(3))}), deleted/merged {(~still & ~retag).mean():.1%}"
        )
        check(
            still.mean() < 0.10,
            "> 90% of those cells are explained by the 2018 road leaving the drivable network",
        )

    print("== 7. quick-look")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    for i, s in enumerate(snaps):
        for j, (colname, cmap) in enumerate(
            (
                ("log_dist_major", "magma_r"),
                ("road_density", "viridis"),
                ("bldg_area_frac", "Greys"),
            )
        ):
            img = np.full(lat.shape, np.nan)
            img[grid["row"], grid["col"]] = C3[s][colname].to_numpy()
            im = axes[i, j].imshow(img, cmap=cmap, vmax=np.nanpercentile(img, 99))
            fig.colorbar(im, ax=axes[i, j], shrink=0.7)
            axes[i, j].set_title(f"{colname} ({s})")
            axes[i, j].set_axis_off()
    out = cfg.paths["figures"] / "verify_vector_features.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=80, bbox_inches="tight")
    print(f"  wrote {out}")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
