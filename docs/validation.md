# Validation

How well does each score predict where Bengaluru South actually grew? This document records the
metrics, figures and misses (PRD §9.8, deliverable D13). Numbers come from `outputs/metrics/*.json`;
figures are in `outputs/figures/`.

**Status:** Abhinav's parts are complete: the MCDA comparison, the sensitivity analysis, the
held-out building check, and a preview of the learned models. Harsh's harness sections (temporal
validation of the combined score, lift, TOC, LEI split, ablation, suitability hit rates; P7.4) are
marked *to be added*.

## 1. Design in one paragraph

Every score is computed **as of 2018** (the validation run): 2018 land cover, the 2018-01-01 OSM
snapshot, and a 3-class map and exclusion mask built from data up to 2019 (time-travel rule, D12).
It is then compared with **persistent growth**: candidate cells (non-built in 2018 and 2019, not
excluded) that are built in **both 2022 and 2023** (`grew`, C5). Cells that are neither clearly
grown nor clearly non-built in 2022/23 (`ambiguous`) are left out. That leaves **12,777 candidate
cells, of which 1,125 grew (8.8 %)**. Models trained on growth labels (the change RF) are scored
**out of fold** with 2 km spatial blocks (D11). Distance to built-up and random are always shown
as baselines (D7).

## 2. Headline: AUC on persistent growth

| Score | AUC on `grew` | Notes |
|---|---|---|
| Change RF (out of fold) | **0.779** | trained on 2018 → 2020/21 change, tuned on that label only |
| Distance to built-up | 0.763 | the bar to beat (prototype: 0.75) |
| State RF (out of fold) | 0.702 | built vs non-built in 2018; comparison only |
| MCDA / AHP | 0.636 | fixed expert weights, CR 0.003 |
| MCDA without land cover | 0.614 | |
| Random | 0.500 | |
| Aggregate similarity (kNN) | *to be added (P6.4 / P7.4)* | |
| Combined suitability score | *to be added (P7.1 / P7.4)* | |

Figure: `chart_roc.png`. The change RF meets the PRD target (best model ≥ distance to built-up),
but only just: +0.016 AUC. Most of the predictable signal is "growth happens next to existing
built-up land", which a single distance already captures.

**Why out-of-fold scoring matters:** scored on its own training cells, the change RF would claim
AUC 0.997 against its honest 0.779. Its 2020/21 training positives are mostly also 2022/23 growth
cells, so in-sample scores would leak the answer (`scripts/verify_similarity_models.py`, check 3).

## 3. MCDA / AHP baseline (P7.3, P7.5)

Five criteria, each rescaled to 0–1 (`src/suitability/mcda.py`, `config.yaml → mcda`):

| Criterion | 1 (most suitable) → 0 | AHP weight | AUC alone |
|---|---|---|---|
| Distance to built-up | next to built-up → ≥ 2 km | 0.298 | **0.763** |
| Distance to a major road | on the road → ≥ 3 km | 0.298 | 0.548 |
| Slope | flat → ≥ 15° | 0.158 | 0.612 |
| Land cover | rangeland / bare 1, crops 0.6, trees 0.2 | 0.158 | 0.527 |
| Distance to water | ≥ 200 m → within 100 m | 0.089 | 0.518 |

Pairwise matrix on Saaty's 1–9 scale: λmax = 5.013, **consistency ratio 0.003** (< 0.1).

**Why the overlay does worse than one of its own criteria.** Only distance to built-up carries
real signal. Roads, water and land cover are close to chance on their own, and slope is weak. The
AHP weights give the near-random criteria 70 % of the weight, which dilutes the one good signal:
the overlay's 0.636 is below distance to built-up alone (0.763). Land cover helps a little
(0.614 without it).

We did **not** tune the weights on the growth label. That label is the test set, so tuning on it
would be leakage. A fixed, defensible expert overlay is what this baseline stands for. The
learned models pick their own weighting from the 2020/21 change and do better.

**Is the land-cover criterion a leak?** No. D4 bans own-cell land cover from *trained* models,
because the fractions sum to 1 − built and a model would learn the label from them. MCDA is not
trained, and the validation scores only cells that were non-built in 2018/19. The score metadata
lists it as `own_cell_inputs`, apart from `features`, so the leakage check
(`schema.check_model_inputs`) still applies to every learned model.

## 4. Held-out building check (P6.6)

