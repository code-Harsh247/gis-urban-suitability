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
| A1 | Malczewski, *GIS-based land-use suitability analysis: a critical overview* | 2004 | — (review) | Review of GIS suitability methods: overlay, MCDA, AI-based | — | Defines the MCDA approach our baseline follows; names weight subjectivity as a core weakness | Abhinav |
| A2 | Collins, Steiner & Rushman, *Land-use suitability analysis in the United States: historical development …* | 2001 | USA (review) | History of suitability analysis from McHarg-style hand overlays to GIS | — | Background for the introduction | Abhinav |
| A3 | Mosadeghi et al., *Comparison of Fuzzy-AHP and AHP … urban land-use planning* | 2015 | North-east Gold Coast, Australia | Spatial MCDA weighted with AHP vs Fuzzy-AHP | The two outputs compared | Same option ranking, different zone extents: the weighting method changes *where*, which is the subjectivity argument | Abhinav |
| A4 | Parry, Ganaie & Bhat, *GIS based land suitability analysis using AHP … Srinagar and Jammu* | 2018 | Srinagar, Jammu (India) | GIS-AHP on slope, altitude, LULC, existing amenities; municipal wards | None reported | Typical Indian MCDA study: few criteria, expert weights, no validation | Abhinav |
| A5 | Ramachandra, Aithal & Sanna, *Insights to urban dynamics through landscape spatial pattern analysis* | 2012 | **Bangalore** (India) | Landsat 1973–2010 LULC change + landscape metrics | Classification accuracy *(values to verify)* | Context for our study area: built-up +584 %, vegetation −66 %, water bodies −74 % over four decades | Abhinav |
| A6 | Bharath, Chandan, Vinay & Ramachandra, *Modelling urban dynamics in rapidly urbanising Indian cities* | 2018 | Delhi, Mumbai, Pune, Chennai, Coimbatore | CA-Markov with growth agents (soft computing) | *(to verify)* | Indian growth-modelling context: agents (industry, infrastructure) drive growth more than biophysical factors | Abhinav |
| H1 | Li et al., *Spatial suitability evaluation … random forest: Yulin* | 2024 | Yulin, China | RF on built-up (presence) vs protected land, 30 m cells, 25 factors | Random 70/30 split, AUC 0.99 (urban) | Closest prior work; shows the own-cell leakage and random-split inflation we avoid | Harsh |
| H2 | Wang et al., *Urban land expansion … diffusional and aggregated growth: Luoyang* | 2021 | Luoyang, China | MaxEnt (presence-only) + category-selected CA | 2009 → 2018 simulation, Kappa 0.78 | Presence-only framing like ours; aggregated vs diffusional = our LEI split | Harsh |
| H3 | Ahmadlou et al., *Modeling urban dynamics using random forest: ROC and TOC* | 2016 | Rasht, Gilan, Iran (~180 km²) | RF suitability for urban change, Landsat 1985 / 2000 / 2015 | Against observed change; ROC AUC 82.48 % + TOC | Same temporal-validation design; backs ROC + TOC (D7) | Harsh |
| H4 | Liu et al., *A future land use simulation model (FLUS)* | 2017 | China | ANN probability-of-occurrence + CA | Simulated 2000 → 2010 vs actual; beats CLUE-S and CA | Standard reference for "learned suitability surface" | Harsh |
| H5 | Pijanowski et al., *Land Transformation Model* | 2002 | Grand Traverse Bay Watershed, Michigan, USA | ANN + GIS on distance and neighbourhood predictors, 100 m cells | 46 % of the 1980–90 changed cells predicted (same period, not independent) | Ancestor of our context-profile features | Harsh |
| H6 | Roberts et al., *Cross-validation strategies for data with … spatial … structure* | 2017 | — (methods review) | Blocked cross-validation | Shows random CV underestimates error on structured data | Basis for spatial blocks (D11, FR-6.8) | Harsh |
| H7 | Ploton et al., *Spatial validation reveals poor predictive performance of large-scale ecological mapping models* | 2020 | Central Africa | RF biomass mapping | Random vs spatial CV | Concrete case of spatial leakage inflating accuracy | Harsh |
| H8 | Liu et al., *A new landscape index for quantifying urban expansion …* (LEI) | 2010 | Dongguan, Guangdong, China (1988–2006) | Landscape Expansion Index for growth patches | — | Source of our growth-type labels (`lei_type`) | Harsh |
| H9 | Pontius & Si, *The total operating characteristic …* (TOC) | 2014 | — (methods) | TOC curve | — | Source of the TOC metric (D7) | Harsh |
| H10 | Valavi et al., *blockCV: … spatially or environmentally separated folds …* | 2019 | — (methods / software) | Spatial / environmental blocking for k-fold CV | — | Practical reference for our 2 km spatial blocks | Harsh |
| D1 | Venter et al., *Global 10 m LULC datasets: a comparison of Dynamic World, World Cover and Esri Land Cover* | 2022 | Global | Accuracy comparison against ground truth | Overall accuracy per product and class | Backs D2 (ESRI for everything); ESRI over-estimates scrub (the Bannerghatta issue) | Harsh (data) |
| D2 | Herfort et al., *… completeness and inequalities of global urban building data in OpenStreetMap* | 2023 | 13,189 urban centres worldwide | ML estimate of OSM building completeness over time | — | Backs choosing the AOI by 2018 OSM coverage (D1, D9) | Harsh (data) |

