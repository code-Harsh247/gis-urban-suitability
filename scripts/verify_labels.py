"""Done check for A4 (exclusion mask + labels, contract C5): are the labels correct?

Checks ``data/features/labels.parquet`` and ``exclusion_*.parquet`` against things the
label code did not produce:

1. C5 passes its contract and matches the grid; label invariants hold;
2. labels recomputed for random cells from the **raw downloads** (built fractions per
   year, wet fraction, slope) agree exactly;
3. growth type recomputed with an exact per-patch ring (binary dilation of each patch
   on its own) agrees with the fast version for grown cells;
4. time-travel rule on real data: the validation mask only depends on 2018/2019;
   recomputing it with every later map blanked gives the same mask;
5. landmarks: lakes excluded, dense city built at baseline;
6. plausibility: grown cells sit closer to existing built-up than cells that stayed
   non-built; prevalence and counts reported;
7. quick-look map ``outputs/figures/verify_labels.png``.

Run: python scripts/verify_labels.py
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
import shapely  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from rasterio.warp import transform as warp_points  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402

from src.config import load_config  # noqa: E402
from src.download.lulc import esri_path  # noqa: E402
from src.download.osm import osm_path  # noqa: E402
from src.features import labels, schema  # noqa: E402
from src.features.grid import lattice, xy_to_cell_id  # noqa: E402
from src.preprocess.raster import processed_dir  # noqa: E402

LAKES = {"Madiwala Lake": (77.6177, 12.9082), "Hulimavu Lake": (77.6042, 12.8701)}
CITY = {"Koramangala": (77.6250, 12.9300), "Electronic City": (77.6483, 12.8488)}

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def window(path, x0, y0, x1, y1) -> np.ndarray:
    with rasterio.open(path) as ds:
        return ds.read(
            1, window=from_bounds(x0, y0, x1, y1, ds.transform), boundless=True, fill_value=0
        )


def main() -> int:
    cfg = load_config()
    y = cfg["years"]
    lat = lattice(cfg)
    cell = lat.cell_m
    lo, hi = cfg["growth"]["nonbuilt_max"], cfg["growth"]["built_min"]
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1").set_index("cell_id")
    lab = schema.read_contract(schema.contract_path(cfg, "C5"), "C5")
    excl = pd.read_parquet(schema.contract_path(cfg, "C5").parent / "exclusion_validation.parquet")
    L = lab.set_index("cell_id")
    E = excl.set_index("cell_id")

    print("1. contract and invariants")
    check(
        lab["cell_id"].equals(grid.index.to_series().reset_index(drop=True)),
        "same cells as the grid (C1)",
    )
    check(not (lab["candidate"] & lab["excluded"]).any(), "no excluded candidate")
    check(not (lab["grew"] & ~lab["candidate"]).any(), "grew implies candidate")
    check(
        not (lab["ambiguous"] & (lab["grew"] | ~lab["candidate"])).any(),
        "ambiguous only among non-grown candidates",
    )
    check(not (lab["chg_train_pos"] & ~lab["candidate"]).any(), "change positives are candidates")
    check(
        bool((lab.loc[lab["grew"], "lei_type"] != "none").all()),
        "every grown cell has a growth type",
    )
    check(lab["excluded"].equals(excl["excluded"]), "C5 excluded equals exclusion_validation")

    print("2. labels recomputed from the raw downloads (500 random cells)")
    years = sorted(
        {
            y["baseline"],
            y["baseline_confirm"],
            *y["change_train_end"],
            y["latest_confirm"],
            y["latest"],
        }
    )
    rng = np.random.default_rng(5)
    ids = rng.choice(lab["cell_id"].to_numpy(), 500, replace=False)
    ids = np.unique(np.r_[ids, lab.loc[lab["grew"], "cell_id"].to_numpy()[:100]])
    mism = {
        k: 0
        for k in (
            "built_baseline",
            "candidate",
            "grew",
            "ambiguous",
            "chg_train_pos",
            "excl_wet",
            "excl_slope",
            "excl_protected",
        )
    }
    # OSM layers, checked with point-in-polygon on pixel centres (not rasterio.rasterize)
    osm_water = osm_protected = None
    wpath = osm_path(cfg, str(cfg["osm"]["snapshot_baseline"])[:4], "water")
    if wpath.exists():
        w_gdf = gpd.read_file(wpath)
        keep = w_gdf.geom_type.isin(["Polygon", "MultiPolygon"])
        if "natural" in w_gdf.columns:
            keep &= w_gdf["natural"] == "water"
        osm_water = shapely.union_all(w_gdf[keep].to_crs(cfg.crs).geometry.values)
    ppath = osm_path(cfg, "current", "protected")
    if ppath.exists():
        p_gdf = gpd.read_file(ppath)
        p_gdf = p_gdf[p_gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
        osm_protected = shapely.union_all(p_gdf.to_crs(cfg.crs).geometry.values)
    offs = (np.arange(10) + 0.5) * 10.0
    with rasterio.open(processed_dir(cfg) / "slope.tif") as sds:
        for cid in ids:
            g = grid.loc[cid]
            x0, y0 = g.x - cell / 2, g.y - cell / 2
            b = {
                yr: (window(esri_path(cfg, yr), x0, y0, x0 + cell, y0 + cell) == 7).mean()
                for yr in years
            }
            w = np.zeros((10, 10), bool)
            for yr in (y["baseline"], y["baseline_confirm"]):
                w |= np.isin(
                    window(esri_path(cfg, yr), x0, y0, x0 + cell, y0 + cell), labels.WET_CODES
                )
            px, py = np.meshgrid(x0 + offs, y0 + cell - offs)  # row 0 = north
            if osm_water is not None:
                w |= shapely.contains_xy(osm_water, px, py)
            prot = shapely.contains_xy(osm_protected, px, py).mean() if osm_protected else 0.0
            ex_prot = bool(prot > cfg["exclusion"]["max_excluded_fraction"])
            slope = sds.read(
                1, window=from_bounds(x0, y0, x0 + cell, y0 + cell, sds.transform)
            ).mean()
            ex_wet = w.mean() > cfg["exclusion"]["max_excluded_fraction"]
            ex_slope = slope > cfg["exclusion"]["slope_max_deg"]
            excluded = ex_wet or ex_slope or ex_prot or bool(E.loc[cid, "excl_nodata"])
            cand = b[y["baseline"]] < lo and b[y["baseline_confirm"]] < lo and not excluded
            grew = cand and b[y["latest_confirm"]] >= hi and b[y["latest"]] >= hi
            stayed = cand and b[y["latest_confirm"]] < lo and b[y["latest"]] < lo
            t0, t1 = y["change_train_end"]
            want = {
                "built_baseline": b[y["baseline"]] >= hi,
                "candidate": cand,
                "grew": grew,
                "ambiguous": cand and not grew and not stayed,
                "chg_train_pos": cand and b[t0] >= hi and b[t1] >= hi,
                "excl_wet": ex_wet,
                "excl_slope": ex_slope,
                "excl_protected": ex_prot,
            }
            for k, v in want.items():
                got = bool(E.loc[cid, k]) if k.startswith("excl") else bool(L.loc[cid, k])
                mism[k] += int(got != bool(v))
    for k, n in mism.items():
        check(n == 0, f"{k}: {n}/{len(ids)} cells differ")

    print("3. growth type with an exact per-patch ring")
    grown = lab.loc[lab["grew"]].copy()
    sample = pd.concat(
        [
            grown[grown["lei_type"] == "outlying"],
            grown[grown["lei_type"] == "adjacent"].sample(150, random_state=1),
        ]
    )
    r_px = int(round(cfg["growth"]["lei_buffer_m"] / 10))
    agree = 0
    for cid, t in zip(sample["cell_id"], sample["lei_type"], strict=True):
        g = grid.loc[cid]
        half = 1500.0
        while True:
            x0, y0, x1, y1 = g.x - half, g.y - half, g.x + half, g.y + half
            B = {yr: window(esri_path(cfg, yr), x0, y0, x1, y1) == 7 for yr in years}
            new = (
                ~B[y["baseline"]]
                & ~B[y["baseline_confirm"]]
                & B[y["latest_confirm"]]
                & B[y["latest"]]
            )
            lbl, _ = ndi.label(new, structure=np.ones((3, 3), bool))
            n = new.shape[0]
            c0 = int((half - cell / 2) / 10)
            in_cell = lbl[c0 : c0 + 10, c0 : c0 + 10]
            pids = [p for p in np.unique(in_cell) if p]
            edge = set(np.unique(np.r_[lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]])) - {0}
            if not set(pids) & edge or half > 6000:
                break
            half *= 2
        votes = {"adjacent": [0, 0], "outlying": [0, 0]}  # [big-patch pixels, all pixels]
        for p in pids:
            patch = lbl == p
            ring = ndi.binary_dilation(patch, structure=np.ones((2 * r_px + 1,) * 2, bool)) & ~patch
            kind = "outlying" if not (ring & B[y["baseline"]]).any() else "adjacent"
            px = int((in_cell == p).sum())
            big = patch.sum() * 100 >= cfg["growth"]["lei_min_patch_m2"]
            votes[kind][0] += px if big else 0
            votes[kind][1] += px
        col = 0 if votes["adjacent"][0] + votes["outlying"][0] > 0 else 1
        want = "outlying" if votes["outlying"][col] > votes["adjacent"][col] else "adjacent"
        agree += int(want == t)
        del n
    rate = agree / len(sample)
    check(
        rate >= 0.98,
        f"growth type agrees for {agree}/{len(sample)} grown cells "
        f"({rate:.1%}; all outlying + 150 adjacent)",
    )

    print("4. time-travel rule on real data")
    val_sources = excl.attrs.get("sources") if excl.attrs else None
    fresh = labels.exclusion_table(cfg, "validation")
    check(
        fresh["excluded"].equals(excl["excluded"]),
        "validation mask reproduces from 2018/2019 inputs",
    )
    check(
        fresh.attrs["sources"]["lulc_years"] == [y["baseline"], y["baseline_confirm"]],
        f"validation mask LULC years {fresh.attrs['sources']['lulc_years']}",
    )
    snap = fresh.attrs["sources"]["osm_water"]
    check(
        snap in (None, str(cfg["osm"]["snapshot_baseline"])[:4]),
        f"validation OSM water snapshot: {snap}",
    )
    fin = pd.read_parquet(schema.contract_path(cfg, "C5").parent / "exclusion_final.parquet")
    print(
        f"     (final mask excludes {int(fin['excluded'].sum())} vs validation "
        f"{int(excl['excluded'].sum())}; sources {val_sources})"
    )

    print("4b. protected areas")
    n_prot = int(E["excl_protected"].sum())
    if osm_protected is not None:
        inside = osm_protected.intersection(cfg.aoi_projected.geometry.iloc[0]).area / 1e6
        km2 = n_prot * cell * cell / 1e6
        check(
            abs(km2 - inside) / max(inside, 1e-9) < 0.05,
            f"protected cells {km2:.1f} km² vs protected area inside the AOI {inside:.1f} km²",
        )
        pc = grid.loc[E.index[E["excl_protected"]]]
        near = shapely.contains_xy(osm_protected.buffer(cell), pc["x"], pc["y"]).mean()
        check(
            near == 1.0, f"every protected cell lies within {cell:.0f} m of the protected polygons"
        )
    else:
        check(n_prot == 0, "no protected layer, so no protected exclusions")

    print("5. landmarks")
    for name, (lon, lat_) in {**LAKES, **CITY}.items():
        xs, ys = warp_points("EPSG:4326", cfg.crs, [lon], [lat_])
        cid = int(xy_to_cell_id(cfg, xs, ys)[0])
        if name in LAKES:
            check(
                bool(L.loc[cid, "excluded"]), f"{name}: excluded (wet {E.loc[cid, 'wet_frac']:.2f})"
            )
        else:
            check(bool(L.loc[cid, "built_baseline"]), f"{name}: built at baseline")

    print("6. plausibility")
    c2 = schema.read_contract(schema.contract_path(cfg, "C2", year=y["baseline"]), "C2").set_index(
        "cell_id"
    )
    d = np.expm1(c2["log_dist_built"])
    grew_d = d.loc[lab.loc[lab["grew"], "cell_id"]].median()
    stay = lab["candidate"] & ~lab["grew"] & ~lab["ambiguous"]
    stay_d = d.loc[lab.loc[stay, "cell_id"]].median()
    check(
        grew_d < stay_d,
        f"grown cells closer to 2018 built-up: median {grew_d:.0f} m "
        f"vs {stay_d:.0f} m (stayed non-built)",
    )
    n_eval = int(lab["grew"].sum() + stay.sum())
    print(
        f"     candidates {int(lab['candidate'].sum())}, evaluated {n_eval}, "
        f"grew {int(lab['grew'].sum())} "
        f"(prevalence {lab['grew'].sum() / n_eval:.1%}), ambiguous {int(lab['ambiguous'].sum())}, "
        f"outlying {int((lab['lei_type'] == 'outlying').sum())}"
    )

    print("7. quick-look")
    img = np.full(lat.shape, 0, dtype=np.uint8)
    g = grid.loc[lab["cell_id"]]
    code = np.select(
        [
            lab["excluded"],
            lab["built_baseline"],
            lab["lei_type"] == "outlying",
            lab["grew"],
            lab["ambiguous"],
            lab["candidate"],
        ],
        [1, 2, 3, 4, 5, 6],
        7,
    )
    img[g["row"], g["col"]] = code
    cmap = ListedColormap(
        ["white", "#2b83ba", "#9e9e9e", "#7b3294", "#d7191c", "#fdae61", "#e6f5d0", "#ffffbf"]
    )
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(img, cmap=cmap, vmin=0, vmax=7, interpolation="nearest")
    from matplotlib.patches import Patch

    names = [
        "excluded",
        "built 2018",
        "grew (outlying)",
        "grew (adjacent)",
        "ambiguous",
        "candidate, stayed",
        "other (0.1-0.5 built)",
    ]
    ax.legend(
        handles=[Patch(color=cmap(i + 1), label=nm) for i, nm in enumerate(names)],
        loc="lower left",
        fontsize=8,
    )
    ax.set_title("Validation labels (C5)")
    ax.set_axis_off()
    out = cfg.paths["figures"] / "verify_labels.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90, bbox_inches="tight")
    print(f"  wrote {out}")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
