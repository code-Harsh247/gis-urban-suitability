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
| A1 | Malczewski, *GIS-based land-use suitability analysis: a critical overview* | 2004 | — (review) | Review of GIS-MCDA suitability methods | — | Defines the MCDA approach our baseline follows | Abhinav *(suggested)* |
| A2 | Collins et al., *Land-use suitability analysis in the United States: historical development …* | 2001 | USA (review) | History of overlay / GIS suitability analysis | — | Background for the introduction | Abhinav *(suggested)* |
| A3 | Mosadeghi et al., *Comparison of Fuzzy-AHP and AHP … urban land-use planning* | 2015 | Gold Coast, Australia | GIS-MCDA with AHP vs Fuzzy-AHP weights | Comparison of the two outputs | Shows how sensitive results are to the weighting: the subjectivity argument | Abhinav *(suggested)* |
| A4 | Parry et al., *GIS based land suitability analysis using AHP … Srinagar and Jammu* | 2018 | Srinagar, Jammu (India) | GIS-AHP urban suitability | *(to verify)* | Typical Indian urban MCDA study we compare against | Abhinav *(suggested)* |
| A5 | Ramachandra et al., *Monitoring urbanization and its implications in a mega city from space* | 2015 | Bengaluru (India) | Multi-date remote-sensing LULC change + landscape metrics | *(to verify)* | Context for our study area: growth, loss of vegetation and lakes | Abhinav *(suggested)* |
| A6 | Bharath et al., *Modelling urban dynamics in rapidly urbanising Indian cities* | 2018 | Indian cities *(which: to verify)* | Urban growth modelling | *(to verify)* | Indian growth-modelling context (optional) | Abhinav *(suggested)* |
| H1 | Li et al., *Spatial suitability evaluation … random forest: Yulin* | 2024 | Yulin, China | RF on built-up (presence) vs protected land, 30 m cells, 25 factors | Random 70/30 split, AUC 0.99 (urban) | Closest prior work; shows the own-cell leakage and random-split inflation we avoid | Harsh |
| H2 | Wang et al., *Urban land expansion … diffusional and aggregated growth: Luoyang* | 2021 | Luoyang, China | MaxEnt (presence-only) + category-selected CA | 2009 → 2018 simulation, Kappa 0.78 | Presence-only framing like ours; aggregated vs diffusional = our LEI split | Harsh |
| H3 | Ahmadlou et al., *Modeling urban dynamics using random forest: ROC and TOC* | 2016 | *(to verify)* | RF suitability for urban change, Landsat 1985 / 2000 / 2015 | Against observed change; ROC AUC 82.48 % + TOC | Same temporal-validation design; backs ROC + TOC (D7) | Harsh |
| H4 | Liu et al., *A future land use simulation model (FLUS)* | 2017 | China | ANN probability-of-occurrence + CA | Simulated 2000 → 2010 vs actual; beats CLUE-S and CA | Standard reference for "learned suitability surface" | Harsh |
| H5 | Pijanowski et al., *Land Transformation Model* | 2002 | *(to verify)* | ANN + GIS on distance and neighbourhood predictors | Against later observed change *(to verify)* | Ancestor of our context-profile features | Harsh |
| H6 | Roberts et al., *Cross-validation strategies for data with … spatial … structure* | 2017 | — (methods review) | Blocked cross-validation | Shows random CV underestimates error on structured data | Basis for spatial blocks (D11, FR-6.8) | Harsh |
| H7 | Ploton et al., *Spatial validation reveals poor predictive performance of large-scale ecological mapping models* | 2020 | Central Africa | RF biomass mapping | Random vs spatial CV | Concrete case of spatial leakage inflating accuracy | Harsh |
| H8 | Liu et al., *A new landscape index for quantifying urban expansion …* (LEI) | 2010 | Dongguan, China *(to verify)* | Landscape Expansion Index for growth patches | — | Source of our growth-type labels (`lei_type`) | Harsh |
| H9 | Pontius & Si, *The total operating characteristic …* (TOC) | 2014 | — (methods) | TOC curve | — | Source of the TOC metric (D7) | Harsh |
| H10 | Valavi et al., *blockCV: … spatially or environmentally separated folds …* | 2019 | — (methods / software) | Spatial / environmental blocking for k-fold CV | — | Practical reference for our 2 km spatial blocks | Harsh |
| D1 | Venter et al., *Global 10 m LULC datasets: a comparison of Dynamic World, World Cover and Esri Land Cover* | 2022 | Global | Accuracy comparison against ground truth | Overall accuracy per product and class | Backs D2 (ESRI for everything); ESRI over-estimates scrub (the Bannerghatta issue) | Harsh (data) |
| D2 | Herfort et al., *… completeness and inequalities of global urban building data in OpenStreetMap* | 2023 | 13,189 urban centres worldwide | ML estimate of OSM building completeness over time | — | Backs choosing the AOI by 2018 OSM coverage (D1, D9) | Harsh (data) |

