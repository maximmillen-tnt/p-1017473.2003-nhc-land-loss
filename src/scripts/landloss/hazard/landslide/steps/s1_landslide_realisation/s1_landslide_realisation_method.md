# Step 1 — Landslide realisation: method

- The step turns a supplied per-cell probability of slope failure into a set of
  individual landslides, each with a polygon for the ground it left and a polygon
  for the ground it landed on. It is run by `s1_simulate_landslides.py`, and the
  figure it is checked against is produced by `fig_landslide_realisation.py` in
  the same folder, written to
  `report/hazard/landslide/landslide-realisation/fig/`.
- What a run does is set by `config.py` in the step folder — `PILOT`, `SEED` and
  `USE_CACHED_DEM` — read in each script's `if __name__ == "__main__":` block and
  passed into `main()` as keyword arguments. Neither script takes command line
  arguments and neither `main()` carries a default, so a realisation can be
  accounted for from the tracked source alone. `PILOT` is `True`, meaning runs go
  over `SMALL_WLG_PILOT` rather than the four territorial authorities.
- The base rate is ESNZ's earthquake-induced landslide probability grid, read by
  `landloss.io.source_material.get_eil_landslide_probability`. The file it reads
  is named once, in `EIL_PROBABILITY_SOURCE_PATH` in
  `landloss.domain.constants`, rather than in the script.
- The supplied file is a **32 m** grid in NZTM, float32 with NaN nodata, covering
  1,730,628–1,791,588 E and 5,409,316–5,459,044 N, with about 57% of its cells
  carrying a value. Probabilities run from 0.002 to 0.98, median 0.024. Nothing
  in the code assumes 32 m — `cell_size()` reads it off the grid and every
  derivative is computed at whatever it finds — so a resupply at another
  resolution needs no code change.
- That extent stops short of the study area on the east (1,791,588 against
  1,794,002) and the north (5,459,044 against 5,464,683), so a full run covers
  slightly less ground than the four territorial authorities. `describe_extent()`
  prints the grid's extent rather than the requested one for that reason.
- The shaking level the grid is conditioned on is taken from the file name
  (`EILProb_PGA2g.tif`) and has not been confirmed with the supplier. Nothing in
  the code depends on it — the grid is used exactly as supplied — but no result
  from this step can be described in the report until it is. The same constant's
  comment records this.
- The grid is used as supplied in one further respect: it is not rescaled or
  clipped. `check_probabilities()` refuses to run on a grid holding any value
  outside [0, 1], because a grid in per cent and a grid carrying an undeclared
  nodata marker both look like ordinary numbers and would each produce a hundred
  times too many landslides.
- **Each cell is sampled independently.** A cell fails when a uniform draw falls
  below its probability. Real failures cluster, so this is the largest known
  error in the step; it is stated in the module docstring of
  `s1_simulate_landslides.py` and again in the run output.
- **Size** is drawn from a bounded power law between `MIN_SOURCE_AREA_M2` (3 m²)
  and `MAX_SOURCE_AREA_M2` (3000 m²), with exponent `SIZE_EXPONENT`, by inverting
  the cumulative distribution in `sample_areas()`. The exponent is **1.19, and it
  is calibrated to total area rather than fitted to a size inventory.** The
  supplied grid fixes how many failures there are and says nothing about how
  large they are, so the exponent is the only free parameter controlling total
  landslide area, and it is solved backwards from the areal-coverage cross-check:
  1.19 gives a mean source area of 259 m², a median of 33 m², and 0.98% areal
  coverage over the graded area, against the order of 1% that Nowicki Jessee et
  al. (2018) give for strong shaking in steep terrain.
- That exponent is far shallower than any published size fit — Massey et al.
  (2020) give 2.1 for the Kaikōura greywacke source polygons and Malamud et al.
  (2004) 2.3 to 2.5 generally — and the reason is stated in the constant's own
  comment. Those fits hold above a cutoff near 500 m², real inventories roll over
  below it, and a single power law stretched two decades below the cutoff cannot
  carry both a published slope and the right total area. **This step currently
  buys the right total area at the price of the right shape.** A size
  distribution quoted from it has to say so; a total area quoted from it is
  calibrated and defensible.
