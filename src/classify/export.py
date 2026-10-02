"""Export the 3-class map (contract C7) as a GeoTIFF and a GeoPackage (PRD §13; Tasks P5.7).

- ``outputs/lulc_3class.tif``: one pixel per 100 m grid cell, on the cell lattice (same
  origin as the 10 m reference grid, so it overlays every processed raster exactly).
  uint8 values 1 built-up, 2 forest, 3 usable, 255 excluded; 0 = outside the AOI (nodata);
- ``outputs/clusters.gpkg``: cell squares with ``cluster_id``, ``class_3`` and the class name.

Run: python -m src.classify.export [--c7 path]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from affine import Affine

from src.classify.evaluate import NAMES
from src.config import load_config
from src.features import schema
from src.features.grid import Lattice, grid_geodataframe, lattice
from src.io_utils import setup_logging

log = logging.getLogger(__name__)

NODATA = 0


def lattice_transform(lat: Lattice) -> Affine:
    return Affine(lat.cell_m, 0.0, lat.left, 0.0, -lat.cell_m, lat.top)


def class_raster_path(cfg) -> Path:
    return Path(cfg.paths["outputs"]) / "lulc_3class.tif"


def clusters_gpkg_path(cfg) -> Path:
    return Path(cfg.paths["outputs"]) / "clusters.gpkg"


def class_image(cfg, c7: pd.DataFrame) -> np.ndarray:
    lat = lattice(cfg)
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    g = grid.merge(c7[["cell_id", "class_3"]], on="cell_id", how="left", validate="1:1")
    if g["class_3"].isna().any():
        raise ValueError(f"{int(g['class_3'].isna().sum())} grid cells have no class in C7")
    img = np.full(lat.shape, NODATA, dtype="uint8")
    img[g["row"].to_numpy(), g["col"].to_numpy()] = g["class_3"].to_numpy().astype("uint8")
    return img


def write_class_raster(cfg, c7: pd.DataFrame, path: Path | None = None) -> Path:
    path = Path(path or class_raster_path(cfg))
    img = class_image(cfg, c7)
    profile = {
        "driver": "GTiff", "height": img.shape[0], "width": img.shape[1], "count": 1,
        "dtype": "uint8", "crs": cfg.crs, "transform": lattice_transform(lattice(cfg)),
        "nodata": NODATA, "compress": "deflate",
    }  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(img, 1)
        ds.update_tags(1, **{str(k): v for k, v in NAMES.items()})
    return path


def write_clusters_gpkg(cfg, c7: pd.DataFrame, path: Path | None = None) -> Path:
    path = Path(path or clusters_gpkg_path(cfg))
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    g = grid.merge(
        c7[["cell_id", "cluster_id", "class_3"]], on="cell_id", how="inner", validate="1:1"
    )
    g["class_name"] = g["class_3"].map(NAMES)
    path.parent.mkdir(parents=True, exist_ok=True)
    grid_geodataframe(g, cfg).to_file(path, driver="GPKG")
    return path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c7", help="C7 file (default: the contract path)")
    args = parser.parse_args(argv)
    cfg = load_config()
    setup_logging(cfg, "classify")
    c7 = schema.read_contract(Path(args.c7) if args.c7 else schema.contract_path(cfg, "C7"), "C7")
    log.info("wrote %s", write_class_raster(cfg, c7))
    log.info("wrote %s", write_clusters_gpkg(cfg, c7))


if __name__ == "__main__":
    main()
