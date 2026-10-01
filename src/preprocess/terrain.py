"""Terrain derivatives from a DEM in a projected CRS (PRD FR-3.6).

Usage:
    from src.preprocess.terrain import slope_degrees
    slope = slope_degrees(elevation, pixel_m=30.0)
"""

from __future__ import annotations

import numpy as np


def _pad_linear(z: np.ndarray) -> np.ndarray:
    """Pad by one cell with linear extrapolation, so a plane stays exact at the edges."""
    return np.pad(z, 1, mode="reflect", reflect_type="odd")


def horn_gradients(z: np.ndarray, pixel_m: float) -> tuple[np.ndarray, np.ndarray]:
    """dz/dx (east) and dz/dy (north) with Horn's (1981) 3 × 3 weighted differences.

    Rows run north -> south, as in a north-up raster. NaN cells make their
    neighbours' gradients NaN.
    """
    p = _pad_linear(np.asarray(z, dtype="float64"))
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * pixel_m)
    dzdy = ((a + 2 * b + c) - (g + 2 * h + i)) / (8 * pixel_m)  # positive = rising northward
    return dzdx, dzdy


def slope_degrees(z: np.ndarray, pixel_m: float) -> np.ndarray:
    """Slope in degrees (0–90), Horn method."""
    dzdx, dzdy = horn_gradients(z, pixel_m)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy))).astype("float32")


def aspect_degrees(z: np.ndarray, pixel_m: float) -> np.ndarray:
    """Aspect in degrees clockwise from north (0–360) that the slope faces; NaN on flat cells."""
    dzdx, dzdy = horn_gradients(z, pixel_m)
    aspect = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360.0) % 360.0
    aspect[(dzdx == 0) & (dzdy == 0)] = np.nan
    return aspect.astype("float32")
