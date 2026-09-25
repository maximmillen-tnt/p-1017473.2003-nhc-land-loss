# Step 2 — Land value: method

- The step runs on the address spine from step 1. Both
  `s1_build_terrain_attributes.py` and `s4_estimate_land_value.py` read
  `temp/exposure/address-spine.geoparquet` and rebuild it from LINZ in their own
  `get_spine()` if it is not there, so either script runs on a clean checkout.
- The run settings of both scripts — `PILOT`, `FRESH`, the `SPINE`,
  `TERRAIN`, `LAND_VALUE_OUT` and `COHORTS_OUT` path overrides and the
  `WINDOW_M` override — are read from the one `config.py` in this folder and
  passed into each `main()` as keyword arguments; neither script takes
  command-line arguments. Sharing `PILOT` and `TERRAIN` keeps s4 reading
  what s1 wrote.
- Each address is tagged flat or hill by
  `landloss.exposure.land.landform.classify_landform`, against the National
  Liquefaction Model flatland polygons read by
  `landloss.exposure.land.landform.get_flatland`. An address lying exactly on a
  flatland boundary is hill, because the join is `within` rather than
  `intersects`.
- The NLM is reused rather than a slope surface rebuilt from a DEM, and what
  that reuse costs is carried as limitation L-16 in the project register; the
  module docstring of `src/landloss/exposure/landform.py` records both.
- `classify_landform` assigns hill and flat only. The third class,
  `elevated_flat`, is assigned separately by
  `landloss.exposure.land.landform.assign_elevated_flat` from a terrain attribute,
  and the module docstring of `src/landloss/exposure/landform.py` records why
  the two are kept apart — the flatland join is a spatial question with no
  raster in it, and stays runnable on an extent no DEM has been fetched for.
- The terrain attributes are built by `s1_build_terrain_attributes.py`, which
  reads the same spine, fetches the elevation model through
  `landloss.io.readers.get_dem` and writes one row per address. The DEM is
  LINZ's, served from the STAC catalogue rather than Koordinates — LiDAR where
  it has been flown, falling back to the 8 m contour-derived model where it has
  not — which is the same elevation data the National Liquefaction Model stands
  on; the docstring of `get_dem` carries that and the survey-vintage limitation.
- The working resolution is `landloss.domain.constants.DEM_RESOLUTION_M`, and
  the comment on that constant is where the choice is argued: the study area at
  1 m is about 3.2 billion cells, at 10 m about 32 million, and nothing the land
  value model asks of the terrain is decided at finer than 10 m.
- Slope in degrees is computed by
  `landloss.common.utils.terrain.slope_degrees`, using Horn's 3x3 kernel — the
  one GDAL, ArcGIS and the NLM all use, so a slope from here is comparable with
  a slope quoted from any of them. Its docstring carries the kernel and the
  reason it is written out in numpy rather than taken from a library.
- Relative height is computed by
  `landloss.common.utils.terrain.topographic_position`: elevation minus the mean
  elevation of a square neighbourhood centred on the cell, in metres, positive
  on terraces and spurs and negative on valley floors. The neighbourhood width
  is the `topographic_position_window_m` row of
  `src/landloss/io/assets/land-value-factors.csv`, converted to an odd number of
  cells by `window_in_cells`; the window lives in the factors asset rather than
  in the script because the elevated flat threshold is only meaningful against a
  position measured over it.
- The DEM is fetched over the spine's own extent buffered by half that window
  plus one cell, computed by `dem_bbox()` in `s1_build_terrain_attributes.py`. A
  centred rolling window has no answer within half a window of the edge of its
  grid, so without the buffer every address around the outside of the extent
  would sample NaN because of where the extent was drawn rather than because of
  anything about the ground.
- Both derivative rasters are written to `temp/exposure/terrain-slope.tif` and
  `temp/exposure/terrain-position.tif` by
  `landloss.common.utils.terrain.write_raster`, sampled at every address point
  by `sample_at_points`, and the sampled values written to
  `temp/exposure/terrain-by-address.geoparquet` carrying `address_id`,
  `slope_deg`, `topographic_position_m` and the geometry. All four take a
  `-pilot` suffix when `PILOT` is True.
- Nodata is masked to NaN before either derivative is computed, by
  `mask_nodata()` in `s1_build_terrain_attributes.py`, and the run names which
  of the three nodata cases the DEM presented. Addresses that still sampled no
  value are counted per territorial authority by `describe_missing()` rather
  than passed quietly downstream.
- A flat address standing more than
  `elevated_flat_min_topographic_position_m` metres above its neighbourhood is
  promoted to `elevated_flat` by
  `landloss.exposure.land.landform.assign_elevated_flat`. A hill address is never
  promoted however high it stands, and an address with no topographic position
  keeps the class the flatland join gave it; the threshold is a row of
  `src/landloss/io/assets/land-value-factors.csv` with its basis on the row.
