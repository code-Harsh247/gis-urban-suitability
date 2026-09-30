"""Done check for A3 (grid C1 + raster features C2): are the features correct?

Checks ``data/features/`` against things the feature code did not produce:

1. C1: cell count matches the AOI area, ids unique, centres inside the AOI, cells on
   the reference lattice, cells tile the AOI;
2. C2: passes its contract, same cells as C1, fractions sum to 1;
3. fractions recomputed from the **raw download** for random cells (exact);
4. ring fractions recomputed by brute force over neighbouring cells;
5. distance to built-up (outside the cell) and to water recomputed by brute-force search;
6. terrain vs the raw DEM;
7. leak guard: fully built cells never have distance 0 to built-up;
8. landmarks: lakes are water with distance 0, the dense city is built, Bannerghatta
   is surrounded by trees/rangeland;
9. growth 2018 -> 2023 is positive;
10. quick-look maps in ``outputs/figures/verify_features.png``.

Run: python scripts/verify_features.py
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
import shapely  # noqa: E402
from rasterio.warp import transform as warp_points  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402

from src.config import load_config  # noqa: E402
from src.download.dem import dem_path  # noqa: E402
from src.download.lulc import esri_path  # noqa: E402
from src.features import schema  # noqa: E402
from src.features.grid import lattice, xy_to_cell_id  # noqa: E402
from src.features.lulc_features import ESRI_CODE  # noqa: E402
from src.features.raster_features import features_years  # noqa: E402

LANDMARKS = {
    "Madiwala Lake": (77.6177, 12.9082),
    "Koramangala": (77.6250, 12.9300),
    "Bannerghatta block": (77.5750, 12.7800),
}

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def read_window(path, left, bottom, right, top) -> np.ndarray:
    with rasterio.open(path) as ds:
        return ds.read(
            1,
            window=from_bounds(left, bottom, right, top, ds.transform),
            boundless=True,
            fill_value=0,
        )


def brute_dist(raw_path, cx, cy, cell_m, cls, outside_cell: bool, cap: float) -> float:
    """Nearest pixel of ``cls`` to (cx, cy) by scanning growing windows of the raw raster."""
    for half in (300.0, 1000.0, 2500.0, cap + 50):
        arr = read_window(raw_path, cx - half, cy - half, cx + half, cy + half)
        r, c = np.nonzero(arr == cls)
        if r.size == 0:
            continue
        px = cx - half + (c + 0.5) * 10.0
        py = cy + half - (r + 0.5) * 10.0
        if outside_cell:
            inside = (np.abs(px - cx) < cell_m / 2) & (np.abs(py - cy) < cell_m / 2)
            px, py = px[~inside], py[~inside]
        if px.size:
            d = float(np.hypot(px - cx, py - cy).min())
            if d <= half:  # anything outside this window is farther than ``half``
                return min(d, cap)
    return cap


def main() -> int:
    cfg = load_config()
    lat = lattice(cfg)
    cell = lat.cell_m
    years = features_years(cfg)
    cap = float(cfg["features"]["distance_cap_m"])
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    c2 = {y: schema.read_contract(schema.contract_path(cfg, "C2", year=y), "C2") for y in years}
    sample = grid.sample(300, random_state=11)

    print("1. grid (C1)")
    n_exp = cfg.aoi_area_km2 * 1e6 / cell**2
    check(
        abs(len(grid) - n_exp) / n_exp < 0.01, f"{len(grid)} cells vs AOI area / cell = {n_exp:.0f}"
    )
    check(grid["cell_id"].is_unique, "cell ids unique")
    aoi = cfg.aoi_projected.geometry.iloc[0]
    check(bool(shapely.contains_xy(aoi, grid["x"], grid["y"]).all()), "all centres inside the AOI")
    on_lattice = np.allclose(((grid["x"] - cell / 2 - lat.left) / cell) % 1, 0) and np.allclose(
        ((lat.top - grid["y"] - cell / 2) / cell) % 1, 0
    )
    check(on_lattice, "cells on the reference lattice")
    np.testing.assert_array_equal(
        xy_to_cell_id(cfg, grid["x"] + 30, grid["y"] - 30), grid["cell_id"]
    )
    check(True, "xy_to_cell_id maps points back to their cell")
    union = shapely.union_all(
        shapely.box(grid.x - cell / 2, grid.y - cell / 2, grid.x + cell / 2, grid.y + cell / 2)
    )
    check(
        abs(union.area - aoi.area) / aoi.area < 0.01,
        f"cells tile the AOI (area {union.area / 1e6:.1f} vs {aoi.area / 1e6:.1f} km²)",
    )

    print("2. raster features (C2)")
    for y, df in c2.items():
        check(df["cell_id"].equals(grid["cell_id"]), f"{y}: same cells as the grid")
        s = df[list(schema.OWN_FRACTIONS)].sum(axis=1)
        check(
            bool(np.allclose(s, 1.0)), f"{y}: fractions sum to 1 (max err {abs(s - 1).max():.1e})"
        )
        check(float(df["nodata_frac"].max()) == 0.0, f"{y}: no nodata")

    for y in years:
        df = c2[y].set_index("cell_id")
        raw = esri_path(cfg, y)
        print(f"3-5. independent recomputation, {y} (300 random cells)")
        frac_err = ring_err = 0.0
        d_b_err, d_w_err = [], []
        for _, g in sample.iterrows():
            x0, y0 = g.x - cell / 2, g.y - cell / 2
            block = read_window(raw, x0, y0, x0 + cell, y0 + cell)
            for name in ("built", "tree", "crop", "range", "water"):
                frac_err = max(
                    frac_err,
                    abs((block == ESRI_CODE[name]).mean() - df.loc[g.cell_id, f"frac_{name}"]),
                )
            n = 5  # 500 m ring
            big = read_window(
                raw, x0 - n * cell, y0 - n * cell, x0 + (n + 1) * cell, y0 + (n + 1) * cell
            )
            ring_built = ((big == 7).sum() - (block == 7).sum()) / (big.size - block.size)
            ring_err = max(ring_err, abs(ring_built - df.loc[g.cell_id, "ring500_built"]))
            d_b_err.append(
                abs(
                    brute_dist(raw, g.x, g.y, cell, 7, True, cap)
                    - np.expm1(df.loc[g.cell_id, "log_dist_built"])
                )
            )
            d_w_err.append(
                abs(
                    brute_dist(raw, g.x, g.y, cell, 1, False, cap)
                    - np.expm1(df.loc[g.cell_id, "log_dist_water"])
                )
            )
        check(frac_err < 1e-9, f"fractions equal the raw download (max err {frac_err:.1e})")
        check(ring_err < 1e-9, f"ring500_built equals brute force (max err {ring_err:.1e})")
        check(
            max(d_b_err) < 1e-6,
            f"dist to built outside cell equals brute force (max err {max(d_b_err):.1e} m)",
        )
        check(
            max(d_w_err) < 1e-6, f"dist to water equals brute force (max err {max(d_w_err):.1e} m)"
        )

    print("6. terrain vs raw DEM")
    base = c2[years[0]].set_index("cell_id")
    with rasterio.open(dem_path(cfg)) as ds:
        errs = []
        for _, g in sample.iterrows():
            offs = np.array([-30.0, 0.0, 30.0])
            xs, ys = np.meshgrid(g.x + offs, g.y + offs)
            lon, lat_ = warp_points(cfg.crs, ds.crs, xs.ravel(), ys.ravel())
            z = np.mean([v[0] for v in ds.sample(zip(lon, lat_, strict=True))])
            errs.append(abs(z - base.loc[g.cell_id, "elev_mean"]))
    check(
        np.median(errs) < 2.0,
        f"elev_mean vs raw DEM: median |diff| {np.median(errs):.2f} m, max {max(errs):.1f} m",
    )
    check(
        bool((base["slope_max"] >= base["slope_mean"] - 1e-6).all()),
        "slope_max >= slope_mean everywhere",
    )

    print("7. leak guard (decision D4)")
    for y, df in c2.items():
        full = df[df["frac_built"] == 1.0]
        dmin = float(np.expm1(full["log_dist_built"]).min())
        check(
            dmin >= 50.0,
            f"{y}: {len(full)} fully built cells, "
            f"min distance to built outside the cell {dmin:.1f} m (>= 50)",
        )

    print("8. landmarks")
    latest = c2[years[-1]].set_index("cell_id")
    for name, (lon, lat_) in LANDMARKS.items():
        x, y = warp_points("EPSG:4326", cfg.crs, [lon], [lat_])
        cid = int(xy_to_cell_id(cfg, x, y)[0])
        row = latest.loc[cid]
        if "Lake" in name:
            # distances run to pixel centres; a cell centre sits between pixels -> >= 7.07 m
            d = float(np.expm1(row["log_dist_water"]))
            check(
                row["frac_water"] > 0.8 and d <= 10,
                f"{name}: frac_water {row['frac_water']:.2f}, dist_water {d:.1f} m",
            )
        elif name == "Koramangala":
            check(row["frac_built"] > 0.8, f"{name}: frac_built {row['frac_built']:.2f}")
        else:
            veg = row["ring500_tree"] + row["ring500_range"]
            check(veg > 0.8, f"{name}: ring500 trees+rangeland {veg:.2f}")

    print("9. growth")
    b0, b1 = c2[years[0]]["frac_built"].mean(), c2[years[-1]]["frac_built"].mean()
    check(b1 > b0, f"mean frac_built {years[0]} {b0:.3f} -> {years[-1]} {b1:.3f}")

    print("10. quick-look")
    fig_path = cfg.paths["figures"] / "verify_features.png"
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    shape = lat.shape
    cols = [
        ("frac_built", years[0], "viridis"),
        ("ring500_built", years[0], "viridis"),
        ("log_dist_built", years[0], "magma_r"),
        ("log_dist_water", years[0], "magma_r"),
        ("slope_mean", years[0], "magma"),
        ("ring500_tree", years[0], "Greens"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    for ax, (col, yr, cmap) in zip(axes.ravel(), cols, strict=True):
        img = np.full(shape, np.nan)
        img[grid["row"], grid["col"]] = c2[yr][col].to_numpy()
        im = ax.imshow(img, cmap=cmap)
        fig.colorbar(im, ax=ax, shrink=0.7)
        ax.set_title(f"{col} ({yr})")
        ax.set_axis_off()
    fig.savefig(fig_path, dpi=80, bbox_inches="tight")
    print(f"  wrote {fig_path}")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
