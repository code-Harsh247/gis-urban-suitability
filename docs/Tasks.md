# Tasks

Task tracker for **GIS-Based Land Suitability Analysis for Urban Development**. Requirements and method details are in [PRD.md](PRD.md).

## How to use this file

- Each task has an **ID** (`P<phase>.<n>`), an **owner**, and the **PRD requirement** it covers.
- Tick the box (`- [x]`) in the **same PR** that completes the task.
- Owners: **Harsh**, **Abhinav**, or **Both** (both must contribute; split noted in the task).
- The reviewer of a task is the other teammate, unless the task is marked **Both**.
- Every phase ends with a **Phase Gate**:
  1. **Automated check:** `pytest tests/gates/test_phaseN.py` must pass.
  2. **Manual checklist:** every item must be ticked.
  3. **Sign-off:** both teammates tick their name.
- **Do not start the next phase's dependent tasks until the gate passes.** Independent tasks (e.g. report writing) may start early.

**Status legend:** `- [ ]` not started · `- [~]` in progress (write `[~]` by hand) · `- [x]` done

---

## Progress overview

| Phase | Name | Harsh | Abhinav | Both | Gate test by | Gate passed |
|---|---|---|---|---|---|---|
| 0 | Setup and planning | 6 (5 done) | 4 (3 done by Harsh) | 2 | Harsh | ☐ |
| 1 | Literature review and data discovery | 3 | 3 | 2 | Abhinav | ☐ |
| 2 | Data acquisition | 4 | 4 | 1 | Harsh | ☐ |
| 3 | Preprocessing | 3 | 4 | 2 | Abhinav | ☐ |
| 4 | Grid and feature engineering | 4 | 4 | 1 | Harsh | ☐ |
| 5 | Land classification (clustering) | 3 | 5 | 1 | Abhinav | ☐ |
| 6 | Building similarity | 4 | 4 | 1 | Harsh | ☐ |
| 7 | Suitability mapping and validation | 4 | 4 | 1 | Abhinav | ☐ |
| 8 | Visualisation, report and presentation | 5 | 5 | 3 | Harsh | ☐ |
| | **Total** | **36** | **37** | **14** | 5 / 4 | |

Ownership in short: **Harsh** leads the raster/LULC pipeline, building similarity, suitability scoring, temporal validation and the pipeline runner. **Abhinav** leads OSM/vector data, distance features, clustering, the Random Forest model, the MCDA baseline and static maps. Gate tests alternate between the two, so each person checks the other's phase work.

---

## Phase 0 — Setup and planning

**Goal:** a working shared repo and environment on both laptops, agreed conventions, and a chosen study area.
**Depends on:** nothing. **Est.:** Week 1.

### Todos

