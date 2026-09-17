# Step 2 — Land value: implementation plan

**Status:** Phases 0 and 1 complete. Phase 2 waits on the DEM, Phase 5 on the
District Valuation Roll data that register task T-20 covers, and Phase 6 on the
hazard module.

The scripts in this folder are numbered from `s4`, not from `s1`. Terrain,
accessibility and amenity are steps `s1` to `s3` of this same folder in later
phases; land value is the only one of the four that Phase 1 models, so the gap
is deliberate and the earlier numbers are reserved rather than missing.

## Phase 0 — The steps-folder convention (complete)

- [x] Write the convention down as a repository skill,
      `.agents/skills/adding-steps-scripts/SKILL.md`, so every step is laid out
      the same way and the methodology is current when the report is assembled.
- [x] Carry the two markdown files in every step folder — a phased
      implementation plan holding everything aspirational, and a method file
      describing only what is implemented.

## Phase 1 — Value every address from the published rating valuations (complete)

- [x] Tag each address as flat or hill against the NLM flatland layer
      (`landloss.exposure.landform.classify_landform`).
- [x] Index the four published average land values onto a common valuation date
      (`landloss.exposure.land_value.index_base_rates`).
- [x] Spread each authority's indexed average across its addresses in proportion
      to a landform multiplier, with a per-authority normalising constant that
      holds the modelled mean on the published figure
      (`landloss.exposure.land_value.estimate_land_value`).
- [x] Write the valued addresses and the per-suburb cohort table
      (`s4_estimate_land_value.py`).
- [x] Print the modelled mean against the published average, so the calibration
      is visible without opening the outputs.
- [x] Map the modelled rate across the study area (`fig_land_value_map.py`).
- [x] Check the outputs against the published anchors, the rating unit counts,
      the known market order and the shape of the rate distribution
      (`src/scripts/landloss/exposure/validations/check_land_value_totals.py`).

## Phase 2 — DEM terrain

- [ ] Derive continuous slope from the DEM, replacing the binary flat/hill cut
      with a gradient every address carries in its own right.
- [ ] Derive relative topographic position, so an address is placed against the
      land around it rather than only against its own slope.
- [ ] Assign the elevated flat class — flat land raised above the surrounding
      floodplain — which Phase 1 declares in
      `landloss.exposure.landform.LANDFORM_CLASSES` and prices in
      `src/landloss/io/assets/land-value-factors.csv` but cannot assign without
      the DEM.
- [ ] Re-derive the landform factors once three classes exist, since the current
      two are ratios taken against hill as the reference class.
- [ ] Build on `ttpy.gis.raster` and `ttpy.gis.flatland` rather than a private
      raster stack, and add `rioxarray`, `xarray` and `rasterio` as direct
      dependencies.

## Phase 3 — Accessibility

- [ ] Give each address a gravity decay to the main centres,
      `A_i = sum over centres c of W_c * exp(-d_ic / L_c)`, with `W_c` the
      centre's weight — Wellington CBD 1.00, Lower Hutt CBD 0.30, Porirua CBD
      0.20, Upper Hutt CBD 0.12, local centres 0.05 to 0.10 — and `L_c` its
      decay length, 6 km for the Wellington CBD and 3 km for the secondary
      centres.
- [ ] Add a rail proximity term, `1 + a * exp(-d_station / 400 m)`.
- [ ] Stage 3a: straight-line distance, which is cheap and needs no network
      data.
- [ ] Stage 3b: road-network travel time. The test that decides whether 3b is
      worth building is Days Bay and Eastbourne, about 9 km from the Wellington
      CBD in a straight line and a 25 minute drive around the harbour — if 3a
      prices them as inner suburbs, the network build is justified.
- [ ] Show the centres and their weights in the figure produced by
      `fig_town_centres.py`, so the weights are reviewable on a map rather than
      in a table.

## Phase 4 — Amenity: sea view and winter sun

- [ ] Sea view by inverted viewshed: because visibility is reciprocal, run
      WhiteboxTools viewshed from a few hundred station points sampled on the
      sea over a 10 m DEM and read the visible-station count off the land,
      rather than running a viewshed from every property.
- [ ] Winter sun by WhiteboxTools `time_in_daylight` over a June-July window
      with terrain shadowing. This is what separates a good Wellington section
      from a bad one, and what a plain aspect calculation misses.
- [ ] Work at 10 m resolution. A 1 m DEM over the study area is about 3.2
      billion cells, which is not a sensible cost for an amenity multiplier.

## Phase 5 — Calibration against the District Valuation Roll

- [ ] Refit the landform, terrain, accessibility and amenity factors by
      regression against council District Valuation Roll land values, when
      register task T-20 closes. Until then every factor in
      `src/landloss/io/assets/land-value-factors.csv` is engineering judgement
      and the within-authority distribution is unvalidated.

## Phase 6 — Hazard discounts

- [ ] Discount land exposed to a modelled hazard, once the hazard module
      produces the layers to discount against.

## Potential future improvements

- Take land area from a measured parcel rather than the per-authority
  `median_lot_size_m2` in the base rates asset. The parcel join is Phase 2 of
  step 1's plan, `s1_address_spine_implementation_plan.md`, and this step
  consumes it when it lands.
- Have a valuer sign off the `index_to_2025_09` factors, or replace them with a
  valuer's own basis. They are read off the published QV House Price Index for
  the greater Wellington region, with the September figure interpolated between
  two published annual changes.
- Use sale prices where they exist rather than the rating valuation averages.
  More accurate, but the data is not held for the full study area.
- Narrow the published averages to residential addresses. They are residential
  averages applied to every address, because the LINZ address layer has no
  residential flag; this is the same gap step 1's plan carries.
- Revisit the clip multiples in the factors asset. They are judgement floors and
  ceilings rather than researched figures, and with the shipped factors they
  never bind, so nothing currently depends on them being right.