---

## Abhinav: GIS / MCDA and LULC-based urban growth (P1.2)

> **Suggested by Harsh (2026-10-01), for Abhinav to review.** The citations are checked against Crossref or publisher pages. The method / validation details below are from the abstracts only, so read each paper and fill in or correct the fields before ticking P1.2. Swap any paper for a better one.

### A1. Malczewski (2004): GIS-MCDA review

- **Citation:** Malczewski, J. (2004). *GIS-based land-use suitability analysis: a critical overview.* Progress in Planning, 62(1), 3–65.
- **Study area:** none (review).
- **Method:** reviews GIS-based land-use suitability approaches: overlay, MCDA and AI methods.
- **Relevance:** the standard reference for the MCDA framework our baseline (`mcda`, FR-7.1) follows. It also discusses the subjectivity of criterion weights, which our data-driven models aim to reduce.
- **To fill (Abhinav):** key findings, typical criteria and weighting methods.

### A2. Collins, Steiner & Rushman (2001): history of suitability analysis

- **Citation:** Collins, M. G., Steiner, F. R. & Rushman, M. J. (2001). *Land-use suitability analysis in the United States: historical development and promising technological achievements.* Environmental Management. https://doi.org/10.1007/s002670010247
- **Study area:** USA (review).
- **Method:** traces suitability analysis from hand-drawn map overlays to GIS-based methods.
- **Relevance:** background and history for the report introduction.
- **To fill (Abhinav):** key findings.

### A3. Mosadeghi et al. (2015): AHP vs Fuzzy-AHP for urban land-use planning

- **Citation:** Mosadeghi, R., Warnken, J., Tomlinson, R. & Mirfenderesk, H. (2015). *Comparison of Fuzzy-AHP and AHP in a spatial multi-criteria decision making model for urban land-use planning.* Computers, Environment and Urban Systems, 49, 54–65.
- **Study area:** north-east Gold Coast, Queensland, Australia.
- **Method:** a spatial MCDA for urban land-use planning, weighted with AHP and with Fuzzy-AHP, and the outcomes compared.
- **Relevance:** shows how the choice of weighting method changes an MCDA result. That supports our point that hand-set weights are subjective, and it's a reference for our AHP consistency-ratio check.
- **To fill (Abhinav):** criteria used, size of the differences found.

### A4. Parry, Ganaie & Bhat (2018): GIS-AHP urban suitability, Srinagar and Jammu

- **Citation:** Parry, J. A., Ganaie, S. A. & Bhat, M. S. (2018). *GIS based land suitability analysis using AHP model for urban services planning in Srinagar and Jammu urban centers of J&K, India.* Journal of Urban Management, 7(2), 46–56. https://doi.org/10.1016/j.jum.2018.05.002
- **Study area:** Srinagar and Jammu, India.
- **Method:** GIS overlay with AHP weights for urban services planning.
- **Relevance:** a typical Indian urban MCDA study, close to what our MCDA baseline reproduces. Useful for listing the criteria and weights that Indian studies use.
- **To fill (Abhinav):** criteria, weights, validation (if any).

### A5. Ramachandra, Bharath & Sowmyashree (2015): Bengaluru urbanisation from space

- **Citation:** Ramachandra, T. V., Bharath, A. H. & Sowmyashree, M. V. (2015). *Monitoring urbanization and its implications in a mega city from space: spatiotemporal patterns and its indicators.* Journal of Environmental Management, 148, 67–81.
- **Study area:** Bengaluru, India.
- **Method:** multi-date remote-sensing land-use change with spatial / landscape metrics.
- **Relevance:**
  - Context for our **study area**: how fast Bengaluru has grown and its loss of vegetation and water bodies (lakes / tanks).
  - That loss is why our water mask and protected-area mask matter.
- **To fill (Abhinav):** the periods covered, growth figures, main findings.

### A6. Bharath, Chandan, Vinay & Ramachandra (2018): urban dynamics in Indian cities (optional)

- **Citation:** Bharath, H. A., Chandan, M. C., Vinay, S. & Ramachandra, T. V. (2018). *Modelling urban dynamics in rapidly urbanising Indian cities.* The Egyptian Journal of Remote Sensing and Space Science, 21(3), 201–210. https://doi.org/10.1016/j.ejrs.2017.08.002
- **Study area:** rapidly urbanising Indian cities *(check whether Bengaluru is included)*.
- **Method:** urban growth modelling *(model type to verify)*.
- **Relevance:** Indian growth-modelling context; optional if A1–A5 are enough.

*Also cited in the PRD (§22), for reference: Saaty (1980), FAO (1976), Karra et al. (2021).*

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

### H8. Liu et al. (2010): Landscape Expansion Index (LEI)

