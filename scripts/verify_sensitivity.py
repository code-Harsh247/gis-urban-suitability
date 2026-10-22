"""Done check for P7.6 (sensitivity analysis).

1. the default rows (slope 15°, k = 7, 100 m) reproduce the stored main results
   (metrics/mcda.json, similarity.json, classification_eval.json) exactly;
2. cell counts x cell area = the same AOI area for 50 / 100 / 200 m (within 1 %);
3. the other cell-size projects sit on the reference grid: their C1 centres are odd
   multiples of half a cell from the grid origin;
4. slope: a lower threshold never excludes fewer cells; class shares sum to 1 for every k;
5. the model ranking (rf_change > distance-to-built > MCDA) is reported for every row.

Run: python scripts/verify_sensitivity.py
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import load_config
from src.features import schema

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def main() -> int:
    cfg = load_config()
    met = Path(cfg.paths["metrics"])
    sens = json.loads((met / "sensitivity.json").read_text())
    mc = json.loads((met / "mcda.json").read_text())
    sim = json.loads((met / "similarity.json").read_text())
    evj = json.loads((met / "classification_eval.json").read_text())

    print("== 1. defaults reproduce the main results")
    want = {
        "auc_mcda": mc["mcda"]["temporal_preview"]["auc_grew"],
        "auc_dist_to_built": mc["baseline_dist_to_built_auc"],
        "auc_rf_change": sim["rf_change"]["temporal_preview"]["auc_grew_oof"],
    }
    for exp, key, val in (("slope", "slope_max_deg", 15), ("cell", "cell_size_m", 100)):
        row = next(r for r in sens[exp] if r[key] == val)
        ok = all(abs(row[k] - v) < 1e-9 for k, v in want.items())
        check(ok, f"{exp} = {val}: AUCs equal the stored main results")
    row7 = next(r for r in sens["k"] if r["k"] == cfg["clustering"]["k"])
    stored = evj["final"][f"esri_{cfg['years']['latest']}"]["land"]["agreement"]
    check(
        abs(row7["agreement_esri_land"] - stored) < 1e-9,
        f"k = 7: ESRI land agreement {stored:.3f} = stored",
    )

    print("== 2. cell counts x cell area")
    areas = {r["cell_size_m"]: r["n_cells"] * r["cell_size_m"] ** 2 / 1e6 for r in sens["cell"]}
    ref = areas[100]
    check(
        all(abs(a / ref - 1) < 0.01 for a in areas.values()),
        f"AOI area per cell size (km²): { {k: round(v, 1) for k, v in areas.items()} }",
    )

    print("== 3. other cell sizes on the reference grid")
    origin = json.loads((Path(cfg.paths["data_processed"]) / "reference_grid.json").read_text())[
        "transform"
    ]
    for cell in (50, 200):
        p = (
            Path(cfg.paths["outputs"])
            / "sensitivity"
            / f"cell_{cell}"
            / "data"
            / "features"
            / "grid.parquet"
        )
        g = pd.read_parquet(p)
        fx = ((g["x"] - origin[2]) / (cell / 2)) % 2
        fy = ((origin[5] - g["y"]) / (cell / 2)) % 2
        check(
            bool(np.allclose(fx, 1) and np.allclose(fy, 1)),
            f"{cell} m: {len(g)} cell centres on the {cell} m lattice",
        )
        schema.validate_frame(g, "C1")

    print("== 4. monotonic / consistent")
    s = sorted(sens["slope"], key=lambda r: r["slope_max_deg"])
    check(
        all(a["n_excluded"] >= b["n_excluded"] for a, b in zip(s, s[1:], strict=False)),
        "lower slope threshold excludes at least as many cells",
    )
    for r in sens["k"]:
        tot = sum(v for k, v in r.items() if k.startswith("share_"))
        check(abs(tot - 1) < 1e-9, f"k = {r['k']}: class shares sum to 1")

    print("== 5. ranking rf_change > distance-to-built > MCDA")
    for exp, key in (("slope", "slope_max_deg"), ("cell", "cell_size_m")):
        for r in sens[exp]:
            ok = r["auc_rf_change"] > r["auc_dist_to_built"] > r["auc_mcda"]
            print(
                f"  {'ok ' if ok else 'NOT'} {exp} {r[key]}: rf {r['auc_rf_change']:.3f}, "
                f"d2b {r['auc_dist_to_built']:.3f}, mcda {r['auc_mcda']:.3f}"
            )

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
