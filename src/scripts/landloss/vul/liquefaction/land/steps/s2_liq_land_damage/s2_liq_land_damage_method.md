# Step 2 — Liquefaction land damage: method

- The step puts a **land damage state and a repair cost on every insured
  property**, and writes one row per property per realisation for the loss
  module to settle. It is run by `gen_liq_land_damage.py`.
- Properties come from `temp/exposure/insured-land[-pilot].geoparquet`, the
  layer step 5 writes, read through its own `insured_land_path()`.
- The damage state comes from the hazard module's realised state raster,
  `ld_state_path()`, sampled at each property's **representative point** with
  `landloss.common.utils.terrain.sample_at_points`. A property therefore carries
  one state rather than a mixture of the states under it.
- **A property outside the grid carries no state and no cost.** The liquefaction
  model covers flat land, as expected, so over the Wellington pilot roughly two
  properties in five come back with nothing. The run prints that split rather
  than reporting it as coverage loss.
- Costs are looked up, not modelled, by `landloss.vul.liquefaction.costs`. They
  are what NHC settled for land damage after the 2010 and 2011 Canterbury
  earthquakes, grouped by the damage state surveyed on the ground, and shipped
  in `costs_liq_ld_refined_states_2011.csv` beside that module.
- **The rates are a cost per property, not per square metre**, which is what
  `rate_basis = "per_property"` on every row records. An area never multiplies
  them: a property assessed at Moderate cost what it cost, whatever its size.
  Insured area and land rate ride along as columns because the loss module needs
  them for the market value side of the cap, not because the repair cost uses
  them.
- **The percentile is a run-level scenario**, set by `COST_PERCENTILE` in
  `config.py` and carried onto every row. The 15th, 50th and 85th are the spread
  of settled costs *between* Canterbury properties assessed at the same state,
  not a confidence interval, and the 85th runs two to four times the median. The
  model is run once per value because `min(repair, cap)` is non-linear.
- **States 5 and 6 carry identical costs**, both read from the source band
  "5 or 6", so the severe end rests on one estimate rather than two.
- The money is **2011 dollars excluding GST**, recorded in `cost_year` on every
  row because land values are indexed to a different date and the loss module
  compares the two.
- Output is `temp/vul/liq-land-damage-r<nnn>[-pilot].parquet`.

Potential future improvements see
`s2_liq_land_damage_implementation_plan.md`.
