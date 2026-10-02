"""Done check for P4.8 (feature table, contract C4): is the merge correct?

C2 and C3 are checked by scripts/verify_features.py and scripts/verify_vector_features.py;
this checks what the merge adds:

1. C4 passes its contract; cell_id unique; rows = grid cells - cells with nodata_frac
   above the limit;
2. time-travel rule: the baseline year's road/building columns equal the 2018 OSM
   snapshot (C3), the later year's equal the current snapshot, not the other way round;
3. every value of 500 random cells equals the C2 / C3 row with the same cell_id
   (looked up independently, not via a merge);
4. own-cell LULC fractions sum to 1; no infinite values; NaN share < 1 % per column;
5. the GeoPackage copy: same cells and values as the parquet, geometry = 100 m square
   centred on the grid's x / y;
6. landmarks from OSM (independent of the ESRI fractions): the largest named OSM lake
   is mostly ESRI water; cells inside Bannerghatta National Park are natural vegetation
   (trees + rangeland), barely built, and steeper than the rest.

Run: python scripts/verify_feature_table.py
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import sys

import geopandas as gpd
import numpy as np

from src.config import load_config
from src.features import schema
from src.features.grid import xy_to_cell_id
from src.features.raster_features import features_years
from src.preprocess.vector import processed_osm_path

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def main() -> int:
    cfg = load_config()
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1").set_index("cell_id")
    max_nod = float(cfg["features"]["max_nodata_fraction"])
    years = list(features_years(cfg))
    c3 = {
        s: schema.read_contract(schema.contract_path(cfg, "C3", snapshot=s), "C3").set_index(
            "cell_id"
        )
        for s in ("2018", "current")
    }
    rng = np.random.default_rng(8)

    for y in years:
        print(f"== {y}")
        path = schema.contract_path(cfg, "C4", year=y)
        c4 = schema.read_contract(path, "C4")
        c2 = schema.read_contract(schema.contract_path(cfg, "C2", year=y), "C2").set_index(
            "cell_id"
        )
        n_keep = int((c2["nodata_frac"] <= max_nod).sum())
        check(c4["cell_id"].is_unique, "1. cell_id unique")
        check(
            len(c4) == n_keep,
            f"1. {len(c4)} rows = {len(grid)} grid cells - {len(grid) - n_keep} high-nodata",
        )
        c4 = c4.set_index("cell_id")

        # 2. which snapshot
        want = schema.vector_snapshot_for(cfg, y)
        other = "current" if want == "2018" else "2018"
        cols = list(schema.VECTOR_FEATURES)
        same = c4[cols].equals(c3[want].loc[c4.index, cols])
        diff = not c4[cols].equals(c3[other].loc[c4.index, cols])
        check(same and diff, f"2. road/building columns are the {want} OSM snapshot (not {other})")

        # 3. random cells, value by value
        ids = rng.choice(c4.index.to_numpy(), 500, replace=False)
        bad = 0
        for cid in ids:
            for col in c4.columns:
                src = c2 if col in c2.columns else c3[want]
                if not np.isclose(c4.at[cid, col], src.at[cid, col], equal_nan=True):
                    bad += 1
        check(
            bad == 0, f"3. 500 random cells × {c4.shape[1]} columns equal C2/C3 ({bad} mismatches)"
        )

        # 4. sanity
        s = c4[list(schema.FEATURE_GROUPS["lulc_own"])].sum(axis=1)
        check(
            bool(np.allclose(s, 1, atol=0.01)),
            f"4. own-cell fractions sum to 1 ({s.min():.4f}..{s.max():.4f})",
        )
        num = c4.select_dtypes("number")
        check(bool(np.isfinite(num.fillna(0)).all().all()), "4. no infinite values")
        nan = float(num.isna().mean().max())
        check(nan < 0.01, f"4. max NaN share per column {nan:.2%}")

        # 5. gpkg copy
        g = gpd.read_file(path.with_suffix(".gpkg")).set_index("cell_id")
        check(g.index.equals(c4.index), "5. gpkg has the same cells")
        check(
            bool(np.allclose(g[c4.columns].to_numpy(float), c4.to_numpy(float), equal_nan=True)),
            "5. gpkg values = parquet",
        )
        cen = g.geometry.centroid
        ok = np.allclose(cen.x, grid.loc[g.index, "x"]) and np.allclose(
            cen.y, grid.loc[g.index, "y"]
        )
        check(
            bool(ok and np.allclose(g.area, cfg.cell_size_m**2)),
            "5. gpkg geometry = 100 m squares on the grid centres",
        )

        # 6. landmarks from OSM
        snap = schema.vector_snapshot_for(cfg, y)
        water = gpd.read_file(processed_osm_path(cfg, snap, "water"))
        lakes = water.loc[(water["kind"] == "water_body") & water["name"].notna()]
        lake = lakes.loc[lakes.area.idxmax()]
        pt = lake.geometry.representative_point()
        cid = int(xy_to_cell_id(cfg, np.array([pt.x]), np.array([pt.y]))[0])
        fw = c4.at[cid, "frac_water"] if cid in c4.index else np.nan
        ha = lake.geometry.area / 1e4
        name = lake["name"]
        check(fw > 0.5, f"6. largest named OSM lake '{name}' ({ha:.0f} ha): frac_water {fw:.2f}")
        park = gpd.read_file(processed_osm_path(cfg, "current", "protected")).union_all()
        inside = c4.index[
            gpd.points_from_xy(grid.loc[c4.index, "x"], grid.loc[c4.index, "y"]).within(park)
        ]
        # Bannerghatta is dry deciduous forest and scrub: ESRI splits it into trees and
        # rangeland (about half each), with almost nothing built
        m = c4.loc[inside]
        veg, built = float((m["frac_tree"] + m["frac_range"]).mean()), float(m["frac_built"].mean())
        steeper = m["slope_mean"].median() > c4.drop(inside)["slope_mean"].median()
        check(veg > 0.9 and built < 0.05 and steeper,
              f"6. {len(inside)} cells in the protected area: trees + rangeland {veg:.2f}, "
              f"built {built:.3f}, steeper than outside: {steeper}")  # fmt: skip

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
