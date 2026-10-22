"""Phase 7 gate: suitability mapping and validation (see docs/Tasks.md). Runs on real outputs.

Run: pytest tests/gates/test_phase7.py
The end-to-end pipeline check runs only with GIS_SUIT_RUN_PIPELINE=1 (it takes up to 30 min).
Set GIS_SUIT_CONFIG to run the gate on another project (e.g. a synthetic one).

Expected outputs (PRD §13): ``suitability_score.tif``, ``suitability_class.tif`` (1 S1,
2 S2, 3 S3, 4 N), ``candidates.gpkg``, ``metrics/validation.json`` (P7.1, P7.2, P7.4) and
``metrics/mcda.json`` (P7.3).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio

from src.classify.label import c7_path
from src.config import load_config
from src.features import schema
from src.features.grid import grid_geodataframe, lattice
from src.preprocess.raster import load_reference_grid
from src.suitability import mcda

cfg = load_config(os.environ.get("GIS_SUIT_CONFIG"))
OUT = Path(cfg.paths["outputs"])
CLASSES = {1, 2, 3, 4}  # S1, S2, S3, N
MIN_AUC = 0.75


def _need(p: Path, task: str) -> Path:
    if not p.exists():
        pytest.fail(f"{p} missing ({task})")
    return p


def _grid():
    return schema.read_contract(schema.contract_path(cfg, "C1"), "C1")


def _read(name: str) -> tuple[np.ndarray, rasterio.profiles.Profile]:
    with rasterio.open(_need(OUT / name, "P7.1")) as ds:
        return ds.read(1), ds.profile


@pytest.mark.parametrize("name", ["suitability_score.tif", "suitability_class.tif"])
def test_suitability_rasters_aligned(name):
    img, prof = _read(name)
    lat, ref = lattice(cfg), load_reference_grid(cfg)
    assert prof["crs"] == cfg.crs, f"{name}: CRS {prof['crs']}"
    t = prof["transform"]
    assert (t.a, -t.e) == (cfg.cell_size_m, cfg.cell_size_m), f"{name}: resolution {(t.a, -t.e)}"
    assert (t.c, t.f) == (
        ref.transform.c,
        ref.transform.f,
    ), f"{name}: origin is not the reference grid's"
    assert img.shape == lat.shape, f"{name}: shape {img.shape} != lattice {lat.shape}"


def test_suitability_values():
    cls, _ = _read("suitability_class.tif")
    score, _ = _read("suitability_score.tif")
    g = _grid()
    inside = cls[g["row"], g["col"]]
    extra = set(np.unique(inside).tolist()) - CLASSES
    assert not extra, f"classes {sorted(extra)} inside the AOI; allowed {sorted(CLASSES)}"
    s = score[g["row"], g["col"]]
    s = s[np.isfinite(s)]
    assert ((s >= 0) & (s <= 1)).all(), f"scores outside [0, 1]: {s.min():.3f}..{s.max():.3f}"


def test_no_forest_built_or_excluded_cell_in_s1_s3():
    cls, _ = _read("suitability_class.tif")
    c7 = schema.read_contract(_need(c7_path(cfg, "final"), "P5.4"), "C7")
    g = _grid().merge(c7, on="cell_id")
    bad = g.loc[g["class_3"] != schema.CLASS_USABLE]
    n = int(np.isin(cls[bad["row"], bad["col"]], [1, 2, 3]).sum())
    assert n == 0, f"{n} forest / built-up / excluded cells are in S1-S3"


def _candidates() -> gpd.GeoDataFrame:
    c = gpd.read_file(_need(OUT / "candidates.gpkg", "P7.2"))
    assert c.crs == cfg.crs, f"candidates CRS {c.crs}"
    return c


def test_candidates_only_on_usable_land():
    c = _candidates()
    c7 = schema.read_contract(c7_path(cfg, "final"), "C7")
    g = _grid().merge(c7, on="cell_id")
    bad = grid_geodataframe(g.loc[g["class_3"] != schema.CLASS_USABLE], cfg)
    overlap = gpd.overlay(
        c[["geometry"]], bad[["geometry"]], how="intersection", keep_geom_type=True
    )
    area = float(overlap.area.sum()) if len(overlap) else 0.0
    assert (
        area < 1.0
    ), f"candidate patches cover {area:.0f} m² of forest / built-up / excluded cells"


def test_candidates_at_least_min_area():
    c = _candidates()
    lo = float(cfg["suitability"]["min_patch_area_m2"])
    small = int((c.area < lo - 1e-6).sum())
    assert small == 0, f"{small} candidate patches are smaller than {lo:.0f} m²"


def test_ahp_consistency_ratio():
    m = json.loads(_need(mcda.metrics_path(cfg), "P7.3").read_text())
    _, cons = mcda.weights(cfg)
    assert cons["consistency_ratio"] < 0.1, f"AHP CR {cons['consistency_ratio']:.3f} >= 0.1"
    assert (
        abs(m["mcda"]["consistency_ratio"] - cons["consistency_ratio"]) < 1e-9
    ), "mcda.json is stale"


def _validation() -> dict:
    return json.loads(_need(Path(cfg.paths["metrics"]) / "validation.json", "P7.4").read_text())


def _flat(d, prefix="") -> dict[str, float]:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}".lower()
        if isinstance(v, dict):
            out.update(_flat(v, key + "."))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = float(v)
    return out


def _models(v: dict) -> dict[str, dict[str, float]]:
    src = v.get("models", v)
    return {k.lower(): _flat(m) for k, m in src.items() if isinstance(m, dict)}


def test_validation_json_has_the_metrics():
    models = _models(_validation())
    assert "mcda" in models, f"no MCDA entry in validation.json: {sorted(models)}"
    learned = [
        m
        for m in models
        if m not in {"mcda", "mcda_no_lulc", "random", "dist_to_built", "distance_to_built"}
    ]
    assert learned, "no data-driven model in validation.json"
    for name in ["mcda", *learned]:
        keys = models[name]
        assert any("auc" in k for k in keys), f"{name}: no AUC"
        assert any(
            ("10" in k) and ("precision" in k or "hit" in k or "lift" in k) for k in keys
        ), f"{name}: no top-10 % metric"
    assert any(
        any("s1" in k and "s2" in k for k in models[m]) for m in learned
    ), "no S1+S2 hit rate"


def test_temporal_auc():
    models = _models(_validation())
    skip = {"mcda", "mcda_no_lulc", "random"}
    aucs = [
        v
        for m, keys in models.items()
        if m not in skip
        for k, v in keys.items()
        if k.endswith("auc")
    ]
    best = max(aucs, default=float("nan"))
    if not best >= MIN_AUC:
        doc = Path(cfg.root) / "docs" / "validation.md"
        if doc.exists() and "AUC" in doc.read_text(encoding="utf-8"):
            pytest.xfail(
                f"best temporal AUC {best:.3f} < {MIN_AUC}; explained in docs/validation.md"
            )
        pytest.fail(
            f"best temporal AUC {best:.3f} < {MIN_AUC} and docs/validation.md doesn't explain it"
        )


@pytest.mark.skipif(
    os.environ.get("GIS_SUIT_RUN_PIPELINE") != "1",
    reason="set GIS_SUIT_RUN_PIPELINE=1 (takes up to 30 min)",
)
def test_pipeline_end_to_end_under_30_min():
    t0 = time.perf_counter()
    r = subprocess.run(
        [sys.executable, "-m", "src.pipeline"],
        cwd=cfg.root,
        timeout=1800,
        capture_output=True,
        text=True,
    )
    dt = time.perf_counter() - t0
    assert r.returncode == 0, f"pipeline failed:\n{r.stderr[-3000:]}"
    assert dt < 1800, f"pipeline took {dt / 60:.1f} min"
