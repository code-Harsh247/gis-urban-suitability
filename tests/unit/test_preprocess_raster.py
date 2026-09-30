"""Unit tests for raster preprocessing (A2): reference grid, alignment, slope, class mapping."""

from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.enums import Resampling
from rasterio.transform import from_origin

from src.preprocess import raster as pr
from src.preprocess.terrain import aspect_degrees, slope_degrees
from src.synthetic import make_synthetic_project

# ---------------------------------------------------------------- terrain


@pytest.mark.parametrize(
    ("gx", "gy"), [(0.0, 0.0), (0.1, 0.0), (0.0, -0.3), (0.2, 0.2), (1.0, 0.5)]
)
def test_slope_of_plane_is_exact_everywhere(gx, gy):
    """z = gx·x + gy·y has slope atan(|grad|) at every cell, edges included."""
    rows, cols = np.indices((20, 30))
    x, y = cols * 30.0, -rows * 30.0  # north-up: y decreases with row
    z = gx * x + gy * y + 800
    s = slope_degrees(z, 30.0)
    np.testing.assert_allclose(s, np.degrees(np.arctan(np.hypot(gx, gy))), atol=1e-4)


def test_aspect_of_plane():
    rows, cols = np.indices((10, 10))
    z_east_down = -0.2 * cols * 10.0  # height falls toward the east -> faces east (90°)
    np.testing.assert_allclose(aspect_degrees(z_east_down, 10.0), 90.0, atol=1e-4)
    z_north_down = -0.2 * rows * -10.0  # height falls toward the north -> faces north (0°)
    a = aspect_degrees(z_north_down, 10.0)
    assert np.allclose(np.minimum(a, 360 - a), 0.0, atol=1e-4)


def test_slope_range():
    z = np.random.default_rng(0).normal(900, 50, (40, 40))
    s = slope_degrees(z, 10.0)
    assert s.min() >= 0 and s.max() <= 90


# ---------------------------------------------------------------- class harmonisation


def test_worldcover_mapping_covers_all_classes():
    assert set(pr.WORLDCOVER_TO_ESRI) == {10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100}
    assert set(pr.WORLDCOVER_TO_ESRI.values()) <= set(pr.ESRI_VALID)


def test_harmonise_worldcover():
    arr = np.array([[10, 20, 30, 40], [50, 80, 90, 0]], dtype=np.uint8)
    np.testing.assert_array_equal(pr.harmonise_worldcover(arr), [[2, 11, 11, 5], [7, 1, 4, 0]])


# ---------------------------------------------------------------- reference grid


@pytest.fixture
def project(tmp_path):
    return make_synthetic_project(tmp_path / "proj", n=10)


def test_reference_grid_whole_cells_and_covers_aoi_buffer(project):
    ref = pr.build_reference_grid(project)
    left, bottom, right, top = ref.bounds
    for v in ref.bounds:
        assert v % project.cell_size_m == pytest.approx(
            0
        ) or v % project.cell_size_m == pytest.approx(project.cell_size_m)
    assert ref.width % 10 == 0 and ref.height % 10 == 0
    need = project.aoi_projected.buffer(project["aoi"]["buffer_m"]).total_bounds
    assert left <= need[0] and bottom <= need[1] and right >= need[2] and top >= need[3]


def test_reference_grid_json_round_trip(project):
    ref = pr.build_reference_grid(project)
    again = pr.ReferenceGrid.from_json(json.loads(json.dumps(ref.to_json())))
    assert again == ref


def test_cell_size_must_be_multiple_of_pixel(project):
    from dataclasses import replace

    with pytest.raises(ValueError, match="multiple"):
        pr.build_reference_grid(replace(project, cell_size_m=95.0))


# ---------------------------------------------------------------- alignment


def _write(path, arr, crs, transform, nodata):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=str(arr.dtype),
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(arr, 1)