- [x] **P0.1** Create GitHub repo, first commit, push to `main`. — **Harsh**
- [x] **P0.2** Add `.gitignore` (Python, data, rasters, vectors). — **Harsh**
- [x] **P0.3** Add `docs/CLAUDE.md`, root `CLAUDE.md` pointer, `.claude/settings.json` (no AI attribution). — **Harsh**
- [x] **P0.4** Write PRD and Tasks. — **Harsh**
- [~] **P0.5** Add Abhinav as a collaborator on GitHub; Abhinav clones the repo. — **Harsh** · *Invite sent; waiting for Abhinav to accept and clone.*
- [x] **P0.6** Create `environment.yml` (conda-forge, Python 3.11, all libraries from PRD §12) and `scripts/check_env.py`. — **Harsh** · PRD NFR-1, NFR-3
- [x] **P0.7** Create the folder skeleton from PRD §11 (`src/` subpackages with `__init__.py`, `notebooks/`, `tests/unit/`, `tests/gates/`, `config/`, `outputs/`, `report/`) and `pyproject.toml` (black, ruff, pytest config). — **Abhinav** · NFR-4 · *Done by Harsh; `data/`, `outputs/`, `logs/` are git-ignored and created by `Config.ensure_dirs()`.*
- [x] **P0.8** Set up `pre-commit` with `black`, `ruff`, `nbstripout`. — **Abhinav** · NFR-6 · *Done by Harsh; hooks run the env's own tools (plus a 1 MB file-size guard), so run `pre-commit install` inside `gis-suit`.*
- [x] **P0.9** Propose 3 candidate study areas that meet PRD §5.1. For each, give: approx. area (km²), a screenshot of WorldCover, an OSM building coverage check, and visible growth 2017→2023. Write it up in `docs/study_area.md`. — **Abhinav** · PRD §5 · *14 areas checked with `scripts/study_area_candidates.py` (persistent 2018→2023 growth, OSM buildings in 2018 and 2026). Recommends Bengaluru South, then Hyderabad West; Pune West as fallback.*
- [~] **P0.10** Choose the study area together; draw `config/aoi.geojson`; set the UTM EPSG code. — **Both** · Q1 · *Bengaluru South adopted as the default (see `docs/execution_plan.md` §2). AOI = the study-area bbox (582 km², EPSG:32643 via `crs.epsg: auto`). Waiting for Harsh to confirm; the polygon can still be refined.*
- [x] **P0.11** Write `config/config.yaml` and `src/config.py` (load + validate: AOI valid polygon, CRS projected, cell size > 0). — **Abhinav** · FR-1.1, FR-1.2 · *Done by Harsh, with 15 unit tests in `tests/unit/test_config.py`. `crs.epsg: auto` picks the UTM zone from the AOI, so P0.10 only needs the polygon + `aoi.name`.*
- [ ] **P0.12** Find out the deadline, intermediate reviews and report format from the instructor; update PRD §15 and §20. — **Both** (Harsh: deadline/reviews, Abhinav: report format) · Q2, Q3

### Phase 0 Gate

**Automated — `tests/gates/test_phase0.py`** (written by **Harsh**):
- [x] Every library in `environment.yml` imports (`scripts/check_env.py` exits 0).
- [x] `config/config.yaml` loads through `src/config.py` without error.
- [x] `config/aoi.geojson` has exactly one valid polygon; area between 50 and 1,500 km² when projected.
- [x] The configured CRS is projected with units in metres.
- [x] `aoi.name` in the config is set (not `TBD`).
- [x] All tracked folders from PRD §11 and the key files exist; every `src/` subpackage has `__init__.py`.

Status on Harsh's laptop (2026-09-27): **30 passed, 5 failing**. All 5 need the AOI.
Status on Abhinav's laptop (2026-10-01, Linux, micromamba): **35 passed** (+ 15 unit tests), with the Bengaluru South AOI.

**Manual checklist:**
- [ ] Both teammates created the conda env and ran `pytest tests/gates/test_phase0.py` successfully on **their own laptop**. *(Harsh: env done, rerun now that the AOI exists; Abhinav: done 2026-10-01)*
- [x] `pre-commit run --all-files` passes.
- [ ] `docs/study_area.md` states the chosen AOI and the reason.
- [ ] Deadline is recorded in PRD, and phase dates in this file are adjusted.

**Sign-off:** - [ ] Harsh  - [ ] Abhinav

---

## Phase 1 — Literature review and data discovery

**Goal:** understand prior work and lock in the datasets.
**Depends on:** P0.10 (study area) for the coverage checks. **Est.:** Weeks 1–2.

### Todos

