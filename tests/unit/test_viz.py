"""Unit tests for P8.1 / P8.2: figure style and map helpers."""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from matplotlib_scalebar.scalebar import ScaleBar  # noqa: E402
from PIL import Image  # noqa: E402

from src.features import schema  # noqa: E402
from src.preprocess import raster as pr  # noqa: E402
from src.synthetic import make_synthetic_project  # noqa: E402
from src.viz import static_maps as sm  # noqa: E402
from src.viz import style  # noqa: E402


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    cfg = make_synthetic_project(tmp_path / "proj", n=20)
    ref = pr.build_reference_grid(cfg)
    pr.processed_dir(cfg).mkdir(parents=True, exist_ok=True)
    pr.reference_grid_path(cfg).write_text(json.dumps(ref.to_json()))
    monkeypatch.setattr(sm, "BASEMAP", False)  # no network in tests
    return cfg


def test_class_colours_distinct_and_semantic():
    assert len(set(style.CLASS_COLORS.values())) == 4
    assert set(style.CLASS_COLORS) == set(schema.CLASS_3_VALUES)
    assert (
        style.CLASS_COLORS[255] == style.NEUTRAL
    )  # excluded is the neutral grey, not a series hue


def test_cell_image_places_values(cfg):
    grid = pd.read_parquet(schema.contract_path(cfg, "C1"))
    img = sm.cell_image(cfg, grid["cell_id"], grid["cell_id"])
    assert (img[grid["row"], grid["col"]] == grid["cell_id"]).all()
    assert np.isnan(img).sum() == img.size - len(grid)


def test_map_frame_has_scale_bar_north_arrow_and_saves_300_dpi(cfg):
    fig, ax = sm.base_map(cfg, "Title", "subtitle")
    assert any(isinstance(a, ScaleBar) for a in ax.artists)
    assert any(t.get_text() == "N" for t in ax.texts)
    p = sm.save(fig, cfg, "map_test")
    dpi = Image.open(p).info["dpi"]
    assert round(dpi[0]) == style.DPI


def test_class3_map(cfg):
    p = sm.class3_map(cfg, "final")
    assert p.exists() and p.name == "map_class3_final.png"