- **The calibration now leans on the 3000 m² upper bound.** A shallow exponent
  puts most of the area in the largest failures, so the cap is doing real work
  rather than just trimming a tail: holding the exponent at 1.19 and moving the
  cap to 1,000 m² gives 0.44% coverage, 5,000 m² gives 1.44% and 10,000 m² gives
  2.42%. The 3 m² floor barely matters any more; the cap decides the answer. Both
  bounds were given as the range to model rather than derived, so the cap is now
  as much a calibration parameter as the exponent, and phase 2 has to fit the two
  together.
- **Shape** is a circle centred on the cell, built by `circles()`. The radius
  comes from `circle_radius()`, which corrects for the fact that a buffer is a
  64-sided polygon rather than a true circle, so the polygon carries exactly the
  area that was sampled. Real source areas are elongated downslope; a circle of
  the right area is the crudest shape that gets the area right, and area is what
  the loss model reads.
- **Overlaps are resolved on the source areas only**, by `drop_overlapping()`,
  which works largest first and drops any smaller failure touching one that has
  survived. A failure that has already been dropped cannot drop anything else, so
  one large landslide cannot clear a hole wider than itself through a chain of
  failures that did not happen.
- **A dropped failure takes its runout with it.** `to_polygons()` only ever sees
  the survivors, so a landslide removed for overlapping a larger one contributes
  neither an evacuated nor an inundated polygon. This is the settled rule: no two
  evacuated polygons overlap, inundated polygons may overlap each other, and
  evacuated and inundated polygons may overlap. Two landslides cannot start from
  the same ground; they can perfectly well finish on it.
- Overlap removal now bites, where at the earlier exponent it almost never did.
  Cell centres are a cell apart — 32 m on the supplied grid — so two circles meet
  only if their radii sum to more than that, and at a median 33 m² failure
  (radius 3.2 m) most still do not. The top of the distribution does: over the
  full study area 586 failures of 66,431, just under 1%, are dropped for
  overlapping a larger one. The step therefore trims the top of the size
  distribution slightly, which is part of why the delivered rate is 0.99 times
  the grid's rather than exactly 1.00.
- **Slope and downhill direction** come from `landloss.common.utils.terrain`:
  `slope_degrees()` and `downhill_azimuth_degrees()`, both Horn's 3×3 kernel on
  the same gradient, so the steepness and the bearing describe the same
  hillside. The bearing is degrees clockwise from grid north and points
  downslope, the convention GDAL and ArcGIS use. Level ground and nodata return
  NaN rather than a direction.
- The elevation model is the LINZ LiDAR, fetched by
  `landloss.io.readers.get_dem` at the probability grid's own cell size and
  resampled bilinearly onto that grid in `build_terrain()`. The probability grid
  is never moved: its cells are the units the answer is counted in. The DEM is
  fetched over the extent plus `DEM_BUFFER_CELLS` (3) cells and the derivatives
  trimmed back, so that the outermost ring of the probability grid — the
  coastline, on any real extent — still gets a slope.
- Any failure whose cell has no slope or no downhill direction is dropped, and
  the count is printed. There is nowhere to put the debris, and a landslide that
  does not move is not what this step models.
- **Displacement** is a function of slope alone, `displacement_from_slope()`: a
  straight ramp from `MIN_DISPLACEMENT_M` (1 m) at or below 10° to
  `MAX_DISPLACEMENT_M` (40 m) at or above 45°. This stands in for a Newmark
  displacement, which would take the yield acceleration and the shaking rather
  than the slope on its own. The "How far" panel of the figure plots this
  assumption directly, so it is visible beside the landslides it produced.
