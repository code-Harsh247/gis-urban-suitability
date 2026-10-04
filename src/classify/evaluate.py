"""Evaluate the 3-class map against land-cover references (PRD FR-5.6, §9.4; Tasks P5.6).

References, one class per 100 m cell (largest share of its 10 m pixels):

- **ESRI** (primary): the run's feature year, from the own-cell fractions in C4;
- **WorldCover** (cross-check): ``lulc.worldcover_check`` (2021), WorldCover codes
  harmonised to ESRI codes (``preprocess.raster.harmonise_worldcover``).

Both use the PRD §6 collapse: built area → built-up; trees → forest; crops, bare ground,
rangeland → usable; water, flooded vegetation, snow → excluded.

Two comparisons per reference:

- ``all``: every cell, four classes (built-up, forest, usable, excluded). The map's
  excluded class also holds steep and protected cells, which the land-cover reference
  can't know, so these show up as disagreement;
- ``land``: cells that neither side calls excluded, three classes. This is the agreement
  the Phase 5 gate reads (≥ 80 %).

Input: C7 (``cell_id, cluster_id, class_3``). Output: ``outputs/metrics/classification_eval.json``.

Run: python -m src.classify.evaluate [--run final|validation] [--c7 path]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from src.classify.cluster import RUNS, run_year
from src.config import load_config
from src.features import schema
from src.features.grid import lattice
from src.features.lulc_features import class_fractions
from src.io_utils import setup_logging
from src.preprocess.raster import harmonise_worldcover, processed_dir

log = logging.getLogger(__name__)

B, F, U, X = schema.CLASS_BUILT, schema.CLASS_FOREST, schema.CLASS_USABLE, schema.CLASS_EXCLUDED
CLASSES = (B, F, U, X)
NAMES = {B: "built-up", F: "forest", U: "usable", X: "excluded"}

# PRD §6: ESRI class -> 3-class map (+ excluded)
ESRI_TO_CLASS3 = {
    "built": B,
    "tree": F,
    "crop": U,
    "bare": U,
    "range": U,
    "water": X,
    "flooded": X,
    "snow": X,
}


def collapse_fractions(fr: pd.DataFrame) -> np.ndarray:
    """Class with the largest summed share per row (ties: built-up, forest, usable, excluded)."""
    groups = np.column_stack(
        [sum(fr[f"frac_{n}"] for n, c in ESRI_TO_CLASS3.items() if c == cls) for cls in CLASSES]
    )
    return np.array(CLASSES)[np.argmax(groups, axis=1)]


def esri_reference(cfg, year: int) -> pd.DataFrame:
    c4 = schema.read_contract(schema.contract_path(cfg, "C4", year=year), "C4")
    return pd.DataFrame({"cell_id": c4["cell_id"], "ref": collapse_fractions(c4)})


def worldcover_path(cfg) -> Path:
    return processed_dir(cfg) / f"worldcover_{cfg['lulc']['worldcover_check']}.tif"


def worldcover_reference(cfg) -> pd.DataFrame:
    lat = lattice(cfg)
    with rasterio.open(worldcover_path(cfg)) as ds:
        esri = harmonise_worldcover(ds.read(1))
    fr = class_fractions(esri, lat.px_per_cell)
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1")
    r, c = grid["row"].to_numpy(), grid["col"].to_numpy()
    cells = pd.DataFrame({k: v[r, c] for k, v in fr.items()})
    return pd.DataFrame({"cell_id": grid["cell_id"], "ref": collapse_fractions(cells)})


def compare(pred: np.ndarray, ref: np.ndarray, classes=CLASSES) -> dict:
    """Confusion matrix (rows: reference, columns: map), agreement, precision / recall."""
    cm = pd.crosstab(
        pd.Categorical(ref, categories=classes), pd.Categorical(pred, categories=classes),
        dropna=False,
    )  # fmt: skip
    m = cm.to_numpy()
    n = int(m.sum())
    per = {}
    for i, c in enumerate(classes):
        tp, col, row = m[i, i], m[:, i].sum(), m[i, :].sum()
        per[NAMES[c]] = {
            "precision": float(tp / col) if col else None,
            "recall": float(tp / row) if row else None,
            "map_share": float(col / n) if n else None,
            "ref_share": float(row / n) if n else None,
        }
    return {
        "n_cells": n,
        "agreement": float(np.trace(m) / n) if n else None,
        "per_class": per,
        "confusion": {
            NAMES[r]: {NAMES[c]: int(m[i, j]) for j, c in enumerate(classes)}
            for i, r in enumerate(classes)
        },
    }


def evaluate(cfg, c7: pd.DataFrame, run: str) -> dict:
    refs = {
        f"esri_{run_year(cfg, run)}": esri_reference(cfg, run_year(cfg, run)),
        f"worldcover_{cfg['lulc']['worldcover_check']}": worldcover_reference(cfg),
    }
    out = {}
    for name, ref in refs.items():
        m = c7[["cell_id", "class_3"]].merge(ref, on="cell_id", how="inner", validate="1:1")
        pred, r = m["class_3"].to_numpy(), m["ref"].to_numpy()
        land = (pred != X) & (r != X)
        out[name] = {
            "all": compare(pred, r),
            "land": compare(pred[land], r[land], classes=(B, F, U)),
        }
        log.info(
            "%s vs %s: agreement %.1f %% (all cells, 4 classes), %.1f %% (land, 3 classes)",
            run, name, 100 * out[name]["all"]["agreement"], 100 * out[name]["land"]["agreement"],
        )  # fmt: skip
    return out


def eval_path(cfg) -> Path:
    return Path(cfg.paths["metrics"]) / "classification_eval.json"


def write_evaluation(cfg, run: str = "final", c7_path: Path | None = None) -> dict:
    c7 = schema.read_contract(Path(c7_path) if c7_path else schema.contract_path(cfg, "C7"), "C7")
    res = evaluate(cfg, c7, run)
    p = eval_path(cfg)
    allm = json.loads(p.read_text()) if p.exists() else {}
    allm[run] = res
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(allm, indent=1, allow_nan=False))
    return res


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="final", choices=RUNS)
    parser.add_argument("--c7", help="C7 file (default: the contract path)")
    args = parser.parse_args(argv)
    cfg = load_config()
    setup_logging(cfg, "classify")
    write_evaluation(cfg, args.run, args.c7)


if __name__ == "__main__":
    main()
