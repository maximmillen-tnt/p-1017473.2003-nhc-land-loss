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
- The output is `temp/exposure/beta-wall-population-rNNN[-pilot].geoparquet`
  from `wall_population_path()`, carrying `address_id`, `size_class`,
  `initial_condition`, `height_m`, `length_m` and the line.
- The run prints the slope distribution it drew against, the share of properties
  that took a wall, and the counts by size class and initial condition, so the
  draw can be checked against the prevalence it came from. It ends by saying
  plainly that the population is not evidence about Wellington.
- Over the pilot box it draws 758 walls over 4,764 properties, 15.9%, with a
  median retained height of 1.8 m.

Potential future improvements: see `s6_wall_population_implementation_plan.md`.
