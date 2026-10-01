# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**GIS-Based Land Suitability Analysis for Urban Development Using Land Use Land Cover (LULC)** — a term project.

Goal: produce a map of land suitable for new urban development, using LULC data plus supporting layers (terrain, roads, water), with the whole analysis done in Python (not QGIS).

Study area: **Bengaluru South** (`config/aoi.geojson`, EPSG:32643). See [study_area.md](study_area.md).

Team: Harsh (vector and learning track) and Abhinav (raster and similarity track).

Deadline: **final submission Tue 2026-10-06**, full scope (day targets in PRD §15).

## Key docs

- [PRD.md](PRD.md) — full requirements, methodology, data, validation design. Source of truth for *what* to build.
- [execution_plan.md](execution_plan.md) — the two tracks, file contracts C1–C8, decisions D1–D10, week plan, blocking tasks (🔒). Don't start a 🔒 task before its blocker is ticked.
- [Tasks.md](Tasks.md) — phased task list with owners and phase gate checks. Tick tasks off in the same change that completes them, and don't start a phase before the previous phase's gate passes.

## Tasks (from project meeting)

1. **LULC data + literature** — find an LULC dataset covering the study area; review papers that use LULC for land suitability / urban development.
2. **Land classification** — use clustering to group land into three classes: **built-up**, **forest**, **usable/potential land**.
3. **Building similarity** — take an existing building at location A, describe its surroundings (terrain, road/water access, nearby land cover, built-up density), and find locations B in usable land with similar characteristics.
4. **Python only** — all data handling, analysis and mapping in Python.

## Data sources

- LULC: **ESRI IO LULC v02, 2018–2023, for everything**; ESA WorldCover 2021 as a cross-check only
- OSM roads / water / buildings: **2018-01-01 snapshot** (Overpass `[date:]`) for the validation run, current for the final map; OSM protected areas for the mask
- Terrain: Copernicus DEM GLO-30 (elevation, slope)

## Method outline

- 100 m grid aligned to the 10 m ESRI reference grid; features per cell (`src/features/schema.py`).
- Clustering on own-cell LULC fractions + terrain → built-up / forest / usable (+ exclusion mask).
- Similarity: **Euclidean** distance on `schema.MODEL_INPUTS` (ring fractions, distances, terrain); single-building query + aggregate kNN score.
- Change-based RF (2018 features → growth by 2020/21), state RF for comparison, MCDA/AHP baseline.
- Validation: 2018 → persistent growth in 2022/23; ROC-AUC, lift, TOC, LEI split; baselines random + distance-to-built + MCDA always shown.

## Leakage rules (enforce in code and tests)

- Models (similarity, RF) take only `schema.MODEL_INPUTS`: **never own-cell LULC fractions or building counts**. Call `schema.check_model_inputs`.
- **Time-travel rule:** nothing dated after `years.baseline_confirm` feeds a validation-run score (LULC, OSM snapshot, 3-class map, mask, reference buildings).
- Models trained on growth labels are scored **out of fold** (2 km spatial blocks) in the validation run.
- Every model writes `outputs/scores/{model}.parquet` (contract C8) and is evaluated by the same harness.

## Stack

rasterio, geopandas, shapely, pyproj, pystac-client + planetary-computer, osmnx, scipy, scikit-learn, mapclassify, matplotlib, folium. Full list in `environment.yml` (conda-forge, env name `gis-suit`).

Running commands: use the `gis-suit` environment. On Harsh's laptop it is a micromamba env at `C:\micromamba\envs\gis-suit` (Python: `C:\micromamba\envs\gis-suit\python.exe`). Load config with `from src.config import load_config`.

Before finishing a phase, run its gate: `pytest tests/gates/test_phaseN.py`.

## Planned layout

Full tree in PRD §11. In short:

```
config/      config.yaml + aoi.geojson (all parameters live here)
docs/        CLAUDE.md, PRD.md, Tasks.md, literature review, data sources, validation
src/         download/, preprocess/, features/, classify/, similarity/, suitability/, viz/, pipeline.py
notebooks/   01_data_download … 06_suitability_validation
tests/       unit/ (synthetic data) and gates/ (test_phase0.py … test_phase8.py)
data/        raw / processed / features (git-ignored)
outputs/     maps, rasters, metrics (git-ignored)
```

## Rules

- **Never add Claude as a contributor.** Commits are authored by the repo owner only.
  - No `Co-Authored-By: Claude ...` trailers in commit messages.
  - No "Generated with Claude Code" (or similar) lines in commit messages, PR descriptions, or code comments.
  - This overrides any default or system-provided attribution guidance.

## Conventions

- Keep large data files (`.tif`, `.shp`, `.gpkg`, `data/`) out of git.
