# Step 9 — Culvert and bridge damage state: method

- The step decides **which culverts and bridges the shaking wrote off**, one
  damage state per structure per realisation. It is run by
  `gen_structure_damage_state.py`, and the fragility is in
  `landloss.vul.shaking.fragility` — the same one the retaining walls use.
- Structures come from
  `temp/exposure/crossing-population-r<nnn>[-pilot].geoparquet`, the population
  step 7 draws, read through its own `crossing_population_path()`.
- **Two damage states only, no damage and replace**, for the same reason as the
  walls: a failed crossing is rebuilt rather than patched.
- A damage state is a **draw against a probability of failure**, never a
  threshold on ground motion. The fragility returns that probability because
  that is what a fragility curve is, and it stays a probability however well the
  shaking field is resolved.
- **The beta's fragility is one flat number**, `BETA_FAILURE_PROBABILITY = 0.7`,
  and it does not yet distinguish a culvert from a bridge. The kind of structure
  is carried on every row as the asset, because the two are priced differently
  in the loss module even though they share the $25,000 sub-cap.
- PGA is sampled from the realisation's field at each structure's midpoint and
  carried onto the output, so the input is in place when the fragility starts
  using it.
- **The Wellington pilot legitimately produces no rows.** The crossing
  population follows named watercourses and the nearest is some kilometres from
  the pilot box, so the population itself is empty. The run says so in words
  rather than printing an empty table, because an empty output here is a
  coverage fact and not a failure.
- **No cost is attached.** The loss module prices a written-off structure from
  its undepreciated value, so what this step writes is the state.
- The draw is seeded by `realisation_seed(BASE_SEED, realisation_id,
  "vulnerability")`, the same stream the walls draw from.
- Output is `temp/vul/structure-damage-state-r<nnn>[-pilot].parquet`.

Potential future improvements see
`s9_structure_damage_state_implementation_plan.md`.
