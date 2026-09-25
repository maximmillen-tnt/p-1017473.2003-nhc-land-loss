# Seismic Fragility Curves for Retaining Walls — Summary

Compiled 17 September 2026. Six representative published fragility function sets, spanning cantilever, gravity, quay and reinforced-soil retaining walls.

## Summary table

| # | Source | Wall type & characterisation attributes | Damage states (EDP & thresholds) | Intensity measure | Method |
|---|---|---|---|---|---|
| 1 | Argyroudis, Kaynia & Pitilakis (2013), *SDEE* 50:106–116 | Cantilever RC wall / bridge abutment on surface footing; **H = 6.0 and 7.5 m**; two soil profiles (strain-dependent stiffness & damping, Mohr–Coulomb); walls dimensioned to pseudo-static design | 4 states (minor / moderate / extensive / collapse) on **permanent vertical ground displacement** (backfill settlement) | **PGA**, free-field ground surface | 2D nonlinear FE time-history; two-parameter lognormal (median, β) |
| 2 | Ichii (2004), 13WCEE Paper 3040 | Gravity **caisson quay wall**, H = 13 m; **aspect ratio W/H = 0.65 / 0.90 / 1.05**; foundation **equivalent SPT N = 5–25**; normalised foundation (liquefiable) thickness **D₁/H = 0–1.0** | 4 degrees on **normalised residual seaward displacement d/H**: **0.05 / 0.10 / 0.20 / 0.30**, calibrated to restoration cost bands | **PGA at base layer** (0.1–0.6 g) | Effective-stress FE (FLIP, strain-space plasticity, liquefaction); MLE-fitted lognormal |
| 3 | Seo, Lee, Park & Kim (2022), *SDEE* 161 | Inverted-T cantilever wall with shear key, **H = 4 m**; **backfill slope 0° / 10° / 20°**; Korean site classes **S2–S5** (bedrock depth, V<sub>s</sub>) | 3 states on **relative wall displacement** = **0.02H / 0.05H / 0.1H** (0.08 / 0.20 / 0.40 m); and on **backfill settlement 0.05 / 0.15 / 0.30 m** | **PGA** (0.1–0.9 g) **+ CAV** — two-parameter fragility *surfaces* | 1D site response → FLAC2D; probabilistic seismic demand model |
| 4 | Cosentini & Bozzoni (2022), *SDEE* 152 | Roadway **gravity earth-retaining walls** (Italy); **trapezoid vs leaning** section; three heights; **flat vs sloped backfill**; >200 analyses | States on **horizontal displacement and rotation** of the wall | **PGV** (optimal) and **PGA**, screened from 35 candidate IMs on efficiency / practicality / proficiency / sufficiency | 2D nonlinear dynamic, 18 real records; validated against 2016 Central Italy damage survey |
| 5 | Li, Li, Cui, Ji, Zhang & Qing (2024), *SDEE* 183 | **Concrete gravity wall**, **H = 9 m** (Wenchuan, China; surveyed population 2–15.4 m); **backfill slope 0° and 12°**; soil and wall material properties randomised | States on **cumulative displacement index at wall top (δ<sub>CDI</sub>)** — captures sliding and overturning | Optimal IM selected via PSDM from three candidates | OpenSees incremental dynamic analysis + Monte Carlo; lognormal (μ, β) |
| 6 | Koutsoupaki, Sotiriadis, Klimis & Dokas (2023), *Geosciences* 14(1):2 | Cantilever walls, **H = 3, 6 and 9 m**, cohesionless backfill, all dimensioned to **FS = 1.5 dry**; primary variable is **initial condition** — water table raised to give **FS = 1.5 / 1.4 / 1.3 / 1.2 / 1.1** | 3 states on **horizontal displacement = 2% / 5% / 10% of H**; plus permanent vertical backfill displacement **0.05 / 0.15 / 0.40 m** | **PGA** (most efficient of PGA, PGV, CAV), free field | 2D FE; lognormal |

## Observations

