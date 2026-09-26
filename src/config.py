"""Load and validate the project configuration (PRD FR-1).

Usage:
    from src.config import load_config
    cfg = load_config()
    cfg.crs, cfg.cell_size_m, cfg.aoi_projected, cfg.paths["data_raw"], cfg["years"]["baseline"]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import yaml
from pyproj import CRS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

REQUIRED_SECTIONS = ("project", "aoi", "crs", "grid", "years", "paths")


class ConfigError(ValueError):
    """Raised when the configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Validated project configuration."""

    raw: dict[str, Any]
    root: Path
    aoi: gpd.GeoDataFrame  # single-row, EPSG:4326
    crs: CRS  # projected CRS in metres used for all processing
    cell_size_m: float
    seed: int
    paths: dict[str, Path]

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    @property
    def aoi_projected(self) -> gpd.GeoDataFrame:
        """AOI in the project CRS."""
        return self.aoi.to_crs(self.crs)

    @property
    def aoi_area_km2(self) -> float:
        return float(self.aoi_projected.area.iloc[0]) / 1e6

    def ensure_dirs(self) -> None:
        """Create all configured data/output directories."""
        for path in self.paths.values():
            path.mkdir(parents=True, exist_ok=True)


def utm_epsg_for(lon: float, lat: float) -> int:
    """EPSG code of the WGS 84 / UTM zone containing (lon, lat)."""
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ConfigError(f"Coordinates out of range: lon={lon}, lat={lat}")
    zone = min(int((lon + 180) // 6) + 1, 60)
    return (32600 if lat >= 0 else 32700) + zone


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ConfigError(f"Config file is empty or not a mapping: {path}")
    missing = [s for s in REQUIRED_SECTIONS if s not in data]
    if missing:
        raise ConfigError(f"Config is missing sections: {', '.join(missing)}")
    return data


def _load_aoi(path: Path) -> gpd.GeoDataFrame:
    if not path.exists():
        raise ConfigError(
            f"AOI file not found: {path}. Create it once the study area is chosen (Task P0.10)."
        )
    aoi = gpd.read_file(path)
    if len(aoi) != 1:
        raise ConfigError(f"AOI must contain exactly one feature, found {len(aoi)}: {path}")
    geom = aoi.geometry.iloc[0]
    if geom is None or geom.is_empty:
        raise ConfigError(f"AOI geometry is empty: {path}")
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise ConfigError(f"AOI must be a Polygon or MultiPolygon, got {geom.geom_type}")
    if not geom.is_valid:
        raise ConfigError(f"AOI geometry is invalid: {path}")
    if aoi.crs is None:
        aoi = aoi.set_crs(4326)
    return aoi.to_crs(4326)


def _resolve_crs(setting: Any, aoi: gpd.GeoDataFrame) -> CRS:
    if setting in (None, "auto"):
        centroid = aoi.to_crs(6933).centroid.to_crs(4326).iloc[0]  # equal-area centroid
        crs = CRS.from_epsg(utm_epsg_for(centroid.x, centroid.y))
    else:
        try:
            crs = CRS.from_epsg(int(setting))
        except Exception as exc:
            raise ConfigError(f"Invalid crs.epsg: {setting!r}") from exc
    if not crs.is_projected:
        raise ConfigError(f"CRS {crs.to_string()} is not projected; use a metric CRS (e.g. UTM)")
    units = {axis.unit_name for axis in crs.axis_info}
    if units != {"metre"}:
        raise ConfigError(f"CRS {crs.to_string()} must use metres, found units {units}")
    return crs


def load_config(path: str | Path | None = None) -> Config:
    """Load, validate and return the project configuration.

    Relative paths in the config are resolved against the directory that
    contains the ``config/`` folder (the repository root).
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw = _read_yaml(config_path)
    root = config_path.resolve().parent.parent

    try:
        cell_size = float(raw["grid"]["cell_size_m"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError("grid.cell_size_m must be a number") from exc
    if cell_size <= 0:
        raise ConfigError(f"grid.cell_size_m must be > 0, got {cell_size}")

    try:
        aoi_path = root / raw["aoi"]["path"]
    except (KeyError, TypeError) as exc:
        raise ConfigError("aoi.path is required") from exc
    aoi = _load_aoi(aoi_path)
    crs = _resolve_crs(raw["crs"].get("epsg"), aoi)

    paths = {name: root / rel for name, rel in raw["paths"].items()}
    seed = int(raw["project"].get("random_seed", 42))

    return Config(
        raw=raw, root=root, aoi=aoi, crs=crs, cell_size_m=cell_size, seed=seed, paths=paths
    )