- Within a landform class, value is spread by the continuous terrain modifier
  `landloss.exposure.land.land_value.terrain_modifier`: slope and topographic
  position are standardised within each `TERRAIN_GROUP_COLUMNS` group, combined
  as `exp(beta_slope * z_slope + beta_tpi * z_tpi)`, clipped to the
  `terrain_modifier_clip_min` and `terrain_modifier_clip_max` rows of the
  factors asset, and rescaled so the group mean is exactly one.
- The standardising and the rescaling are both within the territorial authority
  and landform class rather than across them, and the module docstring of
  `src/landloss/exposure/land_value.py` sets out why: steep land is already
  classed as hill, so a slope term running across the classes would be paid for
  twice, once by the class and again by the slope. Held to a mean of one inside
  the group, the class keeps all of the between-class signal and the modifier
  does nothing but redistribute value inside it.
- An address the DEM had no value for, a cohort of one and a cohort whose
  addresses all share a value all resolve to a modifier of one rather than to
  NaN, which `_standardise_within_groups` carries and
  `tests/landloss/exposure/test_land_value.py` covers.
- The published average land value for each territorial authority, its rating
  unit count, its index to the common valuation date and its median lot size are
  held in `src/landloss/io/assets/land-value-base-rates.csv`, one row per
  authority with the QV media release URL on the row. How the two derived
  columns were arrived at is written up in `src/landloss/io/assets/README.md`.
- The landform multipliers and the clip multiples are held in
  `src/landloss/io/assets/land-value-factors.csv`, one row per parameter with
  the derivation of the number in the `basis` cell on the same row.
- Values are assigned by `landloss.exposure.land.land_value.estimate_land_value`: the
  published average is indexed onto `COMMON_VALUATION_DATE` by
  `index_base_rates`, each address takes its landform multiplier — multiplied by
  its terrain modifier whenever the frame carries both of `TERRAIN_COLUMNS`, and
  by the landform multiplier alone when it does not — a normalising
  constant from `solve_normalising_constant` scales the multipliers so the
  authority's mean equals the indexed average, the result is clipped to the
  configured multiples of that average, and the constant is re-solved once
  across the unclipped addresses so the mean still lands on the published
  figure. `_value_one_ta` carries that arithmetic and the one case it is not
  exact in.
- The consequence of that design, stated in the module docstring of
  `src/landloss/exposure/land_value.py`, is that the landform judgement moves
  value between properties within an authority and never changes what the
  authority is worth in total.
- The terrain join is optional. `s4_estimate_land_value.py` reads the attributes
  with `read_terrain()` and joins them with `attach_terrain()` — a left merge on
  `address_id` validated one-to-one, with the unmatched count printed — and when
  the file is absent it prints what the run is going without and values on
  landform class alone. `TERRAIN` in `config.py` points both scripts at
  a different file.
- The run prints the calibration per territorial authority in
  `describe_calibration()` — the modelled mean, the indexed published average
  and the percentage difference between them — together with the hill, flat and
  elevated flat counts in `describe_landform()`, whose last column is the share
  of flat land the topographic position threshold promoted and is what that
  threshold is judged on.
- `describe_distinct_rates()` prints how many distinct rates to the cent the run
  produced, across addresses and across suburb cohorts. That count is what the
  terrain modifier is measured by: on landform class alone an address's rate
  depends on nothing but its authority and one of three classes, so four
  authorities can produce at most twelve rates between them however many
  addresses they hold.
- The per-address result is written to
  `temp/exposure/land-value-by-address.geoparquet`, and the cohort table from
  `landloss.exposure.land.land_value.summarise_by_suburb`, one row per territorial
  authority, suburb and landform class, to `temp/exposure/land-value-by-suburb.csv`.
  Both take a `-pilot` suffix when `PILOT` is True, so a pilot run cannot overwrite
  the full outputs.
- The distribution of the modelled rate across the study area is shown in the
  figure produced by `fig_land_value_map.py`, written to
  `report/exposure/land/land-value/fig/`. It draws one colour per distinct modelled
  rate while there are no more than `MAX_DISCRETE_CLASSES` of them, which is a
  run valued on landform class alone, and falls back to the `QUANTILE_CLASSES`
  quantile bins once the terrain modifier makes the surface continuous; both
  thresholds are constants in that script.
- The two terrain attributes themselves are shown in the figure produced by
  `fig_terrain_attributes.py`, also written to
  `report/exposure/land/land-value/fig/`: slope on a sequential ramp pinned at zero,
  topographic position on a diverging ramp held symmetric about zero. It takes
  the same `--pilot`, `--ta <name>` and `--ta all` arguments as
  `fig_land_value_map.py`, and reads the s1 output rather than rebuilding it,
  refusing with the command to run when the file is absent.
