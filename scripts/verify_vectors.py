"""Done check for P3.4–P3.6 (vector preprocessing): are the cleaned OSM layers correct?

Checks ``data/processed/osm/`` and the C6 files against things the cleaning code did
not produce:

1. every layer is in the project CRS, valid, non-empty, inside the reference grid;
2. roads: classes only major/minor, and drivable road length is conserved: the raw
   drivable roads clipped independently to the extent have the same length;
3. counts inside the AOI agree with the ohsome history API (``docs/data_coverage.json``):
   2018 buildings and 2018 major-road length;
4. buildings: area limits hold, ``area_m2`` equals the geometry area, ``cell_id``
   recomputed from the centroid via the grid table (C1);
5. C6 passes its contract and only holds buildings in analysis grid cells;
6. water: OSM water bodies (2018) agree with ESRI water (2018), and known lakes
   (Nominatim coordinates) are inside an OSM water polygon in both snapshots;
7. Bannerghatta NP is in the protected layer;
8. quick-look overlay ``outputs/figures/verify_vectors.png``: roads, water and
   buildings over ESRI 2018 (P3.9).

Run: python scripts/verify_vectors.py
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
import rasterio  # noqa: E402
import shapely  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from rasterio.warp import transform as warp_points  # noqa: E402

from src.config import PROJECT_ROOT, load_config  # noqa: E402
from src.download.osm import layers_for, osm_path, snapshots  # noqa: E402
from src.features import schema  # noqa: E402
from src.preprocess.raster import load_reference_grid, processed_dir  # noqa: E402
from src.preprocess.vector import MAJOR_ROADS, MINOR_ROADS, processed_osm_path  # noqa: E402

LAKES = {"Madiwala Lake": (77.6177, 12.9082), "Hulimavu Lake": (77.6042, 12.8701)}

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def main() -> int:
    cfg = load_config()
    ref = load_reference_grid(cfg)
    extent = shapely.box(*ref.bounds)
    aoi = cfg.aoi_projected.geometry.iloc[0]
    ohsome = json.loads((PROJECT_ROOT / "docs" / "data_coverage.json").read_text())["osm"]
    snaps = list(snapshots(cfg))
    L = {
        (s, layer): gpd.read_file(processed_osm_path(cfg, s, layer))
        for s in snaps
        for layer in layers_for(s)
    }

    print("1. CRS, validity, extent")
    for (s, layer), g in L.items():
        ok = (
            g.crs == cfg.crs
            and len(g) > 0
            and bool(g.is_valid.all())
            and not bool(g.is_empty.any())
            and bool(g.within(extent.buffer(0.01)).all())
        )
        check(ok, f"{s}/{layer}: {len(g)} features, project CRS, valid, inside the grid extent")

    print("2. roads: classes and length conservation")
    keep_tracks = bool(cfg["vector"]["keep_tracks"])
    drivable = MAJOR_ROADS | MINOR_ROADS | ({"track"} if keep_tracks else set())
    for s in snaps:
        r = L[(s, "roads")]
        check(
            set(r["road_class"]) == {"major", "minor"},
            f"{s}: road_class values {sorted(set(r['road_class']))}",
        )
        raw = gpd.read_file(osm_path(cfg, s, "roads")).to_crs(cfg.crs)
        tag = raw["highway"].astype(str).str.split(";").str[0].str.strip()
        raw = raw.loc[tag.isin(drivable)]
        raw_len = (
            float(shapely.length(shapely.intersection(raw.geometry.values, extent)).sum()) / 1000
        )
        got = float(r.length.sum()) / 1000
        check(
            abs(got - raw_len) / raw_len < 1e-3,
            f"{s}: drivable length {got:.1f} km vs raw clipped {raw_len:.1f} km",
        )

    print("3. counts in the AOI vs ohsome (docs/data_coverage.json)")
    c6 = {s: gpd.read_file(schema.contract_path(cfg, "C6", snapshot=s)) for s in snaps}
    base = str(cfg["osm"]["snapshot_baseline"])
    n18, o18 = len(c6[base[:4]]), ohsome[base]["buildings"]
    check(
        abs(n18 - o18) / o18 < 0.02,
        f"2018 buildings in AOI cells: {n18} vs ohsome {o18} ({(n18 - o18) / o18:+.1%})",
    )
    later = max(k for k in ohsome if k != base)
    check(
        len(c6["current"]) >= ohsome[later]["buildings"] * 0.98,
        f"current buildings {len(c6['current'])} >= ohsome {later} "
        f"{ohsome[later]['buildings']} (OSM keeps growing)",
    )
    maj = L[(base[:4], "roads")]
    maj_km = (
        float(
            shapely.length(
                shapely.intersection(maj.loc[maj["road_class"] == "major"].geometry.values, aoi)
            ).sum()
        )
        / 1000
    )
    o_maj = ohsome[base]["roads_major_km"]
    check(
        abs(maj_km - o_maj) / o_maj < 0.05,
        f"2018 major roads in AOI: {maj_km:.0f} km vs ohsome {o_maj} km "
        f"({(maj_km - o_maj) / o_maj:+.1%})",
    )

    print("4-5. buildings and C6")
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    lo, hi = cfg["vector"]["building_min_area_m2"], cfg["vector"]["building_max_area_m2"]
    for s in snaps:
        b = L[(s, "buildings")]
        check(
            bool(((b["area_m2"] >= lo) & (b["area_m2"] <= hi)).all()),
            f"{s}: all areas within [{lo}, {hi}] m²",
        )
        check(bool(np.allclose(b["area_m2"], b.area)), f"{s}: area_m2 equals the geometry area")
        schema.validate_frame(c6[s], "C6")
        check(True, f"{s}: C6 passes its contract ({len(c6[s])} buildings)")
        # cell_id recomputed: the grid cell whose centre is within half a cell of the centroid
        tree = shapely.STRtree(shapely.points(grid["x"], grid["y"]))
        sample = c6[s].sample(min(3000, len(c6[s])), random_state=1)
        idx = tree.query_nearest(shapely.centroid(sample.geometry.values), all_matches=False)[1]
        want = grid["cell_id"].to_numpy()[idx]
        check(
            bool((want == sample["cell_id"].to_numpy()).all()),
            f"{s}: cell_id matches the nearest grid-cell centre (3000 checked)",
        )
        check(
            bool(c6[s]["cell_id"].isin(grid["cell_id"]).all()),
            f"{s}: every C6 building is in an analysis grid cell",
        )

    print("6. water vs ESRI and landmarks")
    w = L[(base[:4], "water")]
    bodies = shapely.union_all(w.loc[w["kind"] == "water_body"].geometry.values)
    with rasterio.open(processed_dir(cfg) / f"lulc_esri_{cfg['years']['baseline']}.tif") as ds:
        esri = ds.read(1)
        rng = np.random.default_rng(3)
        r, c = np.nonzero(esri == 1)
        pick = rng.choice(len(r), min(5000, len(r)), replace=False)
        xs, ys = rasterio.transform.xy(ds.transform, r[pick], c[pick])
    xs, ys = np.array(xs), np.array(ys)
    # alignment: overlap of ESRI water with the OSM lakes must peak with no shift
    shifts = {
        (dx, dy): float(shapely.contains_xy(bodies, xs - dx, ys - dy).mean())
        for dx in (-30, -10, 0, 10, 30)
        for dy in (-30, -10, 0, 10, 30)
    }
    best = max(shifts, key=shifts.get)
    gain = shifts[best] - shifts[(0, 0)]
    # OSM is traced on aerial imagery and Sentinel-2 geolocation is ~10 m, so a sub-pixel
    # offset between the two is normal. A processing error would show as a large shift
    # or a big overlap gain. Checked on the raw files too: raw OSM vs raw ESRI and vs raw
    # WorldCover both peak ~5-10 m off, so the offset is in the sources, not our code.
    check(
        max(abs(best[0]), abs(best[1])) <= 10 and gain < 0.02,
        f"OSM lakes align with ESRI water within one pixel (best shift {best} m, "
        f"overlap gain {gain:+.3f})",
    )
    # coverage is reported, not tested: OSM 2018 misses many small tanks (median
    # distance of uncovered ESRI water to the nearest OSM lake is > 1 km)
    print(
        f"     coverage: {shifts[(0, 0)]:.0%} of ESRI 2018 water pixels lie in OSM 2018 lakes "
        "(OSM 2018 lacks many small tanks; the ESRI water rule covers them)"
    )
    for s in snaps:
        ws = L[(s, "water")]
        wb = shapely.union_all(ws.loc[ws["kind"] == "water_body"].geometry.values)
        for name, (lon, lat) in LAKES.items():
            x, y = warp_points("EPSG:4326", cfg.crs, [lon], [lat])
            check(
                bool(shapely.contains_xy(wb, x[0], y[0])),
                f"{s}: {name} is inside an OSM water polygon",
            )

    print("7. protected areas")
    p = L[("current", "protected")]
    has = p["name"].astype(str).str.contains("Bannerghatta").any()
    check(bool(has), "Bannerghatta National Park present")

    print("8. quick-look overlay (P3.9)")
    fig, ax = plt.subplots(figsize=(11, 11))
    lut = np.zeros(256, np.uint8)
    for i, code in enumerate((1, 2, 4, 5, 7, 8, 11)):
        lut[code] = i + 1
    cmap = ListedColormap(
        ["white", "#a6cee3", "#33a02c", "#b2df8a", "#fdbf6f", "#bdbdbd", "#e0e0e0", "#f3efd9"]
    )
    b0 = ref.bounds
    ax.imshow(
        lut[esri],
        cmap=cmap,
        vmin=0,
        vmax=7,
        extent=(b0[0], b0[2], b0[1], b0[3]),
        interpolation="nearest",
    )
    rb = L[(base[:4], "roads")]
    rb.loc[rb["road_class"] == "minor"].plot(ax=ax, color="#636363", linewidth=0.2)
    rb.loc[rb["road_class"] == "major"].plot(ax=ax, color="#d7301f", linewidth=0.9)
    w.loc[w["kind"] == "water_body"].boundary.plot(ax=ax, color="#08519c", linewidth=0.6)
    L[("current", "protected")].boundary.plot(ax=ax, color="#006d2c", linewidth=1.5)
    gpd.GeoSeries([aoi], crs=cfg.crs).boundary.plot(ax=ax, color="black", linewidth=1)
    ax.set_title(
        "2018: OSM roads (red major, grey minor), OSM lakes (blue), "
        "Bannerghatta (green) over ESRI 2018"
    )
    ax.set_axis_off()
    out = cfg.paths["figures"] / "verify_vectors.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110, bbox_inches="tight")
    # zoom on a built-up block to check buildings sit on ESRI built pixels
    fig, ax = plt.subplots(figsize=(8, 8))
    x, y = warp_points("EPSG:4326", cfg.crs, [77.6483], [12.8488])
    zx0, zy0 = x[0] - 600, y[0] - 600
    win = rasterio.windows.from_bounds(zx0, zy0, zx0 + 1200, zy0 + 1200, ref.transform)
    sub = esri[
        int(win.row_off) : int(win.row_off + win.height),
        int(win.col_off) : int(win.col_off + win.width),
    ]
    ax.imshow(
        lut[sub],
        cmap=cmap,
        vmin=0,
        vmax=7,
        extent=(zx0, zx0 + 1200, zy0, zy0 + 1200),
        interpolation="nearest",
    )
    bz = c6[base[:4]].cx[zx0 : zx0 + 1200, zy0 : zy0 + 1200]
    bz.boundary.plot(ax=ax, color="black", linewidth=0.4)
    rb.cx[zx0 : zx0 + 1200, zy0 : zy0 + 1200].plot(ax=ax, color="#d7301f", linewidth=1)
    ax.set_xlim(zx0, zx0 + 1200)
    ax.set_ylim(zy0, zy0 + 1200)
    ax.set_title("Electronic City, 1.2 km: 2018 OSM buildings (black) and roads over ESRI 2018")
    fig.savefig(cfg.paths["figures"] / "verify_vectors_zoom.png", dpi=110, bbox_inches="tight")
    print(f"  wrote {out} and verify_vectors_zoom.png")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
