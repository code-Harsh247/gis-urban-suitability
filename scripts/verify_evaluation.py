"""Done check for P5.6 (evaluation): are the land-cover references and agreements right?

1. ESRI reference: for 300 random cells, the majority class of the raw 10 m pixels
   (read from the processed GeoTIFF window, collapsed with a separately written table)
   equals ``evaluate.esri_reference``;
2. WorldCover reference: the same from the raw WorldCover codes (own WorldCover table,
   not via the ESRI harmonisation);
3. class shares of both references over the AOI (WorldCover is known to show more trees);
4. if C7 exists: agreement recomputed with numpy equals ``classification_eval.json``,
   and the GeoTIFF matches C7 cell by cell.

Run: python scripts/verify_evaluation.py
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

from src.classify import evaluate as ev
from src.classify import export as ex
from src.classify.cluster import run_year
from src.config import load_config
from src.features import schema
from src.features.grid import lattice
from src.preprocess.raster import processed_dir

failures: list[str] = []
B, F, U, X = ev.B, ev.F, ev.U, ev.X
ESRI = {7: B, 2: F, 5: U, 8: U, 11: U, 1: X, 4: X, 9: X}  # ESRI code -> class (PRD §6)
WC = {50: B, 10: F, 20: U, 30: U, 40: U, 60: U, 100: U, 70: X, 80: X, 90: X, 95: X}
ORDER = (B, F, U, X)  # tie order


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def majority(px: np.ndarray, table: dict[int, int]) -> int:
    counts = {c: 0 for c in ORDER}
    for code, n in zip(*np.unique(px, return_counts=True), strict=True):
        if int(code) in table:
            counts[table[int(code)]] += int(n)
    return max(ORDER, key=lambda c: (counts[c], -ORDER.index(c)))


def from_pixels(path, cells: pd.DataFrame, k: int, table) -> np.ndarray:
    out = []
    with rasterio.open(path) as ds:
        for r, c in zip(cells["row"], cells["col"], strict=True):
            out.append(majority(ds.read(1, window=Window(c * k, r * k, k, k)), table))
    return np.array(out)


def main() -> int:
    cfg = load_config()
    k = lattice(cfg).px_per_cell
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    rng = np.random.default_rng(5)
    cells = grid.iloc[rng.choice(len(grid), 300, replace=False)]
    year = run_year(cfg, "final")

    print(f"== 1. ESRI {year} reference")
    ref = ev.esri_reference(cfg, year).set_index("cell_id")
    mine = from_pixels(processed_dir(cfg) / f"lulc_esri_{year}.tif", cells, k, ESRI)
    bad = int((ref.loc[cells["cell_id"], "ref"].to_numpy() != mine).sum())
    check(bad == 0, f"majority class from raw pixels = esri_reference for 300 cells ({bad} differ)")

    print("== 2. WorldCover reference")
    wc = ev.worldcover_reference(cfg).set_index("cell_id")
    mine = from_pixels(ev.worldcover_path(cfg), cells, k, WC)
    bad = int((wc.loc[cells["cell_id"], "ref"].to_numpy() != mine).sum())
    check(
        bad == 0, f"majority class from raw WorldCover codes = worldcover_reference ({bad} differ)"
    )

    print("== 3. class shares over the AOI")
    shares = pd.DataFrame(
        {
            f"ESRI {year}": ref["ref"].map(ev.NAMES).value_counts(normalize=True),
            "WorldCover": wc["ref"].map(ev.NAMES).value_counts(normalize=True),
        }
    ).round(3)
    print(shares.to_string())
    check(bool((shares.sum() > 0.999).all()), "shares sum to 1")

    c7_path = schema.contract_path(cfg, "C7")
    if not c7_path.exists() or not ev.eval_path(cfg).exists():
        print("== 4. [skip] no C7 / evaluation yet (P5.4)")
    else:
        print("== 4. agreement recomputed")
        c7 = pd.read_parquet(c7_path).set_index("cell_id")
        stored = json.loads(ev.eval_path(cfg).read_text())["final"]
        for name, r in (
            (f"esri_{year}", ref),
            (f"worldcover_{cfg['lulc']['worldcover_check']}", wc),
        ):
            p, q = c7.loc[r.index, "class_3"].to_numpy(), r["ref"].to_numpy()
            land = (p != X) & (q != X)
            a_all, a_land = float((p == q).mean()), float((p[land] == q[land]).mean())
            s = stored[name]
            ok = np.isclose(a_all, s["all"]["agreement"]) and np.isclose(
                a_land, s["land"]["agreement"]
            )
            check(bool(ok), f"{name}: all {a_all:.3f}, land {a_land:.3f} = stored")
        tif = ex.class_raster_path(cfg)
        if tif.exists():
            with rasterio.open(tif) as ds:
                img = ds.read(1)
            g = grid.set_index("cell_id").loc[c7.index]
            check(
                bool((img[g["row"], g["col"]] == c7["class_3"].to_numpy()).all()),
                "GeoTIFF = C7 cell by cell",
            )

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