- [ ] **P1.1** Create `docs/literature_review.md` with a template matrix: title, authors, year, venue, study area, data used, method, criteria/features, validation, key findings, relevance to us. — **Abhinav**
- [ ] **P1.2** Review ≥ 5 papers on **GIS/MCDA land suitability and urban growth using LULC** (AHP, weighted overlay, FAO framework, LULC change). — **Abhinav** · G2
- [ ] **P1.3** Review ≥ 5 papers on **ML / clustering / similarity for land classification and site selection** (K-Means/GMM on land features, RF urban growth models, spatial CV). — **Harsh** · G2
- [ ] **P1.4** Write a 1-page synthesis in the review: common criteria, typical weights, common validation methods, and the gap our similarity approach fills. — **Both** (Abhinav: MCDA part, Harsh: ML part)
- [ ] **P1.5** Check coverage and access for WorldCover (2020, 2021), ESRI Annual LULC (2017–2023) and Copernicus DEM over the AOI via Planetary Computer STAC. Record item IDs, tiles and sizes. — **Harsh** · PRD §7
- [ ] **P1.6** Check OSM coverage in the AOI: count buildings, road length and water features with a quick `osmnx` query. Decide whether a fallback building dataset (Microsoft / Google Open Buildings) is needed. — **Abhinav** · PRD §7, Risk 1
- [ ] **P1.7** Write `docs/data_sources.md`: final dataset list, versions, years, licences, access method, and known issues. — **Harsh**
- [ ] **P1.8** Decide the baseline and latest year for temporal validation (e.g. 2017 → 2023), and confirm there is visible growth between them. — **Both** · FR-8.1

### Phase 1 Gate

**Automated — `tests/gates/test_phase1.py`** (written by **Abhinav**):
- [ ] `docs/literature_review.md` exists and contains ≥ 10 paper entries (count matrix rows).
- [ ] `docs/data_sources.md` exists and lists WorldCover, ESRI LULC, DEM and OSM, each with licence and access method.
- [ ] A STAC search for each raster collection over the AOI bbox returns ≥ 1 item (network test, marked `@pytest.mark.network`).

**Manual checklist:**
- [ ] Each teammate has read the other's paper summaries.
- [ ] The synthesis section clearly states what our project adds.
- [ ] Building data source decided (OSM only, or OSM + fallback).
- [ ] Temporal validation years fixed in `config.yaml`.

**Sign-off:** - [ ] Harsh  - [ ] Abhinav

---

## Phase 2 — Data acquisition

**Goal:** all raw data downloaded reproducibly and recorded in a manifest.
**Depends on:** Phase 1 gate. **Est.:** Week 3.

### Todos

- [x] **P2.1** Write `src/io_utils.py`: manifest read/write (`data/manifest.json`), SHA-256 checksum, "skip if exists and checksum matches" helper, logging setup. — **Harsh** · FR-2.5, FR-2.6, NFR-9
- [x] **P2.2** Write `src/download/lulc.py`: download ESA WorldCover (AOI + 1 km buffer) via STAC, mosaic tiles if needed. — **Harsh** · FR-2.1
- [x] **P2.3** Extend `lulc.py`: download ESRI Annual LULC for the baseline and latest years. — **Harsh** · FR-2.2
- [x] **P2.4** Write `src/download/dem.py`: download Copernicus DEM GLO-30 (AOI + buffer). — **Abhinav** · FR-2.3
- [ ] **P2.5** Write `src/download/osm.py`: download roads (keep the `highway` tag), water (`natural=water`, `waterway=*`) and buildings (`building=*`) with osmnx. Save as GeoPackage. — **Abhinav** · FR-2.4
- [ ] **P2.6** If needed (from P1.6): download fallback building footprints (Microsoft / Google Open Buildings) for the AOI. — **Abhinav** · Risk 1
- [ ] **P2.7** Add retries and clear error messages to all downloaders. — **Abhinav** · FR-2.6
- [x] **P2.8** Create `notebooks/01_data_download.ipynb`: calls the download functions and shows quick-look plots of each layer over the AOI. — **Harsh** · FR-10.1
- [ ] **P2.9** Unit tests: manifest round-trip, checksum, skip-if-exists logic (with temporary files). — **Both** (Harsh: io_utils tests, Abhinav: downloader error-handling tests with mocked network)

### Phase 2 Gate

**Automated — `tests/gates/test_phase2.py`** (written by **Harsh**):
- [ ] Every expected raw file exists: WorldCover, ESRI LULC × 2 years, DEM, roads, water, buildings.
- [ ] Every raster opens with rasterio, has a CRS and nodata defined, and its bounds cover the AOI bbox.
- [ ] Every vector opens with geopandas, has a CRS, and is non-empty.
- [ ] LULC rasters contain only valid class codes (WorldCover: {10,20,…,100} + nodata; ESRI: documented codes).
- [ ] `data/manifest.json` has one entry per file, and the stored checksums match the files on disk.
- [ ] Rerunning the downloads doesn't re-download (checks file modified times).

