"""Shared I/O helpers: download manifest, checksums, retries, logging (PRD §7.3, FR-2.5, FR-2.6).

Every downloaded file gets an entry in ``data/manifest.json`` with its source, date,
CRS, resolution, bounds, size and SHA-256. Downloaders call ``needs_download`` first
and skip files that already exist with a matching checksum, so reruns are free.

Usage:
    from src.io_utils import Manifest, needs_download, record_download, retry, setup_logging
    manifest = Manifest.for_config(cfg)
    if needs_download(path, manifest):
        ...write path...
        record_download(manifest, path, cfg.root, dataset="esri-lulc", source={...}, year=2018)
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- checksums


def sha256(path: str | Path, chunk: int = 1 << 20) -> str:
    """Hex SHA-256 of a file."""
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------- manifest


class Manifest:
    """``data/manifest.json``: one entry per downloaded file, keyed by repo-relative path."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.entries: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            self.entries = json.loads(self.path.read_text(encoding="utf-8"))

    @classmethod
    def for_config(cls, cfg) -> Manifest:
        return cls(Path(cfg.paths["data_raw"]).parent / "manifest.json")

    def get(self, key: str) -> dict[str, Any] | None:
        return self.entries.get(key)

    def set(self, key: str, entry: dict[str, Any]) -> None:
        self.entries[key] = entry
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.entries, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)  # atomic: never leave a half-written manifest


def manifest_key(path: str | Path, root: str | Path) -> str:
    """Repo-relative POSIX path used as the manifest key (same on Windows and Linux)."""
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def needs_download(path: str | Path, manifest: Manifest, root: str | Path) -> bool:
    """True unless the file exists, is in the manifest and its checksum still matches."""
    path = Path(path)
    if not path.exists():
        return True
    entry = manifest.get(manifest_key(path, root))
    if entry is None:
        log.warning("%s exists but is not in the manifest; downloading again", path)
        return True
    if entry.get("sha256") != sha256(path):
        log.warning("%s checksum does not match the manifest; downloading again", path)
        return True
    return False


def record_download(
    manifest: Manifest, path: str | Path, root: str | Path, *, dataset: str, **info: Any
) -> dict[str, Any]:
    """Add or replace the manifest entry for a freshly written file."""
    path = Path(path)
    entry = {
        "dataset": dataset,
        "downloaded": datetime.now(UTC).isoformat(timespec="seconds"),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        **info,
    }
    manifest.set(manifest_key(path, root), entry)
    return entry


def raster_info(path: str | Path) -> dict[str, Any]:
    """CRS, resolution, bounds, shape and nodata of a raster, for the manifest."""
    import rasterio

    with rasterio.open(path) as ds:
        return {
            "crs": ds.crs.to_string() if ds.crs else None,
            "resolution": [abs(ds.res[0]), abs(ds.res[1])],
            "bounds": list(ds.bounds),
            "shape": [ds.height, ds.width],
            "dtype": ds.dtypes[0],
            "nodata": ds.nodata,
        }


# ---------------------------------------------------------------- retries


class DownloadError(RuntimeError):
    """A download failed after all retries."""


def retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    wait_s: float = 5.0,
    what: str = "request",
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Call ``fn`` until it succeeds, waiting ``wait_s × attempt`` between tries."""
    last: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except exceptions as exc:  # noqa: PERF203 - retry loop
            last = exc
            log.warning("%s failed (attempt %d/%d): %s", what, attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(wait_s * attempt)
    raise DownloadError(
        f"{what} failed after {attempts} attempts: {last}. "
        "Check the network connection and whether the source is up, then rerun."
    ) from last


# ---------------------------------------------------------------- logging


def setup_logging(cfg=None, name: str = "pipeline", level: int = logging.INFO) -> logging.Logger:
    """Log to the console and, if a config is given, to ``logs/<name>.log``."""
    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
    if not any(getattr(h, "_gis_console", False) for h in root.handlers):
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(fmt)
        console._gis_console = True  # type: ignore[attr-defined]
        root.addHandler(console)
    if cfg is not None:
        log_dir = Path(cfg.paths["logs"])
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = (log_dir / f"{name}.log").resolve()
        if not any(getattr(h, "baseFilename", None) == str(log_file) for h in root.handlers):
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(fmt)
            root.addHandler(fh)
    return logging.getLogger(name)
