# Step 11 — Crossing landslide damage: method

- The step records **whether a landslide reached each culvert or bridge, and
  from where**. It is run by `gen_crossing_landslide_damage.py`, and the test is
  `landloss.vul.landslide.flags.landslide_flags()`.
- The damage measure is **a flag, not an area**. A structure is settled on
  whether a landslide reached it at all, unlike land, where the quantity is how
  much ground was taken.
- Crossings come from exposure step 7's
  `temp/exposure/crossing-population-r<nnn>[-pilot].geoparquet` and landslides
  from the hazard module's
  `temp/hazard/landslide/landslide-realisation-r<nnn>[-pilot].geoparquet`, each
  read through its own step's path function. Both are read per realisation,
  because which structure sits at a crossing is itself a draw.
- Only insured crossings arrive here: exposure step 7 keeps a crossing only
  where it lies wholly inside its claim's insured land.
- A crossing whose geometry **intersects an evacuated polygon** is
  `is_evacuated`; one that **intersects an inundated polygon** is
  `is_inundated`. A crossing touching both kinds of ground carries both flags.
  The land classes are the ones named in
  `landloss.vul.landslide.land.damaged_area`.
- `is_evacuated` is computed for **culverts as well as bridges**. The contract
  in `.agents/plans/asset-pricing-approach.md` section 1 asks for it on bridges
  only; culverts carry it as an extra column, pending **Q-09**.
- Rows are keyed on `crossing_id`, the id minted in exposure step 7, and carry
  `claim_id`. The split into `culvert_id` and `bridge_id` by structure kind
  happens at vul step 10, not here. Column names come from
  `landloss.domain.loss_contract`.
- **Every crossing is written**, one row each, with both flags False where no
  landslide reached it. The run prints how many carry each flag and how many
  carry both.
- An empty crossing population, as over the pilot box, writes an empty file
  with the same columns and boolean flags, and the run prints "no crossings
  over this extent".
- A crossing population written before `crossing_id` existed is refused with a
  message to rerun exposure steps 5 and 7.
- Output is `temp/vul/crossing-landslide-damage-r<nnn>[-pilot].parquet`, with
  columns `realisation_id`, `crossing_id`, `claim_id`, `is_evacuated`,
  `is_inundated`.

Potential future improvements see
`s11_crossing_landslide_damage_implementation_plan.md`.
