# Step 7 — Culvert and bridge crossings: method

- The step finds where an insured accessway crosses a watercourse and puts a
  culvert or a bridge there. It is run by `gen_crossing_population.py`, and the
  detection and the draw are both in
  `landloss.exposure.culverts_bridges.crossings`.
- The exposure is the **crossing**, not the structure. A culvert or a bridge
  exists to carry the accessway over water, so where an accessway crosses
  nothing there is nothing to find.
- Accessways come from `temp/exposure/driveways[-pilot].geoparquet`, the
  corridors step 5 generates and writes out beside the insured land extent, read
  through its own `driveway_path()`.
- **Both river layers are read**: the LINZ river name lines
  (`get_nz_river_name_lines`) and the river name polygons
  (`get_nz_river_name_polygons`, added by this step). A narrow stream exists only
  as a centreline while a river wide enough to need a bridge has an areal extent,
  so the lines alone would miss exactly the crossings most likely to carry a
  bridge. Each crossing records which layer found it, in
  `watercourse_source`, so what the second layer earns is visible per run.
- **Any watercourse counts**, not only the named rivers
  `classify_waterways` separates out for lateral spreading, because most
  accessway crossings are of small streams.
- A crossing is the **part of the accessway lying on the water**, from
  `detect_crossings`, rather than the whole corridor.
- The structure is **drawn, not observed**: a culvert at
  `CULVERT_PROBABILITY`, a bridge otherwise. The two are exhaustive, because
  something has to carry the accessway over the water. Both figures are
  engineering judgement fitted to nothing.
- The draw is seeded by `realisation_seed(BASE_SEED, realisation_id,
  "exposure")`, the same stream the wall population uses, so the crossings of
  realisation 3 belong to the same modelled earthquake as its hazards.
- The output is
  `temp/exposure/crossing-population-rNNN[-pilot].geoparquet` from
  `crossing_population_path()`, carrying `address_id`, `structure`,
  `watercourse_source` and the crossing geometry.
- **Over the pilot box the population is empty.** Neither river layer returns a
  feature there: the nearest named watercourse is about 2.8 km away, while the
  same readers return 9,233 lines and 37 polygons over the four territorial
  authorities. Central Wellington's streams are piped and are not named
  watercourses in the LINZ data. The run says so in its own output rather than
  leaving a zero to be read as a failure.
- Both layers carry **named** watercourses only, so the unnamed streams most
  small accessway crossings sit on are not counted. The run ends by saying the
  count is a floor rather than an estimate.

Potential future improvements: see `s7_crossing_population_implementation_plan.md`.
