# Product Requirements Document (PRD)

## GIS-Based Land Suitability Analysis for Urban Development Using Land Use Land Cover

| Field | Value |
|---|---|
| Project type | Term project |
| Team | Harsh, Abhinav |
| Repository | https://github.com/code-Harsh247/gis-urban-suitability |
| Document status | Draft v1.0 |
| Created | 2026-09-27 |
| Task tracker | [Tasks.md](Tasks.md) |

---

## Table of contents

1. [Summary](#1-summary)
2. [Background and problem statement](#2-background-and-problem-statement)
3. [Goals and non-goals](#3-goals-and-non-goals)
4. [Stakeholders and users](#4-stakeholders-and-users)
5. [Study area](#5-study-area)
6. [Deliverables](#6-deliverables)
7. [Data requirements](#7-data-requirements)
8. [Functional requirements](#8-functional-requirements)
9. [Methodology in detail](#9-methodology-in-detail)
10. [Non-functional requirements](#10-non-functional-requirements)
11. [System design and repository layout](#11-system-design-and-repository-layout)
12. [Technology stack and environment](#12-technology-stack-and-environment)
13. [Output specifications](#13-output-specifications)
14. [Evaluation, validation and success metrics](#14-evaluation-validation-and-success-metrics)
15. [Development phases](#15-development-phases)
16. [Roles and responsibilities](#16-roles-and-responsibilities)
17. [Team workflow and conventions](#17-team-workflow-and-conventions)
18. [Risks and mitigations](#18-risks-and-mitigations)
19. [Assumptions and dependencies](#19-assumptions-and-dependencies)
20. [Open questions](#20-open-questions)
21. [Glossary](#21-glossary)
22. [References](#22-references)

---

## 1. Summary

We will build a Python pipeline that takes freely available satellite-derived **Land Use Land Cover (LULC)** data, terrain data and infrastructure data (roads, water, buildings) for a chosen study area and produces a **land suitability map for urban development**.

The pipeline does three things:

1. **Classifies land** into three groups — **built-up**, **forest**, and **usable / potential land** — using unsupervised clustering.
2. **Learns from existing buildings** ("building similarity"): given a building at location **A**, it describes the surroundings of A (terrain, access, nearby land cover, density) and finds locations **B** on usable land with similar surroundings.
3. **Produces a ranked suitability map** and a list of top candidate sites, validated against real urban growth that happened between two dates.

Everything is done in Python (no QGIS in the workflow). QGIS may be used only to visually spot-check outputs.

---

## 2. Background and problem statement

Cities grow into surrounding land, often without a systematic check of whether that land is appropriate. Planners need to know **where new development can reasonably happen**: land that is not forest or water, not too steep, reachable by roads, and similar to places where development already works.

Traditional GIS suitability analysis uses **multi-criteria decision analysis (MCDA)**: a planner picks criteria (slope, distance to roads, etc.), assigns weights (for example with AHP), and overlays layers in desktop GIS. This has two weaknesses:

- Weights are subjective.
- The workflow is manual and hard to reproduce.

This project addresses both:

- It is **data-driven**. Clustering finds natural land groupings, and similarity to existing buildings replaces hand-set weights.
- It is **fully scripted in Python**, so it is reproducible and can be rerun for a different city by changing a config file.

**Problem statement:** *Given a study area, identify and rank the land that is suitable for new urban development, using LULC and supporting spatial data, with a reproducible Python workflow.*

---

## 3. Goals and non-goals

### 3.1 Goals

| ID | Goal |
|---|---|
| G1 | Acquire and document LULC and supporting datasets for the study area. |
| G2 | Review existing research on LULC-based land suitability / urban growth analysis. |
| G3 | Classify the study area into **built-up**, **forest**, and **usable** land using clustering. |
| G4 | Implement the **building similarity** method: from a reference building/location A, find similar candidate locations B. |
| G5 | Produce a final **suitability map** (graded classes) and a ranked list of candidate sites. |
| G6 | **Validate** the results quantitatively (temporal validation against real growth + held-out buildings). |
| G7 | Implement everything in **Python**, reproducible from a clean clone with one config file. |
| G8 | Deliver a written report and presentation explaining the method and results. |

### 3.2 Non-goals

- Not building a web application or production service. Interactive HTML maps are enough.
- Not training a deep-learning LULC classifier from raw imagery. We use existing LULC products.
- Not modelling legal/zoning restrictions, land prices or ownership, unless a free dataset is readily available (optional stretch).
- Not predicting *when* land will be developed (no time-series forecasting like CA-Markov). We rank *where*.
- Not doing field surveys or collecting new ground truth.

---

## 4. Stakeholders and users

| Stakeholder | Interest |
|---|---|
| Course instructor / evaluator | Correct method, clear results, reproducibility, report quality. |
| Harsh, Abhinav (team) | Complete the project, share work fairly, learn geospatial Python. |
| Hypothetical end user: urban planner | A map showing where development fits, with an explanation of why. |

---

## 5. Study area

The study area (Area of Interest, **AOI**) is **not yet decided** and is the first decision in Phase 0.

### 5.1 Selection criteria

The AOI must:

1. Have a **growing urban area with surrounding non-built land**, so there is something to predict.
2. Contain **all three classes** (built-up, forest, usable land) in meaningful amounts.
3. Be covered by **ESA WorldCover** and **ESRI 10 m Annual LULC**. Both are global, so this is almost always true.
4. Have **reasonable OpenStreetMap coverage** for roads and buildings. Check by viewing the area on openstreetmap.org.
5. Be **small enough to run on a laptop**: about **200–1,000 km²**. At 100 m grid cells that is 20,000–100,000 cells.
6. Show **visible urban growth between 2017 and 2023**, needed for temporal validation.

### 5.2 AOI definition

- Stored as a polygon in `config/aoi.geojson` (EPSG:4326).
- All processing is done in the local **UTM zone** CRS (a projected CRS in metres), stored in `config/config.yaml`.

---

## 6. Deliverables

| ID | Deliverable | Format | Location |
|---|---|---|---|
| D1 | Source code (pipeline modules) | Python package | `src/` |
| D2 | Analysis notebooks (one per stage) | `.ipynb` | `notebooks/` |
| D3 | Automated tests and phase gate checks | `pytest` | `tests/` |
| D4 | Literature review (≥ 10 papers, summary matrix) | Markdown | `docs/literature_review.md` |
| D5 | Data sources and decisions log | Markdown | `docs/data_sources.md` |
| D6 | Land classification map (3 classes) | GeoTIFF + PNG | `outputs/` |
| D7 | Building similarity results (per-query + aggregate) | GeoTIFF, GeoPackage, PNG | `outputs/` |
| D8 | Final suitability map (graded classes) | GeoTIFF + PNG | `outputs/` |
| D9 | Top-N candidate sites | GeoPackage + CSV | `outputs/` |
| D10 | Interactive map | HTML (folium/leafmap) | `outputs/` |
| D11 | Validation report (metrics, figures) | Markdown / notebook | `docs/validation.md` |
| D12 | Final project report | PDF | `report/` |
| D13 | Presentation slides | PDF / PPTX | `report/` |
| D14 | README with setup and run instructions | Markdown | `README.md` |

---

## 7. Data requirements

### 7.1 Primary datasets

| Layer | Dataset | Resolution | Years | Access (Python) | Purpose |
|---|---|---|---|---|---|
| LULC (main) | **ESA WorldCover** | 10 m | 2020, 2021 | Microsoft Planetary Computer STAC (`esa-worldcover`) | Main land cover for classification and features |
| LULC (time series) | **ESRI 10 m Annual LULC** (Impact Observatory) | 10 m | 2017–2023 | Planetary Computer STAC (`io-lulc-annual-v02`) | Temporal validation (growth 2017 → 2023) |
| LULC (optional) | Dynamic World | 10 m | 2015–present | Google Earth Engine | Class probabilities; cross-check |
| Elevation | **Copernicus DEM GLO-30** (or SRTM) | 30 m | static | Planetary Computer STAC (`cop-dem-glo-30`) | Elevation, slope |
| Roads | **OpenStreetMap** | vector | current | `osmnx` | Distance to roads, road density |
| Water | OpenStreetMap + WorldCover water class | vector / 10 m | current | `osmnx`, WorldCover | Distance to water; exclusion mask |
| Buildings | **OpenStreetMap** footprints (fallback: Microsoft / Google Open Buildings) | vector | current | `osmnx` / direct download | Reference buildings for similarity; building density |

### 7.2 Optional / stretch datasets

| Layer | Dataset | Purpose |
|---|---|---|
| Built-up surface | GHSL (Global Human Settlement Layer) | Built-up density; historical built-up (1975–2030 epochs) |
| Vegetation | Sentinel-2 L2A → NDVI | Vegetation vigour feature |
| Population | WorldPop | Population density feature |
| Protected areas | WDPA (Protected Planet) | Exclusion mask |
| India-specific LULC | Bhuvan / NRSC | Cross-check if AOI is in India |

### 7.3 Data handling rules

- Raw downloads go to `data/raw/`, processed layers to `data/processed/`, features to `data/features/`. All of `data/` is **git-ignored**.
- Every downloaded file is recorded in `data/manifest.json`: dataset name, source URL/collection, date downloaded, year of data, CRS, resolution, bounding box, file size and SHA-256 checksum. This makes the data reproducible without committing it.
- Download scripts must be **idempotent**: rerunning skips files that already exist with a matching checksum.

### 7.4 LULC class reference (ESA WorldCover)

| Code | Class | Maps to project class |
|---|---|---|
| 10 | Tree cover | Forest |
| 20 | Shrubland | Usable (candidate) |
| 30 | Grassland | Usable (candidate) |
| 40 | Cropland | Usable (candidate; flagged as agricultural) |
| 50 | Built-up | Built-up |
| 60 | Bare / sparse vegetation | Usable (candidate) |
| 70 | Snow and ice | Excluded |
| 80 | Permanent water bodies | Excluded |
| 90 | Herbaceous wetland | Excluded |
| 95 | Mangroves | Excluded (forest-like, protected) |
| 100 | Moss and lichen | Usable (rare) |

This mapping is a **reference** used to label and check clusters. The clustering itself must not simply copy it (see §9.4).

---

## 8. Functional requirements

Each requirement has an ID that tasks in [Tasks.md](Tasks.md) refer to.

### FR-1 Configuration

- **FR-1.1** A single `config/config.yaml` holds: AOI path, target CRS (EPSG code), grid cell size (default 100 m), years, buffer radii, slope threshold, clustering parameters, random seed, and output paths.
- **FR-1.2** A config loader validates the config on load: the AOI is a valid polygon, the CRS is projected (metres), the cell size is > 0, and paths exist or can be created.
- **FR-1.3** Changing only the config (and AOI file) must be enough to rerun the pipeline for a different area.

### FR-2 Data acquisition

- **FR-2.1** Download ESA WorldCover tiles covering the AOI (plus a 1 km buffer to avoid edge effects).
- **FR-2.2** Download ESRI Annual LULC for at least two years (baseline year, e.g. 2017, and latest year, e.g. 2023).
- **FR-2.3** Download the DEM covering the AOI plus buffer.
- **FR-2.4** Download OSM roads (with `highway` type), waterways/water bodies, and building footprints for the AOI plus buffer.
- **FR-2.5** Record each download in `data/manifest.json` (§7.3).
- **FR-2.6** Downloads are idempotent and fail with a clear error message if the network or source is unavailable.

### FR-3 Preprocessing

- **FR-3.1** Reproject all rasters to the project CRS and **align them to one reference grid** (same transform, resolution and shape). Use nearest-neighbour resampling for categorical data (LULC) and bilinear for continuous data (DEM).
- **FR-3.2** Clip all layers to the AOI plus buffer.
- **FR-3.3** Handle nodata consistently (one defined nodata value per raster, masked in analysis).
- **FR-3.4** Reproject and clip vector layers. Fix invalid geometries and drop empty ones.
- **FR-3.5** Classify OSM roads into **major** (motorway, trunk, primary, secondary) and **minor** (tertiary, residential, unclassified, service).
- **FR-3.6** Compute **slope** (degrees) and optionally **aspect** from the DEM.

### FR-4 Grid and feature engineering

- **FR-4.1** Create a regular vector grid of square cells (default 100 m) over the AOI, each with a unique `cell_id`.
- **FR-4.2** Compute for every cell the features listed in §9.3.
- **FR-4.3** Compute **neighbourhood context features** (focal means within 250 m and 500 m radii) for the similarity step.
- **FR-4.4** Save the feature table as `data/features/grid_features.parquet` (geometry in a GeoParquet / GeoPackage copy).
- **FR-4.5** Record missing values. Cells with > 50 % nodata are dropped and logged.

### FR-5 Land classification (clustering)

- **FR-5.1** Standardise features (z-score). PCA is optional; if used, keep components explaining ≥ 90 % variance.
- **FR-5.2** Run **K-Means** as the baseline, and at least one alternative (**Gaussian Mixture Model** or **HDBSCAN**).
- **FR-5.3** Choose the number of clusters *k* using the **elbow method** and **silhouette score** (range k = 3 to 10).
- **FR-5.4** Map clusters to the three project classes (**built-up**, **forest**, **usable**) using documented rules based on cluster centroids (§9.4).
- **FR-5.5** Apply the **exclusion mask** (water, wetland, snow, mangroves, slope > threshold) so excluded cells are never labelled usable.
- **FR-5.6** Compare the clustering result to the LULC reference (collapsed to 3 classes) with a confusion matrix and overall agreement.
- **FR-5.7** Results are reproducible with a fixed random seed.

### FR-6 Building similarity

- **FR-6.1** Build a **reference set** of existing buildings (OSM footprints, or built-up cells if footprints are sparse).
- **FR-6.2** For each reference building compute a **context profile** from features within 100 m, 250 m and 500 m buffers (§9.5).
- **FR-6.3** **Single query mode:** given one building A (by ID or coordinates), return the top-N most similar candidate locations B in usable land, with a similarity score.
- **FR-6.4** **Aggregate mode:** for every usable cell compute a similarity score to the whole reference set (e.g. mean of top-k nearest reference profiles).
- **FR-6.5** **ML alternative:** train a Random Forest classifier (built vs non-built) on context features and use its predicted probability as a suitability score.
- **FR-6.6** Prevent **data leakage**: features that directly encode "this cell is built" (e.g. the cell's own built-up fraction or building count) must not be used as inputs for the similarity or ML score.
- **FR-6.7** Candidates are restricted to cells labelled **usable** and not in the exclusion mask.

### FR-7 Suitability mapping

- **FR-7.1** Combine the similarity score (and optionally the ML score) into a final suitability score in [0, 1].
- **FR-7.2** Classify the score into four classes: **S1 Highly suitable, S2 Moderately suitable, S3 Marginally suitable, N Not suitable** (thresholds by quantiles or natural breaks, documented).
- **FR-7.3** Produce a **baseline MCDA map** (weighted overlay of slope, distance to roads, distance to built-up, distance to water, with weights from literature or AHP) for comparison.
- **FR-7.4** Export the top-N candidate sites (cells or merged patches with minimum area) with their scores and key attributes.

### FR-8 Validation

- **FR-8.1** **Temporal validation:** using ESRI LULC, find cells that were non-built in the baseline year and built in the latest year ("new growth"). Build the model only on baseline-year data and measure how highly it ranks the new-growth cells.
- **FR-8.2** **Held-out buildings:** use spatial block cross-validation (not random splits) to hold out reference buildings and check that their locations get high similarity.
- **FR-8.3** Report metrics: ROC-AUC, precision@top-10 %, hit rate of new growth in S1+S2, and a comparison with the MCDA baseline.
- **FR-8.4** Sanity checks: querying building A must return A's own location (or its neighbours) as a top match; no excluded cell appears in the candidate list.

### FR-9 Visualisation

- **FR-9.1** Static maps (PNG, 300 dpi) with title, legend, scale bar, north arrow and basemap for: LULC, three-class map, each key feature, similarity map, suitability map, and top candidates.
- **FR-9.2** Interactive HTML map with toggleable layers (LULC, classes, suitability, candidates, reference buildings).
- **FR-9.3** Charts: elbow and silhouette plots, cluster centroid profiles, feature importance (RF), ROC curve, and class-area statistics.

### FR-10 Reproducibility and orchestration

- **FR-10.1** Notebooks `01`–`06` run top to bottom without manual edits.
- **FR-10.2** A script `python -m src.pipeline` runs all stages end to end using the config.
- **FR-10.3** Every stage reads its inputs from disk and writes its outputs to disk, so stages can be rerun independently.

---

## 9. Methodology in detail

### 9.1 Pipeline overview

```
config.yaml + aoi.geojson
        │
        ▼
[Phase 2] Download ──► data/raw/  (WorldCover, ESRI LULC, DEM, OSM)
        │
        ▼
[Phase 3] Preprocess ──► data/processed/  (aligned rasters, clean vectors, slope)
        │
        ▼
[Phase 4] Grid + features ──► data/features/grid_features.parquet
        │
        ├──► [Phase 5] Clustering ──► 3-class map (built-up / forest / usable)
        │
        └──► [Phase 6] Building similarity ──► similarity score per usable cell
                        │
                        ▼
               [Phase 7] Suitability classes + validation + MCDA baseline
                        │
                        ▼
               [Phase 8] Maps, report, slides
```

### 9.2 Grid

- Square cells, default **100 m** (1 ha). Configurable (50–250 m).
- Why a grid: it turns mixed data (10 m rasters, 30 m DEM, vectors) into one table with one row per cell. That table suits scikit-learn.
- Each cell stores the geometry, `cell_id`, row/col index and centroid coordinates.

### 9.3 Feature list

| Feature | Unit | Computed from | Notes |
|---|---|---|---|
| `frac_tree`, `frac_shrub`, `frac_grass`, `frac_crop`, `frac_built`, `frac_bare`, `frac_water`, `frac_wetland` | 0–1 | WorldCover | Fraction of the cell's 10 m pixels in each class; fractions sum to ≈ 1 |
| `elev_mean` | m | DEM | |
| `slope_mean`, `slope_max` | degrees | DEM | |
| `dist_road_major` | m | OSM roads | Distance from cell centroid |
| `dist_road_any` | m | OSM roads | |
| `road_density` | km / km² | OSM roads | Road length inside a 500 m radius |
| `dist_water` | m | OSM water + WorldCover water | |
| `dist_built` | m | WorldCover built-up | Distance to nearest built-up pixel outside the cell |
| `dist_center` | m | Config (city centre point) | Optional |
| `bldg_count`, `bldg_area_frac` | count, 0–1 | OSM buildings | **Not used** in similarity/ML inputs (leakage) |
| `ctx250_*`, `ctx500_*` | same as base | Focal mean of base features | Neighbourhood context |
| `ndvi_mean` | −1 to 1 | Sentinel-2 | Optional |
| `pop_density` | people / km² | WorldPop | Optional |

Distances are computed with a Euclidean distance transform on a rasterised version of the target (`scipy.ndimage.distance_transform_edt`) at 10–30 m resolution, then sampled at cell centroids. Distance values are capped at a maximum (e.g. 5 km) and log-transformed before clustering to reduce skew.

### 9.4 Land classification (clustering)

1. **Inputs:** LULC fractions, slope, elevation, NDVI (if available), distances. Standardised.
2. **Algorithms:** K-Means (k-means++, `n_init=10`, fixed seed) as the baseline, plus GMM (full covariance) or HDBSCAN as an alternative.
3. **Choosing k:** plot inertia (elbow) and silhouette score for k = 3…10. *k* may be larger than 3. Several clusters can then map to one project class, e.g. "usable–flat–near roads" and "usable–hilly".
4. **Mapping clusters → 3 classes:** a rule table based on cluster centroids:
   - highest mean `frac_built` (and above a threshold, e.g. 0.3) → **built-up**
   - highest mean `frac_tree` (above a threshold, e.g. 0.5) → **forest**
   - clusters dominated by water/wetland → **excluded**
   - all remaining clusters → **usable**
5. **Exclusion mask** applied last. Water, wetland, snow, mangroves and slope > threshold (default 15°, configurable) are never usable.
6. **Evaluation:** silhouette score, Davies–Bouldin index, confusion matrix against WorldCover majority class collapsed to 3 classes, and centroid profile plots to interpret each cluster.
7. **Discussion point for the report:** because LULC fractions are inputs, agreement with LULC is expected to be high. The value of clustering is in the **sub-groups** it finds inside "usable" land (flat vs hilly, near vs far from roads), which feed the similarity and suitability steps.

### 9.5 Building similarity

**Idea:** a building exists at A because the surroundings of A suit a building. Locations whose surroundings look like A's are good candidates for a similar building.

**Context profile** for a location (building centroid or cell centroid). For each radius r ∈ {100, 250, 500 m}:

- LULC class fractions within r (excluding the building's own footprint / own cell for built-up)
- mean and max slope within r, mean elevation
- distance to nearest major road, any road, water
- road density within r
- built-up fraction of the **surrounding ring** (r minus the inner cell), measuring "near existing development" without leaking the cell's own status

The profile is a fixed-length vector. It is standardised using statistics from **all candidate + reference locations**.

**Single-query mode (as described in the project meeting):**

1. The user picks building A (ID or lat/lon).
2. Compute A's profile.
3. Compute the similarity between A and every usable cell: **cosine similarity** (primary) and **Euclidean distance in standardised space** (alternative). Optionally use feature weights.
4. Return the top-N cells (B₁…Bₙ), with scores and a map.

**Aggregate mode:**

- The reference set is all (or a stratified sample of) existing buildings.
- For each usable cell: score = mean similarity to its **k nearest reference profiles** in feature space (k ≈ 10). Use `sklearn.neighbors.NearestNeighbors`.
- Rescale to [0, 1].

**ML alternative (Random Forest):**

- Positives: built cells (baseline year). Negatives: sampled non-built, non-excluded cells.
- Inputs: context features only (no own-cell built-up / building count).
- Use `RandomForestClassifier` with class balancing and spatial block cross-validation.
- Output: probability of "built-like" context = suitability score.
- Report feature importance (impurity-based and permutation).

**Building types (stretch):** if OSM `building=*` tags are rich enough (residential, commercial, industrial), run similarity per type to answer "where could a similar *residential* building go?".

### 9.6 Suitability score and classes

- Final score = similarity score (aggregate mode), or a documented weighted mean of the similarity and RF scores.
- Classes: S1 (top 10 %), S2 (next 20 %), S3 (next 30 %), N (the rest plus all excluded / built / forest cells). Alternatively Jenks natural breaks; the choice is documented.
- Post-processing: merge adjacent S1 cells into **candidate patches**. Drop patches smaller than a minimum area (e.g. 1 ha).

### 9.7 MCDA baseline (for comparison)

- Criteria: slope (lower is better), distance to major road (closer is better), distance to built-up (closer is better), distance to water (not too close; apply a buffer), LULC (bare/grass/shrub > crop).
- Each criterion is rescaled to 0–1. Weights come from the literature or a small **AHP** pairwise matrix, with the consistency ratio reported (must be < 0.1).
- Output: MCDA suitability map, compared with the data-driven map (map agreement, correlation, validation metrics).

### 9.8 Validation design

| Check | How | Target |
|---|---|---|
| Temporal validation | Build features and model on the baseline year (e.g. ESRI 2017). Label new-growth cells from 2017 → 2023. Compute ROC-AUC of the score for predicting new growth among non-built baseline cells. | ROC-AUC ≥ 0.75 |
| Top-k hit rate | Share of new-growth cells in the top 10 % / top 30 % of scores | ≥ 2× random (i.e. ≥ 20 % in top 10 %) |
| Class hit rate | Share of new-growth cells falling in S1 + S2 | Higher than MCDA baseline |
| Held-out buildings | Spatial block CV: similarity rank of held-out building locations | Median percentile ≥ 80th |
| Self-query sanity | Query building A → A's own cell is in top 1 % | Must pass |
| Exclusion sanity | No excluded / forest / built cell in S1–S3 or candidate list | Must pass (0 violations) |
| Clustering agreement | Overall agreement with collapsed WorldCover | ≥ 80 % |

Targets are initial goals. If a target is missed, the report explains why. That is an acceptable result for a term project, as long as it is analysed honestly.

---

## 10. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 Reproducibility | Fresh clone + `conda env create` + config → same outputs (fixed seeds, pinned versions, data manifest with checksums). |
| NFR-2 Performance | Full pipeline for the AOI runs in **< 30 min** on a normal laptop (8–16 GB RAM). Peak memory **< 8 GB**. Use windowed reads / chunking if needed. |
| NFR-3 Portability | Works on Windows and Linux. Use conda-forge for GDAL-based packages (pip wheels for GDAL on Windows are unreliable). Use `pathlib` for all paths. |
| NFR-4 Code quality | Functions in `src/` have docstrings and type hints. Notebooks call `src/` functions instead of repeating long code. Format with `black`, lint with `ruff`. |
| NFR-5 Testing | `pytest` unit tests on small synthetic data for core functions (distance, fractions, similarity, masking), plus phase gate tests (see Tasks.md). |
| NFR-6 Version control | Data and large outputs are not committed. Notebook outputs are stripped before commit (`nbstripout`). |
| NFR-7 Documentation | README (setup + run), PRD, Tasks, data sources, literature review, validation, and a report. |
| NFR-8 CRS correctness | All distance/area computations happen in the projected CRS (metres). Never compute distances in EPSG:4326. |
| NFR-9 Logging | Each stage logs inputs, outputs, counts and timings to `logs/` (git-ignored) and the console. |

---

## 11. System design and repository layout

```
gis-urban-suitability/
├── CLAUDE.md                  # pointer to docs/CLAUDE.md
├── README.md                  # setup + how to run
├── environment.yml            # conda environment (pinned)
├── pyproject.toml             # package metadata, black/ruff/pytest config
├── config/
│   ├── config.yaml            # all parameters
│   └── aoi.geojson            # study area polygon
├── docs/
│   ├── CLAUDE.md
│   ├── PRD.md                 # this document
│   ├── Tasks.md               # task tracker
│   ├── literature_review.md
│   ├── data_sources.md
│   └── validation.md
├── src/
│   ├── __init__.py
│   ├── config.py              # load + validate config
│   ├── io_utils.py            # read/write helpers, manifest
│   ├── download/
│   │   ├── lulc.py            # WorldCover + ESRI via STAC
│   │   ├── dem.py
│   │   └── osm.py             # roads, water, buildings via osmnx
│   ├── preprocess/
│   │   ├── raster.py          # reproject, align, clip
│   │   ├── vector.py          # clean, reproject, classify roads
│   │   └── terrain.py         # slope, aspect
│   ├── features/
│   │   ├── grid.py            # create grid
│   │   ├── lulc_features.py   # class fractions
│   │   ├── distance.py        # distance transforms
│   │   ├── context.py         # focal / buffer features
│   │   └── build.py           # assemble feature table
│   ├── classify/
│   │   ├── cluster.py         # kmeans, gmm, hdbscan, k selection
│   │   └── label.py           # cluster → 3 classes, exclusion mask
│   ├── similarity/
│   │   ├── profiles.py        # context profiles
│   │   ├── query.py           # single-building query
│   │   ├── aggregate.py       # kNN aggregate score
│   │   └── rf_model.py        # random forest alternative
│   ├── suitability/
│   │   ├── score.py           # combine + classify S1–N
│   │   ├── mcda.py            # baseline weighted overlay + AHP
│   │   └── validate.py        # temporal + holdout validation
│   ├── viz/
│   │   ├── static_maps.py
│   │   └── interactive.py
│   └── pipeline.py            # end-to-end runner
├── notebooks/
│   ├── 01_data_download.ipynb
│   ├── 02_preprocessing.ipynb
│   ├── 03_feature_engineering.ipynb
│   ├── 04_clustering.ipynb
│   ├── 05_similarity.ipynb
│   └── 06_suitability_validation.ipynb
├── tests/
│   ├── conftest.py            # synthetic fixtures
│   ├── unit/                  # unit tests per module
│   └── gates/                 # phase gate tests (test_phase0.py … test_phase8.py)
├── scripts/
│   └── check_env.py
├── outputs/                   # git-ignored (except small final PNGs if desired)
├── report/                    # final report + slides
├── data/                      # git-ignored
└── logs/                      # git-ignored
```

---

## 12. Technology stack and environment

| Area | Libraries |
|---|---|
| Core | Python 3.11, numpy, pandas, pyyaml |
| Raster | rasterio, rioxarray, xarray |
| Vector | geopandas, shapely ≥ 2, pyproj, pyogrio |
| Data access | pystac-client, planetary-computer, osmnx, requests; (optional) earthengine-api, geemap |
| Terrain | richdem or numpy-based slope (Horn method) |
| Analysis | scipy, scikit-learn, hdbscan (or `sklearn.cluster.HDBSCAN`) |
| Visualisation | matplotlib, contextily, matplotlib-scalebar, folium / leafmap, seaborn (optional) |
| Dev | jupyterlab, pytest, black, ruff, nbstripout, pre-commit |

Environment:

- `environment.yml` using the **conda-forge** channel, with versions pinned after the first working install.
- Everyone uses the same environment name: `gis-suit`.
- `scripts/check_env.py` imports every library and prints versions (used in the Phase 0 gate).

---

## 13. Output specifications

| Output | Format | CRS | Content |
|---|---|---|---|
| `outputs/lulc_3class.tif` | GeoTIFF (uint8, LZW) | Project CRS | 1 built-up, 2 forest, 3 usable, 255 excluded/nodata |
| `outputs/clusters.gpkg` | GeoPackage | Project CRS | Grid cells with `cluster_id`, `class_3`, key features |
| `outputs/similarity_query_<id>.gpkg` / `.png` | GeoPackage, PNG | Project CRS | Top-N matches for query building `<id>` |
| `outputs/similarity_score.tif` | GeoTIFF (float32) | Project CRS | Aggregate similarity score 0–1 |
| `outputs/rf_probability.tif` | GeoTIFF (float32) | Project CRS | RF probability 0–1 |
| `outputs/suitability_score.tif` | GeoTIFF (float32) | Project CRS | Final score 0–1 |
| `outputs/suitability_class.tif` | GeoTIFF (uint8) | Project CRS | 1 S1, 2 S2, 3 S3, 4 N |
| `outputs/mcda_score.tif` | GeoTIFF (float32) | Project CRS | Baseline score |
| `outputs/candidates.gpkg` / `.csv` | GeoPackage, CSV | Project CRS / lat-lon in CSV | Candidate patches: id, area, mean score, slope, dist to road, dist to built |
| `outputs/map.html` | HTML | Web Mercator | Interactive map |
| `outputs/figures/*.png` | PNG 300 dpi | — | All report figures |

---

## 14. Evaluation, validation and success metrics

The project is **complete and successful** when:

1. All deliverables D1–D14 exist.
2. `python -m src.pipeline` runs end to end from a fresh clone (with data downloaded) without errors.
3. `pytest` passes: all unit tests and all phase gate tests.
4. The validation targets in §9.8 are met, **or** misses are explained in the report with analysis.
5. The report explains the method, results, limitations and possible improvements.
6. Both teammates have reviewed each other's code (every PR has one approval).

---

## 15. Development phases

Detailed todos, owners and gate checks are in **[Tasks.md](Tasks.md)**. Durations are estimates; adjust them once the submission deadline is known.

| Phase | Name | Goal | Est. duration |
|---|---|---|---|
| 0 | Setup and planning | Repo, environment, conventions, study area chosen | Week 1 |
| 1 | Literature review and data discovery | ≥ 10 papers reviewed; datasets chosen and coverage verified | Weeks 1–2 |
| 2 | Data acquisition | All raw data downloaded, documented in manifest | Week 3 |
| 3 | Preprocessing | All layers aligned, clipped and clean in project CRS | Week 3–4 |
| 4 | Grid and feature engineering | Feature table for every cell | Week 4–5 |
| 5 | Land classification (clustering) | 3-class map with evaluation | Week 5–6 |
| 6 | Building similarity | Single-query + aggregate + RF scores | Week 6–7 |
| 7 | Suitability mapping and validation | Final map, candidates, MCDA baseline, metrics | Week 8–9 |
| 8 | Visualisation, report and presentation | Figures, interactive map, report, slides, final clean-up | Week 9–10 |

Each phase ends with a **Phase Gate**: an automated test file (`tests/gates/test_phaseN.py`) plus a manual checklist. A phase is **done** only when the gate passes and both teammates sign off in Tasks.md.

---

## 16. Roles and responsibilities

Work is split so that **both teammates write code in every phase** and each owns specific modules end to end.

| Area | Lead | Support / reviewer |
|---|---|---|
| Repo, conda environment, docs | Harsh | Abhinav |
| Folder skeleton, config loader, pre-commit | Abhinav | Harsh |
| Study area proposal | Abhinav | Harsh |
| Literature review | Both (split by topic) | — |
| LULC + DEM download (STAC) | Harsh | Abhinav |
| OSM download (roads, water, buildings) | Abhinav | Harsh |
| Raster preprocessing + terrain | Harsh | Abhinav |
| Vector preprocessing | Abhinav | Harsh |
| Grid + LULC fractions + context features | Harsh | Abhinav |
| Distance features + density | Abhinav | Harsh |
| Clustering + labelling | Abhinav | Harsh |
| Building similarity (profiles, query, aggregate) | Harsh | Abhinav |
| Random Forest alternative | Abhinav | Harsh |
| Suitability scoring + temporal validation | Harsh | Abhinav |
| MCDA baseline + AHP | Abhinav | Harsh |
| Static maps | Abhinav | Harsh |
| Interactive map + pipeline runner | Harsh | Abhinav |
| Report + slides | Both (split by section) | — |

**Rule:** the reviewer on each area reviews the PR and runs the relevant gate test before merge.

---

## 17. Team workflow and conventions

- **Branches:** `main` is always working. Work on `feat/<phase>-<short-name>` branches (e.g. `feat/p2-osm-download`).
- **Pull requests:** every change goes through a PR reviewed by the other teammate. Link the task ID (e.g. `P2.4`) in the PR title.
- **Commits:** small and descriptive, in the present tense ("Add slope computation"). **No Claude / AI co-author lines** (see `docs/CLAUDE.md`).
- **Notebooks:** strip outputs before commit (`nbstripout`). Put reusable logic in `src/`. Only one person edits a given notebook at a time (the owner in Tasks.md).
- **Task tracking:** update checkboxes in Tasks.md in the same PR that completes the task.
- **Sync:** short check-in twice a week, plus a phase-gate review at the end of each phase.
- **Data sharing:** do not commit data. Each teammate runs the download scripts. If downloads are slow, share `data/raw/` via a drive link recorded in `docs/data_sources.md`.

---

## 18. Risks and mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| OSM building footprints sparse in AOI | Similarity reference set too small | Medium (high in many Indian cities) | Fall back to Microsoft / Google Open Buildings, or use WorldCover built-up cells as reference |
| GDAL / rasterio install problems on Windows | Blocks setup | Medium | Use conda-forge only; test env in Phase 0 on both machines |
| Planetary Computer / Overpass API downtime or rate limits | Delays downloads | Low–Medium | Idempotent downloads with retries; cache raw data; share via drive |
| Study area too large | Slow runs, memory errors | Medium | Size limit in §5.1; windowed processing; larger cell size |
| CRS mismatches | Wrong distances/overlays | Medium | Single project CRS in config; gate tests assert CRS/alignment |
| Data leakage in similarity/RF | Falsely high validation scores | Medium | FR-6.6; gate test asserts leaky columns are absent from model inputs |
| Spatial autocorrelation inflating accuracy | Over-optimistic metrics | High | Spatial block CV; temporal validation |
| LULC classification errors (e.g. crop vs grass confusion) | Noisy features | Medium | Cross-check WorldCover vs ESRI; discuss in limitations |
| Clusters don't separate cleanly into 3 classes | Weak classification | Low–Medium | Allow k > 3 and map several clusters per class; try GMM/HDBSCAN |
| Uneven workload / coordination issues | Delays | Medium | Owners per task in Tasks.md; twice-weekly check-in; phase gates |
| Deadline pressure | Incomplete deliverables | Medium | Stretch items clearly marked optional; core pipeline first |

---

## 19. Assumptions and dependencies

- Free access to Microsoft Planetary Computer STAC (no key needed for public data; signing via the `planetary-computer` package).
- Overpass API (used by osmnx) is available.
- Google Earth Engine is **optional**. It needs a registered account/project and is only used for Dynamic World.
- Both teammates have a laptop with ≥ 8 GB RAM and ~10 GB free disk space.
- Existing buildings are a reasonable signal of suitable land. This is a key assumption and must be stated in the report: past development reflects past decisions, which are not always "good" planning.

---

## 20. Open questions

| # | Question | Owner | Needed by |
|---|---|---|---|
| Q1 | Which city / region is the study area? | Both | End of Phase 0 |
| Q2 | What is the submission deadline, and are there intermediate reviews? | Harsh | End of Phase 0 |
| Q3 | Does the instructor require a specific report format / length? | Abhinav | End of Phase 1 |
| Q4 | Grid cell size: 100 m default, or 50 m for a small AOI? | Both | Phase 4 start |
| Q5 | Is agricultural land (cropland) treated as usable, or excluded / penalised? | Both | Phase 5 start |
| Q6 | Slope threshold for exclusion (15° default)? | Both | Phase 5 start |
| Q7 | Should similarity be run per building type (residential / commercial / industrial)? | Harsh | Phase 6 start |

---

## 21. Glossary

| Term | Meaning |
|---|---|
| **LULC** | Land Use Land Cover: a map that labels each pixel with a land type (forest, water, built-up, etc.). |
| **AOI** | Area of Interest: the study area. |
| **CRS** | Coordinate Reference System. A projected CRS (e.g. UTM) uses metres. |
| **STAC** | SpatioTemporal Asset Catalog: a standard API for searching satellite data. |
| **DEM** | Digital Elevation Model: a raster of ground height. |
| **Grid cell** | A square unit (e.g. 100 m × 100 m) that becomes one row in the feature table. |
| **Clustering** | Grouping cells that have similar features, without labels. |
| **Context profile** | A vector describing a location's surroundings (land cover, terrain, access). |
| **Cosine similarity** | Similarity between two vectors based on their angle: 1 means same direction. |
| **MCDA / AHP** | Multi-Criteria Decision Analysis / Analytic Hierarchy Process: expert-weighted overlay methods. |
| **Data leakage** | When a model input secretly contains the answer, which inflates accuracy. |
| **Spatial block CV** | Cross-validation that splits data by geographic blocks, so nearby (similar) cells don't end up in both train and test. |
| **ROC-AUC** | How well a score separates positives from negatives. 0.5 is random, 1.0 is perfect. |
| **S1 / S2 / S3 / N** | FAO-style suitability classes: highly, moderately, marginally, not suitable. |

---

## 22. References

Starting points. The literature review in Phase 1 extends these to ≥ 10 papers.

- Malczewski, J. (2004). *GIS-based land-use suitability analysis: a critical overview.* Progress in Planning, 62(1), 3–65.
- Saaty, T. L. (1980). *The Analytic Hierarchy Process.* McGraw-Hill.
- FAO (1976). *A Framework for Land Evaluation.* FAO Soils Bulletin 32.
- Zanaga, D. et al. (2021/2022). *ESA WorldCover 10 m v100 / v200.* ESA WorldCover project.
- Karra, K. et al. (2021). *Global land use / land cover with Sentinel 2 and deep learning.* IGARSS 2021 (ESRI / Impact Observatory LULC).
- Brown, C. F. et al. (2022). *Dynamic World, Near real-time global 10 m land use land cover mapping.* Scientific Data, 9, 251.
- Pesaresi, M. et al. *Global Human Settlement Layer (GHSL)* — European Commission JRC.
- Dataset docs: Microsoft Planetary Computer catalog (`esa-worldcover`, `io-lulc-annual-v02`, `cop-dem-glo-30`); OSMnx documentation.