- **Citation:** Liu, X., Li, X., Chen, Y., Tan, Z., Li, S. & Ai, B. (2010). *A new landscape index for quantifying urban expansion using multi-temporal remotely sensed data.* Landscape Ecology, 25(5), 671–682. https://doi.org/10.1007/s10980-010-9454-5
- **Study area:** *(to verify; a Chinese city)*.
- **Method:** the **LEI** scores each new urban patch by how much of a buffer around it overlaps existing urban land. This sorts growth into **infilling**, **edge-expansion** and **outlying**.
- **Relevance:**
  - The source of our `lei_type` label (C5, A4.3). We merge infilling + edge-expansion into `adjacent`, and keep `outlying`.
  - It lets us report AUC per growth type, linking to the aggregated vs diffusional finding in H2.

### H9. Pontius & Si (2014): Total Operating Characteristic (TOC)

- **Citation:** Pontius, R. G. Jr. & Si, K. (2014). *The total operating characteristic to measure diagnostic ability for multiple thresholds.* International Journal of Geographical Information Science, 28(3), 570–583. https://doi.org/10.1080/13658816.2013.862623
- **Method:** the **TOC** curve. Like ROC, it plots hits against thresholds, but it also shows the actual number of cells flagged (hits + false alarms) at each threshold.
- **Relevance:** the source of the TOC curve we report for every model (D7, FR-8.3). It's more informative than ROC for maps where growth is a small share of the land. Cited together with H3.

### H10. Valavi et al. (2019): blockCV

- **Citation:** Valavi, R., Elith, J., Lahoz-Monfort, J. J. & Guillera-Arroita, G. (2019). *blockCV: An R package for generating spatially or environmentally separated folds for k-fold cross-validation of species distribution models.* Methods in Ecology and Evolution, 10(2), 225–232. https://doi.org/10.1111/2041-210X.13107
- **Method:** builds CV folds from spatial blocks, spatial / environmental clusters or buffers, so that training and test data are separated.
- **Key findings:** random CV on structured data underestimates prediction error and can lead to the wrong model being chosen.
- **Relevance:** the practical reference for **how** we build the 2 km spatial blocks (FR-6.8, H5.4). H6 (Roberts et al.) is the reference for **why**. We implement the blocks in Python, not with the R package.

---

## Data-source papers (for `docs/data_sources.md` and the report's data chapter)

### D1. Venter et al. (2022): comparison of global 10 m LULC products

- **Citation:** Venter, Z. S., Barton, D. N., Chakraborty, T., Simensen, T. & Singh, G. (2022). *Global 10 m Land Use Land Cover Datasets: A Comparison of Dynamic World, World Cover and Esri Land Cover.* Remote Sensing, 14(16), 4101. https://doi.org/10.3390/rs14164101
- **Method:** compares the three products against global ground-truth data (minimum mapping unit 250 m²).
- **Key findings:**
  - Overall accuracy: **Esri 75 %**, Dynamic World 72 %, WorldCover 65 %.
  - By class: water is best mapped (92 %), then built area (83 %), tree cover (81 %) and crops (78 %).
  - Biases: WorldCover over-estimates grass, **Esri over-estimates shrub / scrub**, Dynamic World over-estimates snow / ice.
- **Relevance:**
  - Supports **D2** (ESRI as the LULC source for everything): the highest overall accuracy, and built area is one of its most reliable classes.
  - Explains the **Bannerghatta issue**: ESRI's scrub bias is why the forest shows up as rangeland, and why we add a protected-area mask and cross-check forest with WorldCover.

### D2. Herfort et al. (2023): OSM building completeness

- **Citation:** Herfort, B., Lautenbach, S., Porto de Albuquerque, J., Anderson, J. & Zipf, A. (2023). *A spatio-temporal analysis investigating completeness and inequalities of global urban building data in OpenStreetMap.* Nature Communications, 14, 3985. https://doi.org/10.1038/s41467-023-39698-6
- **Method:** a machine-learning model estimates the completeness of OSM building footprints over time for 13,189 urban centres.
- **Key findings:**
  - Only 1,848 urban centres (16 % of the urban population) have OSM building data over 80 % complete.
  - 9,163 cities (48 % of the urban population) are below 20 %.
  - Completeness differs hugely between cities and over time.
- **Relevance:** supports choosing the study area by **OSM coverage at the baseline date** (D1, study_area.md) and using the 2018 snapshot for reference buildings (D9). The OSM completeness caveat belongs in the limitations section.

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

**3. Growth type matters.** Wang et al. (2021) find scattered (diffusional) growth much harder to predict than growth next to existing urban land. We test this with the LEI split (Liu et al. 2010) and report TOC next to ROC (Pontius & Si 2014).

**4. Data quality shapes the design.**
- ESRI is the most accurate 10 m LULC product overall but over-estimates scrub (Venter et al. 2022). Hence ESRI for everything, plus a WorldCover cross-check and a protected-area mask.
- OSM building completeness varies strongly between cities and over time (Herfort et al. 2023). Hence the study area was chosen by its OSM coverage in 2018.

**5. What our project adds:**
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
