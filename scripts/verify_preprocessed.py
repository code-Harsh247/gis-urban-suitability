"""Done check for A2 / Phase 3 raster part: are the preprocessed rasters correct?

Checks ``data/processed/`` against things the preprocessing code did not produce:

1. the saved reference grid equals a fresh build from the config; edges are whole cells;
2. every processed raster has exactly the reference grid (CRS, transform, shape);
3. no nodata anywhere on the grid; only valid class codes;
4. ESRI values equal the raw downloads at random points (same lattice -> exact copy);
5. WorldCover values agree with the raw download at random points (nearest resampling);
6. elevation agrees with the raw DEM sampled at the same points;
7. slope agrees with an independent slope (np.gradient on the raw DEM with metric spacing);
8. landmarks: lakes are water and flat, the dense city is flat;
9. harmonised WorldCover agrees with ESRI where it should (water, built-up);
10. a quick-look PNG is written to ``outputs/figures/verify_preprocessed.png``.

Run: python scripts/verify_preprocessed.py
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.warp import transform as warp_points  # noqa: E402

from src.config import load_config  # noqa: E402
from src.download.dem import dem_path  # noqa: E402
from src.download.lulc import esri_path, esri_years, worldcover_path  # noqa: E402
from src.preprocess import raster as pr  # noqa: E402

LAKES = {"Madiwala Lake": (77.6177, 12.9082), "Hulimavu Lake": (77.6042, 12.8701)}
CITY = {"Koramangala": (77.6250, 12.9300)}

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def sample(path, xs, ys, crs) -> np.ndarray:
    with rasterio.open(path) as ds:
        if ds.crs != crs:
            xs, ys = warp_points(crs, ds.crs, xs, ys)
        return np.array([v[0] for v in ds.sample(zip(xs, ys, strict=True))])


def window_mean(path, lon, lat, half=3) -> float:
    with rasterio.open(path) as ds:
        x, y = warp_points("EPSG:4326", ds.crs, [lon], [lat])
        r, c = ds.index(x[0], y[0])
        return float(ds.read(1, window=((r - half, r + half + 1), (c - half, c + half + 1))).mean())


def window_major(path, lon, lat, half=2) -> int:
    with rasterio.open(path) as ds:
        x, y = warp_points("EPSG:4326", ds.crs, [lon], [lat])
        r, c = ds.index(x[0], y[0])
        v, n = np.unique(
            ds.read(1, window=((r - half, r + half + 1), (c - half, c + half + 1))),
            return_counts=True,
        )
    return int(v[n.argmax()])


def main() -> int:
    cfg = load_config()
    out = pr.processed_dir(cfg)
    ref = pr.load_reference_grid(cfg)
    years = esri_years(cfg)
    wc_year = int(cfg["lulc"]["worldcover_check"])
    esri = {y: out / f"lulc_esri_{y}.tif" for y in years}
    files = [
        *esri.values(),
        out / f"worldcover_{wc_year}.tif",
        out / "elevation.tif",
        out / "slope.tif",
    ]

    print("1. reference grid")
    check(ref == pr.build_reference_grid(cfg), "saved grid equals a fresh build from config")
    cell = cfg.cell_size_m
    check(
        all(abs(v / cell - round(v / cell)) < 1e-9 for v in ref.bounds),
        f"edges on whole {cell:.0f} m cells",
    )
    aoi_need = cfg.aoi_projected.buffer(cfg["aoi"]["buffer_m"]).total_bounds
    b = ref.bounds
    check(
        b[0] <= aoi_need[0] and b[1] <= aoi_need[1] and b[2] >= aoi_need[2] and b[3] >= aoi_need[3],
        "covers AOI + buffer",
    )

    print("2-3. every raster on the grid, no gaps, valid values")
    for f in files:
        with rasterio.open(f) as ds:
            same = ds.crs == ref.crs and ds.transform == ref.transform and ds.shape == ref.shape
            arr = ds.read(1)
            gaps = float((arr == ds.nodata).mean())
        check(same, f"{f.name}: on the reference grid")
        check(gaps == 0, f"{f.name}: nodata {gaps:.4%}")
        if f.name.startswith("lulc_esri"):
            bad = set(np.unique(arr).tolist()) - set(pr.ESRI_VALID)
            check(not bad, f"{f.name}: class codes valid {bad or ''}")
        if f.name == "slope.tif":
            check(
                float(arr.min()) >= 0 and float(arr.max()) <= 90,
                f"slope range {arr.min():.1f}-{arr.max():.1f} deg",
            )

    rng = np.random.default_rng(7)
    xs = rng.uniform(b[0] + 50, b[2] - 50, 2000)
    ys = rng.uniform(b[1] + 50, b[3] - 50, 2000)

    print("4. ESRI equals the raw download (2000 random points per year)")
    for y in years:
        diff = int(
            (sample(esri[y], xs, ys, ref.crs) != sample(esri_path(cfg, y), xs, ys, ref.crs)).sum()
        )
        check(diff == 0, f"{y}: {diff}/2000 differ")

    print("5. WorldCover vs raw download, at processed pixel centres")
    # Nearest resampling gives each 10 m pixel the source value at its centre. The two
    # grids differ in pixel size, so a few pixels on class boundaries can tie-break
    # differently. What must hold: no systematic shift (agreement peaks at offset 0)
    # and every mismatch is a value from the source pixel's 3x3 neighbourhood.
    rows = rng.integers(5, ref.height - 5, 4000)
    cols = rng.integers(5, ref.width - 5, 4000)
    px, py = (np.array(v) for v in rasterio.transform.xy(ref.transform, rows, cols))
    with rasterio.open(files[len(years)]) as p_:
        got = p_.read(1)[rows, cols]
    with rasterio.open(worldcover_path(cfg, wc_year)) as raw_ds:
        raw_arr = raw_ds.read(1)

        def raw_at(dx: float, dy: float):
            lo, la = warp_points(ref.crs, raw_ds.crs, px + dx, py + dy)
            r, c = (np.array(v) for v in rasterio.transform.rowcol(raw_ds.transform, lo, la))
            return raw_arr[r, c], r, c

        offsets = {
            (dx, dy): float((got == raw_at(dx, dy)[0]).mean())
            for dx in (-2, 0, 2)
            for dy in (-2, 0, 2)
        }
        want, r, c = raw_at(0, 0)
    best = max(offsets, key=offsets.get)
    bad = np.nonzero(got != want)[0]
    in_nbhd = all(got[i] in raw_arr[r[i] - 1 : r[i] + 2, c[i] - 1 : c[i] + 2] for i in bad)
    check(
        best == (0, 0), f"no shift: agreement peaks at offset {best} ({offsets[(0, 0)]:.2%} at 0,0)"
    )
    check(
        offsets[(0, 0)] >= 0.98 and in_nbhd,
        f"{len(bad)} boundary tie-breaks, all from the source 3x3 neighbourhood",
    )

    print("6. elevation vs raw DEM")
    dz = np.abs(
        sample(out / "elevation.tif", xs, ys, ref.crs) - sample(dem_path(cfg), xs, ys, ref.crs)
    )
    check(
        np.median(dz) < 1.0 and np.percentile(dz, 99) < 5.0,
        f"|diff| median {np.median(dz):.2f} m, p99 {np.percentile(dz, 99):.2f} m",
    )

    print("7. slope vs an independent computation")
    with rasterio.open(dem_path(cfg)) as ds:
        z = ds.read(1).astype(float)
        lat = np.deg2rad(np.linspace(ds.bounds.top, ds.bounds.bottom, ds.height))[:, None]
        dy = ds.res[1] * 110_574.0
        dx = ds.res[0] * 111_320.0 * np.cos(lat)
        gy = np.gradient(z, axis=0) / dy
        gx = np.gradient(z, axis=1) / dx
        s_ind = np.degrees(np.arctan(np.hypot(gx, gy)))
        lon, lat_pts = warp_points(ref.crs, ds.crs, xs, ys)
        rows, cols = rasterio.transform.rowcol(ds.transform, lon, lat_pts)
        s_ind_pts = s_ind[np.clip(rows, 0, ds.height - 1), np.clip(cols, 0, ds.width - 1)]
    ds_ = np.abs(sample(out / "slope.tif", xs, ys, ref.crs) - s_ind_pts)
    check(
        np.median(ds_) < 1.0,
        f"|diff| median {np.median(ds_):.2f} deg, p90 {np.percentile(ds_, 90):.2f} deg",
    )

    print("8. landmarks")
    for name, (lon, lat) in LAKES.items():
        cls = window_major(esri[years[0]], lon, lat)
        check(cls == 1, f"{name}: ESRI {years[0]} class {cls} (water = 1)")
        s = window_mean(out / "slope.tif", lon, lat)
        check(s < 1.5, f"{name}: mean slope {s:.2f} deg (lake surface should be flat)")
    for name, (lon, lat) in CITY.items():
        s = window_mean(out / "slope.tif", lon, lat)
        check(s < 4.0, f"{name}: mean slope {s:.2f} deg (flat dense city)")

    print("9. harmonised WorldCover vs ESRI 2021")
    with (
        rasterio.open(esri.get(2021, esri[years[-1]])) as e_,
        rasterio.open(files[len(years)]) as w_,
    ):
        E, W = e_.read(1), pr.harmonise_worldcover(w_.read(1))
    for name, code, floor in (("water", 1, 0.8), ("built", 7, 0.9)):
        m = W == code
        a = float((E[m] == code).mean())
        check(
            a >= floor,
            f"{name}: ESRI agrees with {a:.0%} of harmonised WorldCover {name}"
            f" (need >= {floor:.0%})",
        )

    print("10. quick-look")
    fig_path = cfg.paths["figures"] / "verify_preprocessed.png"
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    ext = (b[0], b[2], b[1], b[3])
    with rasterio.open(esri[years[-1]]) as ds:
        axes[0].imshow(ds.read(1) == 7, cmap="Greys", extent=ext)
    with rasterio.open(out / "elevation.tif") as ds:
        im = axes[1].imshow(ds.read(1), cmap="terrain", extent=ext)
        fig.colorbar(im, ax=axes[1], label="m")
    with rasterio.open(out / "slope.tif") as ds:
        im = axes[2].imshow(ds.read(1), cmap="magma", vmin=0, vmax=20, extent=ext)
        fig.colorbar(im, ax=axes[2], label="deg")
    for ax, t in zip(axes, (f"ESRI {years[-1]} built", "elevation", "slope"), strict=True):
        cfg.aoi_projected.boundary.plot(ax=ax, color="cyan", lw=1)
        for lon, lat in {**LAKES, **CITY}.values():
            x, y = warp_points("EPSG:4326", ref.crs, [lon], [lat])
            ax.plot(x, y, "c+", ms=10)
        ax.set_title(t)
        ax.set_axis_off()
    fig.savefig(fig_path, dpi=90, bbox_inches="tight")
    print(f"  wrote {fig_path}")

    json.dumps(ref.to_json())
    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