---

## Abhinav: GIS / MCDA and LULC-based urban growth (P1.2)

> **Reviewed by Abhinav (2026-10-01)** from Harsh's suggestions. Every citation was checked against Crossref / Europe PMC / OpenAlex; details come from the source named in each entry (**Source:**).
> - **Correction:** the suggested A5 (Ramachandra, Bharath & Sowmyashree 2015, *J. Env. Mgmt* 148, 67–81) studies **Delhi**, not Bengaluru: its abstract says *"This communication quantifies the urbanisation and associated growth pattern in Delhi"*. It was replaced by a Bangalore paper from the same IISc group (new A5).
> - A6 also does **not** include Bengaluru.
> - Items marked *(to verify)* need the full text (available through the institute library) before they're cited in the report.

### A1. Malczewski (2004): GIS-MCDA review

- **Citation:** Malczewski, J. (2004). *GIS-based land-use suitability analysis: a critical overview.* Progress in Planning, 62(1), 3–65. https://doi.org/10.1016/j.progress.2003.09.002
- **Study area:** none (review).
- **Data:** none (review of the literature).
- **Method:** reviews GIS-based land-use suitability analysis in three groups:
  1. computer-assisted overlay mapping (Boolean and weighted overlay);
  2. multicriteria decision analysis (weighted linear combination, AHP-derived weights, ideal-point methods);
  3. "soft computing" / AI approaches (fuzzy logic, neural networks, cellular automata, genetic algorithms).
- **Criteria / weights:** criteria are problem-specific; weights usually come from expert judgement (rating, ranking, pairwise comparison).
- **Validation:** the review notes that suitability maps are rarely validated against outcomes.
- **Key findings:** GIS made suitability analysis routine, but results depend heavily on subjective choices (criteria, standardisation, weights) and on data uncertainty. Methods for handling that uncertainty and for involving stakeholders are the main open problems.
- **Source:** the abstract isn't openly available; the summary follows how the paper is widely cited *(to verify against the full text)*.
- **Relevance:**
  - The standard reference for the MCDA framework our baseline (`mcda`, FR-7.1) follows.
  - Its point that weights are subjective and results rarely validated is exactly what our design answers: learned scores plus temporal validation against real growth.

### A2. Collins, Steiner & Rushman (2001): history of suitability analysis