- **The two polygons** are built by `to_polygons()`: the source circle, labelled
  `evacuated land`, and the same circle rebuilt at the displaced centre,
  labelled `inundated land`. They are two rows sharing a `landslide_id`, told
  apart by the `land_class` column. They are deliberately not merged or
  differenced — NHC settles loss of support and runout differently, so the
  vulnerability model needs to know which is which. Where the displacement is
  short next to the landslide the two overlap, which is real: the ground is
  stripped and then buried again.
- The realisation is written under `temp/hazard/landslide/` to the path
  `realisation_path()` returns — `landslide-realisation-pilot.geoparquet` when
  `PILOT` is set and `landslide-realisation.geoparquet` otherwise — so a pilot
  run cannot overwrite a full one. `temp/` is gitignored and the directory comes
  from `TEMP_DIR` in `scripts.landloss.paths`.
  `fig_landslide_realisation.py` calls `realisation_path()` with the same
  `config.PILOT` rather than rebuilding the name, so the figure cannot draw a
  different extent from the one last run.
- Every run is seeded from `SEED` and prints the seed, so a realisation can be
  reproduced exactly.
- `describe_extent()` prints the extent of the grid actually read rather than the
  extent asked for. The two differ whenever the supplied grid stops short of the
  study area, and it is the ground simulated that a result has to be quoted
  against.
- A run where cells failed but every one of them was dropped for want of a slope
  raises rather than reporting an empty realisation: it means the elevation model
  does not cover the probability grid, which is a broken run rather than a quiet
  one. A run where nothing failed at all prints that and writes nothing.
- The reusable parts are covered without the network:
  `tests/landloss/common/utils/test_terrain.py` for the slope and the downhill
  direction, on hillsides whose answer can be pointed at, and
  `tests/landloss/io/test_source_material.py` for the reader, against rasters the
  tests write themselves. The sampling and the overlap logic live in the script
  and are not covered.

## Known weaknesses

- Independent cell sampling produces too few clusters. This biases the *shape*
  of the loss distribution — too few very bad days and too few very quiet ones —
  much more than it biases the average, and the portfolio question NHC is asking
  is a question about the shape.
- The size distribution, the displacement ramp and the circular shape are all
  assumptions, none of them fitted to an inventory. The sizes are the most
  consequential of the three, because total area drives the loss answer.
- Displacement does not depend on the size of the failure, only on the slope, so
  a 3 m² slip and a 3000 m² one on the same hillside travel the same distance.
- Runout is a rigid translation of the source, so the debris keeps the source's
  area and shape and does not spread, thin or follow a gully.
- **No two evacuated polygons overlap; two inundated ones can.** `drop_overlapping()`
  acts on the sources, and the runouts are those same circles moved different
  distances in different directions — two failures on opposite sides of a gully
  both run into its floor and land on top of one another. Ground buried twice is
  still buried once, so anything summing inundated area has to dissolve first.
  `describe_result()` prints the summed and the dissolved area for the inundated
  polygons, and says in words how much of the sum is polygons lying over each
  other; for the evacuated polygons it prints the sum alone and says none of it
  overlaps, because `drop_overlapping()` has already guaranteed that and
  dissolving a hundred thousand of them to confirm it costs about a minute.
- The probability grid carries no spatial correlation of its own to inherit, and
  nothing in this step adds any.
- Each run draws one realisation per id in `config.REALISATION_IDS`. The
  generator comes from `landloss.hazard.realisation.realisation_seed` with the
  project-wide `BASE_SEED`, the realisation id and the stream name
  `"landslide"`, so the landslides of realisation 3 belong to the same modelled
  earthquake as the shaking and liquefaction of realisation 3. The step holds no
  seed of its own; two hazards seeded separately could not be paired.
- Every polygon carries `realisation_id`, and the output is written per
  realisation as `landslide-realisation-rNNN[-pilot].geoparquet` by
  `realisation_path()`.


Potential future improvements: see `s1_landslide_realisation_implementation_plan.md`.