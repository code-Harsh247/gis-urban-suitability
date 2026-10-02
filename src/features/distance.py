"""Vector features per cell (contract C3) from the cleaned OSM layers (FR-4.2; Tasks P4.4, P4.5).

For each OSM snapshot (``2018`` and ``current``):

- ``log_dist_major`` / ``log_dist_any``: log1p of the exact distance (m) from the cell
  centre to the nearest major / any road line, capped at ``features.distance_cap_m``
  (STRtree nearest-neighbour on the line geometries, so no rasterisation error);
- ``road_density``: road length (km) within ``features.road_density_radius_m`` of the
  cell, per km². Lines are cut into pieces of at most 5 m; each piece's length goes to
  the cell holding its midpoint, then lengths are summed over the disk of cells whose
  centres lie within the radius;
- ``bldg_count``, ``bldg_area_frac``: buildings whose centroid lies in the cell, and
  their footprint area / cell area (capped at 1). These are **leaky** (they encode
  whether the cell is built) and are only for analysis (schema.LEAKY_FEATURES).

Distances and density use every road in the reference grid (AOI + buffer); the buffer
equals the distance cap, so cells at the AOI edge see all roads that matter.

Run: python -m src.features.distance [--snapshot 2018|current]
"""

from __future__ import annotations

import argparse
import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy import ndimage as ndi

from src.config import load_config
from src.download.osm import snapshots
from src.features import schema
from src.features.grid import Lattice, build_grid, lattice
from src.io_utils import setup_logging
from src.preprocess.vector import processed_osm_path

log = logging.getLogger(__name__)

SEGMENT_M = 5.0  # max piece length when assigning road length to cells


def nearest_line_distance(lines, xs: np.ndarray, ys: np.ndarray, cap_m: float) -> np.ndarray:
    """Exact distance (m) from each point to the nearest line, capped at ``cap_m``."""
    geoms = np.asarray(lines)
    out = np.full(len(xs), cap_m, dtype="float64")
    if len(geoms) == 0:
        return out
    tree = shapely.STRtree(geoms)
    pts = shapely.points(xs, ys)
    (pi, _), dist = tree.query_nearest(
        pts, max_distance=cap_m, return_distance=True, all_matches=False
    )
    out[pi] = np.minimum(dist, cap_m)
    return out


def road_length_per_cell(lines, lat: Lattice) -> np.ndarray:
    """Road length (m) per lattice cell, from pieces of at most SEGMENT_M metres."""
    geoms = np.asarray(lines)
    total = np.zeros(lat.shape, dtype="float64")
    if len(geoms) == 0:
        return total
    lengths = shapely.length(geoms)
    n = np.maximum(1, np.ceil(lengths / SEGMENT_M).astype(np.int64))
    owner = np.repeat(np.arange(len(geoms)), n)
    k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)  # piece index within its line
    frac = (k + 0.5) / n[owner]  # midpoint of each piece, as a fraction of the line
    mids = shapely.line_interpolate_point(geoms[owner], frac, normalized=True)
    x, y = shapely.get_x(mids), shapely.get_y(mids)
    w = lengths[owner] / n[owner]
    row, col = lat.xy_to_rowcol(x, y)
    ok = (row >= 0) & (row < lat.shape[0]) & (col >= 0) & (col < lat.shape[1])
    np.add.at(total, (row[ok], col[ok]), w[ok])
    return total


def disk_kernel(radius_m: float, cell_m: float) -> np.ndarray:
    n = int(np.floor(radius_m / cell_m))
    i, j = np.mgrid[-n : n + 1, -n : n + 1]
    return (np.hypot(i, j) * cell_m <= radius_m + 1e-9).astype("float64")


def road_density(length_m: np.ndarray, radius_m: float, cell_m: float) -> np.ndarray:
    """km of road per km² within ``radius_m`` (disk of cells; only cells on the lattice count)."""
    k = disk_kernel(radius_m, cell_m)
    km = ndi.convolve(length_m, k, mode="constant", cval=0.0) / 1000.0
    n_cells = ndi.convolve(np.ones_like(length_m), k, mode="constant", cval=0.0)
    area_km2 = n_cells * (cell_m / 1000.0) ** 2
    return np.clip(km / area_km2, 0.0, None)


def vector_features(cfg, snapshot: str) -> pd.DataFrame:
    """C3 for one OSM snapshot: one row per analysis grid cell."""
    lat = lattice(cfg)
    grid = build_grid(cfg)
    cap = float(cfg["features"]["distance_cap_m"])
    roads = gpd.read_file(processed_osm_path(cfg, snapshot, "roads"))
    if roads.crs != cfg.crs:
        raise ValueError(f"{snapshot} roads are in {roads.crs}, expected {cfg.crs}")
    xs, ys = grid["x"].to_numpy(), grid["y"].to_numpy()
    major = roads.loc[roads["road_class"] == "major"].geometry.values
    d_major = nearest_line_distance(major, xs, ys, cap)
    d_any = nearest_line_distance(roads.geometry.values, xs, ys, cap)

    dens = road_density(
        road_length_per_cell(roads.geometry.values, lat),
        float(cfg["features"]["road_density_radius_m"]),
        lat.cell_m,
    )

    b = gpd.read_file(
        processed_osm_path(cfg, snapshot, "buildings"),
        columns=["cell_id", "area_m2"],
        ignore_geometry=True,
    )
    per_cell = b.loc[b["cell_id"] >= 0].groupby("cell_id")["area_m2"].agg(["count", "sum"])
    counts = per_cell["count"].reindex(grid["cell_id"]).fillna(0).astype("int64").to_numpy()
    area = per_cell["sum"].reindex(grid["cell_id"]).fillna(0.0).to_numpy()

    df = pd.DataFrame(
        {
            "cell_id": grid["cell_id"].to_numpy(),
            "log_dist_major": np.log1p(d_major),
            "log_dist_any": np.log1p(d_any),
            "road_density": dens[grid["row"], grid["col"]],
            "bldg_count": counts,
            "bldg_area_frac": np.clip(area / lat.cell_m**2, 0.0, 1.0),
        }
    )
    schema.validate_frame(df, "C3")
    return df


def write_vector_features(cfg, only: list[str] | None = None) -> dict[str, pd.DataFrame]:
    out = {}
    for snap in only or list(snapshots(cfg)):
        df = vector_features(cfg, snap)
        path = schema.contract_path(cfg, "C3", snapshot=snap)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        log.info(
            "wrote %s: %d cells, median dist major %.0f m / any %.0f m, median density %.1f km/km²",
            path.name, len(df), np.expm1(df["log_dist_major"]).median(),
            np.expm1(df["log_dist_any"]).median(), df["road_density"].median(),
        )  # fmt: skip
        out[snap] = df
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="append", help="2018 or current (default: both)")
    args = parser.parse_args(argv)
    cfg = load_config()
    setup_logging(cfg, "features")
    write_vector_features(cfg, args.snapshot)


if __name__ == "__main__":
    main()
