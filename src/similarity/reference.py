"""Reference building set for the similarity and held-out checks (PRD FR-6.1; Tasks P6.2).

Per run (time-travel rule, FR-8.2):

- ``validation``: OSM buildings of the 2018 snapshot (C6) and ESRI built cells of
  ``years.baseline``;
- ``final``: current OSM buildings and ESRI built cells of ``years.latest``.

Buildings are summarised per grid cell, because profiles are per cell (PRD §9.5). With
``similarity.reference_source: osm+esri`` (default) ESRI built cells (``frac_built >=
growth.built_min``) without an OSM building are added: OSM covers most built cells in the
north but almost none in the south, so OSM alone would describe only northern surroundings.

Output: ``data/features/reference_{run}.parquet`` with ``cell_id, source`` (osm / esri /
both), ``n_buildings, bldg_area_m2, main_type`` (most common typed group, ``unknown`` when
all are ``building=yes``).

Run: python -m src.similarity.reference [--run validation|final]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from src.classify.cluster import RUNS, run_year
from src.config import load_config
from src.features import schema
from src.io_utils import setup_logging

log = logging.getLogger(__name__)

SOURCES = ("osm", "osm+esri")

# OSM building=* values -> coarse groups (for the per-type stretch, P6.7)
TYPE_GROUPS = {
    "residential": {
        "apartments", "house", "residential", "detached", "semidetached_house", "terrace",
        "bungalow", "dormitory", "villa", "hut",
    },
    "commercial": {"commercial", "retail", "office", "hotel", "supermarket", "kiosk", "shop"},
    "industrial": {"industrial", "warehouse", "manufacture", "factory", "storage_tank"},
    "institutional": {
        "school", "college", "university", "hospital", "public", "government", "civic",
        "temple", "church", "mosque", "religious", "train_station", "transportation",
    },
}  # fmt: skip


def type_group(building_type: pd.Series) -> pd.Series:
    lut = {t: g for g, ts in TYPE_GROUPS.items() for t in ts}
    t = building_type.fillna("yes").astype(str).str.lower()
    return t.map(lut).where(t.isin(lut), np.where(t == "yes", "unknown", "other"))


def run_snapshot(cfg, run: str) -> str:
    return schema.vector_snapshot_for(cfg, run_year(cfg, run))


def buildings(cfg, run: str) -> pd.DataFrame:
    """C6 buildings of the run's OSM snapshot (no geometry), with ``type_group``."""
    b = gpd.read_file(
        schema.contract_path(cfg, "C6", snapshot=run_snapshot(cfg, run)), ignore_geometry=True
    )
    b = pd.DataFrame(b)
    b["type_group"] = type_group(b["building_type"])
    return b


def reference_cells(cfg, run: str) -> pd.DataFrame:
    source = cfg["similarity"].get("reference_source", "osm+esri")
    if source not in SOURCES:
        raise ValueError(f"similarity.reference_source must be one of {SOURCES}, got {source!r}")
    b = buildings(cfg, run)
    per = b.groupby("cell_id").agg(n_buildings=("bldg_id", "size"), bldg_area_m2=("area_m2", "sum"))
    typed = b.loc[b["type_group"] != "unknown"]
    main = typed.groupby("cell_id")["type_group"].agg(lambda s: s.value_counts().index[0])
    per["main_type"] = main.reindex(per.index).fillna("unknown")
    per["source"] = "osm"
    if source == "osm+esri":
        c4 = schema.read_contract(schema.contract_path(cfg, "C4", year=run_year(cfg, run)), "C4")
        built = set(c4.loc[c4["frac_built"] >= float(cfg["growth"]["built_min"]), "cell_id"])
        per.loc[per.index.isin(built), "source"] = "both"
        extra = pd.DataFrame(index=pd.Index(sorted(built - set(per.index)), name="cell_id"))
        extra = extra.assign(n_buildings=0, bldg_area_m2=0.0, main_type="unknown", source="esri")
        per = pd.concat([per, extra])
    out = per.sort_index().reset_index()
    out["n_buildings"] = out["n_buildings"].astype("int64")
    return out[["cell_id", "source", "n_buildings", "bldg_area_m2", "main_type"]]


def reference_path(cfg, run: str) -> Path:
    return Path(cfg.paths["data_features"]) / f"reference_{run}.parquet"


def write_reference(cfg, runs: list[str] | None = None) -> dict[str, pd.DataFrame]:
    out = {}
    for run in runs or list(RUNS):
        ref = reference_cells(cfg, run)
        ref.to_parquet(reference_path(cfg, run), index=False)
        log.info(
            "%s: %d reference cells (%s), %d OSM buildings -> %s",
            run, len(ref), ref["source"].value_counts().to_dict(), ref["n_buildings"].sum(),
            reference_path(cfg, run).name,
        )  # fmt: skip
        out[run] = ref
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", choices=RUNS, help="default: both")
    args = parser.parse_args(argv)
    cfg = load_config()
    setup_logging(cfg, "similarity")
    write_reference(cfg, args.run)


if __name__ == "__main__":
    main()