Do surroundings identify building locations in areas a model never saw? Reference cells (OSM
buildings, plus ESRI built cells where OSM has none) are held out by 2 km block. Each scorer
learns from the other blocks and ranks every non-excluded cell in the held-out blocks.

| Scorer | AUC (held-out reference vs other cells) | Median percentile (best possible 70.0) |
|---|---|---|
| Random forest | **0.984** | 70.0 |
| kNN similarity, all inputs | 0.895 | 68.5 |
| Distance to built-up | 0.887 | 65.5 |
| kNN similarity, 500 m rings only | 0.871 | 66.9 |

Reference cells are about 60 % of the non-excluded cells, so even a perfect scorer reaches a
median percentile of only about 70. AUC is the fair measure. Keeping both ring scales (250 m and
500 m) beats 500 m only, despite their correlation (r 0.91–0.95, notebook 03). Figure:
`chart_holdout.png`.

## 5. Sensitivity (P7.6)

`src/suitability/sensitivity.py` → `outputs/metrics/sensitivity.json`; figure `chart_sensitivity.png`.

**Slope threshold** (exclusion mask and the MCDA slope criterion):

| Slope | Slope-excluded cells | Candidates | Grew | Change RF | Dist. to built-up | MCDA |
|---|---|---|---|---|---|---|
| 10° | 1,685 | 15,288 | 1,101 | 0.774 | 0.759 | 0.646 |
| **15°** | 472 | 15,658 | 1,125 | **0.779** | **0.763** | **0.636** |
| 20° | 158 | 15,762 | 1,130 | 0.780 | 0.765 | 0.633 |

**Number of clusters k** (final run): class shares move by about 1 percentage point and agreement
with ESRI on land cells stays at 96.6–98.8 %. k = 5 agrees slightly better with ESRI, but it loses
the steep-rangeland cluster (the Bannerghatta hills): forest drops from 5.0 % to 3.9 %. k = 7 keeps
the best silhouette (0.606).

**Cell size** (features and labels rebuilt at each size):

| Cell | Cells | Candidates | Grew | Change RF | Dist. to built-up | MCDA |
|---|---|---|---|---|---|---|
| 50 m | 232,785 | 84,985 | 6,273 | 0.839 | 0.810 | 0.699 |
| **100 m** | 58,218 | 15,658 | 1,125 | **0.779** | **0.763** | **0.636** |
| 200 m | 14,567 | 4,322 | 148 | 0.834 | 0.825 | 0.733 |

AUCs are **not comparable across cell sizes**: the growth label itself changes with the cell
("≥ 50 % built" in 50 m vs 200 m), and at 200 m only 148 cells grew, with 42 change-RF training
positives. **What holds everywhere is the ranking: change RF > distance to built-up > MCDA, at every
slope threshold and every cell size.**

## 6. To be added (Harsh, P7.4)

- Top-N hit rate and lift in the top 10 % / 30 % for every score (target: lift ≥ 2 in the top 10 %).
- TOC curves.
- AUC by LEI growth type (adjacent vs outlying; outlying is expected to be harder).
- Group ablation (drop one feature group at a time).
- Combined score and suitability classes: S1 + S2 hit rate; precision in the top 10 %.

## 7. Misses and limitations

- **The learned model only just beats distance to built-up** (+0.016 AUC). Growth here is mostly
  edge expansion. A model that adds roads, terrain and land-cover context gains little over "next
  to existing built-up land".
- **OSM completeness.** Road mapping grew a lot between 2018 and today (median road density
  3.0 → 12.4 km/km²), mostly through mapping effort, not construction. Each run therefore uses its
  own OSM snapshot, and the RF uses within-year percentiles. OSM buildings cover only about 1 % of
  built cells in the south in 2018, so ESRI built cells fill the reference set. Almost no buildings
  are typed, so similarity per building type was not possible.
- **Land-cover errors.** ESRI and WorldCover disagree on built-up land (62 % vs 33 % of the AOI):
  ESRI generalises urban areas. Growth labels inherit ESRI's errors; the two-year rule (D3)
  removes flicker but not systematic bias.
- **Past growth ≠ good planning.** Every score learns or encodes where building *has* happened,
  not where it *should*. Protected areas, water and steep slopes are excluded, but other planning
  constraints (zoning, flood risk, infrastructure capacity) are not in the data.
