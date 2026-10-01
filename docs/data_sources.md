# Data sources

Final dataset list for **Bengaluru South** (Tasks P1.5–P1.7, joint task J7).
- Requirements: [PRD §7](PRD.md#7-data-requirements). Decisions D2, D3, D8, D9: [execution_plan.md §2](execution_plan.md#2-decisions-defaults-adopted-2026-10-01).
- Coverage numbers come from [`scripts/check_data_coverage.py`](../scripts/check_data_coverage.py), run on 2026-10-01. Raw output: [`data_coverage.json`](data_coverage.json).
- To rerun: `python scripts/check_data_coverage.py`. It reads STAC metadata and runs ohsome queries; it downloads no rasters.

Ownership:
- Raster sections: Abhinav's track. Drafted by Harsh from the coverage check; **Abhinav to review**.
- OSM sections: Harsh's track.

---

## 1. Summary

| Dataset | Version / collection | Years used | Resolution | Licence | Access (Python) | Used for |
|---|---|---|---|---|---|---|
| **ESRI IO LULC** (Impact Observatory, Microsoft, Esri) | `io-lulc-annual-v02` ("10m Annual LULC (9-class) V2") | **2018–2023**, every year | 10 m | **CC BY 4.0** | Planetary Computer STAC → `src/download/lulc.py` | All LULC features, 3-class map, growth labels (D2) |
| **ESA WorldCover** | `esa-worldcover`, v200 | **2021** | 10 m | **CC BY 4.0** | Planetary Computer STAC → `src/download/lulc.py` | Cross-check only (forest, classes) |
| **Copernicus DEM GLO-30** | `cop-dem-glo-30` | static (2011–2015 acquisition) | 30 m | **Copernicus DEM licence** (free use with attribution; STAC lists it as "proprietary", see the [licence annex](https://spacedata.copernicus.eu/documents/20126/0/CSCDA_ESA_Mission-specific+Annex.pdf)) | Planetary Computer STAC → `src/download/dem.py` | Elevation, slope |
| **OpenStreetMap** roads, water, buildings | Overpass API (`[date:]` for history) | **2018-01-01 snapshot** + current | vector | **ODbL 1.0** | Overpass with mirror fallback → `src/download/osm.py` (H1.1) | Road features, reference buildings (D8, D9) |
| **OpenStreetMap** protected areas | Overpass API | current | vector | **ODbL 1.0** | `src/download/osm.py` (H1.4) | Exclusion mask (Bannerghatta NP) |
| OSM history statistics | ohsome API | 2018-01-01, 2026-01-01 | — | ODbL 1.0 (data) | `scripts/study_area_candidates.py`, `scripts/check_data_coverage.py` | Coverage checks only |

**Required attributions** (report, figures, interactive map):
- ESRI LULC: "Impact Observatory, Microsoft, and Esri", 10 m Annual Land Use Land Cover v02, CC BY 4.0.
- WorldCover: "© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium", CC BY 4.0.
- Copernicus DEM: the attribution required by the licence annex above (check the exact wording before submission).
- OSM: "© OpenStreetMap contributors", ODbL 1.0.

---

## 2. Raster coverage over the AOI (P1.5)

Search area: AOI + 1 km buffer, bbox 77.5108–77.7492 E, 12.7110–12.9490 N. Every dataset is covered by **one tile**, and the tile **fully covers** the buffered AOI.

| Dataset | Year | STAC item | Covers AOI + buffer | Full tile size |
|---|---|---|---|---|
| ESRI LULC | 2018 | `43P-2018` | ✅ | 139.7 MB |
| ESRI LULC | 2019 | `43P-2019` | ✅ | 142.0 MB |
| ESRI LULC | 2020 | `43P-2020` | ✅ | 144.5 MB |
| ESRI LULC | 2021 | `43P-2021` | ✅ | 144.6 MB |
| ESRI LULC | 2022 | `43P-2022` | ✅ | 147.5 MB |
| ESRI LULC | 2023 | `43P-2023` | ✅ | 123.5 MB |
| WorldCover | 2021 | `ESA_WorldCover_10m_2021_v200_N12E075` | ✅ | 127.7 MB |
| Copernicus DEM | — | `Copernicus_DSM_COG_10_N12_00_E077_00_DEM` | ✅ | 42.0 MB |

**Notes:**
- The tiles are Cloud-Optimised GeoTIFFs. The downloaders read only the AOI window, so the local files are a few MB each, not the full-tile sizes above.
- The ESRI tile `43P` is UTM zone 43N, the same zone as the project CRS (EPSG:32643), so there's no cross-zone warping.
- 2017 is available but **not used** (D3: noticeably noisier than later years).

---

## 3. OSM coverage inside the AOI (P1.6)

Counted with the ohsome history API over the AOI bbox (77.52–77.74 E, 12.72–12.94 N).

| Layer (ohsome filter) | 2018-01-01 | 2026-01-01 | Change |
|---|---|---|---|
| Buildings (`building=*`, polygons) | **151,374** | 186,526 | +23 % |
| All roads (`highway=*`), km | 3,889 | **8,730** | **+124 %** |
| Major roads (motorway–secondary + links), km | 448 | 630 | +41 % |
| Water bodies (`natural=water`, polygons) | 159 | 408 | +157 % |
| Waterways (`waterway=*`), km | 107 | 255 | +138 % |
| Protected areas (`boundary=protected_area` / `leisure=nature_reserve`) | 3 | 2 | −1 |

**Decision: OSM only, no fallback building dataset.**
- 151k building polygons were already mapped in 2018. That's enough for a 2018 reference set, so Microsoft / Google Open Buildings aren't needed (PRD Risk 1 closed for this AOI).

**What the numbers show:**
- **Today's roads would leak future growth** (confirms D8):
  - All-road length more than doubled between the 2018 snapshot and today.
  - Much of that is new residential streets in growth areas, and partly late mapping.
  - Either way, "distance to any road" from current OSM partly encodes growth after 2018. Validation-run road features must use the **2018 snapshot**.
  - Major roads grew less (+41 %), which fits the prototype finding that they barely leak.
- **Water:** OSM water polygons nearly tripled, which is mostly mapping effort, not new lakes. That's one reason `log_dist_water` comes from the ESRI water class (consistent across years), not from OSM.
- **Protected areas (checked in H1.4):**
  - The 2 `boundary=protected_area` polygons are only small heritage sites: Kalyani Vasanthapura Temple and Purandara Mantapa.
  - **Bannerghatta National Park is tagged `boundary=national_park`** (relation 8124064, `protect_class=2`, `landuse=forest`), so the ohsome count above missed it. The downloader therefore also queries `boundary=national_park`.
  - There are no `leisure=nature_reserve` features in the AOI.
  - Protected areas are a static layer, so the current version may be used in the validation run (time-travel rule exception, PRD FR-8.2).

---

## 4. Temporal validation years (P1.8)

Fixed in `config/config.yaml → years` (decision D3):

| Key | Year | Role |
|---|---|---|
| `baseline` | 2018 | Features, reference buildings, roads (validation run) |
| `baseline_confirm` | 2019 | Candidate cells must be non-built in 2018 **and** 2019 |
| `change_train_end` | 2020, 2021 | Change-RF positives: built in both |
| `latest_confirm`, `latest` | 2022, 2023 | Growth label: built in both |

There is visible growth between them: **8.4 % of the land non-built in 2018 became persistently built by 2022/23** ([study_area.md](study_area.md)).

---

## 5. OSM snapshot method (Harsh's track, H1.1)

Implemented in [`src/download/osm.py`](../src/download/osm.py). Run it with `python -m src.download.osm`.

- **Baseline snapshot `2018`:** osmnx `features_from_bbox` is run with `overpass_settings` ending in `[date:"2018-01-01T00:00:00Z"]` (from `osm.snapshot_baseline`). Overpass then returns the data as it was on that date. osmnx assembles multipolygons (e.g. buildings and lakes mapped as relations).
- **Current snapshot `current`:** the same query without `[date:]`.
- **Layers:**

  | Layer | Tags | Snapshots |
  |---|---|---|
  | `roads` | `highway=*` | both |
  | `water` | `natural=water` (queried as `natural=*`, filtered locally), `waterway=*` | both |
  | `buildings` | `building=*` | both |
  | `protected` | `boundary=protected_area` / `national_park`, `leisure=nature_reserve` | current only (static layer) |

  Each layer keeps the tag columns listed in `LAYERS` plus `osm_type` and `osm_id`.
- **Files:** `data/raw/osm/<snapshot>/<layer>.gpkg` (EPSG:4326). Each one is recorded in `data/manifest.json` with the mirror used, tags, date, bbox, feature count and checksum.
- **Mirrors:** tried in order from `osm.overpass_mirrors`: overpass-api.de → overpass.kumi.systems → overpass.private.coffee. Each mirror gets 2 attempts (`io_utils.retry`).
- **Caching:** osmnx caches raw Overpass responses in `data/raw/osm/cache/`. Reruns skip any file whose checksum matches the manifest.
- **One query per tag key, key-only for history:**
  - Overpass history (`[date:]`) queries with a key=value filter, like `natural=water`, run through the global tag index. They fail with "Query run out of memory using about 2048 MB" on both overpass-api.de and kumi, even for a 6 km tile.
  - Key-only queries, like `natural=*` or `highway=*`, are bounded by the bbox and take seconds.
  - So `osm.py` queries `natural=*` and keeps `natural=water` locally (`LOCAL_FILTERS`).
  - Per-tag feature counts go into the manifest (`n_features_by_tag`).
- **Empty tags:**
  - A tag that every mirror reports as empty is recorded with count 0 and skipped.
  - osmnx reports an Overpass error the same way, so the Phase 2 gate cross-checks building and lake counts against the ohsome numbers in §3.
- **Network note:**
  - osmnx normally pins the Overpass host to its IPv4 address.
  - On Harsh's connection, IPv4 to overpass-api.de times out while IPv6 works, so `osm.py` turns that pinning off and uses normal DNS resolution.
- **Not usable as a fallback:** the ohsome geometry endpoint (`/elements/geometry`) returns 403 for public requests. Only its count / length endpoints are open.
- **Sharing:** the 2018 snapshot is slow to query, so `data/raw/osm/` also goes on the team's shared drive. *Link: to add (H1.5).*
- **Last resort:** if historical queries fail on every mirror, use major roads only for the validation run (they barely leak; PRD §18).

---

## 6. ESRI ↔ WorldCover class mapping (A2.3, Abhinav)

*To be added with A2.3. Used for the WorldCover cross-check of the 3-class map only.*

---

## 7. Known issues

| Issue | Source | Handling |
|---|---|---|
| ESRI **over-estimates shrub / scrub**; Bannerghatta shows as rangeland | Venter et al. 2022 (literature review D1); notebook 01 | Protected-area mask (A4.1b); forest checked against WorldCover 2021 |
| ESRI **tree cover flickers** between years in the AOI (7.0 % → 2.3 % → 8.4 %) | Notebook 01 (A1.4) | Forest class from one documented year + WorldCover cross-check (H4 note, PRD §9.4) |
| ESRI **built-up flickers** between years: only 35–49 % of raw single-year growth is persistent | study_area.md | Persistent labels: two years at each end (D3) |
| ESRI 2017 noticeably noisier | study_area.md | 2017 not used (D3) |
| ESRI "built area" is broader than WorldCover "built-up" | study_area.md | Compare within one product only; WorldCover is a cross-check |
| ESRI class 10 = clouds | ESRI class list | Treated as nodata |
| **Copernicus DEM is a surface model (DSM)**: heights include buildings and trees | Copernicus DEM documentation | Slope in dense built-up / forest cells is less reliable; slope matters most on non-built candidate land, where the effect is smaller. Mention in limitations |
| DEM acquisition (2011–2015) predates the baseline | Copernicus DEM | Terrain is treated as static |
| OSM completeness varies by city and over time; buildings mapped after 2018 may have existed in 2018 | Herfort et al. 2023 (literature review D2); study_area.md | AOI chosen for good 2018 coverage; caveat in limitations |
| OSM roads more than doubled 2018 → today | §3 | 2018 snapshot for validation-run features (D8) |
| Bannerghatta NP is tagged `boundary=national_park`, not `protected_area` | §3 (H1.4) | `national_park` added to the protected query; the Phase 2 gate checks that Bannerghatta is present |
| osmnx returns whole features that intersect the bbox (long roads / rivers extend far beyond it) | Quick-look, 2026-10-01 | Clip to AOI + buffer in preprocessing (H2.1) |