**Manual checklist:**
- [ ] Quick-look plots in notebook 01 visually match the real area (compare with Google Maps / OSM).
- [ ] Both teammates have the full raw data locally (via download or shared drive link recorded in `docs/data_sources.md`).
- [ ] Unit tests pass: `pytest tests/unit`.

**Sign-off:** - [ ] Harsh  - [ ] Abhinav

---

## Phase 3 — Preprocessing

**Goal:** every layer is clipped, in the project CRS, aligned to one reference grid, and clean.
**Depends on:** Phase 2 gate. **Est.:** Weeks 3–4.

### Todos

- [x] **P3.1** Write `src/preprocess/raster.py`: reproject to the project CRS, clip to AOI + buffer, align to a reference grid (WorldCover at 10 m is the reference). Nearest-neighbour for categorical, bilinear for continuous. Set nodata consistently. — **Harsh** · FR-3.1–3.3
- [x] **P3.2** Write `src/preprocess/terrain.py`: slope (degrees, Horn method) and aspect from the aligned DEM. — **Harsh** · FR-3.6
- [x] **P3.3** Harmonise ESRI LULC classes with WorldCover (mapping table in `src/preprocess/raster.py` + `docs/data_sources.md`), so temporal validation uses the same "built-up" definition. — **Harsh** · FR-8.1
- [ ] **P3.4** Write `src/preprocess/vector.py`: reproject, clip, fix invalid geometries (`make_valid`), drop empties, explode multi-parts where needed. — **Abhinav** · FR-3.4
- [ ] **P3.5** Classify roads into `major` / `minor` by `highway` tag (PRD FR-3.5); drop footpaths / tracks if configured. — **Abhinav** · FR-3.5
- [ ] **P3.6** Clean buildings: remove tiny (< 10 m²) and huge outlier footprints; compute centroid, area and `building` type; dedupe fallback + OSM footprints if both are used. — **Abhinav**
- [ ] **P3.7** Create `notebooks/02_preprocessing.ipynb`: before/after plots and a table of CRS, resolution, shape and nodata % per layer. — **Abhinav** · FR-10.1
- [ ] **P3.8** Unit tests on synthetic data: reprojection keeps category values, slope of a known plane equals the expected angle, road classification mapping. — **Both** (Harsh: raster/terrain tests, Abhinav: vector tests)
- [ ] **P3.9** Visual overlay check in the notebook: roads, water and buildings drawn over LULC line up correctly (no shifts). — **Both**

### Phase 3 Gate

