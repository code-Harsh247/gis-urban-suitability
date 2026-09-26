# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**GIS-Based Land Suitability Analysis for Urban Development Using Land Use Land Cover (LULC)** — a term project.

Goal: produce a map of land suitable for new urban development, using LULC data plus supporting layers (terrain, roads, water), with the whole analysis done in Python (not QGIS).

Study area: **TBD** — the choice decides which LULC datasets have coverage.

Team: Harsh and Abhinav.

## Key docs

- [PRD.md](PRD.md) — full requirements, methodology, data, validation design. Source of truth for *what* to build.
- [Tasks.md](Tasks.md) — phased task list with owners and phase gate checks. Tick tasks off in the same change that completes them, and don't start a phase before the previous phase's gate passes.

## Tasks (from project meeting)

1. **LULC data + literature** — find an LULC dataset covering the study area; review papers that use LULC for land suitability / urban development.
2. **Land classification** — use clustering to group land into three classes: **built-up**, **forest**, **usable/potential land**.
3. **Building similarity** — take an existing building at location A, describe its surroundings (terrain, road/water access, nearby land cover, built-up density), and find locations B in usable land with similar characteristics.
4. **Python only** — all data handling, analysis and mapping in Python.

## Data sources

- LULC: ESA WorldCover (10 m), Dynamic World (10 m), ESRI 10 m Annual LULC; Bhuvan/NRSC for India
- Built-up: GHSL; building footprints and roads from OpenStreetMap
- Terrain: SRTM or Copernicus DEM (elevation, slope)
- Optional: Sentinel-2 (NDVI), WorldPop (population)

## Method outline

- Split the study area into a regular grid; per cell compute: LULC class fractions, elevation, slope, distance to roads / water / built-up, built-up density, NDVI.
- Clustering: K-Means (baseline), GMM or HDBSCAN; choose k with elbow + silhouette; map clusters to the three classes.
- Similarity: context profiles in 100 / 250 / 500 m buffers around existing buildings; score candidate cells by cosine / Euclidean similarity, or use a random-forest built vs non-built probability. Exclude forest, water and steep cells.
- Validation: hold out some existing buildings and check they rank highly.

## Stack

rasterio, geopandas, shapely, pyproj, pystac-client + planetary-computer, osmnx, richdem, scipy, scikit-learn, matplotlib, folium / leafmap.

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
