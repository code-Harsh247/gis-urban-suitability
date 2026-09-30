"""Compare candidate study areas for Task P0.9 (PRD section 5.1).

For each candidate bounding box this reports:
  - area in km² (in the local UTM zone)
  - ESA WorldCover 2021 class shares
  - ESRI Annual LULC built-up share in 2018 and 2023, and *persistent* new growth
    (non-built in 2018 and 2019, built in 2022 and 2023) to filter classifier flicker.
    2018 is the baseline because the 2017 IO map is noticeably noisier.
  - OSM buildings (2018 and today) and major-road length, from the ohsome history API
and saves a WorldCover quick-look PNG to docs/img/.

Rasters are read from COG overviews (~80 m) to keep downloads small; the numbers
are for comparing candidates, not for the analysis itself.

Run: python scripts/study_area_candidates.py [name ...]
"""

from __future__ import annotations

import json
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import planetary_computer as pc  # noqa: E402
import pystac_client  # noqa: E402
import rasterio  # noqa: E402
import requests  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from pyproj import Transformer  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.merge import merge  # noqa: E402
from shapely.geometry import box  # noqa: E402
from shapely.ops import transform  # noqa: E402

from src.config import PROJECT_ROOT, utm_epsg_for  # noqa: E402

# name -> (min_lon, min_lat, max_lon, max_lat)
CANDIDATES = {
    "pune_west": (73.62, 18.48, 73.86, 18.70),
    "bhubaneswar": (85.70, 20.20, 85.92, 20.42),
    "dehradun": (77.92, 30.22, 78.14, 30.42),
    "guwahati": (91.62, 26.05, 91.86, 26.23),
    "bengaluru_south": (77.52, 12.72, 77.74, 12.94),
    "chennai_southwest": (80.02, 12.80, 80.24, 13.02),
    "gurugram": (76.94, 28.34, 77.16, 28.52),
    "navi_mumbai": (73.00, 18.92, 73.22, 19.12),
    "hyderabad_west": (78.22, 17.32, 78.44, 17.52),
    "bhopal": (77.26, 23.14, 77.48, 23.34),
    "ranchi": (85.22, 23.26, 85.44, 23.46),
    "coimbatore": (76.84, 10.92, 77.06, 11.12),
    "visakhapatnam": (83.10, 17.68, 83.32, 17.88),
    "kharagpur": (87.20, 22.24, 87.42, 22.44),
}

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
OHSOME_URL = "https://api.ohsome.org/v1/elements"
USER_AGENT = "gis-urban-suitability/0.1 (term project)"
READ_RES_DEG = 0.00075  # ~80 m
ESRI_YEARS = (2018, 2019, 2022, 2023)
OSM_DATES = ("2018-01-01", "2026-01-01")

WORLDCOVER = {
    10: ("Tree cover", "#006400"),
    20: ("Shrubland", "#ffbb22"),
    30: ("Grassland", "#ffff4c"),
    40: ("Cropland", "#f096ff"),
    50: ("Built-up", "#fa0000"),
    60: ("Bare / sparse", "#b4b4b4"),
    70: ("Snow / ice", "#f0f0f0"),
    80: ("Water", "#0064c8"),
    90: ("Wetland", "#0096a0"),
    95: ("Mangroves", "#00cf75"),
    100: ("Moss / lichen", "#fae6a0"),
}
USABLE = ("Shrubland", "Grassland", "Cropland", "Bare / sparse", "Moss / lichen")
ESRI_BUILT = 7  # io-lulc-annual-v02 class "Built area"; 0 = nodata


def area_km2(bbox: tuple[float, float, float, float]) -> float:
    lon, lat = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    to_utm = Transformer.from_crs(4326, utm_epsg_for(lon, lat), always_xy=True).transform
    return transform(to_utm, box(*bbox)).area / 1e6


def read_worldcover(hrefs: list[str], bbox) -> np.ndarray:
    """Mosaic WorldCover (EPSG:4326) tiles over the bbox at ~80 m."""
    datasets = [rasterio.open(h) for h in hrefs]
    arr, _ = merge(datasets, bounds=bbox, res=READ_RES_DEG, resampling=Resampling.nearest)
    for ds in datasets:
        ds.close()
    return arr[0]


def read_esri(hrefs: list[str], bbox) -> np.ndarray:
    """Read the bbox from projected (UTM) ESRI tiles at ~80 m, flattened.

    Tiles must be passed in a fixed order so pixels line up across years.
    """
    parts = []
    for h in hrefs:
        with rasterio.open(h) as ds:
            to_tile = Transformer.from_crs(4326, ds.crs, always_xy=True).transform
            b = transform(to_tile, box(*bbox)).bounds
            window = ds.window(*b).intersection(rasterio.windows.Window(0, 0, ds.width, ds.height))
            scale = 80 / ds.res[0]
            shape = (max(1, int(window.height / scale)), max(1, int(window.width / scale)))
            parts.append(
                ds.read(1, window=window, out_shape=shape, resampling=Resampling.nearest).ravel()
            )
    return np.concatenate(parts)