**Automated — `tests/gates/test_phase3.py`** (written by **Abhinav**):
- [ ] All processed rasters have **identical** CRS, transform, width and height.
- [ ] All processed rasters and vectors use the project CRS from the config.
- [ ] Processed LULC contains only valid codes (resampling didn't create new values).
- [ ] Slope values are within [0, 90] and elevation is within a plausible range for the AOI (config min/max).
- [ ] All vector geometries are valid and non-empty; roads have a `road_class` column with values in {major, minor}.
- [ ] Nodata share within the AOI is < 5 % for every raster.

**Manual checklist:**
- [ ] Overlay plot (P3.9) reviewed by both: no misalignment visible.
- [ ] Slope map looks sensible (hills steep, plains flat).
- [ ] ESRI → WorldCover class mapping documented.

**Sign-off:** - [ ] Harsh  - [ ] Abhinav

---

## Phase 4 — Grid and feature engineering

**Goal:** one feature table with a row per grid cell and all PRD §9.3 features.
**Depends on:** Phase 3 gate. **Est.:** Weeks 4–5.

### Todos

- [x] **P4.1** Write `src/features/grid.py`: square grid of `cell_size` over the AOI, with `cell_id`, row, col and centroid; keep cells whose centre is inside the AOI. — **Harsh** · FR-4.1
- [x] **P4.2** Write `src/features/lulc_features.py`: per-cell class fractions from the 10 m LULC (block aggregation on the aligned raster, not slow polygon zonal stats). For both the baseline and latest years. — **Harsh** · FR-4.2
- [x] **P4.3** Terrain features per cell: `elev_mean`, `slope_mean`, `slope_max`. — **Harsh** · FR-4.2
- [ ] **P4.4** Write `src/features/distance.py`: distance transforms (`scipy.ndimage.distance_transform_edt` with correct pixel size) for major road, any road, water and built-up; sample at cell centroids; cap and log-transform. — **Abhinav** · FR-4.2
- [ ] **P4.5** Road density within 500 m, and building count / area fraction per cell (for analysis only; flagged as leaky). — **Abhinav** · FR-4.2, FR-6.6
- [x] **P4.6** Write `src/features/context.py`: focal means at 250 m and 500 m for base features; the "surrounding ring" built-up fraction (excluding the centre cell). — **Harsh** · FR-4.3
- [ ] **P4.7** Optional: NDVI (Sentinel-2 median composite) and WorldPop density. — **Abhinav** · PRD §7.2
- [~] **P4.8** Write `src/features/build.py` to assemble everything into `data/features/grid_features.parquet` (+ `.gpkg` with geometry); log dropped cells (> 50 % nodata). Create `notebooks/03_feature_engineering.ipynb` with a map of each feature, histograms and a correlation matrix. — **Abhinav** · FR-4.4, FR-4.5
- [ ] **P4.9** Unit tests: grid cell count and area on a synthetic AOI; fractions on a synthetic raster; distance transform of a single-pixel target gives the correct metres. — **Both** (Harsh: grid/fractions/context, Abhinav: distance/density)

### Phase 4 Gate

**Automated — `tests/gates/test_phase4.py`** (written by **Harsh**):
- [ ] The feature table row count equals the number of grid cells minus logged drops; `cell_id` is unique.
- [ ] All PRD §9.3 core columns are present (list defined in `src/features/build.py`).
- [ ] For each cell, the LULC fractions sum to 1 ± 0.01.
- [ ] Distances ≥ 0; slope in [0, 90]; no infinite values; NaN share per column < 1 %.
- [ ] Leaky columns (`frac_built`, `bldg_count`, `bldg_area_frac`) are listed in a `LEAKY_FEATURES` constant.
- [ ] Spot check: a cell containing a known major road has `dist_road_major` ≤ `cell_size`.

**Manual checklist:**
- [ ] Feature maps in notebook 03 look spatially sensible (distance grows away from roads, etc.).
- [ ] Highly correlated features (|r| > 0.9) noted, with a decision on whether to drop them.
- [ ] Feature build runs in < 10 min.

**Sign-off:** - [ ] Harsh  - [ ] Abhinav

---

## Phase 5 — Land classification (clustering)

**Goal:** a three-class map (built-up / forest / usable) from clustering, evaluated and explained.
**Depends on:** Phase 4 gate. **Est.:** Weeks 5–6.

### Todos

- [ ] **P5.1** Write `src/classify/cluster.py`: feature selection, standardisation, optional PCA (≥ 90 % variance). — **Abhinav** · FR-5.1
- [ ] **P5.2** K-Means for k = 3…10: elbow (inertia) and silhouette plots; pick k with justification. — **Abhinav** · FR-5.2, FR-5.3
- [ ] **P5.3** Alternative: GMM (choose components by BIC) and/or HDBSCAN; compare with K-Means (silhouette, Davies–Bouldin, maps). — **Abhinav** · FR-5.2
- [ ] **P5.4** Write `src/classify/label.py`: rule table mapping clusters → built-up / forest / usable / excluded from centroids (PRD §9.4); thresholds in config. — **Harsh** · FR-5.4
- [ ] **P5.5** Exclusion mask: water, wetland, snow, mangroves and slope > threshold; applied after labelling. Save `outputs/exclusion_mask.tif`. — **Harsh** · FR-5.5
- [ ] **P5.6** Evaluation: confusion matrix vs WorldCover majority class (collapsed to 3), overall agreement, per-class precision/recall; centroid profile plots (radar or heatmap) to interpret clusters. — **Abhinav** · FR-5.6
- [ ] **P5.7** Export `outputs/lulc_3class.tif` and `outputs/clusters.gpkg`; create `notebooks/04_clustering.ipynb` with all plots and a written interpretation of each cluster. — **Abhinav** · PRD §13
- [ ] **P5.8** Unit tests: labelling rules on synthetic centroids; mask removes all water/steep cells; same seed gives identical labels. — **Harsh** · FR-5.7
- [ ] **P5.9** Decide on open questions Q5 (cropland) and Q6 (slope threshold); record in the PRD and config. — **Both**

### Phase 5 Gate

**Automated — `tests/gates/test_phase5.py`** (written by **Abhinav**):
- [ ] `outputs/lulc_3class.tif` is aligned with the project grid and contains only {1, 2, 3, 255}.
- [ ] Every class (built-up, forest, usable) covers ≥ 1 % of the AOI.
- [ ] **Zero** cells inside the exclusion mask are labelled usable.
- [ ] Two runs with the same seed give identical cluster labels.
- [ ] Overall agreement with collapsed WorldCover ≥ 80 % (or the test logs the value and the manual checklist requires an explanation).
- [ ] Silhouette score for the chosen k is computed and saved to `outputs/metrics/clustering.json`.

**Manual checklist:**
- [ ] The 3-class map was visually compared with satellite imagery for 5 random locations.
- [ ] Each cluster has a written description in notebook 04.
- [ ] The choice of k and algorithm is justified in writing.

**Sign-off:** - [ ] Harsh  - [ ] Abhinav

---

## Phase 6 — Building similarity

**Goal:** given building A, find similar locations B, plus an aggregate similarity score and an RF alternative for every usable cell.
**Depends on:** Phase 5 gate. **Est.:** Weeks 6–7.

### Todos

- [ ] **P6.1** Write `src/similarity/profiles.py`: context profile per location (100 / 250 / 500 m buffers, PRD §9.5), excluding leaky own-cell features; standardisation fitted on reference + candidate locations. — **Harsh** · FR-6.2, FR-6.6
- [ ] **P6.2** Build the reference building set (OSM / fallback centroids, cleaned in P3.6); optionally a stratified sample by building type and area. — **Abhinav** · FR-6.1
- [ ] **P6.3** Write `src/similarity/query.py`: single-query mode (building ID or lat/lon → top-N usable cells by cosine similarity; Euclidean as an option). Export `outputs/similarity_query_<id>.gpkg` + a map PNG showing A and B₁…Bₙ. — **Harsh** · FR-6.3, FR-6.7
- [ ] **P6.4** Write `src/similarity/aggregate.py`: kNN mean similarity of every usable cell to the reference set; rescale to [0, 1]; export `outputs/similarity_score.tif`. — **Harsh** · FR-6.4
- [ ] **P6.5** Write `src/similarity/rf_model.py`: RF built vs non-built on context features, class-balanced, **spatial block CV** (e.g. 2 km blocks); feature importance (impurity + permutation); export `outputs/rf_probability.tif`. — **Abhinav** · FR-6.5, FR-8.2
- [ ] **P6.6** Held-out building check: spatial blocks of buildings held out; report the median percentile rank of held-out locations. — **Abhinav** · FR-8.2
- [ ] **P6.7** Stretch: similarity per building type (residential / commercial / industrial), if tags allow. — **Harsh** · Q7
- [ ] **P6.8** Create `notebooks/05_similarity.ipynb`: 3–5 example queries (different building types/areas), aggregate map, RF map, feature importance, and a comparison of the three. — **Abhinav** · FR-10.1
- [ ] **P6.9** Unit tests on synthetic data: identical profiles → similarity 1; the query never returns excluded/non-usable cells; leaky features are rejected by the profile builder (raises an error). — **Both** (Harsh: profiles/query, Abhinav: RF/CV split)

### Phase 6 Gate

**Automated — `tests/gates/test_phase6.py`** (written by **Harsh**):
- [ ] **Self-query sanity:** querying an existing building returns a cell within 1 cell of its own location in the top 1 % (run with the building's own cell temporarily allowed as a candidate).
- [ ] Query results contain only usable, non-excluded cells.
- [ ] `similarity_score.tif` and `rf_probability.tif` are aligned with the grid, values in [0, 1], and NaN only outside usable land.
- [ ] No column from `LEAKY_FEATURES` appears in the profile or RF input feature list.
- [ ] Spatial CV folds have no overlapping blocks between train and test.
- [ ] RF spatial-CV ROC-AUC is saved to `outputs/metrics/similarity.json`.

**Manual checklist:**
- [ ] Example query maps make intuitive sense (matches near roads and similar terrain).
- [ ] Feature importance is discussed: which surroundings matter most?
- [ ] Aggregate vs RF maps compared and differences explained.

**Sign-off:** - [ ] Harsh  - [ ] Abhinav

---

## Phase 7 — Suitability mapping and validation

**Goal:** final suitability classes, candidate sites, MCDA baseline, and validation metrics.
**Depends on:** Phase 6 gate. **Est.:** Weeks 8–9.

### Todos

- [ ] **P7.1** Write `src/suitability/score.py`: combine the similarity and RF scores (documented weights); classify into S1/S2/S3/N (quantiles or Jenks); export `suitability_score.tif` and `suitability_class.tif`. — **Harsh** · FR-7.1, FR-7.2
- [ ] **P7.2** Candidate patches: merge adjacent S1 cells, drop patches below the minimum area, compute patch attributes; export `candidates.gpkg` + `.csv`. — **Harsh** · FR-7.4
- [ ] **P7.3** Write `src/suitability/mcda.py`: rescale criteria, AHP pairwise matrix with consistency ratio, weighted overlay; export `mcda_score.tif`. — **Abhinav** · FR-7.3
- [ ] **P7.4** Write `src/suitability/validate.py` **temporal validation**: rerun features + scores on baseline-year data only; label new-growth cells (baseline non-built → latest built); compute ROC-AUC, precision@top-10 %, and the S1+S2 hit rate. — **Harsh** · FR-8.1, FR-8.3
- [ ] **P7.5** Apply the same validation to the MCDA baseline; create a comparison table + ROC curves (data-driven vs MCDA vs random). — **Abhinav** · FR-8.3
- [ ] **P7.6** Sensitivity analysis: vary cell size (e.g. 50/100/200 m), k, and slope threshold; report how the metrics change. — **Abhinav**
- [ ] **P7.7** Write `docs/validation.md` with all metrics, figures and an honest discussion of misses. Create `notebooks/06_suitability_validation.ipynb`. — **Both** (Harsh: temporal validation, Abhinav: MCDA comparison + sensitivity)
- [ ] **P7.8** Write `src/pipeline.py`: runs stages 2→7 from the config, with a `--from-stage` option; logs timings. — **Harsh** · FR-10.2, FR-10.3
- [ ] **P7.9** Unit tests: classification thresholds produce the expected class proportions; AHP consistency ratio on a textbook matrix; the new-growth labelling on a synthetic 2-year raster. — **Abhinav**

### Phase 7 Gate

**Automated — `tests/gates/test_phase7.py`** (written by **Abhinav**):
- [ ] Suitability rasters are aligned with the grid; classes only in {1, 2, 3, 4}.
- [ ] **Zero** excluded / forest / built-up cells in S1–S3 or in `candidates.gpkg`.
- [ ] All candidate patches are ≥ the minimum area.
- [ ] AHP consistency ratio < 0.1.
- [ ] Temporal validation ROC-AUC ≥ 0.75 **or** the test is marked `xfail` with a reason referencing `docs/validation.md`.
- [ ] `outputs/metrics/validation.json` contains AUC, precision@10 % and S1+S2 hit rate for both the data-driven model and MCDA.
- [ ] `python -m src.pipeline` runs end to end (from processed data) in < 30 min.

**Manual checklist:**
- [ ] Top 10 candidate sites checked against satellite imagery: no obvious nonsense (e.g. a lake or a stadium).
- [ ] `docs/validation.md` reviewed by both teammates.
- [ ] Limitations listed (OSM completeness, LULC errors, "past ≠ good planning" assumption, etc.).

**Sign-off:** - [ ] Harsh  - [ ] Abhinav

---

## Phase 8 — Visualisation, report and presentation

**Goal:** polished outputs, report and slides; the repo is clean and reproducible.
**Depends on:** Phase 7 gate (report writing can start earlier). **Est.:** Weeks 9–10.

### Todos

- [ ] **P8.1** Write `src/viz/static_maps.py`: a consistent map style (title, legend, scale bar, north arrow, basemap) for all maps in FR-9.1; export to `outputs/figures/` at 300 dpi. — **Abhinav** · FR-9.1
- [ ] **P8.2** Charts: class-area bar charts, elbow/silhouette, centroid profiles, feature importance, ROC curves. Same style throughout. — **Abhinav** · FR-9.3
- [ ] **P8.3** Write `src/viz/interactive.py`: folium HTML with toggleable layers (LULC, 3-class, suitability, candidates, reference buildings) and popups for candidates. — **Harsh** · FR-9.2
- [ ] **P8.4** README: project summary, setup (conda), data download, how to run the pipeline and notebooks, and outputs description. — **Harsh** · D14
- [ ] **P8.5** Report sections: Introduction, Study area, Data, Literature review. — **Abhinav** · D12
- [ ] **P8.6** Report sections: Methodology (features, clustering, similarity, suitability), Validation design. — **Harsh** · D12
- [ ] **P8.7** Report sections: Results, Discussion, Limitations, Future work, Conclusion. — **Both** (Harsh: similarity + validation results; Abhinav: clustering + MCDA results)
- [ ] **P8.8** Slides (10–15): each person presents the parts they built. — **Both**
- [ ] **P8.9** Code clean-up: remove dead code, check docstrings/type hints, `ruff` + `black` clean. — **Harsh** (`src/download`, `preprocess`, `similarity`, `suitability/score+validate`, `pipeline`) · NFR-4
- [ ] **P8.10** Code clean-up for the remaining modules (`features/distance`, `classify`, `suitability/mcda`, `viz/static_maps`). — **Abhinav** · NFR-4
- [ ] **P8.11** Fresh-clone reproducibility test: the teammate who did **not** set up the env last clones the repo into a new folder, creates the env, downloads data, runs the pipeline and all notebooks, and records issues. — **Abhinav** · NFR-1
- [ ] **P8.12** Fix any issues found in P8.11. — **Harsh**
- [ ] **P8.13** Final PRD update: mark requirements met / not met; close open questions. — **Both**

### Phase 8 Gate (final)

**Automated — `tests/gates/test_phase8.py`** (written by **Harsh**):
- [ ] All deliverable files D1–D14 from PRD §6 exist.
- [ ] All figures listed in FR-9.1 / FR-9.3 exist in `outputs/figures/` and are ≥ 300 dpi.
- [ ] `outputs/map.html` exists and contains all required layer names.
- [ ] `ruff check .` and `black --check .` exit 0.
- [ ] No notebook in the repo has stored outputs (nbstripout check).
- [ ] The **full test suite passes**: `pytest` (unit + all gates 0–7).

**Manual checklist:**
- [ ] Fresh-clone test (P8.11) passed with no manual fixes.
- [ ] Report proofread by both; every figure is referenced in the text; references are formatted.
- [ ] Slides rehearsed once with timing.
- [ ] No Claude / AI co-author lines in the git history (`git log --format=%B | grep -i co-authored` returns nothing).
- [ ] Final commit tagged `v1.0` and pushed.

**Sign-off:** - [ ] Harsh  - [ ] Abhinav

---

## Definition of Done (whole project)

- [ ] All phase gates 0–8 passed and signed off.
- [ ] All deliverables D1–D14 complete.
- [ ] Validation metrics reported, and misses explained.
- [ ] Report and slides submitted.

---

## Change log

| Date | Change | By |
|---|---|---|
| 2026-09-27 | Initial PRD and task breakdown | Harsh |
