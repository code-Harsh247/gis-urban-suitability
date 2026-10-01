"""Phase 1 gate: literature review and data discovery (see docs/Tasks.md).

Run: pytest tests/gates/test_phase1.py
Offline only: pytest tests/gates/test_phase1.py -m "not network"
"""

from __future__ import annotations

import re

import pytest

from src.config import PROJECT_ROOT, load_config

LIT = PROJECT_ROOT / "docs" / "literature_review.md"
SOURCES = PROJECT_ROOT / "docs" / "data_sources.md"

# dataset -> (how it is named in data_sources.md, licence, access method)
DATASETS = {
    "WorldCover": (r"WorldCover", r"CC BY 4\.0", r"Planetary Computer|STAC|esa-worldcover"),
    "ESRI LULC": (r"ESRI IO LULC|io-lulc-annual-v02", r"CC BY 4\.0", r"Planetary Computer|STAC"),
    "DEM": (
        r"Copernicus DEM",
        r"Copernicus DEM licence",
        r"Planetary Computer|STAC|cop-dem-glo-30",
    ),
    "OSM": (r"OpenStreetMap", r"ODbL", r"Overpass|osmnx"),
}
RASTER_COLLECTIONS = ("io-lulc-annual-v02", "esa-worldcover", "cop-dem-glo-30")


def _matrix_rows(text: str) -> list[str]:
    return re.findall(r"^\| ([AHD]\d+) \|", text, flags=re.M)


# ---------------------------------------------------------------- literature review


def test_literature_review_exists():
    assert LIT.is_file(), "docs/literature_review.md is missing"


def test_literature_review_has_at_least_10_papers():
    rows = _matrix_rows(LIT.read_text(encoding="utf-8"))
    assert len(rows) >= 10, f"only {len(rows)} papers in the summary matrix"
    assert len(rows) == len(set(rows)), "duplicate paper ids in the matrix"


@pytest.mark.parametrize(("prefix", "minimum"), [("A", 5), ("H", 5)])
def test_each_half_has_at_least_5_papers(prefix, minimum):
    """P1.2 (Abhinav, A*) and P1.3 (Harsh, H*) each need >= 5 papers."""
    rows = [r for r in _matrix_rows(LIT.read_text(encoding="utf-8")) if r.startswith(prefix)]
    assert len(rows) >= minimum, f"{prefix}-papers: {len(rows)} < {minimum}"


def test_every_matrix_row_has_a_detail_entry():
    text = LIT.read_text(encoding="utf-8")
    detail = set(re.findall(r"^### ([AHD]\d+)\. ", text, flags=re.M))
    missing = sorted(set(_matrix_rows(text)) - detail)
    assert not missing, f"no detail entry for {missing}"


def test_synthesis_written():
    text = LIT.read_text(encoding="utf-8")
    assert "## Synthesis" in text
    syn = text.split("## Synthesis", 1)[1]
    assert "To be written" not in syn, "part of the synthesis is still 'to be written'"


# ---------------------------------------------------------------- data sources


def test_data_sources_exists():
    assert SOURCES.is_file(), "docs/data_sources.md is missing"


@pytest.mark.parametrize("dataset", list(DATASETS))
def test_data_sources_lists_dataset_with_licence_and_access(dataset):
    """Each dataset appears in a summary-table row together with its licence and access method."""
    name, licence, access = DATASETS[dataset]
    rows = [ln for ln in SOURCES.read_text(encoding="utf-8").splitlines() if ln.startswith("|")]
    hits = [ln for ln in rows if re.search(name, ln)]
    assert hits, f"{dataset} not listed in a table in data_sources.md"
    assert any(re.search(licence, ln) for ln in hits), f"{dataset}: licence ({licence}) missing"
    assert any(re.search(access, ln) for ln in hits), f"{dataset}: access method missing"


# ---------------------------------------------------------------- data coverage (network)


@pytest.mark.network
@pytest.mark.parametrize("collection", RASTER_COLLECTIONS)
def test_stac_search_returns_items_over_aoi(collection):
    from src.download.stac import aoi_bounds_4326, search_items

    cfg = load_config()
    items = search_items(collection, aoi_bounds_4326(cfg))
    assert len(items) >= 1, f"no {collection} items over the AOI"
