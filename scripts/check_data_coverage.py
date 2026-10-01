"""Check data coverage and access for the configured AOI (Tasks P1.5, P1.6).

- Rasters (Planetary Computer STAC): for every dataset and year in the config, the
  items that intersect the AOI + buffer, whether they cover it fully, the full-tile
  asset sizes, and the collection licence.
- OSM (ohsome history API): buildings, roads, water and protected areas inside the AOI
  at the baseline snapshot and today.

No rasters are downloaded; only STAC metadata and HTTP HEAD requests are used.
Results go to docs/data_coverage.json and are summarised in docs/data_sources.md.

Run: python scripts/check_data_coverage.py
"""

from __future__ import annotations

import json
import sys

import requests
from shapely.geometry import box
from shapely.ops import unary_union
from study_area_candidates import OSM_DATES, USER_AGENT, ohsome

from src.config import PROJECT_ROOT, load_config
from src.download.dem import DEM_COLLECTION
from src.download.lulc import ESRI_COLLECTION, WORLDCOVER_COLLECTION, esri_years
from src.download.stac import STAC_URL, aoi_bounds_4326, search_items

OUT = PROJECT_ROOT / "docs" / "data_coverage.json"

# (filter, endpoint) per OSM layer; lengths in metres, counts in features
OSM_LAYERS = {
    "buildings": ("building=* and geometry:polygon", "count"),
    "roads_all_km": ("highway=* and type:way", "length"),
    "roads_major_km": (
        "highway in (motorway,motorway_link,trunk,trunk_link,primary,primary_link,"
        "secondary,secondary_link) and type:way",
        "length",
    ),
    "water_polygons": ("natural=water and geometry:polygon", "count"),
    "waterways_km": ("waterway=* and type:way", "length"),
    "protected_areas": (
        "(boundary=protected_area or leisure=nature_reserve) and geometry:polygon",
        "count",
    ),
}


def collection_license(collection: str) -> dict:
    import pystac_client

    col = pystac_client.Client.open(STAC_URL).get_collection(collection)
    links = [lk.href for lk in col.links if lk.rel == "license"]
    return {"license": col.license, "license_links": links, "title": col.title}


def head_size(href: str) -> int | None:
    try:
        r = requests.head(href, timeout=60, allow_redirects=True)
        return int(r.headers["Content-Length"]) if r.ok else None
    except (requests.RequestException, KeyError, ValueError):
        return None


def raster_coverage(bbox, collection: str, asset: str, datetime=None, item_filter=None) -> dict:
    items = search_items(collection, bbox, datetime)
    if item_filter:
        items = [i for i in items if item_filter(i)]
    union = unary_union([box(*i.bbox) for i in items])
    sizes = [head_size(i.assets[asset].href) for i in items]
    return {
        "items": [i.id for i in items],
        "n_items": len(items),
        "covers_aoi_buffer": bool(union.covers(box(*bbox))),
        "tile_sizes_mb": [None if s is None else round(s / 1e6, 1) for s in sizes],
    }


def main() -> int:
    cfg = load_config()
    bbox = aoi_bounds_4326(cfg)
    aoi_bbox = tuple(round(v, 5) for v in cfg.aoi.total_bounds)
    result: dict = {
        "aoi": cfg["aoi"]["name"],
        "aoi_bbox_4326": list(aoi_bbox),
        "aoi_buffer_bbox_4326": [round(v, 5) for v in bbox],
        "rasters": {},
        "osm": {},
    }

    esri = {"collection": ESRI_COLLECTION, **collection_license(ESRI_COLLECTION), "years": {}}
    for year in esri_years(cfg):
        esri["years"][year] = raster_coverage(
            bbox, ESRI_COLLECTION, "data", str(year), lambda i, y=year: i.id.endswith(f"-{y}")
        )
    result["rasters"]["esri_lulc"] = esri

    wc_year = int(cfg["lulc"]["worldcover_check"])
    result["rasters"]["worldcover"] = {
        "collection": WORLDCOVER_COLLECTION,
        **collection_license(WORLDCOVER_COLLECTION),
        "years": {
            wc_year: raster_coverage(
                bbox,
                WORLDCOVER_COLLECTION,
                "map",
                str(wc_year),
                lambda i, y=wc_year: f"_{y}_" in i.id,
            )
        },
    }
    result["rasters"]["dem"] = {
        "collection": DEM_COLLECTION,
        **collection_license(DEM_COLLECTION),
        "static": raster_coverage(bbox, DEM_COLLECTION, "data"),
    }

    for date in OSM_DATES:
        stats = {}
        for name, (filter_, endpoint) in OSM_LAYERS.items():
            value = ohsome(endpoint, aoi_bbox, date, filter_)
            if value is not None and endpoint == "length":
                value = round(value / 1000)
            stats[name] = None if value is None else int(value)
        result["osm"][date] = stats

    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"\nwrote {OUT.relative_to(PROJECT_ROOT)}  (ohsome user agent: {USER_AGENT})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