- **Citation:** Collins, M. G., Steiner, F. R. & Rushman, M. J. (2001). *Land-use suitability analysis in the United States: historical development and promising technological achievements.* Environmental Management, 28(5), 611–621. https://doi.org/10.1007/s002670010247
- **Study area:** USA (review).
- **Data:** none (historical review).
- **Method:** traces land-use suitability analysis (LUSA) through **six eras**, from hand-drawn overlays (popularised by McHarg's *Design with Nature*, 1969) to computer- and GIS-based methods.
- **Key findings:** the core idea has stayed the same (map factors, rate them by suitability, overlay them into a composite), while the tools have moved from transparent hand overlays to GIS. The authors point to further technology (e.g. decision-support and artificial-intelligence tools) as promising.
- **Validation:** — (review).
- **Source:** bibliographic record + summaries of the paper in later literature (abstract withheld by the publisher) *(eras: to verify against the full text)*.
- **Relevance:** history for the report introduction. Our project is a "next era" step: the factor map is learned from where development actually happened.

### A3. Mosadeghi et al. (2015): AHP vs Fuzzy-AHP for urban land-use planning

- **Citation:** Mosadeghi, R., Warnken, J., Tomlinson, R. & Mirfenderesk, H. (2015). *Comparison of Fuzzy-AHP and AHP in a spatial multi-criteria decision making model for urban land-use planning.* Computers, Environment and Urban Systems, 49, 54–65. https://doi.org/10.1016/j.compenvurbsys.2014.10.001
- **Study area:** north-east Gold Coast, Queensland, Australia (large-scale urban planning scenario).
- **Data:** spatial planning criteria layers *(full list: to verify)*.
- **Method:** the same spatial MCDA model run with **AHP** and with **Fuzzy-AHP** weights; the land-use zones they produce are compared.
- **Validation:** comparison of the two outputs (no test against real outcomes).
- **Key findings:**
  - The two methods agree on **which** development options rank best.
  - The **spatial extents** of the selected zones differ.
  - The authors' advice: plain AHP is enough to pick options early on; to draw boundaries, combine two or more MCDA techniques (e.g. their intersection).
- **Source:** publisher page and summaries of the abstract.
- **Relevance:** direct evidence that the weighting method alone changes *where* an MCDA puts development, which is the subjectivity our data-driven scores avoid. Also a reference for our AHP consistency-ratio check (FR-7.1).

### A4. Parry, Ganaie & Bhat (2018): GIS-AHP urban suitability, Srinagar and Jammu

- **Citation:** Parry, J. A., Ganaie, S. A. & Bhat, M. S. (2018). *GIS based land suitability analysis using AHP model for urban services planning in Srinagar and Jammu urban centers of J&K, India.* Journal of Urban Management, 7(2), 46–56. https://doi.org/10.1016/j.jum.2018.05.002
- **Study area:** Srinagar and Jammu, India.
- **Data:** slope and altitude (DEM), land use / land cover, and the existing status of urban amenities, per **municipal ward**.
- **Method:** AHP-weighted overlay of geo-physical and socio-economic criteria to find land suitable for new urban amenities (services).
- **Criteria:** slope, altitude, land use / land cover, existing amenity status *(AHP weights and consistency ratio: to verify in the full text)*.
- **Validation:** none reported in the abstract.
- **Key findings:** both cities grew fast over the last 30 years, leading to leap-frog development and uneven amenities; the AHP maps show where amenities are lacking and where they could go.
- **Source:** full abstract (via OpenAlex); the paper is open access.
- **Relevance:**
  - A typical Indian urban MCDA study: a handful of criteria, expert weights, ward-level units, **no validation**. That's the "classic method" our MCDA baseline reproduces.
  - Slope and LULC are shared with our feature set; altitude is in our terrain group.

### A5. Ramachandra, Aithal & Sanna (2012): Bangalore urban dynamics from landscape patterns

- **Citation:** Ramachandra, T. V., Aithal, B. H. & Sanna, D. D. (2012). *Insights to urban dynamics through landscape spatial pattern analysis.* International Journal of Applied Earth Observation and Geoinformation, 18, 329–343. https://doi.org/10.1016/j.jag.2012.03.005
- **Study area:** **Bangalore (Bengaluru)**, India: the city and its surroundings.
- **Data:**
  - Landsat MSS (57.5 m) for 1973;
  - Landsat TM / ETM+ (28.5 m) for 1992, 1999, 2002, 2006 and 2010;
  - Survey of India topographic sheets, BBMP ward boundaries, 2001 census population, GPS ground control.
- **Method:** multi-date land-use classification, then landscape (spatial pattern) metrics to describe how the urban form changed *(classifier and metric list: to verify)*.
- **Validation:** classification accuracy assessment *(values to verify)*.
- **Key findings:**
  - Built-up area grew **584 %** over the four decades, while **vegetation fell 66 %** and **water bodies 74 %**.
  - Growth of built-up area per period: 342.83 % (1973–1992), 129.56 % (1992–1999), 106.7 % (1999–2002), 114.51 % (2002–2006), 126.19 % (2006–2010).
- **Source:** the authors' open online version of the paper (IISc Energy & Wetlands Research Group).
- **Relevance:**
  - Context for **our study area**: Bengaluru has grown fast for decades, mostly at the expense of vegetation and lakes / tanks.
  - That's why our exclusion mask matters (water, vegetated lakes such as Hulimavu, the Bannerghatta forest), and why there's enough growth to validate against.

**Replaced suggestion (not used):** Ramachandra, T. V., Bharath, A. H. & Sowmyashree, M. V. (2015). *Monitoring urbanization and its implications in a mega city from space.* J. Environmental Management, 148, 67–81. https://doi.org/10.1016/j.jenvman.2014.02.015. It studies **Delhi** (four decades, zones and 1 km concentric circles, Shannon's entropy), so it's not context for Bengaluru.

### A6. Bharath, Chandan, Vinay & Ramachandra (2018): urban dynamics in Indian cities (optional)

- **Citation:** Bharath, H. A., Chandan, M. C., Vinay, S. & Ramachandra, T. V. (2018). *Modelling urban dynamics in rapidly urbanising Indian cities.* The Egyptian Journal of Remote Sensing and Space Science, 21(3), 201–210. https://doi.org/10.1016/j.ejrs.2017.08.002
- **Study area:** five Indian mega cities: **Delhi, Mumbai, Pune, Chennai and Coimbatore** (Bengaluru is not included).
- **Data:** multi-date land-use maps covering about four decades, plus growth "agents" (industrial, infrastructural, socio-economic and biophysical factors).
- **Method:** **CA-Markov** (cellular automata + Markov chain) with agent-based weighting of the growth drivers through soft-computing techniques; future growth visualised for each city.
- **Validation:** *(to verify: the abstract reports no accuracy figures)*.
- **Key findings:**
  - Industrial, infrastructural and socio-economic factors influence urban growth **more than biophysical factors**.
  - Growth concentrates in urban corridors, industrial areas and zones earmarked for development.
- **Source:** full abstract (via Semantic Scholar); the paper is open access.
- **Relevance:**
  - Indian growth-modelling context, from the same IISc group as A5.
  - Its finding that infrastructure-type drivers dominate matches our feature design (roads and nearby built-up as the main context features, terrain secondary). It also fits our prototype, where the near-built group carried most of the signal.
  - Like the CA models in H2/H4, it simulates *when*; we only rank *where* (PRD §3.2).

*Also cited in the PRD (§22), for reference: Saaty (1980), FAO (1976), Karra et al. (2021).*

---

## Harsh: machine learning, presence-based suitability and validation (P1.3)

> **Read and reviewed by Abhinav (2026-10-01)** (Phase 1: each teammate reads the other's summaries). H2, H3 and H5 were checked against their full texts, H8 against the authors' PDF. Their "to verify" fields are now filled. One correction in H5: the 3 × 3 to 9 × 9 windows are a goodness-of-fit metric, not predictors. H1, H4, H6, H7, H9, H10, D1 and D2 were read as summaries; no issues found.

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
- **Data:** built-up land 2009–2018 from China's second national land survey (vector). **8 driving factors:** distance to original built-up land, main roads, the political centre, the commercial centre, the airport and the high-speed rail station; GDP density; density of firms added 2009–2018.
- **Method:** a **MaxEnt** model (maximum entropy, from species-distribution modelling) uses existing urban land as **presence-only** data to estimate a probability surface. A category-selected CA (MaxEnt-CSCA) then simulates two growth types at the same time: **aggregated** (next to existing urban land) and **diffusional** (scattered).
- **Validation:** simulated 2009 → 2018 against actual 2018. Overall accuracy 87.65 %, Kappa 0.78 (Base-CA 0.71, MaxEnt-CA 0.74). Aggregated growth simulated with 47.40 % accuracy. The abstract gives 37.13 % for diffusional growth, the results section 34.13 % (an inconsistency in the paper). Projection to 2035.
- **Key findings:** treating the two growth types separately helps. Diffusional growth is much harder to predict than aggregated growth.
- **Relevance to us:**
  - **Same framing** as our similarity idea: "a building exists at A, so find places like A" is a presence-only problem.
  - Their aggregated vs diffusional split is the same idea as our **LEI breakdown** (adjacent vs outlying growth, A6.3). We should expect our models to do worse on outlying growth too.
  - MaxEnt could be a third scoring model (the validation harness accepts any C8 score file). It needs an extra package (e.g. `elapid`), so given the deadline it stays a **discussion point** unless time allows.

### H3. Ahmadlou et al. (2016): random forest with ROC and TOC

- **Citation:** Ahmadlou, M., Delavar, M. R., Shafizadeh-Moghadam, H. & Tayyebi, A. (2016). *Modeling urban dynamics using random forest: implementing ROC and TOC for model evaluation.* International Archives of the Photogrammetry, Remote Sensing and Spatial Information Sciences, XLI-B2, 285–290. https://isprs-archives.copernicus.org/articles/XLI-B2/285/2016/
- **Study area:** Rasht, capital of Gilan Province, Iran (~180 km², Caspian coast).
- **Data:** Landsat TM / ETM+ for 1985, 2000 and 2015, classified into 5 classes (Kappa 0.86–0.88), 30 m. **11 predictors:** distance to agriculture, sea, built-up, rivers, forest and roads; DEM, slope, aspect; easting and northing.
- **Method:** a random forest produces a suitability map for land-use change to urban, with variable importance reported.
- **Validation:** calibrated on 1985 → 2000 change, tested on 2000 → 2015. The top 68,313 cells (= the observed amount of change) contained 44,476 real changes (65 %). ROC AUC 82.48 %, complemented by the **TOC** (total operating characteristic).
- **Key findings:** RF gives a well-performing change-suitability surface. TOC adds information that ROC hides: how many cells are flagged at each threshold.
- **Relevance to us:**
  - The **same validation design** as ours: build the score at an earlier date, test it against change that happened afterwards.
  - It supports reporting **TOC next to ROC** (D7, FR-8.3). Cite it with Pontius & Si (2014).
  - Its AUC of about 0.82 gives a realistic reference level for temporal validation, compared with the 0.99 of random-split studies such as H1.
  - Caution: easting and northing are among its strongest predictors. Raw coordinates memorise *where* growth happened in the training period; we don't use them.

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
- **Study area:** Grand Traverse Bay Watershed, Michigan, USA (six counties). 1980 land use rasterised at **100 × 100 m**, the same cell size as ours.
- **Data and features:** **10 predictors:** agricultural density within 1 km (a neighbourhood feature); distance to highways, county roads, residential streets, inland lakes, the Lake Michigan shore, rivers, 1980 urban land and recreation sites; "quality of views" from the DEM. Exclusion zones (urban, water, wetlands, public land) are multiplied into one mask.
  - **Correction:** the 3 × 3 to 9 × 9 windows in the paper are its *scalable-window goodness-of-fit metric*, not predictors.
- **Method:** a GIS-coupled artificial neural network learns which cell conditions precede conversion to urban.
- **Validation:** the top 2,073 cells (= observed 1980–1990 change in Grand Traverse County) contained 941 real changes (**46 %**), rising to 65 % within a 1 km window. Training used every other cell of the **same** period and county, so this is not an independent forward test. Variable importance by dropping one predictor at a time.
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
- **Study area:** Dongguan, Guangdong, China, 1988–2006 (Landsat TM, 30 m: 1988, 1993, 1997, 2001, 2006).
- **Method:** the **LEI** scores each new urban patch from a buffer around it:
  - LEI = 100 × A₀ / (A₀ + A_v), where A₀ is the buffer area on old urban land and A_v the buffer area on vacant land;
  - **infilling** if LEI > 50, **edge-expansion** if 0 < LEI ≤ 50, **outlying** if LEI = 0;
  - buffer of 1 m (vector patches); the paper notes LEI depends on the buffer distance.
- **Key findings:** outlying growth dominated early (47 % of new patches in 1988–1993); later, edge-expansion took over (70 %) and outlying fell to 8–14 %.
- **Relevance:**
  - The source of our `lei_type` label (C5, A4.3). We merge infilling + edge-expansion into `adjacent` (LEI > 0), and keep `outlying` (LEI = 0).
  - Our buffer is 20 m on 10 m pixels: on a raster the smallest buffer is one pixel, and two pixels tolerate the one-pixel gaps in ESRI built-up maps. Mention this in the methods.
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

**1. Common criteria.** GIS suitability studies combine a small set of physical and access criteria:
- terrain: slope and altitude / elevation;
- current land use / land cover;
- proximity: roads, existing built-up land or amenities, water.

Parry et al. (2018, A4) is typical for Indian cities: slope, altitude, LULC and existing amenities, at municipal-ward level. Our feature table has the same core (slope, elevation, LULC context, distance to roads, built-up and water), at 100 m cells instead of wards.

**2. Typical weights.**
- Weights are set by **expert judgement**, usually AHP pairwise comparison with a consistency-ratio check (Malczewski 2004, A1). They differ from study to study and from expert to expert.
- The weighting method itself changes the result: AHP and Fuzzy-AHP on the same criteria ranked the development options the same way but drew **different zone boundaries** (Mosadeghi et al. 2015, A3).
- So an MCDA map says as much about the weights as about the land. That's the subjectivity our learned scores avoid (and why our MCDA baseline reports its consistency ratio and is compared on equal terms, decision D7).

**3. Common validation methods.** Mostly **none**, or indirect:
- MCDA maps are rarely checked against what actually happened (A1). A4 reports no validation.
- A3 compares two MCDA outputs with each other, not with outcomes.
- LULC-change studies validate the *classification* (accuracy of the land-cover maps, A5), not a suitability score.
- Growth-simulation studies (A6, CA-Markov) compare simulated with observed maps, which tests *how much* and *when* rather than a ranking of *where*.

**4. What the LULC literature tells us about the study area.**
- Bengaluru's built-up area grew 584 % in four decades while vegetation fell 66 % and water bodies 74 % (Ramachandra et al. 2012, A5). Growth has eaten into exactly the land our exclusion mask protects (lakes, vegetated lakes, forest).
- Across Indian mega cities, infrastructure and economic "agents" drive growth more than biophysical factors (Bharath et al. 2018, A6). That's consistent with our design: road access and nearby built-up are the main context features, and terrain is secondary.

**5. The gap.** The MCDA literature (since the overlay methods traced by Collins et al. 2001, A2) answers "where *should* development go, given these expert weights?". It doesn't learn from where development actually happened, and it doesn't test its maps against later growth.

### Combined conclusion (both)

> Drafted by Abhinav from both halves (2026-10-01); **Harsh to review**.

Two families of methods rank land for urban development:
- **Expert MCDA** (A1–A4): transparent and easy to explain, but its weights are subjective. A3 shows the weighting method alone moves zone boundaries, and the maps are almost never validated against real growth.
- **Learned suitability** (H1–H5): learns from where development already is or recently happened, so the weights come from data. But validation is often optimistic: random splits of one date, the cell's own land use as an input, and no test against later change (H1 vs H3; H6, H7 explain why).

Our project combines the strengths and closes the gaps:
1. **One honest test for every method.** Every score, including the expert MCDA baseline, is validated the same way: against **persistent growth from 2018/19 to 2022/23** in Bengaluru, a city with documented fast growth (A5).
   - It's reported as ROC, TOC and lift over random (H3, H9);
   - with baselines (random, distance to built-up);
   - split by growth type (H8, H2).
2. **Leakage rules.** No own-cell LULC in model inputs, OSM snapshots from the baseline date, the time-travel rule and out-of-fold scores (H1, H6, H7, H10).
3. **A per-building similarity query.** "Find land whose surroundings resemble building A", with a per-feature explanation. None of the reviewed papers offers this: MCDA scores land against expert weights, and learned models score it against a whole class (built / changed), not against a specific reference building.
4. **Data choices backed by the literature.** ESRI LULC for everything (paper D1) and OSM coverage at the baseline date (paper D2).