- `fig_land_value_map.py --ta "<name>"` draws a single territorial authority
  zoomed in, and `--ta all` writes one figure per authority. A per-authority map
  is framed on where its addresses are rather than on its boundary — the trim is
  `TA_FRAME_TRIM` in that script — because Wellington City's boundary runs west
  over Makara and Ohariu to the open coast, which is most of its area and a few
  hundred of its addresses. The colour classes are taken from the whole study
  area by the `reference` argument of `classify_rates`, so a rate keeps one
  colour across the set and the four maps can be read side by side.
- The rate per square metre divides the modelled land value by the per-authority
  `median_lot_size_m2` from the base rates asset, not by a measured parcel area.
- The arithmetic is covered by `tests/landloss/exposure/test_land_value.py`,
  `tests/landloss/exposure/test_landform.py` and
  `tests/landloss/common/utils/test_terrain.py`, and the outputs of a real run are
  checked against the published anchors, the rating unit counts, the known
  market order of Wellington suburbs and the shape of the rate distribution by
  `src/scripts/landloss/exposure/land/validations/check_land_value_totals.py`.
- Two of those checks are reported rather than enforced while the model is this
  coarse, and both say so in the run output. The address count per rating unit
  is reported under `--pilot`, because a pilot box covers part of one authority.
  The right-skew test is reported whenever the run produces fewer than
  `SKEW_MIN_DISTINCT_RATES` distinct rates, because on landform class alone every
  address takes one of three values per authority and the sign of the skew is
  then decided by the class shares rather than by anything about the model. A run
  with the terrain modifier on clears that threshold by a wide margin, so the
  test is enforced there and reported only on a landform-only run.

## Known weaknesses

- The four authorities were valued up to a year apart across a falling market —
  the dates are on each row of `src/landloss/io/assets/land-value-base-rates.csv`
  — and they are brought onto one date by the `index_to_2025_09` factor. That
  factor is read off the published QV House Price Index for the greater
  Wellington region, with the September figure interpolated between two
  published annual changes, as `src/landloss/io/assets/README.md` sets out. No
  valuer has signed it off.
- Lot size is assumed. `median_lot_size_m2` is documented judgement anchored on
  a 600 m2 regional convention, not a researched per-authority median, so
  `land_rate_nzd_per_m2` is an order-of-magnitude figure for comparing cohorts
  rather than a valuation of any one property. The derivation and the sense
  check behind each of the four numbers are in
  `src/landloss/io/assets/README.md`.
- The distribution within an authority rests entirely on the three-class
  landform split and the terrain modifier, and every number behind both is in
  the `basis` column of `src/landloss/io/assets/land-value-factors.csv` as
  judgement. Nothing validates it: the
  suburb ranking check in `check_land_value_totals.py` reports how many of the
  suburbs in its `EXPECTED_HIGH_SUBURBS` and `EXPECTED_LOW_SUBURBS` constants
  land in the expected half of the modelled ranking, and prints how few distinct
  medians the model produces across all of them, but its status is
  informational and never fails the run. District Valuation Roll land
  values, which register task T-20 covers, are what the factors are fitted
  against once they arrive.
- The three numbers that decide what the terrain does to a value are engineering
  judgement, not fitted coefficients, and each says so on its own row of
  `src/landloss/io/assets/land-value-factors.csv`. The elevated flat threshold
  `elevated_flat_min_topographic_position_m` decides how much of the flat land
  takes the raised-terrace premium at all; `beta_slope` and `beta_tpi` decide how
  hard the two derivatives push inside a cohort. The regression against
  District Valuation Roll land values, which register task T-20 covers, is
  what replaces all three; until it runs the terrain modifier is a plausible
  shape rather than a measured one.
- The elevated flat factor is a terrain premium and is not the view premium.
  2.06 pays flat, sunny, easy-to-build-on ground a modest premium over ordinary
  flat land, and the `basis` cell on that row records what the number is
  deliberately not paying for: the earlier 3.10 came from the premium flat and
  sea view market band, which describes Seatoun, Oriental Bay and the waterfront,
  while the class is now assigned from terrain alone and picks up every drive-on
  terrace in Karori, Khandallah, Johnsonville, Maungaraki and Pinehaven.
  Nothing in this step models sea view or winter sun, so an elevated flat
  address is credited with neither.
- The elevation model is a merge of LiDAR surveys flown in different years
  across the study area — Wellington in 2023, Hutt City in 2025, Porirua
  unknown — which is limitation L-12 in the project register and is recorded
  in the docstring of `landloss.io.readers.get_dem`. A step in slope or in
  topographic position across a survey boundary may therefore be an artefact
  of the join between two surveys rather than a landform, and every address
  within half a topographic position window of such a boundary has some of
  the other survey in its neighbourhood mean.
- The published averages are residential averages applied to every address,
  because the LINZ NZ Addresses layer carries no residential flag. That gap
  belongs to step 1 and is carried in its method file as well.

Potential future improvements: see `s2_land_value_implementation_plan.md`.
