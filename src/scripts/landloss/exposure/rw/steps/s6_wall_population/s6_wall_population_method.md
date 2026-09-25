# Step 6 — Retaining wall population: method

- The step draws a **stand-in** wall population over the insured properties and
  writes one line per wall. It is run by `gen_wall_population.py`, and every
  number behind it is in `landloss.exposure.rw.beta_population`, which carries
  the `beta` prefix because it is deleted when the real inference arrives.
- Properties come from `temp/exposure/insured-land[-pilot].geoparquet`, the
  layer step 5 writes, read through its own `insured_land_path()`.
- Slope and downhill azimuth are derived from the LINZ elevation model over the
  properties' extent by `landloss.common.utils.terrain.slope_degrees` and
  `downhill_azimuth_degrees`, written to `temp/exposure/` and sampled at each
  property's representative point with `sample_at_points`. A property outside
  the elevation model comes back NaN and draws no wall.
- **Slope is the only driver.** Prevalence ramps from zero below
  `BETA_MIN_SLOPE_DEG` to `BETA_MAX_PREVALENCE` above `BETA_MAX_SLOPE_DEG`, and
  retained height ramps over the same range. Nothing here reads cut-and-fill,
  road batters, section shape or the age of the subdivision, all of which the
  real model uses.
- **Initial condition is drawn, not derived.** The real model reads it off the
  age of the dwelling; no dwelling age is held, so `BETA_POOR_SHARE` splits the
  population evenly between modern and poor.
- Size classes are **small below 1 m, medium 1 to 2.5 m, large above 2.5 m** of
  retained height, by `classify_wall_size`. The boundaries are set by what the
  costing can tell apart: above the sub-cap the settlement stops depending on
  height.
- A wall is drawn as a straight line **along the contour**, perpendicular to the
  downhill azimuth and centred on the property's representative point, by
  `wall_lines`. Its length is `BETA_LENGTH_SHARE` of the width of a square of
  the property's insured area. The orientation is right and the position is not,
  because nothing here knows where on a section a wall sits.
- The draw is seeded by `realisation_seed(BASE_SEED, realisation_id,
  "exposure")`, so the walls of realisation 3 belong to the same modelled
  earthquake as its hazards, and a rerun reproduces.
- **Only walls on insured land are passed on.** After the draw,
  `landloss.exposure.coverage.keep_walls_on_insured_land` keeps a wall only if
  its line intersects its own claim's insured land polygon buffered by
  `RW_COVERAGE_BUFFER_M` (2 m), because a wall can support the insured land from
  just outside it. The test is against the step 5 polygons, not the
  representative points the slope was sampled at, and lying on another claim's
  land does not count. It runs after the draw, so the random stream is unchanged.
  `describe_coverage` prints the walls drawn, kept and dropped; under the beta
  each wall is centred inside its own polygon, so nearly all are kept.
- **Each kept wall gets an `rw_id`** of the form `<claim_id>-RW<nn>`, numbered
  from 01 within its claim, by `landloss.exposure.asset_ids.mint_asset_ids` with
  `RW_ID_SUFFIX`. It is minted after the coverage filter, on walls ordered by
  `sort_by_location` (claim, then the x and y of the line's representative
  point), so it is stable within a realisation and does not depend on row order.
- The output is `temp/exposure/beta-wall-population-rNNN[-pilot].geoparquet`
  from `wall_population_path()`, carrying `rw_id`, `claim_id`, `size_class`,
  `initial_condition`, `height_m`, `length_m` and the line.
- The run prints the slope distribution it drew against, the share of properties
  that took a wall, and the counts by size class and initial condition, so the
  draw can be checked against the prevalence it came from. It ends by saying
  plainly that the population is not evidence about Wellington.
- Before the coverage filter was added, over the pilot box it drew 758 walls over 4,764 properties, 15.9%, with a
  median retained height of 1.8 m.

Potential future improvements: see `s6_wall_population_implementation_plan.md`.
