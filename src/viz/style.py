"""One figure style for every static map and chart (PRD FR-9.1, FR-9.3).

Colours follow the project's data-viz method: categorical identity in a fixed order
(validated for colour-vision deficiency with the palette validator), magnitude on a
single-hue sequential ramp, polarity on a blue <-> red diverging ramp with a grey
midpoint. Text uses ink colours, never series colours.

- 3-class map: built-up orange, forest green, usable blue (all pairs pass: worst CVD
  ΔE 9.2, normal vision 24.0); excluded is the neutral grey (no data / not applicable).
- ESRI land cover keeps Esri's published class colours (the provider convention) and is
  always shown with a labelled legend.
"""

from __future__ import annotations

import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap, ListedColormap

DPI = 300

INK = "#0b0b0b"
INK_2 = "#52514e"
INK_MUTED = "#8a8984"
SURFACE = "#fcfcfb"
GRID = "#e4e3df"
NEUTRAL = "#b8b7b1"  # excluded / not applicable

# categorical slots, fixed order (reference palette, light mode)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

CLASS_COLORS = {
    1: "#eb6834",
    2: "#1baf7a",
    3: "#2a78d6",
    255: NEUTRAL,
}  # built, forest, usable, excluded
CLASS_NAMES = {1: "Built-up", 2: "Forest", 3: "Usable", 255: "Excluded"}

# Esri 10 m Annual LULC published colours
ESRI_COLORS = {
    1: ("Water", "#419bdf"),
    2: ("Trees", "#397d49"),
    4: ("Flooded vegetation", "#7a87c6"),
    5: ("Crops", "#e49635"),
    7: ("Built area", "#c4281b"),
    8: ("Bare ground", "#a59b8f"),
    9: ("Snow / ice", "#a8ebff"),
    11: ("Rangeland", "#e3e2c3"),
}

SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQUENTIAL = LinearSegmentedColormap.from_list("seq_blue", SEQ_BLUE)
DIVERGING = LinearSegmentedColormap.from_list(
    "div_blue_red", ["#184f95", "#6da7ec", "#f0efec", "#ec835a", "#b8302f"]
)


def class_cmap(codes) -> ListedColormap:
    return ListedColormap([CLASS_COLORS[c] for c in codes])


def apply() -> None:
    """Matplotlib defaults: thin, recessive axes and grid; ink text."""
    mpl.rcParams.update(
        {
            "figure.dpi": 100,
            "savefig.dpi": DPI,
            "savefig.bbox": "tight",
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.labelcolor": INK_2,
            "axes.edgecolor": GRID,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "text.color": INK,
            "legend.frameon": False,
            "lines.linewidth": 2.0,
            "axes.prop_cycle": mpl.cycler(color=SERIES),
        }
    )
