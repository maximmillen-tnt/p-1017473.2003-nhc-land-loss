# Step 11 — Retaining wall landslide damage: method

- The step records **whether a landslide reached each insured retaining wall**,
  per kind of ground. It is run by `gen_wall_landslide_damage.py`, and the
  intersection is `landslide_flags()` in `landloss.vul.landslide.flags`.
- Walls come from exposure step 6's
  `temp/exposure/beta-wall-population-r<nnn>[-pilot].geoparquet`, read through
  `wall_population_path()`, so only walls that passed the insured land coverage
  filter there are flagged. Landslides come from the hazard module's
  `temp/hazard/landslide/landslide-realisation-r<nnn>[-pilot].geoparquet`, read
  through `realisation_path()`.
- A wall is `is_evacuated` if its line **intersects** any evacuated polygon and
  `is_inundated` if it intersects any inundated polygon. A wall touching both
  carries both flags, and a wall no landslide reached is present with both
  False.
- The damage measure is a flag, not an area or a damage state. No cost is
  attached.
- Output is `temp/vul/wall-landslide-damage-r<nnn>[-pilot].parquet`, built by
  `wall_landslide_damage_path()`, one row per wall with `realisation_id`,
  `rw_id`, `claim_id`, `is_evacuated` and `is_inundated`. `claim_id` is mapped
  from the wall population on `rw_id`. The column names come from
  `landloss.domain.loss_contract`.
- The run prints the number of walls and how many are evacuated, inundated and
  both.

Potential future improvements see `s11_wall_landslide_damage_implementation_plan.md`.
