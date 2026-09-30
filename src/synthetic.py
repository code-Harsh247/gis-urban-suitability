"""Synthetic project: stub versions of every contract file (docs/execution_plan.md §4).

Builds a small fake city on an n × n grid of 100 m cells: a built-up core that grows
year by year, a forest block, a lake, a steep hill, roads, buildings, labels and two
baseline scores. The fields are consistent with each other (e.g. distance to built-up
really does predict growth), so models and the validation harness behave sensibly on
the stubs while the real data is not ready.

Usage:
    from src.synthetic import make_synthetic_project
    cfg = make_synthetic_project(tmp_path)          # writes config, AOI and C1–C8
    df = pd.read_parquet(schema.contract_path(cfg, "C4", year=2018))
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from pyproj import CRS, Transformer
from scipy import ndimage as ndi
from shapely.geometry import box

from src.config import DEFAULT_CONFIG_PATH, Config, load_config, utm_epsg_for
from src.features import schema

CELL_M = 100.0
# Radius (in cells) of the built-up core per year: slow, then a spurt after 2019
CORE_RADIUS = {2018: 5.0, 2019: 5.2, 2020: 6.0, 2021: 6.5, 2022: 7.0, 2023: 7.5}
LON0, LAT0 = 77.60, 12.80  # south-west corner (Bengaluru South area)


def _ring(frac: np.ndarray, radius_m: float) -> np.ndarray:
    """Mean of a square window of the given radius, excluding the centre cell."""
    r = int(round(radius_m / CELL_M))
    k = 2 * r + 1
    total = ndi.uniform_filter(frac, k, mode="nearest") * k * k
    return (total - frac) / (k * k - 1)


def _log_dist(mask: np.ndarray) -> np.ndarray:
    """log1p of the distance (m) from each cell to the nearest True cell."""
    if not mask.any():
        return np.full(mask.shape, np.log1p(5000.0))
    return np.log1p(ndi.distance_transform_edt(~mask) * CELL_M)


class _City:
    """The fake city: land cover per year, terrain, roads."""

    def __init__(self, n: int, seed: int) -> None:
        self.n = n
        rng = np.random.default_rng(seed)
        self.rng = rng
        r, c = np.indices((n, n))
        self.r, self.c = r, c
        self.cy, self.cx = n * 0.3, n * 0.35
        self.d = np.hypot(r - self.cy, c - self.cx)
        self.noise = rng.normal(0, 0.03, (n, n))
        self.lake = (r >= 2) & (r <= 4) & (c >= n - 5) & (c <= n - 3)
        self.forest = (r >= int(0.6 * n)) & (c >= int(0.6 * n))
        self.hill = (r >= int(0.75 * n)) & (c <= 2)
        self.blob = (np.abs(r - int(0.8 * n)) <= 1) & (np.abs(c - int(0.45 * n)) <= 1)
        self.elev = 880 + 3 * c + 2 * r + rng.normal(0, 1, (n, n))
        slope = 3 + np.abs(rng.normal(0, 1, (n, n)))
        slope[self.forest] = 10 + np.abs(rng.normal(0, 1, self.forest.sum()))
        slope[self.hill] = 20.0
        self.slope = slope
        self.major_row = int(round(self.cy))

    def fracs(self, year: int) -> dict[str, np.ndarray]:
        """Own-cell class fractions for a year; they sum to 1."""
        radius = CORE_RADIUS[year]
        built = np.clip(0.5 + (radius - self.d) * 1.5 + self.noise, 0, 1)
        built[built < 0.05] = 0.0
        if year >= 2022:
            built = np.maximum(built, 0.8 * self.blob)
        built[self.lake] = 0.0
        rest = 1 - built
        water = np.where(self.lake, np.minimum(0.9, rest), 0.0)
        rest = rest - water
        tree = np.where(self.forest, np.minimum(0.8, rest), 0.05 * rest)
        rest = rest - tree
        out = {k: np.zeros_like(built) for k in schema.OWN_FRACTION_CLASSES}
        out.update(
            built=built,
            water=water,
            tree=tree,
            crop=0.5 * rest,
            range=0.35 * rest,
            bare=0.15 * rest,
        )
        return out

    def roads(self, snapshot: str) -> tuple[np.ndarray, np.ndarray]:
        """(major, any) road masks; the current snapshot has more minor roads."""
        major = np.zeros((self.n, self.n), bool)
        major[self.major_row, :] = True
        year = 2018 if snapshot != "current" else 2023
        built = self.fracs(year)["built"] >= 0.3
        minor = built & ((self.r % 4 == 0) | (self.c % 4 == 0))
        return major, major | minor


def _raster_features(city: _City, year: int) -> pd.DataFrame:
    f = city.fracs(year)
    cols = {f"frac_{k}": v for k, v in f.items()}
    for rad in schema.RING_RADII_M:
        for cls in schema.RING_CLASSES:
            cols[f"ring{rad}_{cls}"] = np.clip(_ring(f[cls], rad), 0, 1)
    cols.update(
        elev_mean=city.elev,
        slope_mean=city.slope,
        slope_max=np.clip(city.slope * 1.5, 0, 90),
        log_dist_built=_log_dist(f["built"] >= 0.5),
        log_dist_water=_log_dist(f["water"] >= 0.5),
        nodata_frac=np.zeros_like(city.elev),
    )
    df = pd.DataFrame({k: np.asarray(v, float).ravel() for k, v in cols.items()})
    df.insert(0, "cell_id", np.arange(city.n * city.n, dtype="int64"))
    return df


def _vector_features(city: _City, snapshot: str, buildings: gpd.GeoDataFrame) -> pd.DataFrame:
    major, anyroad = city.roads(snapshot)
    k = 11  # ~500 m window
    road_km = ndi.uniform_filter(anyroad.astype(float), k, mode="constant") * k * k * CELL_M / 1000
    density = np.clip(road_km / ((k * CELL_M / 1000) ** 2), 0, None)  # filter can round below 0
    n_cells = city.n * city.n
    counts = np.bincount(buildings["cell_id"], minlength=n_cells)
    area = np.bincount(buildings["cell_id"], weights=buildings["area_m2"], minlength=n_cells)
    return pd.DataFrame(
        {
            "cell_id": np.arange(n_cells, dtype="int64"),
            "log_dist_major": _log_dist(major).ravel(),
            "log_dist_any": _log_dist(anyroad).ravel(),
            "road_density": density.ravel(),
            "bldg_count": counts.astype("int64"),
            "bldg_area_frac": np.clip(area / CELL_M**2, 0, 1),
        }
    )


def _buildings(city: _City, year: int, x0: float, y_top: float, crs: CRS) -> gpd.GeoDataFrame:
    built = city.fracs(year)["built"]
    rng = np.random.default_rng(year)
    rows = []
    for (i, j), b in np.ndenumerate(built):
        for _ in range(int(b * 4)):
            ox, oy = rng.uniform(5, 85, 2)
            x = x0 + j * CELL_M + ox
            y = y_top - (i + 1) * CELL_M + oy
            rows.append(
                {
                    "area_m2": 100.0,
                    "building_type": str(
                        rng.choice(["residential", "commercial", "industrial", "yes"])
                    ),
                    "cell_id": i * city.n + j,
                    "geometry": box(x, y, x + 10, y + 10),
                }
            )
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)
    gdf.insert(0, "bldg_id", np.arange(len(gdf), dtype="int64"))
    gdf["cell_id"] = gdf["cell_id"].astype("int64")
    return gdf


def _labels(city: _City, cfg: Config) -> pd.DataFrame:
    y = cfg["years"]
    b = {yr: city.fracs(yr)["built"] for yr in range(2018, 2024)}
    ex_codes_water = city.fracs(y["baseline"])["water"] > 0.5
    excluded = ex_codes_water | (city.slope > cfg["exclusion"]["slope_max_deg"])
    lo, hi = cfg["growth"]["nonbuilt_max"], cfg["growth"]["built_min"]
    nb = b[y["baseline"]] < lo
    nb &= b[y["baseline_confirm"]] < lo
    candidate = nb & ~excluded
    grew = candidate & (b[y["latest"]] >= hi) & (b[y["latest_confirm"]] >= hi)
    t0, t1 = y["change_train_end"]
    chg = candidate & (b[t0] >= hi) & (b[t1] >= hi)
    near_old = ndi.maximum_filter(b[y["baseline"]] >= hi, 7)  # within ~300 m of old built-up
    lei = np.where(grew, np.where(near_old, "adjacent", "outlying"), "none")
    return pd.DataFrame(
        {
            "cell_id": np.arange(city.n * city.n, dtype="int64"),
            "excluded": excluded.ravel(),
            "built_baseline": (b[y["baseline"]] >= hi).ravel(),
            "candidate": candidate.ravel(),
            "grew": grew.ravel(),
            "chg_train_pos": chg.ravel(),
            "lei_type": lei.ravel().astype(object),
        }
    )


def _write_score(
    cfg: Config, model: str, cell_id: np.ndarray, score: np.ndarray, meta: dict
) -> None:
    path = schema.contract_path(cfg, "C8", model=model)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"cell_id": cell_id, "score": score.astype(float)}).to_parquet(path, index=False)
    schema.score_meta_path(cfg, model).write_text(json.dumps({"model": model, **meta}, indent=2))


def make_synthetic_project(root: Path, n: int = 20, seed: int = 0) -> Config:
    """Write config, AOI and stub files for every contract under ``root``; return the config."""
    root = Path(root)
    (root / "config").mkdir(parents=True, exist_ok=True)
    utm = CRS.from_epsg(utm_epsg_for(LON0, LAT0))
    to_utm = Transformer.from_crs(4326, utm, always_xy=True)
    to_ll = Transformer.from_crs(utm, 4326, always_xy=True)
    x0, y0 = (np.floor(v / CELL_M) * CELL_M for v in to_utm.transform(LON0, LAT0))
    y_top = y0 + n * CELL_M
    ring = [(x0, y0), (x0 + n * CELL_M, y0), (x0 + n * CELL_M, y_top), (x0, y_top), (x0, y0)]
    aoi = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "synthetic"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[list(to_ll.transform(x, y)) for x, y in ring]],
                },
            }
        ],
    }
    (root / "config" / "aoi.geojson").write_text(json.dumps(aoi), encoding="utf-8")
    raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    raw["aoi"].update(path="config/aoi.geojson", name="synthetic")
    (root / "config" / "config.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    cfg = load_config(root / "config" / "config.yaml")
    cfg.ensure_dirs()

    city = _City(n, seed)
    rows, cols = np.indices((n, n))
    grid = pd.DataFrame(
        {
            "cell_id": np.arange(n * n, dtype="int64"),
            "row": rows.ravel().astype("int64"),
            "col": cols.ravel().astype("int64"),
            "x": x0 + (cols.ravel() + 0.5) * CELL_M,
            "y": y_top - (rows.ravel() + 0.5) * CELL_M,
        }
    )
    grid.to_parquet(schema.contract_path(cfg, "C1"), index=False)

    years = cfg["years"]
    snap_base = schema.vector_snapshot_for(cfg, years["baseline"])
    bldgs = {
        snap_base: _buildings(city, years["baseline"], x0, y_top, cfg.crs),
        "current": _buildings(city, years["latest"], x0, y_top, cfg.crs),
    }
    for snap, gdf in bldgs.items():
        gdf.to_file(schema.contract_path(cfg, "C6", snapshot=snap), driver="GPKG")
        _vector_features(city, snap, gdf).to_parquet(
            schema.contract_path(cfg, "C3", snapshot=snap), index=False
        )

    for year in (years["baseline"], years["latest"]):
        rf = _raster_features(city, year)
        rf.to_parquet(schema.contract_path(cfg, "C2", year=year), index=False)
        vf = pd.read_parquet(
            schema.contract_path(cfg, "C3", snapshot=schema.vector_snapshot_for(cfg, year))
        )
        rf.merge(vf, on="cell_id").to_parquet(
            schema.contract_path(cfg, "C4", year=year), index=False
        )

    labels = _labels(city, cfg)
    labels.to_parquet(schema.contract_path(cfg, "C5"), index=False)

    latest = city.fracs(years["latest"])
    cls = np.where(
        latest["built"] >= cfg["labeling"]["built_threshold"],
        schema.CLASS_BUILT,
        np.where(
            latest["tree"] >= cfg["labeling"]["forest_threshold"],
            schema.CLASS_FOREST,
            schema.CLASS_USABLE,
        ),
    ).ravel()
    cls[labels["excluded"].to_numpy()] = schema.CLASS_EXCLUDED
    cluster = np.where(cls == schema.CLASS_EXCLUDED, -1, cls - 1)
    pd.DataFrame(
        {
            "cell_id": grid["cell_id"],
            "cluster_id": cluster.astype("int64"),
            "class_3": cls.astype("uint8"),
        }
    ).to_parquet(schema.contract_path(cfg, "C7"), index=False)

    base = pd.read_parquet(schema.contract_path(cfg, "C4", year=years["baseline"]))
    _write_score(
        cfg,
        "random",
        grid["cell_id"].to_numpy(),
        np.random.default_rng(seed).random(n * n),
        {"features": [], "train_years": [], "description": "uniform random baseline (stub)"},
    )
    _write_score(
        cfg,
        "dist_built",
        base["cell_id"].to_numpy(),
        -base["log_dist_built"].to_numpy(),
        {
            "features": ["log_dist_built"],
            "train_years": [years["baseline"]],
            "description": "closer to baseline built-up = higher (stub)",
        },
    )
    return cfg