def class_shares(values: np.ndarray, nodata: int = 0) -> dict[int, float]:
    valid = values[values != nodata]
    codes, counts = np.unique(valid, return_counts=True)
    return {int(c): float(n) / valid.size for c, n in zip(codes, counts, strict=True)}


def esri_growth(catalog, bbox) -> dict:
    stack = {}
    for year in ESRI_YEARS:
        items = catalog.search(
            collections=["io-lulc-annual-v02"], bbox=bbox, datetime=str(year)
        ).item_collection()
        hrefs = [i.assets["data"].href for i in sorted(items, key=lambda i: i.id)]
        stack[year] = read_esri(hrefs, bbox)
    valid = np.all([a != 0 for a in stack.values()], axis=0)
    built = {y: (a == ESRI_BUILT)[valid] for y, a in stack.items()}
    b18, b19, b22, b23 = (built[y] for y in ESRI_YEARS)
    raw_new = ~b18 & b23
    persistent = ~b18 & ~b19 & b22 & b23
    return {
        "esri_built_2018": round(float(b18.mean()), 3),
        "esri_built_2023": round(float(b23.mean()), 3),
        "persistent_growth_share": round(float(persistent.mean()), 4),
        "persistent_of_raw_growth": round(float(persistent.sum() / max(raw_new.sum(), 1)), 2),
        "growth_rate_of_nonbuilt": round(float(persistent.sum() / max((~b18).sum(), 1)), 3),
    }


def ohsome(endpoint: str, bbox, time_: str, filter_: str) -> float | None:
    params = {"bboxes": ",".join(map(str, bbox)), "time": time_, "filter": filter_}
    for _ in range(3):
        try:
            r = requests.post(
                f"{OHSOME_URL}/{endpoint}",
                data=params,
                headers={"User-Agent": USER_AGENT},
                timeout=180,
            )
            if r.ok:
                return float(r.json()["result"][0]["value"])
        except (requests.RequestException, ValueError, KeyError, IndexError):
            pass
        time.sleep(5)
    return None


def osm_stats(bbox) -> dict:
    out = {}
    for date in OSM_DATES:
        year = date[:4]
        n = ohsome("count", bbox, date, "building=* and geometry:polygon")
        out[f"osm_buildings_{year}"] = None if n is None else int(n)
    km = ohsome(
        "length",
        bbox,
        OSM_DATES[-1],
        "highway in (motorway,trunk,primary,secondary) and type:way",
    )
    out["osm_major_road_km"] = None if km is None else round(km / 1000)
    return out


def plot_worldcover(arr: np.ndarray, bbox, name: str, out) -> None:
    codes = sorted(WORLDCOVER)
    lut = np.zeros(256, dtype=np.uint8)
    for i, c in enumerate(codes):
        lut[c] = i + 1
    cmap = ListedColormap(["white"] + [WORLDCOVER[c][1] for c in codes])
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(
        lut[arr],
        cmap=cmap,
        vmin=0,
        vmax=len(codes),
        interpolation="nearest",
        extent=(bbox[0], bbox[2], bbox[1], bbox[3]),
    )
    present = [c for c in codes if (arr == c).mean() > 0.001]
    ax.legend(
        handles=[Patch(color=WORLDCOVER[c][1], label=WORLDCOVER[c][0]) for c in present],
        loc="upper left",
        bbox_to_anchor=(1.01, 1),
        fontsize=8,
        frameon=False,
    )
    ax.set_title(f"{name} — ESA WorldCover 2021")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)


def main(names: list[str]) -> None:
    catalog = pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)
    img_dir = PROJECT_ROOT / "docs" / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    out = img_dir / "study_area_candidates.json"
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}

    for name in names:
        bbox = CANDIDATES[name]
        print(f"== {name} {bbox}", flush=True)
        row: dict = {"bbox": bbox, "area_km2": round(area_km2(bbox), 1)}

        wc_items = catalog.search(
            collections=["esa-worldcover"], bbox=bbox, datetime="2021"
        ).item_collection()
        wc = read_worldcover([i.assets["map"].href for i in wc_items], bbox)
        shares = {WORLDCOVER[c][0]: round(v, 3) for c, v in class_shares(wc).items()}
        row["worldcover_2021"] = shares
        row["usable_share"] = round(sum(shares.get(k, 0) for k in USABLE), 3)
        plot_worldcover(wc, bbox, name, img_dir / f"study_area_{name}.png")

        row.update(esri_growth(catalog, bbox))
        row.update(osm_stats(bbox))
        results[name] = row
        print(json.dumps(row), flush=True)
        out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"Saved {out}")


if __name__ == "__main__":
    main(sys.argv[1:] or list(CANDIDATES))
