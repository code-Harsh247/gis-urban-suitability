# Literature review

Phase 1 (tasks P1.1–P1.4, joint task J6). We need **≥ 10 papers** in total:
- **Abhinav (P1.2):** GIS / MCDA land suitability and LULC-based urban growth.
- **Harsh (P1.3):** machine learning, presence-based suitability, and validation of urban-growth models.
- **Both (P1.4):** the synthesis at the end.

Each paper gets a row in the matrix and a detail entry with the P1.1 fields:
- title, authors, year, venue
- study area, data used
- method, criteria / features
- validation, key findings
- relevance to us

Items marked *(to verify)* could not be checked against the full text yet. Check them before citing in the report.

---

## Summary matrix

| # | Paper | Year | Study area | Method | Validation | Relevance to us | By |
|---|---|---|---|---|---|---|---|
| A1 | *(Abhinav)* | | | | | | Abhinav |
| A2 | *(Abhinav)* | | | | | | Abhinav |
| A3 | *(Abhinav)* | | | | | | Abhinav |
| A4 | *(Abhinav)* | | | | | | Abhinav |
| A5 | *(Abhinav)* | | | | | | Abhinav |
| H1 | Li et al., *Spatial suitability evaluation … random forest: Yulin* | 2024 | Yulin, China | RF on built-up (presence) vs protected land, 30 m cells, 25 factors | Random 70/30 split, AUC 0.99 (urban) | Closest prior work; shows the own-cell leakage and random-split inflation we avoid | Harsh |
| H2 | Wang et al., *Urban land expansion … diffusional and aggregated growth: Luoyang* | 2021 | Luoyang, China | MaxEnt (presence-only) + category-selected CA | 2009 → 2018 simulation, Kappa 0.78 | Presence-only framing like ours; aggregated vs diffusional = our LEI split | Harsh |
| H3 | Ahmadlou et al., *Modeling urban dynamics using random forest: ROC and TOC* | 2016 | *(to verify)* | RF suitability for urban change, Landsat 1985 / 2000 / 2015 | Against observed change; ROC AUC 82.48 % + TOC | Same temporal-validation design; backs ROC + TOC (D7) | Harsh |
| H4 | Liu et al., *A future land use simulation model (FLUS)* | 2017 | China | ANN probability-of-occurrence + CA | Simulated 2000 → 2010 vs actual; beats CLUE-S and CA | Standard reference for "learned suitability surface" | Harsh |
| H5 | Pijanowski et al., *Land Transformation Model* | 2002 | *(to verify)* | ANN + GIS on distance and neighbourhood predictors | Against later observed change *(to verify)* | Ancestor of our context-profile features | Harsh |
| H6 | Roberts et al., *Cross-validation strategies for data with … spatial … structure* | 2017 | — (methods review) | Blocked cross-validation | Shows random CV underestimates error on structured data | Basis for spatial blocks (D11, FR-6.8) | Harsh |
| H7 | Ploton et al., *Spatial validation reveals poor predictive performance of large-scale ecological mapping models* | 2020 | Central Africa | RF biomass mapping | Random vs spatial CV | Concrete case of spatial leakage inflating accuracy | Harsh |

---

## Abhinav: GIS / MCDA and LULC-based urban growth (P1.2)

*To be filled by Abhinav. Suggested starting points already cited in the PRD (§22):*
- *Malczewski (2004)*
- *Saaty (1980)*
- *FAO (1976)*
- *Karra et al. (2021)*
- *Liu et al. (2010) on LEI*
- *Pontius & Si (2014) on TOC*

---

## Harsh: machine learning, presence-based suitability and validation (P1.3)

### H1. Li et al. (2024): random forest suitability, Yulin

- **Citation:** Li, A., Zhang, Z., Hong, Z., Liu, L., Liu, L., Ashraf, T. & Liu, Y. (2024). *Spatial suitability evaluation based on multisource data and random forest algorithm: a case study of Yulin, China.* Frontiers in Environmental Science, 12. https://doi.org/10.3389/fenvs.2024.1338931
- **Study area:** Yulin City, Shaanxi, China (42,920 km²). 30 m grid, about 47.7 M evaluation units.
- **Data:** all from 2020. DEM, slope, aspect; soil erosion and texture; **land use**; NDVI, NPP, precipitation; distance to roads and rivers; POI, healthcare, schools, night lights, population density.
- **Method:** separate RF classifiers for ecological, agricultural and urban suitability, with 25 factors. For **urban** suitability:
  - positives are existing built-up cells (121,013);
  - negatives are ecological-protection, permanent-farmland and drinking-water-source zones (242,026).