- **EDP convention splits two ways.** Normalised displacement (d/H — sources 2, 3, 6) transfers between wall heights; absolute settlement (1, 3, 6) is what actually controls serviceability of a road or rail formation behind the wall. Several studies carry both and take the governing one.
- **d/H thresholds are remarkably consistent** at roughly 2 %, 5 % and 10 % of wall height for onshore walls. Ichii's quay-wall set is more permissive (5–30 %) because the consequence metric is berth restoration cost rather than traffic serviceability.
- **PGA dominates as the IM**, but both studies that formally screened IMs (4 and 5) found velocity- or duration-type measures competitive. Relevant for New Zealand subduction motions, where PGA alone tends to under-predict displacement demand.
- **Seismic design coefficient is rarely an explicit variable.** Most sets fix the design k<sub>h</sub> implicitly ("designed to code", "FS = 1.5") and instead vary geometry, backfill slope or groundwater. Source 1 is the closest to fragility conditioned on design level; otherwise a Newmark-type displacement model scaled to the design k<sub>h</sub> is the more defensible route.
- **HAZUS** treats retaining and quay walls only as generic "waterfront structures" keyed to permanent ground deformation, with no wall-type resolution — too coarse for most design-adjacent work.

## Other sources reviewed

- **Rahimi, Firoozfar & Alielahi (2024)** — back-to-back mechanically stabilised earth (MSE) walls with metal strip reinforcement; **overlap length 0.65–0.85H** as the characterisation parameter; scalar and vector fragility on **PGA and PGV**; FLAC2D, far-field vs near-field records. Increasing overlap from 0.65H to 0.85H reduced damage probability by up to 35 % (far-field) and 50 % (near-field).
- **SYNER-G Reference Report 4 (JRC)** — Sections 5.4 and Appendix C.4 cover harbour elements / waterfront structures; PGA and PGD based, limited wall-type resolution.

## References

1. Argyroudis, S., Kaynia, A.M. & Pitilakis, K. (2013). Development of fragility functions for geotechnical constructions: Application to cantilever retaining walls. *Soil Dynamics and Earthquake Engineering*, 50, 106–116. <https://www.sciencedirect.com/science/article/abs/pii/S0267726113000675>
2. Ichii, K. (2004). Fragility curves for gravity-type quay walls based on effective stress analyses. *13th World Conference on Earthquake Engineering*, Vancouver, Paper No. 3040. <https://www.iitk.ac.in/nicee/wcee/article/13_3040.pdf>
3. Seo, H., Lee, Y.-J., Park, D. & Kim, B. (2022). Seismic fragility assessment for cantilever retaining walls with various backfill slopes in South Korea. *Soil Dynamics and Earthquake Engineering*, 161, 107443. <https://www.sciencedirect.com/science/article/abs/pii/S0267726122002925>
4. Seo, H., Kim, B. & Park, D. (2022). Seismic fragility of inverted T-type retaining walls. *20th International Conference on Soil Mechanics and Geotechnical Engineering*, Sydney, Paper 358. <https://www.issmge.org/uploads/publications/1/120/ICSMGE_2022-358.pdf>
5. Cosentini, R.M. & Bozzoni, F. (2022). Fragility curves for rapid assessment of earthquake-induced damage to earth-retaining walls starting from optimal seismic intensity measures. *Soil Dynamics and Earthquake Engineering*, 152, 107017. <https://www.sciencedirect.com/science/article/abs/pii/S0267726121004395>
6. Li, Q., Li, P., Cui, K., Ji, Y., Zhang, D. & Qing, Y. (2024). Seismic fragility curves for concrete gravity retaining wall. *Soil Dynamics and Earthquake Engineering*, 183, 108770. <https://www.sciencedirect.com/science/article/abs/pii/S0267726124003580>
7. Koutsoupaki, E.-I., Sotiriadis, D., Klimis, N. & Dokas, I. (2023). Seismic fragility analysis of retaining walls dependent on initial conditions. *Geosciences*, 14(1), 2. <https://doi.org/10.3390/geosciences14010002>
8. Rahimi, M., Firoozfar, A. & Alielahi, H. (2024). Fragility curves for seismic vulnerability of back-to-back mechanically stabilized earth walls. *Geotechnical and Geological Engineering*. <https://link.springer.com/article/10.1007/s10706-024-02938-7>
9. Pitilakis, K., Crowley, H. & Kaynia, A.M. (eds.) (2013). *SYNER-G Reference Report 4: Guidelines for deriving seismic fragility functions of elements at risk*. JRC Scientific and Policy Report EUR 25880 EN. <https://publications.jrc.ec.europa.eu/repository/bitstream/JRC80561/lbna25880enn.pdf>
10. FEMA (2024). *Hazus Earthquake Model Technical Manual, Hazus 6.1*. <https://www.fema.gov/sites/default/files/documents/fema_hazus-earthquake-model-technical-manual-6-1.pdf>
