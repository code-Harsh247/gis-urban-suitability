"""Download the Copernicus DEM GLO-30 for the AOI + buffer (PRD FR-2.3).

Run: python -m src.download.dem [--force]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rasterio.enums import Resampling

from src.config import load_config
from src.download.stac import fetch_raster
from src.io_utils import setup_logging

DEM_COLLECTION = "cop-dem-glo-30"
DEM_NODATA = -32767.0


def dem_path(cfg) -> Path:
    return Path(cfg.paths["data_raw"]) / "dem" / "copdem_glo30.tif"


def download_dem(cfg, force: bool = False) -> Path:
    """Copernicus DEM GLO-30 mosaic (bilinear if tiles need warping)."""
    return fetch_raster(
        cfg,
        collection=DEM_COLLECTION,
        asset="data",
        out=dem_path(cfg),
        dataset="copernicus-dem-glo-30",
        resampling=Resampling.bilinear,
        nodata=DEM_NODATA,
        force=force,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="download even if the file exists")
    args = parser.parse_args(argv)
    cfg = load_config()
    setup_logging(cfg, "download")
    download_dem(cfg, force=args.force)


if __name__ == "__main__":
    main()