- **Validation:** **random** 70/30 split. Urban accuracy 92 %, AUC 0.99 (ecological and agricultural: AUC 0.98). No temporal validation and no spatial blocking.
- **Key findings:** RF produces a plausible suitability surface from existing land use, and the sample-based approach replaces hand-set MCDA weights.
- **Relevance to us:**
  - The closest prior work: it learns urban suitability from where built-up land already is. That's our state RF and, conceptually, our similarity score.
  - It's also the clearest example of the problems our design avoids:
    1. **Own-cell leakage:** land use is an input factor. In our prototype, own-cell LULC fractions alone separated built from non-built with AUC 1.0, which is why decision D4 bans them from model inputs.
    2. **Random-split inflation:** neighbouring 30 m cells end up in both train and test.
    3. **No test against later growth:** we validate on persistent growth from 2018/19 to 2022/23 (D3, D7).
  - Its negatives are protected land, not ordinary non-built land, which makes the classification easier than "where will growth happen next".

### H2. Wang et al. (2021): MaxEnt-CA, Luoyang

- **Citation:** Wang, R., He, W., Wu, D., Zhang, L. & Li, Y. (2021). *Urban land expansion simulation considering the diffusional and aggregated growth simultaneously: a case study of Luoyang City.* Sustainability, 13(17), 9781. https://doi.org/10.3390/su13179781
- **Study area:** Luoyang, Henan, China.
- **Data:** urban land 2009 and 2018, plus driving factors *(factor list to verify)*.
- **Method:** a **MaxEnt** model (maximum entropy, from species-distribution modelling) uses existing urban land as **presence-only** data to estimate a probability surface. A category-selected CA (MaxEnt-CSCA) then simulates two growth types at the same time: **aggregated** (next to existing urban land) and **diffusional** (scattered).
- **Validation:** simulated 2009 → 2018 against actual 2018. Overall Kappa 0.78. Aggregated growth simulated with 47.40 % accuracy, diffusional with 37.13 %. Projection to 2035.
- **Key findings:** treating the two growth types separately helps. Diffusional growth is much harder to predict than aggregated growth.
- **Relevance to us:**
  - **Same framing** as our similarity idea: "a building exists at A, so find places like A" is a presence-only problem.
  - Their aggregated vs diffusional split is the same idea as our **LEI breakdown** (adjacent vs outlying growth, A6.3). We should expect our models to do worse on outlying growth too.
  - MaxEnt could be a third scoring model (the validation harness accepts any C8 score file). It needs an extra package (e.g. `elapid`), so given the deadline it stays a **discussion point** unless time allows.

### H3. Ahmadlou et al. (2016): random forest with ROC and TOC

- **Citation:** Ahmadlou, M., Delavar, M. R., Shafizadeh-Moghadam, H. & Tayyebi, A. (2016). *Modeling urban dynamics using random forest: implementing ROC and TOC for model evaluation.* International Archives of the Photogrammetry, Remote Sensing and Spatial Information Sciences, XLI-B2, 285–290. https://isprs-archives.copernicus.org/articles/XLI-B2/285/2016/
- **Study area:** *(to verify)*.
- **Data:** multi-temporal Landsat imagery, 1985, 2000 and 2015. Predictor list *(to verify)*.
- **Method:** a random forest produces a suitability map for land-use change to urban, with variable importance reported.
- **Validation:** the suitability map is overlaid with the map of **observed later change**. ROC AUC 82.48 %, complemented by the **TOC** (total operating characteristic).
- **Key findings:** RF gives a well-performing change-suitability surface. TOC adds information that ROC hides: how many cells are flagged at each threshold.
- **Relevance to us:**
  - The **same validation design** as ours: build the score at an earlier date, test it against change that happened afterwards.
  - It supports reporting **TOC next to ROC** (D7, FR-8.3). Cite it with Pontius & Si (2014).
  - Its AUC of about 0.82 gives a realistic reference level for temporal validation, compared with the 0.99 of random-split studies such as H1.

### H4. Liu et al. (2017): FLUS

- **Citation:** Liu, X., Liang, X., Li, X., Xu, X., Ou, J., Chen, Y., Li, S., Wang, S. & Pei, F. (2017). *A future land use simulation model (FLUS) for simulating multiple land use scenarios by coupling human and natural effects.* Landscape and Urban Planning, 168, 94–116. https://doi.org/10.1016/j.landurbplan.2017.09.019
- **Study area:** China.
- **Data:** land use 2000 and 2010, plus human and natural driving factors.
- **Method:**
  - An artificial neural network, trained on land use and driving factors, estimates a **probability-of-occurrence** surface for each land-use type.
  - A cellular automaton (self-adaptive inertia and competition) then allocates land use over time.
  - Four scenarios are run for 2010–2050.
- **Validation:** simulated 2000 → 2010 against actual 2010. Higher accuracy than CLUE-S and standard CA models.
- **Key findings:** coupling a learned suitability surface with CA allocation reproduces observed change better than older models.
- **Relevance to us:**
  - The standard, heavily cited reference for a **learned suitability surface**. Its probability-of-occurrence step corresponds to our RF and similarity scores.
  - The CA / scenario part is **out of scope**: we rank *where*, not *when* (PRD §3.2).

