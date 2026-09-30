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

rasterio, geopandas, shapely, pyproj, pystac-client + planetary-computer, osmnx, scipy, scikit-learn, mapclassify, matplotlib, folium. Full list in `environment.yml` (conda-forge, env name `gis-suit`).

Running commands: use the `gis-suit` environment. On Harsh's laptop it is a micromamba env at `C:\micromamba\envs\gis-suit` (Python: `C:\micromamba\envs\gis-suit\python.exe`). Load config with `from src.config import load_config`.

Before finishing a phase, run its gate: `pytest tests/gates/test_phaseN.py`, then the done check below.

## Done check (after every work package / phase)

A package is **not done** when the code runs. After finishing it, and before ticking it or committing, check that everything is in order:

1. **Tests:** `pytest tests` passes (unit tests + every gate up to the current phase).
2. **Lint:** `git add` the new files first, then `pre-commit run --all-files` passes (it skips files git doesn't track yet).
3. **Contracts:** real output files pass `schema.validate_project(load_config())` (also run by `tests/unit/test_contracts.py`).
4. **Correctness of the data, checked independently.** "It ran" is not enough. Compare outputs against something the code did not produce:
   - the source data (e.g. pixel values at random points);
   - grid/CRS alignment between layers;
   - value ranges and nodata share;
   - known landmarks (look up coordinates, don't guess);
   - agreement with a second dataset;
   - a visual quick-look.

   Keep the check as a rerunnable script in `scripts/verify_*.py`.
5. **Reproducible:** a rerun skips or reproduces the same outputs (same seed, same files).
6. **Record:**
   - tick the tasks in `docs/execution_plan.md` and `docs/Tasks.md`;
   - write any surprises or caveats next to the affected task;
   - commit the package on its own (message starts with its ID, e.g. `A2: ...`) and push to `main`.

If a check fails, fix it (with a regression test) as a separate commit before moving on.

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
