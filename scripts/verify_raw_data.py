"""Done check for A1 / Phase 2 (raster downloads): are the downloaded rasters correct?

Checks the files in ``data/raw/`` against things the download code did not produce:

1. manifest checksums match the files on disk;
2. pixel values equal the source COGs on Planetary Computer at random points (needs network);
3. every ESRI year shares one identical grid;
4. no nodata inside the AOI;
5. landmarks (coordinates from OSM Nominatim) have the expected class;
6. ESRI 2021 agrees with WorldCover 2021 where it should (water, built-up);
7. DEM values and slopes are plausible.

Run: python scripts/verify_raw_data.py [--no-network]
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import Resampling, reproject
from rasterio.warp import transform as warp_points

from src.config import load_config
from src.download import stac
from src.download.lulc import esri_years
from src.io_utils import Manifest, sha256

ESRI = {1: "water", 2: "trees", 4: "flooded", 5: "crops", 7: "built", 8: "bare", 11: "rangeland"}
WC = {
    10: "tree",
    20: "shrub",
    30: "grass",
    40: "crop",
    50: "built",
    60: "bare",
    80: "water",
    90: "wetland",
}
# (lon, lat, expected ESRI class in the latest year) — coordinates from OSM Nominatim
LANDMARKS = {
    "Madiwala Lake": (77.6177, 12.9082, "water"),
    "Electronic City": (77.6483, 12.8488, "built"),
    "Koramangala": (77.6250, 12.9300, "built"),
}

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def majority(path, lon: float, lat: float, half: int = 2) -> int:
    with rasterio.open(path) as ds:
        x, y = warp_points("EPSG:4326", ds.crs, [lon], [lat])
        r, c = ds.index(x[0], y[0])
        win = ds.read(1, window=((r - half, r + half + 1), (c - half, c + half + 1)))
    v, cnt = np.unique(win, return_counts=True)
    return int(v[cnt.argmax()])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-network", action="store_true", help="skip the source comparison")
    args = parser.parse_args(argv)
    cfg = load_config()
    root = cfg.root
    entries = Manifest.for_config(cfg).entries
    raw = {
        k: e
        for k, e in entries.items()
        if k.startswith("data/raw/lulc") or k.startswith("data/raw/dem")
    }
    if not raw:
        print("No raster downloads in the manifest. Run the downloaders first.")
        return 1

    print("1. manifest checksums")
    for key, e in sorted(raw.items()):
        check((root / key).exists() and sha256(root / key) == e["sha256"], f"{key} checksum")

    if not args.no_network:
        print("2. pixel values equal the source COGs (500 random points each)")
        rng = np.random.default_rng(1)
        w, s, e_, n = stac.aoi_bounds_4326(cfg)
        lons, lats = rng.uniform(w, e_, 500), rng.uniform(s, n, 500)
        for key, e in sorted(raw.items()):
            src = e["source"]
            year = str(e["year"]) if e.get("year") else None
            items = [
                i
                for i in stac.search_items(src["collection"], src["bbox_4326"], year)
                if i.id in src["items"]
            ]
            with rasterio.open(root / key) as ours:
                xs, ys = warp_points("EPSG:4326", ours.crs, lons, lats)
                a = np.array([v[0] for v in ours.sample(zip(xs, ys, strict=True))])
            b = np.full_like(a, np.nan if a.dtype.kind == "f" else 0)
            for it in items:
                with rasterio.open(it.assets[src["asset"]].href) as orig:
                    xo, yo = warp_points("EPSG:4326", orig.crs, lons, lats)
                    vals = np.array([v[0] for v in orig.sample(zip(xo, yo, strict=True))])
                    inside = [
                        (orig.bounds.left <= x <= orig.bounds.right)
                        and (orig.bounds.bottom <= y <= orig.bounds.top)
                        for x, y in zip(xo, yo, strict=True)
                    ]
                    b[inside] = vals[inside]
            diff = (np.abs(a - b) > 1e-3) if a.dtype.kind == "f" else (a != b)
            check(
                int(diff.sum()) == 0,
                f"{key.split('/')[-1]}: {int(diff.sum())}/500 differ from source",
            )

    print("3. one grid for every ESRI year")
    grids = set()
    for y in esri_years(cfg):
        with rasterio.open(root / f"data/raw/lulc/esri_lulc_{y}.tif") as ds:
            grids.add((ds.crs.to_string(), tuple(round(v, 6) for v in ds.transform)[:6], ds.shape))
    check(len(grids) == 1, f"identical grid across years: {sorted(grids)[0][1:]}")
    t = sorted(grids)[0][1]
    check(t[2] % t[0] == 0 and t[5] % t[0] == 0, "grid origin on whole pixels")

    print("4. no nodata inside the AOI")
    for key in sorted(raw):
        with rasterio.open(root / key) as ds:
            arr = ds.read(1)
            inside = ~geometry_mask(cfg.aoi.to_crs(ds.crs).geometry, arr.shape, ds.transform)
            gaps = float((arr[inside] == ds.nodata).mean())
        check(gaps == 0, f"{key.split('/')[-1]}: nodata inside AOI {gaps:.4%}")

    print("5. landmarks")
    latest = root / f"data/raw/lulc/esri_lulc_{cfg['years']['latest']}.tif"
    for name, (lon, lat, expected) in LANDMARKS.items():
        got = ESRI.get(majority(latest, lon, lat), "?")
        check(got == expected, f"{name}: expected {expected}, ESRI latest says {got}")

    print("6. ESRI 2021 vs WorldCover 2021")
    esri_2021 = root / "data/raw/lulc/esri_lulc_2021.tif"
    wc_path = root / f"data/raw/lulc/worldcover_{cfg['lulc']['worldcover_check']}.tif"
    if esri_2021.exists() and wc_path.exists():
        with rasterio.open(esri_2021) as es, rasterio.open(wc_path) as wc:
            E = es.read(1)
            W = np.zeros_like(E)
            reproject(
                rasterio.band(wc, 1),
                W,
                dst_transform=es.transform,
                dst_crs=es.crs,
                resampling=Resampling.nearest,
            )
        for name, ec, wcc, floor in (("water", 1, 80, 0.8), ("built", 7, 50, 0.9)):
            w_ = W == wcc
            agree = float((E[w_] == ec).mean()) if w_.any() else 0.0
            check(
                agree >= floor,
                f"{name}: ESRI agrees with {agree:.0%} of WorldCover {name} (need >= {floor:.0%})",
            )

    print("7. DEM plausibility")
    with rasterio.open(root / "data/raw/dem/copdem_glo30.tif") as ds:
        z = ds.read(1).astype(float)
        lat0 = np.deg2rad((ds.bounds.top + ds.bounds.bottom) / 2)
        dx, dy = ds.res[0] * 111_320 * np.cos(lat0), ds.res[1] * 110_574
    gy, gx = np.gradient(z, dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    check(-100 < z.min() and z.max() < 9000, f"elevation {z.min():.0f}-{z.max():.0f} m")
    check(
        np.percentile(slope, 99) < 60,
        f"slope median {np.median(slope):.1f} deg, p99 {np.percentile(slope, 99):.1f} deg",
    )

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