### H5. Pijanowski et al. (2002): Land Transformation Model

- **Citation:** Pijanowski, B. C., Brown, D. G., Shellito, B. A. & Manik, G. A. (2002). *Using neural networks and GIS to forecast land use changes: a Land Transformation Model.* Computers, Environment and Urban Systems, 26(6), 553–575. https://doi.org/10.1016/S0198-9715(01)00015-1
- **Study area:** *(to verify; a Michigan, USA watershed)*.
- **Data and features:** distance to roads, rivers and existing urban land, plus **neighbourhood window** predictors *(3 × 3 to 9 × 9 cells: to verify in the full text)*.
- **Method:** a GIS-coupled artificial neural network learns which cell conditions precede conversion to urban.
- **Validation:** against observed later land-use change *(metric and values to verify)*.
- **Key findings:** an early demonstration that a neural network on simple GIS predictors can forecast where land changes.
- **Relevance to us:** the classic ancestor of our **context-profile** approach. Distances plus neighbourhood windows correspond to our distance features plus 250 / 500 m ring fractions.

### H6. Roberts et al. (2017): cross-validation for structured data

- **Citation:** Roberts, D. R., Bahn, V., Ciuti, S., Boyce, M. S., Elith, J., Guillera-Arroita, G., Hauenstein, S., Lahoz-Monfort, J. J., Schröder, B., Thuiller, W., Warton, D. I., Wintle, B. A., Hartig, F. & Dormann, C. F. (2017). *Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure.* Ecography, 40(8), 913–929. https://doi.org/10.1111/ecog.02881
- **Study area:** none (methods review with simulations).
- **Method:** compares random and **blocked** cross-validation for data whose observations are not independent.
- **Key findings:** with spatial or temporal dependence, random CV gives over-optimistic error estimates. Blocking (by space, time or group) gives more honest estimates of predictive performance.
- **Relevance to us:**
  - The methodological basis for our **2 km spatial blocks**, used for RF hyperparameter tuning and for out-of-fold scores of models trained on growth labels (D11, FR-6.6, FR-6.8).
  - It also supports the time-travel rule (D12), since temporal structure is one of the cases it covers.

### H7. Ploton et al. (2020): spatial validation of mapping models

- **Citation:** Ploton, P., Mortier, F., Réjou-Méchain, M., et al. (2020). *Spatial validation reveals poor predictive performance of large-scale ecological mapping models.* Nature Communications, 11, 4540. https://doi.org/10.1038/s41467-020-18321-y
- **Study area:** Central Africa (forest aboveground biomass, from an inventory of 11.8 million trees).
- **Method:** a random forest maps biomass from multispectral and environmental predictors, evaluated with random vs **spatial** cross-validation.
- **Key findings:**
  - Random CV suggested a good model.
  - Spatial CV showed almost no predictive power beyond the training locations, because nearby samples leaked information.
- **Relevance to us:** a well-known, concrete example of the leakage our rules (D4, D11, D12) guard against. It's also a good citation for why "RF spatial-CV AUC on a trivial task" is **not** one of our success metrics (D7).

---

## Synthesis (P1.4, draft)

### ML / validation part (Harsh, draft)

**1. Learning suitability from where development already is** is well established:
- neural networks: Pijanowski et al. 2002; FLUS (Liu et al. 2017)
- random forests: Ahmadlou et al. 2016; Li et al. 2024
- presence-only MaxEnt: Wang et al. 2021

They share a core of predictors with our feature table: distance to roads, rivers and existing urban land, terrain, and neighbourhood land use.

**2. Validation is the weak point.** Two common patterns inflate accuracy:
- Studies that test on a random split of the same date report very high AUC (0.98–0.99 in Li et al. 2024).
- Including the cell's own land use as an input makes the task close to trivial.

Studies that test against *later observed change* report more modest values, such as AUC 0.82 (Ahmadlou et al. 2016). Roberts et al. (2017) and Ploton et al. (2020) show in general why random CV over-states performance on spatial data.

**3. Growth type matters.** Wang et al. (2021) find scattered (diffusional) growth much harder to predict than growth next to existing urban land. We test this with the LEI split.

**4. What our project adds:**
- **Strict temporal validation** on *persistent* growth (2018/19 → 2022/23), with leakage rules:
  - no own-cell LULC;
  - OSM snapshots from the baseline date;
  - out-of-fold scores;
  - the time-travel rule.
- **Simple baselines are always reported** (random, distance-to-built, MCDA), so improvements are measured honestly.
- **A per-building similarity query** (find locations B similar to an existing building A, with a per-feature explanation). None of the reviewed papers does this. They all score land from presence or change patterns, not by similarity to a specific reference building.

### MCDA / LULC part (Abhinav)

*To be written.*

### Combined conclusion (both)

*To be written once both halves are in.*
