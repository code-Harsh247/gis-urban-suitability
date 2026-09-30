# Data sources

Final dataset list, versions, access method and known issues (Task P1.7 / J7).

- **Rasters:** Abhinav.
- **OSM:** Harsh, to be added below.

Every downloaded file is recorded in `data/manifest.json` (source items, date, CRS, resolution, bounds, SHA-256).

## Rasters (Planetary Computer STAC)

| Layer | Collection | Asset | Years | Native grid | Licence | Code |
|---|---|---|---|---|---|---|
| ESRI / Impact Observatory 10 m Annual LULC v02 | `io-lulc-annual-v02` | `data` | 2018–2023 (`years.baseline`…`years.latest`) | 10 m, UTM per MGRS zone (AOI: tile `43P`, EPSG:32643) | CC BY 4.0 | `src/download/lulc.py` |
| ESA WorldCover v200 | `esa-worldcover` | `map` | 2021 (`lulc.worldcover_check`) | 1/12000° (~9 m), EPSG:4326, 3° tiles (`N12E075`) | CC BY 4.0 | `src/download/lulc.py` |
| Copernicus DEM GLO-30 | `cop-dem-glo-30` | `data` | static | 1 arc-second (~30 m), EPSG:4326, 1° tiles (`N12_00_E077_00`) | Copernicus DEM licence (free use with attribution) | `src/download/dem.py` |

**Access:**
- Anonymous STAC search at `https://planetarycomputer.microsoft.com/api/stac/v1`, with URLs signed by `planetary-computer`. No account needed.
- Downloads cover the reference-grid rectangle plus 2 cells: the AOI plus `aoi.buffer_m` (**3 km**), grown to whole 100 m cells.
- The buffer equals `features.distance_cap_m`, so distances from AOI cells are exact (never cut off at the grid edge).
- Only the needed window is read from each Cloud-Optimised GeoTIFF, clipped on the source's own pixel grid, so values are copied, not resampled.

**Run:**
```bash
python -m src.download.lulc
python -m src.download.dem
python -m src.preprocess.raster
```
Reruns skip files whose checksum matches the manifest.

**Checks:**
- `scripts/verify_raw_data.py`: the downloads match the source files exactly.
- `scripts/verify_preprocessed.py`: the aligned rasters are correct.

## Preprocessing (`src/preprocess/raster.py`)

**Reference grid:**
- EPSG:32643 at 10 m, 3,020 × 3,070 px, bounds (770400, 1404400, 800600, 1435100).
- The edges are multiples of 100 m, so every 10 × 10 block of pixels is one grid cell.
- Saved in `data/processed/reference_grid.json`. Use `load_reference_grid(cfg)`, e.g. when rasterising OSM.

| Output | From | Method |
|---|---|---|
| `lulc_esri_{year}.tif` | ESRI | nearest. The source is on the same 10 m lattice, so values are copied exactly |
| `worldcover_2021.tif` | WorldCover | nearest (0.8 % of pixels on class boundaries tie-break to a neighbouring source pixel; no shift) |
| `elevation.tif` | DEM | warped to UTM at 30 m, then bilinear to 10 m |
| `slope.tif` | DEM | Horn slope (degrees) on the 30 m UTM DEM, then bilinear to 10 m |

## Class harmonisation: ESRI is the reference (decision D2)

ESRI IO LULC v02 classes are used everywhere. WorldCover is mapped onto them for cross-checks (`harmonise_worldcover`):

| ESRI code | ESRI class | WorldCover classes mapped to it |
|---|---|---|
| 1 | Water | 80 Permanent water bodies |
| 2 | Trees | 10 Tree cover |
| 4 | Flooded vegetation | 90 Herbaceous wetland, 95 Mangroves |
| 5 | Crops | 40 Cropland |
| 7 | Built area | 50 Built-up |
| 8 | Bare ground | 60 Bare / sparse vegetation |
| 9 | Snow/ice | 70 Snow and ice |
| 10 | Clouds | (none; treat as nodata) |
| 11 | Rangeland | 20 Shrubland, 30 Grassland, 100 Moss and lichen |
| 0 | nodata | 0 |

**Growth labels:** "built-up" means ESRI class 7 in every year, so the baseline and latest years share the same definition (FR-8.1).

## Known issues

- **ESRI "built area" is broader than WorldCover "built-up":** 57 % vs 31 % of the AOI in 2021. ESRI paints settlements as solid blocks, including gardens and small open spaces. ESRI contains 99 % of WorldCover's built-up. Compare growth within ESRI only.
- **The ESRI 2017 map is noisier than later years**, so the baseline is 2018 (decision D3).
- **ESRI tree cover jumps between years** (2018: 7.0 %, 2019: 2.3 %, 2022: 8.4 %), and ESRI labels much of the Bannerghatta scrub forest as *rangeland*. In a 1 km window there, ESRI shows 39 % trees and 61 % rangeland; WorldCover shows 49 % trees and 44 % shrub. Take the forest class from one year, and cross-check with WorldCover.
- **Some lakes are covered in vegetation.** Hulimavu Lake is water in ESRI 2018, rangeland in 2023, and wetland in WorldCover. Add OSM water polygons to the exclusion mask.
- **Slope is gentle overall:** median 2.7°, and 1.5 % of the area is above 15°. Steep ground is mostly in the Bannerghatta hills (south-west).

## OSM (Harsh)

*To be added in H1: snapshot method (Overpass `[date:]`), mirrors, feature counts per snapshot, licence (ODbL).*
