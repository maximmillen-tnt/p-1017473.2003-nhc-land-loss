# Step 9 — Retaining wall damage state: method

- The step decides **which retaining walls the shaking wrote off**, one damage
  state per wall per realisation. It is run by `gen_wall_damage_state.py`, and
  the fragility is in `landloss.vul.shaking.fragility`.
- Walls come from `temp/exposure/beta-wall-population-r<nnn>[-pilot].geoparquet`,
  the population step 6 draws, read through its own `wall_population_path()`.
- **Two damage states only, no damage and replace.** Repair is not modelled
  because very few damaged walls are repaired in practice, so a third state
  would carry almost nothing.
- A damage state is therefore a **draw against a probability of failure**, never
  a threshold on ground motion. The fragility returns that probability because
  that is what a fragility curve is: nominally identical walls differ in
  capacity and respond variably to the same shaking, and the curve is the
  distribution of that difference. This does not change when the hazard input
  improves.
- Separately, and as a limitation of the hazard rather than of this step, **the
  shaking field is currently flat**. A realisation scales the PGA grid by a
  single factor and the site class is not yet varied, so every wall in the pilot
  reads the same acceleration.
- **The beta's fragility is one flat number**, `BETA_FAILURE_PROBABILITY = 0.7`,
  for every wall regardless of size class, initial condition or the acceleration
  it saw. The realised split lands near 70% as a result. `draw_damage_states()`
  takes probabilities rather than computing them, so the published curves drop
  in without the script changing.
- PGA is sampled anyway, from the realisation's field via `pga_path()`, at each
  wall's **midpoint**. It is carried on every row and reported on every run, so
  that the input is already in place when the fragility starts using it, and so
  a wall sitting outside the hazard field is noticed.
- Size class, initial condition, height and length are carried through from the
  population for the same reason — the real fragility is indexed on them.
- **No cost is attached.** The loss module prices a written-off wall from its
  undepreciated value, against the $50,000-per-dwelling sub-cap, so what this
  step writes is the state and not the money.
- The draw is seeded by `realisation_seed(BASE_SEED, realisation_id,
  "vulnerability")` — one stream for the whole vulnerability module, so adding
  an asset class does not shift the draws of the ones already there.
- Output is `temp/vul/wall-damage-state-r<nnn>[-pilot].parquet`.

Potential future improvements see `s9_wall_damage_state_implementation_plan.md`.
