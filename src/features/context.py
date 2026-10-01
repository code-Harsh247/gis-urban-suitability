"""Neighbourhood context (PRD FR-4.3): ring means that exclude the centre cell.

A ring of radius r is the (2n+1) × (2n+1) window of cells around a cell
(n = r / cell size), **minus the cell itself**, so a ring value never encodes the
cell's own land cover (decision D4). Cells outside the lattice are ignored, not
treated as zero.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi


def ring_mean(values: np.ndarray, radius_m: float, cell_m: float) -> np.ndarray:
    """Mean of ``values`` over the ring of radius ``radius_m`` around each cell."""
    n = int(round(radius_m / cell_m))
    if n < 1:
        raise ValueError(f"ring radius {radius_m} m is smaller than one cell ({cell_m} m)")
    k = 2 * n + 1
    v = np.asarray(values, dtype="float64")
    ones = np.ones_like(v)
    # window sums via uniform_filter (mode="constant" -> cells beyond the edge add 0)
    win_sum = ndi.uniform_filter(v, k, mode="constant", cval=0.0) * (k * k)
    win_cnt = ndi.uniform_filter(ones, k, mode="constant", cval=0.0) * (k * k)
    ring_sum = win_sum - v
    ring_cnt = np.rint(win_cnt - 1.0)
    out = np.divide(ring_sum, ring_cnt, out=np.zeros_like(v), where=ring_cnt > 0)
    return np.clip(out, 0.0, None)  # filters can round a zero to -1e-17
