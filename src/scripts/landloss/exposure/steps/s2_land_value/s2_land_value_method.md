# Step 2 — Land value: method

- The step runs on the address spine from step 1. `s4_estimate_land_value.py`
  reads `temp/exposure/address-spine.geoparquet` and rebuilds it from LINZ in
  `get_spine()` if it is not there, so the script runs on a clean checkout.
- Each address is tagged flat or hill by
  `landloss.exposure.landform.classify_landform`, against the National
  Liquefaction Model flatland polygons read by
  `landloss.exposure.landform.get_flatland`. An address lying exactly on a
  flatland boundary is hill, because the join is `within` rather than
  `intersects`.
- The NLM is reused rather than a slope surface rebuilt from a DEM, and what
  that reuse costs is carried as limitation L-16 in the project register; the
  module docstring of `src/landloss/exposure/landform.py` records both.
- Only hill and flat are assigned. The `elevated_flat` factor is carried in
  `src/landloss/io/assets/land-value-factors.csv` and read into
  `LANDFORM_FACTOR_PARAMETERS`, but nothing assigns that class, which
  `tests/landloss/exposure/test_landform.py` asserts directly.
- The published average land value for each territorial authority, its rating
  unit count, its index to the common valuation date and its median lot size are
  held in `src/landloss/io/assets/land-value-base-rates.csv`, one row per
  authority with the QV media release URL on the row. How the two derived
  columns were arrived at is written up in `src/landloss/io/assets/README.md`.
- The landform multipliers and the clip multiples are held in
  `src/landloss/io/assets/land-value-factors.csv`, one row per parameter with
  the derivation of the number in the `basis` cell on the same row.
- Values are assigned by `landloss.exposure.land_value.estimate_land_value`: the
  published average is indexed onto `COMMON_VALUATION_DATE` by
  `index_base_rates`, each address takes its landform multiplier, a normalising
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
- The run prints the calibration per territorial authority in
  `describe_calibration()` — the modelled mean, the indexed published average
  and the percentage difference between them — together with the flat/hill split
  in `describe_landform()`.
- The per-address result is written to
  `temp/exposure/land-value-by-address.geoparquet`, and the cohort table from
  `landloss.exposure.land_value.summarise_by_suburb`, one row per territorial
  authority, suburb and landform class, to `temp/exposure/land-value-by-suburb.csv`.
  Both take a `-pilot` suffix under `--pilot`, so a pilot run cannot overwrite
  the full outputs.
- The distribution of the modelled rate across the study area is shown in the
  figure produced by `fig_land_value_map.py`, written to
  `report/exposure/land-value/fig/`. It draws one colour per distinct modelled
  rate rather than quantile bins, because the Phase 1 surface takes at most
  eight values; the fallback threshold is `MAX_DISCRETE_CLASSES` in that script.
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
- The arithmetic is covered by `tests/landloss/exposure/test_land_value.py` and
  `tests/landloss/exposure/test_landform.py`, and the outputs of a real run are
  checked against the published anchors, the rating unit counts, the known
  market order of Wellington suburbs and the shape of the rate distribution by
  `src/scripts/landloss/exposure/validations/check_land_value_totals.py`.
- Two of those checks are reported rather than enforced while the model is this
  coarse, and both say so in the run output. The address count per rating unit
  is reported under `--pilot`, because a pilot box covers part of one authority.
  The right-skew test is reported whenever the run produces fewer than
  `SKEW_MIN_DISTINCT_RATES` distinct rates, because with only flat and hill every
  address takes one of two values per authority and the sign of the skew is then
  decided by the flat/hill share rather than by anything about the model. It
  becomes enforced once the terrain and amenity phases make the surface
  continuous.

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
- The distribution within an authority rests entirely on the two-class
  flat/hill split and the two multipliers in
  `src/landloss/io/assets/land-value-factors.csv`. Nothing validates it: the
  suburb ranking check in `check_land_value_totals.py` reports how many of the
  suburbs in its `EXPECTED_HIGH_SUBURBS` and `EXPECTED_LOW_SUBURBS` constants
  land in the expected half of the modelled ranking, and prints how few distinct
  medians the model produces across all of them, but its status is
  informational and never fails the run. District Valuation Roll land
  values, which register task T-20 covers, are what the factors are fitted
  against once they arrive.
- The published averages are residential averages applied to every address,
  because the LINZ NZ Addresses layer carries no residential flag. That gap
  belongs to step 1 and is carried in its method file as well.

Potential future improvements: see `s2_land_value_implementation_plan.md`.
