"""Distances from cell centres to land-cover classes at 10 m (PRD §9.3).

- ``dist_to_class``: centre -> nearest pixel of the class (pixel centres), anywhere.
- ``dist_to_class_outside_cell``: centre -> nearest pixel of the class **outside the
  cell**. Used for built-up, so the distance never encodes whether the cell itself is
  built (PRD §9.3, decision D4).

Both use a KD-tree over the class pixels, so they are exact Euclidean distances.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def _pixel_centres(mask: np.ndarray, left: float, top: float, pixel_m: float) -> np.ndarray:
    r, c = np.nonzero(mask)
    return np.column_stack((left + (c + 0.5) * pixel_m, top - (r + 0.5) * pixel_m))


def dist_to_class(
    mask: np.ndarray,
    left: float,
    top: float,
    pixel_m: float,
    xs: np.ndarray,
    ys: np.ndarray,
    cap_m: float,
) -> np.ndarray:
    """Distance (m) from each (x, y) to the nearest True pixel, capped at ``cap_m``."""
    if not mask.any():
        return np.full(len(xs), cap_m)
    tree = cKDTree(_pixel_centres(mask, left, top, pixel_m))
    d, _ = tree.query(np.column_stack((xs, ys)), k=1, distance_upper_bound=cap_m)
    return np.minimum(d, cap_m)


def dist_to_class_outside_cell(
    mask: np.ndarray,
    left: float,
    top: float,
    pixel_m: float,
    cell_m: float,
    rows: np.ndarray,
    cols: np.ndarray,
    cap_m: float,
) -> np.ndarray:
    """Distance (m) from each cell centre to the nearest True pixel not inside that cell.

    ``rows, cols`` index cells on the lattice whose origin is (left, top).
    """
    n = len(rows)
    if not mask.any():
        return np.full(n, cap_m)
    k = int(round(cell_m / pixel_m))
    pts = _pixel_centres(mask, left, top, pixel_m)
    pix_col = np.floor((pts[:, 0] - left) / cell_m).astype(np.int64)
    pix_row = np.floor((top - pts[:, 1]) / cell_m).astype(np.int64)
    tree = cKDTree(pts)
    cx = left + (cols + 0.5) * cell_m
    cy = top - (rows + 0.5) * cell_m
    centres = np.column_stack((cx, cy))
    out = np.full(n, cap_m, dtype="float64")

    # a cell holds at most k*k pixels, so the (k*k + 1)-th neighbour is always outside it
    own = mask.reshape(mask.shape[0] // k, k, mask.shape[1] // k, k).sum(axis=(1, 3))
    own_n = own[rows, cols]

    clear = own_n == 0  # nothing of the class inside: plain nearest neighbour
    if clear.any():
        d, _ = tree.query(centres[clear], k=1, distance_upper_bound=cap_m)
        out[clear] = np.minimum(d, cap_m)

    busy = np.nonzero(~clear)[0]
    for start in range(0, len(busy), 5000):  # chunks keep memory small
        idx = busy[start : start + 5000]
        kk = int(own_n[idx].max()) + 1
        d, j = tree.query(centres[idx], k=kk, distance_upper_bound=cap_m)
        d, j = np.atleast_2d(d), np.atleast_2d(j)
        valid = j < len(pts)
        jj = np.where(valid, j, 0)
        outside = valid & ((pix_row[jj] != rows[idx, None]) | (pix_col[jj] != cols[idx, None]))
        first = np.where(outside.any(axis=1), np.argmax(outside, axis=1), -1)
        dd = np.where(first >= 0, d[np.arange(len(idx)), np.maximum(first, 0)], cap_m)
        out[idx] = np.minimum(dd, cap_m)
    return out
