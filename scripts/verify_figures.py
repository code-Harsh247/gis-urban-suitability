"""Done check for P8.1 / P8.2 (static maps and charts).

1. every expected map and chart exists in outputs/figures, saved at >= 300 dpi;
2. no figure is blank (pixel variance) and no basemap is a tile-server error page
   (the CARTO 'API KEY REQUIRED' tiles are near-uniform: checked on the area outside the
   AOI of a score map, which is mostly basemap);
3. map pixels match the data: in ``map_class3_final.png`` the colour at the centre of
   200 random cells is the class colour (sampled through the axes' data-to-pixel
   transform of the map re-drawn at 300 dpi).

Run: python scripts/verify_figures.py
Exits with code 1 if any check fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402
from PIL import Image  # noqa: E402

from src.classify.label import c7_path  # noqa: E402
from src.config import load_config  # noqa: E402
from src.features import schema  # noqa: E402
from src.viz import charts, static_maps, style  # noqa: E402

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def main() -> int:
    cfg = load_config()
    fig_dir = Path(cfg.paths["figures"])
    y0, y1 = cfg["years"]["baseline"], cfg["years"]["latest"]
    expected = [
        f"map_lulc_{y0}",
        f"map_lulc_{y1}",
        "map_class3_validation",
        "map_class3_final",
        "map_labels_growth",
    ]
    expected += [f"map_feature_{c}_{y1}" for c in static_maps.FEATURE_MAPS]
    expected += [
        f"map_score_{m}_{r}"
        for m in ("rf_change", "rf_state", "mcda", "mcda_no_lulc")
        for r in ("validation", "final")
    ]
    expected += [
        "chart_k_scan",
        "chart_cluster_profiles",
        "chart_class_areas",
        "chart_rf_importance",
        "chart_roc",
        "chart_sensitivity",
        "chart_holdout",
    ]
    _ = charts  # charts module documents the list

    print("== 1-2. files, dpi, not blank")
    for name in expected:
        p = fig_dir / f"{name}.png"
        if not p.exists():
            check(False, f"{name}.png missing")
            continue
        im = Image.open(p)
        dpi = im.info.get("dpi", (0, 0))[0]
        a = np.asarray(im.convert("RGB"), dtype=float)
        check(
            round(dpi) >= 300 and a.std() > 5,
            f"{name}: {im.size[0]}x{im.size[1]} px, {dpi:.0f} dpi, pixel std {a.std():.0f}",
        )

    a = np.asarray(Image.open(fig_dir / "map_score_rf_change_final.png").convert("L"), dtype=float)
    corner = a[int(a.shape[0] * 0.9) :, int(a.shape[1] * 0.05) : int(a.shape[1] * 0.3)]
    check(
        len(np.unique(corner)) > 20,
        f"basemap has map detail ({len(np.unique(corner))} grey levels in the lower-left corner)",
    )

    print("== 3. map pixels = data")
    c7 = schema.read_contract(c7_path(cfg, "final"), "C7")
    grid = schema.read_contract(schema.contract_path(cfg, "C1"), "C1").merge(c7, on="cell_id")
    # data layer only (no scale bar / north arrow on top), same extent and drawing code
    style.apply()
    fig, ax = plt.subplots(figsize=(6.4, 6.4), dpi=300)
    x0, y0, x1, y1 = cfg.aoi_projected.total_bounds
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_axis_off()
    img = static_maps.cell_image(cfg, c7["cell_id"], c7["class_3"])
    codes = {k: (style.CLASS_NAMES[k], style.CLASS_COLORS[k]) for k in style.CLASS_NAMES}
    static_maps._categorical(cfg, ax, img, codes, static_maps.lattice_extent(cfg), "Class")
    fig.canvas.draw()  # ~5 px per 100 m cell, so a cell centre is never on a neighbour
    rgb = np.asarray(fig.canvas.buffer_rgba())[..., :3] / 255.0
    H = rgb.shape[0]
    sample = grid.sample(200, random_state=0)
    ok = 0
    for _, r in sample.iterrows():
        px, py = ax.transData.transform((r["x"], r["y"]))
        got = rgb[int(round(H - py)), int(round(px))]
        ok += np.abs(got - np.array(to_rgb(style.CLASS_COLORS[int(r["class_3"])]))).max() < 0.03
    plt.close(fig)
    check(ok == 200, f"{ok}/200 sampled cells drawn in their class colour")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
