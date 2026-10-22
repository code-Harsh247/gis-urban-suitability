"""Reproducibility check (Tasks P8.11): compare the outputs of two project folders.

Typical use: a fresh clone that downloaded and rebuilt everything vs the working copy.
Compares, by content (not bytes, so file metadata and row order don't matter):

- parquet tables under ``data/features`` and ``outputs`` (same rows by ``cell_id`` /
  key and the same values, floats within 1e-9);
- GeoTIFFs under ``data/processed`` and ``outputs`` (same grid and pixel values);
- JSON metrics under ``outputs/metrics`` (same numbers within 1e-9).

Files present in only one folder are listed. Outputs built from the *current* OSM
snapshot are expected to differ slightly when the two downloads were made on different
days (OSM is edited continuously); the 2018 snapshot must match exactly.

Run: python scripts/compare_projects.py <project_a> <project_b>
Exits with code 1 if any compared file differs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

PATTERNS = ("data/features/*.parquet", "outputs/*.parquet", "outputs/scores/*.parquet",
            "outputs/final/scores/*.parquet", "data/processed/*.tif", "outputs/*.tif",
            "outputs/metrics/*.json")  # fmt: skip


def _key(df: pd.DataFrame) -> pd.DataFrame:
    for k in ("cell_id", "bldg_id"):
        if k in df.columns:
            return df.sort_values(k).reset_index(drop=True)
    return df.reset_index(drop=True)


def same_parquet(a: Path, b: Path) -> str | None:
    x, y = _key(pd.read_parquet(a)), _key(pd.read_parquet(b))
    if list(x.columns) != list(y.columns):
        return f"columns differ: {sorted(set(x.columns) ^ set(y.columns))}"
    if len(x) != len(y):
        return f"{len(x)} vs {len(y)} rows"
    for c in x.columns:
        u, v = x[c].to_numpy(), y[c].to_numpy()
        if np.issubdtype(u.dtype, np.floating):
            if not np.allclose(u, v, atol=1e-9, equal_nan=True):
                return f"column {c}: max diff {np.nanmax(np.abs(u - v)):.3g}"
        elif not (u == v).all():
            return f"column {c}: {int((u != v).sum())} values differ"
    return None


def same_tif(a: Path, b: Path) -> str | None:
    with rasterio.open(a) as p, rasterio.open(b) as q:
        if (p.crs, p.transform, p.shape) != (q.crs, q.transform, q.shape):
            return "grid differs"
        u, v = p.read(1), q.read(1)
    if np.issubdtype(u.dtype, np.floating):
        diff = ~np.isclose(u, v, atol=1e-9, equal_nan=True)  # NaN = NaN is not a difference
    else:
        diff = u != v
    return None if not diff.any() else f"{int(diff.sum())} pixels differ"


def _numbers(d, prefix=""):
    if isinstance(d, dict):
        for k, v in d.items():
            yield from _numbers(v, f"{prefix}{k}.")
    elif isinstance(d, list):
        for i, v in enumerate(d):
            yield from _numbers(v, f"{prefix}{i}.")
    elif isinstance(d, (int, float)) and not isinstance(d, bool):
        yield prefix.rstrip("."), float(d)
    else:
        yield prefix.rstrip("."), d


def same_json(a: Path, b: Path) -> str | None:
    x = dict(_numbers(json.loads(a.read_text())))
    y = dict(_numbers(json.loads(b.read_text())))
    if set(x) != set(y):
        return f"keys differ: {sorted(set(x) ^ set(y))[:5]}"
    bad = [
        k
        for k in x
        if (x[k] != y[k])
        and not (isinstance(x[k], float) and isinstance(y[k], float) and abs(x[k] - y[k]) < 1e-9)
    ]
    return f"{len(bad)} values differ, e.g. {bad[:3]}" if bad else None


def main(a: str, b: str) -> int:
    ra, rb = Path(a), Path(b)
    diffs = 0
    for pat in PATTERNS:
        fa = {p.relative_to(ra) for p in ra.glob(pat)}
        fb = {p.relative_to(rb) for p in rb.glob(pat)}
        for rel in sorted(fa ^ fb):
            print(f"  [only in {'A' if rel in fa else 'B'}] {rel}")
        for rel in sorted(fa & fb):
            fn = {".parquet": same_parquet, ".tif": same_tif, ".json": same_json}[rel.suffix]
            msg = fn(ra / rel, rb / rel)
            print(
                f"  [{'same' if msg is None else 'DIFF'}] {rel}{'' if msg is None else ': ' + msg}"
            )
            diffs += msg is not None
    print(f"\n{'ALL COMPARED FILES MATCH' if not diffs else f'{diffs} FILE(S) DIFFER'}")
    return 1 if diffs else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
