# GIS-Based Land Suitability Analysis for Urban Development

Term project: using Land Use Land Cover (LULC) data to find land suitable for urban development, done in Python.

- Requirements and method: [docs/PRD.md](docs/PRD.md)
- Task tracker (phases, owners, gate checks): [docs/Tasks.md](docs/Tasks.md)

## Setup

The environment uses **conda-forge** packages (reliable GDAL/rasterio on Windows). Use any conda-compatible tool: Miniforge/conda, mamba, or micromamba.

```bash
git clone https://github.com/code-Harsh247/gis-urban-suitability.git
cd gis-urban-suitability

# conda / mamba
conda env create -f environment.yml
conda activate gis-suit

# or micromamba
micromamba create -f environment.yml
micromamba activate gis-suit
```

Then, inside the activated environment:

```bash
pre-commit install              # black, ruff, nbstripout, large-file check on every commit
python scripts/check_env.py     # verify all libraries import
pytest tests/unit               # unit tests
pytest tests/gates/test_phase0.py
```

To update the environment after `environment.yml` changes: `conda env update -f environment.yml --prune` (or `micromamba update -f environment.yml`).

## Configuration

All parameters live in [config/config.yaml](config/config.yaml). The study area polygon goes in `config/aoi.geojson` (one polygon, EPSG:4326). The processing CRS defaults to the UTM zone of the AOI (`crs.epsg: auto`).

```python
from src.config import load_config
cfg = load_config()
cfg.crs, cfg.cell_size_m, cfg.aoi_area_km2
```

## Layout

```
config/      config.yaml + aoi.geojson
docs/        PRD, Tasks, literature review, data sources, validation
src/         pipeline code (download, preprocess, features, classify, similarity, suitability, viz)
notebooks/   one notebook per stage
tests/       unit/ and gates/ (phase gate checks)
scripts/     helper scripts (environment check, pre-commit hooks)
data/        downloaded and derived data (git-ignored)
outputs/     maps, rasters, metrics (git-ignored)
```
