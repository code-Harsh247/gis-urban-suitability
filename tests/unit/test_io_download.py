"""Unit tests for io_utils and the raster downloaders (no network: local GeoTIFFs, mocked STAC)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin

from src.download import dem, lulc, stac
from src.io_utils import (
    DownloadError,
    Manifest,
    manifest_key,
    needs_download,
    record_download,
    retry,
    sha256,
)
from src.synthetic import make_synthetic_project

# ---------------------------------------------------------------- io_utils


def test_sha256_matches_hashlib(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"hello world" * 1000)
    assert sha256(p) == hashlib.sha256(p.read_bytes()).hexdigest()


def test_manifest_round_trip(tmp_path):
    m = Manifest(tmp_path / "data" / "manifest.json")
    m.set("data/raw/a.tif", {"sha256": "x", "year": 2018})
    again = Manifest(tmp_path / "data" / "manifest.json")
    assert again.get("data/raw/a.tif") == {"sha256": "x", "year": 2018}
    assert not (tmp_path / "data" / "manifest.json.tmp").exists()


def test_needs_download_logic(tmp_path):
    m = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "raw" / "x.bin"
    assert needs_download(f, m, tmp_path)  # missing
    f.parent.mkdir()
    f.write_bytes(b"abc")
    assert needs_download(f, m, tmp_path)  # not in manifest
    record_download(m, f, tmp_path, dataset="test")
    assert not needs_download(f, m, tmp_path)  # present + checksum ok
    f.write_bytes(b"changed")
    assert needs_download(f, m, tmp_path)  # checksum mismatch


def test_manifest_key_is_repo_relative_posix(tmp_path):
    assert manifest_key(tmp_path / "data" / "raw" / "a.tif", tmp_path) == "data/raw/a.tif"


def test_retry_succeeds_after_failures():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("down")
        return "ok"

    assert retry(flaky, attempts=3, wait_s=0) == "ok"
    assert len(calls) == 3


def test_retry_gives_clear_error():
    def broken():
        raise ConnectionError("timeout")

    with pytest.raises(DownloadError, match="after 2 attempts.*timeout"):
        retry(broken, attempts=2, wait_s=0, what="STAC search")


# ---------------------------------------------------------------- mosaicking


def _tile(
    path: Path,
    west: float,
    north: float,
    value: int,
    crs="EPSG:4326",
    res=0.001,
    n=50,
    dtype="uint8",
):
    arr = np.full((1, n, n), value, dtype=dtype)
    profile = dict(
        driver="GTiff",
        height=n,
        width=n,
        count=1,
        dtype=dtype,
        crs=crs,
        transform=from_origin(west, north, res, res),
        nodata=0,
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr)
    return str(path)


def test_mosaic_two_tiles_same_crs(tmp_path):
    a = _tile(tmp_path / "a.tif", 77.00, 13.00, 10)  # 77.00–77.05
    b = _tile(tmp_path / "b.tif", 77.05, 13.00, 20)  # 77.05–77.10
    out = tmp_path / "out" / "m.tif"
    stac.mosaic_to_file(
        [a, b],
        (77.02, 12.97, 77.08, 12.99),
        out,
        dst_crs="EPSG:32643",
        resampling=Resampling.nearest,
        nodata=0,
    )
    with rasterio.open(out) as ds:
        arr = ds.read(1)
        assert ds.crs.to_epsg() == 4326  # native grid kept
        assert set(np.unique(arr)) == {10, 20}  # classes untouched
        assert ds.bounds.left == pytest.approx(77.02, abs=1e-3)
        assert ds.bounds.right == pytest.approx(77.08, abs=1e-3)
    assert not out.with_suffix(".tmp.tif").exists()


def test_mosaic_keeps_source_pixel_grid_and_values(tmp_path):
    """Output pixels must sit exactly on the source grid: values copied, never shifted."""
    n = 100
    arr = np.arange(n * n, dtype="float32").reshape(1, n, n)  # every pixel unique
    src = tmp_path / "dem.tif"
    profile = dict(
        driver="GTiff",
        height=n,
        width=n,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(77.0, 13.0, 0.001, 0.001),
        nodata=-9999.0,
    )
    with rasterio.open(src, "w", **profile) as dst:
        dst.write(arr)
    out = tmp_path / "m.tif"
    # bounds deliberately off-grid by fractions of a pixel
    stac.mosaic_to_file(
        [str(src)],
        (77.01234, 12.95678, 77.05432, 12.98765),
        out,
        dst_crs="EPSG:32643",
        resampling=Resampling.bilinear,
    )
    with rasterio.open(out) as ds, rasterio.open(src) as s0:
        off_x = (ds.transform.c - s0.transform.c) / 0.001
        off_y = (s0.transform.f - ds.transform.f) / 0.001
        assert off_x == pytest.approx(round(off_x), abs=1e-6)
        assert off_y == pytest.approx(round(off_y), abs=1e-6)
        got = ds.read(1)
        r0, c0 = round(off_y), round(off_x)
        np.testing.assert_array_equal(got, arr[0, r0 : r0 + got.shape[0], c0 : c0 + got.shape[1]])
        assert (
            ds.bounds.left <= 77.01234 and ds.bounds.right >= 77.05432
        )  # still covers the request


def test_mosaic_mixed_crs_warps_to_project_crs(tmp_path):
    a = _tile(tmp_path / "a.tif", 77.00, 13.00, 10)
    b = _tile(tmp_path / "b.tif", 77.05, 13.00, 20)
    with rasterio.open(b) as src:  # rewrite b in UTM so the CRSs differ
        data = src.read()
    utm = tmp_path / "b_utm.tif"
    from rasterio.warp import calculate_default_transform, reproject

    with rasterio.open(b) as src:
        t, w, h = calculate_default_transform(
            src.crs, "EPSG:32643", src.width, src.height, *src.bounds
        )
        prof = src.profile | {"crs": "EPSG:32643", "transform": t, "width": w, "height": h}
        with rasterio.open(utm, "w", **prof) as dst:
            reproject(
                data,
                rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=t,
                dst_crs="EPSG:32643",
                resampling=Resampling.nearest,
            )
    out = tmp_path / "m.tif"
    stac.mosaic_to_file(
        [a, str(utm)],
        (77.02, 12.97, 77.08, 12.99),
        out,
        dst_crs="EPSG:32643",
        resampling=Resampling.nearest,
        nodata=0,
    )
    with rasterio.open(out) as ds:
        assert ds.crs.to_epsg() == 32643
        assert {10, 20} <= set(np.unique(ds.read(1)))


# ---------------------------------------------------------------- downloaders (mocked STAC)


@pytest.fixture
def project(tmp_path):
    return make_synthetic_project(tmp_path / "proj", n=10)


def _fake_items(tmp_path, ids, asset, value, dtype="uint8"):
    items = []
    for k, i in enumerate(ids):
        href = _tile(tmp_path / f"{i}.tif", 77.55, 12.85, value + k, res=0.001, n=100, dtype=dtype)
        items.append(SimpleNamespace(id=i, assets={asset: SimpleNamespace(href=href)}))
    return items


def test_esri_download_filters_year_records_manifest_and_skips_rerun(
    project, tmp_path, monkeypatch
):
    calls = []

    def fake_search(collection, bbox, datetime=None, query=None):
        calls.append(datetime)
        return _fake_items(tmp_path, [f"43P-{int(datetime) - 1}", f"43P-{datetime}"], "data", 5)

    monkeypatch.setattr(stac, "search_items", fake_search)
    paths = lulc.download_esri_lulc(project, years=[2018, 2019])
    assert [p.name for p in paths] == ["esri_lulc_2018.tif", "esri_lulc_2019.tif"]
    with rasterio.open(paths[0]) as ds:
        assert set(np.unique(ds.read(1))) == {6}  # only the "-2018" item (value 5+1) was used
    m = Manifest.for_config(project)
    entry = m.get(manifest_key(paths[0], project.root))
    assert entry["dataset"] == "esri-io-lulc-v02" and entry["year"] == 2018
    assert entry["source"]["items"] == ["43P-2018"] and entry["sha256"] == sha256(paths[0])
    assert entry["crs"] == "EPSG:4326" and entry["nodata"] == 0

    mtimes = [p.stat().st_mtime_ns for p in paths]
    lulc.download_esri_lulc(project, years=[2018, 2019])  # rerun: no search, no rewrite
    assert len(calls) == 2
    assert [p.stat().st_mtime_ns for p in paths] == mtimes


def test_worldcover_and_dem_paths(project, tmp_path, monkeypatch):
    monkeypatch.setattr(
        stac,
        "search_items",
        lambda collection, bbox, datetime=None, query=None: _fake_items(
            tmp_path,
            (
                ["ESA_WorldCover_10m_2021_v200_N12E075"]
                if "worldcover" in collection
                else ["Copernicus_DSM_COG_10_N12_00_E077_00_DEM"]
            ),
            "map" if "worldcover" in collection else "data",
            50,
            "uint8" if "worldcover" in collection else "float32",
        ),
    )
    wc = lulc.download_worldcover(project)
    d = dem.download_dem(project)
    assert wc.name == "worldcover_2021.tif" and wc.exists()
    assert d.name == "copdem_glo30.tif" and d.exists()


def test_no_items_is_a_clear_error(project, monkeypatch):
    monkeypatch.setattr(
        stac,
        "search_items",
        lambda *a, **k: [SimpleNamespace(id="43P-2017", assets={})],
    )
    with pytest.raises(DownloadError, match="No io-lulc-annual-v02 items left"):
        lulc.download_esri_lulc(project, years=[2018])


def test_aoi_bounds_include_buffer(project):
    w, s, e, n = stac.aoi_bounds_4326(project)
    aw, as_, ae, an = project.aoi.total_bounds
    assert w < aw and s < as_ and e > ae and n > an  # 1 km buffer
    assert (aw - w) * 111_000 == pytest.approx(1000, rel=0.1)