def test_same_lattice_is_an_exact_copy(tmp_path, project):
    """A source on the same 10 m lattice (offset by whole pixels) is copied, not resampled."""
    ref = pr.build_reference_grid(project)
    rng = np.random.default_rng(0)
    src_arr = rng.choice(
        np.array([1, 2, 5, 7, 11], dtype=np.uint8), size=(ref.height + 40, ref.width + 40)
    )
    t = Affine(
        10.0, 0, ref.transform.c - 200.0, 0, -10.0, ref.transform.f + 200.0
    )  # 20 px bigger each side
    src = tmp_path / "esri.tif"
    _write(src, src_arr, ref.crs, t, 0)
    out = pr.align_to_grid(src, ref, resampling=Resampling.nearest, dtype="uint8", dst_nodata=0)
    np.testing.assert_array_equal(out, src_arr[20 : 20 + ref.height, 20 : 20 + ref.width])


def test_reprojection_keeps_class_values(tmp_path, project):
    ref = pr.build_reference_grid(project)
    w, s, e, n = project.aoi.buffer(0.02).total_bounds
    arr = np.random.default_rng(1).choice(
        np.array([10, 40, 50, 80], dtype=np.uint8), size=(300, 300)
    )
    src = tmp_path / "wc.tif"
    _write(src, arr, "EPSG:4326", from_origin(w, n, (e - w) / 300, (n - s) / 300), 0)
    out = pr.align_to_grid(src, ref, resampling=Resampling.nearest, dtype="uint8", dst_nodata=0)
    assert set(np.unique(out)) <= {10, 40, 50, 80}
    assert (out == 0).mean() == 0  # source covers the whole grid


def test_outside_source_is_nodata(tmp_path, project):
    ref = pr.build_reference_grid(project)
    small = np.full((5, 5), 7, dtype=np.uint8)
    src = tmp_path / "small.tif"
    _write(src, small, ref.crs, Affine(10.0, 0, ref.transform.c, 0, -10.0, ref.transform.f), 0)
    out = pr.align_to_grid(src, ref, resampling=Resampling.nearest, dtype="uint8", dst_nodata=0)
    assert (out[:5, :5] == 7).all() and (out[5:, :] == 0).all()


def test_dem_slope_pipeline_on_a_plane(tmp_path, project):
    """A tilted-plane DEM in EPSG:4326 comes out with the right elevation and slope on the grid."""
    ref = pr.build_reference_grid(project)
    w, s, e, n = project.aoi.buffer(0.05).total_bounds
    rows, cols = np.indices((400, 400))
    res_deg = (e - w) / 400
    z = (800 + 0.05 * cols * res_deg * 111_000).astype("float32")  # 5 % rise to the east
    src = tmp_path / "dem.tif"
    _write(src, z, "EPSG:4326", from_origin(w, n, res_deg, (n - s) / 400), -32767.0)
    z30, t30 = pr.dem_on_native_utm(src, ref)
    from src.preprocess.terrain import slope_degrees as sd

    slope = pr.resample_array(sd(z30, 30.0), t30, ref, Resampling.bilinear)
    assert np.nanmedian(slope) == pytest.approx(np.degrees(np.arctan(0.05)), abs=0.3)
    assert not np.isnan(slope).any()


@pytest.mark.parametrize("which", ["synthetic", "real_aoi"])
def test_download_bounds_cover_reference_grid(project, which):
    """Downloads (stac.aoi_bounds_4326) must cover the whole reference grid, corners included.

    The real AOI (22 km, 1 km buffer) matters: its grid corners stick out ~400 m past the
    rounded corners of the buffered AOI, which a tiny synthetic AOI hides.
    """
    import geopandas as gpd
    from shapely.geometry import box

    from src.config import load_config
    from src.download import stac

    cfg = project if which == "synthetic" else load_config()
    ref = pr.build_reference_grid(cfg)
    w, s, e, n = stac.aoi_bounds_4326(cfg)
    dl = gpd.GeoSeries([box(w, s, e, n).segmentize(0.001)], crs=4326).to_crs(ref.crs).iloc[0]
    assert dl.contains(box(*ref.bounds))
