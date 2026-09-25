# Step 11 — Crossing landslide damage: implementation plan

**Status:** Phase 1 complete. The flags are written; the pilot has not been
rerun against the regenerated crossing population.

## Phase 1 — Landslide flags per crossing (complete)

- [x] Read the crossing population and the landslide realisation per
      realisation.
- [x] Flag each crossing `is_evacuated` and `is_inundated` by intersection with
      the evacuated and inundated polygons, through
      `landloss.vul.landslide.flags.landslide_flags()`.
- [x] Key the output on `crossing_id` and carry `claim_id`, for the split into
      culverts and bridges at vul step 10.
- [x] Write an empty file with the full columns when there are no crossings.

## Phase 2 — Run on regenerated inputs

- [ ] Rerun exposure steps 5 and 7, then this step, and record the counts
      flagged over the pilot and the full extent.
- [ ] Settle **Q-09**: whether culverts leaving out `is_evacuated` is
      deliberate, and so
      whether `is_evacuated` stays on the culvert table.

## Potential future improvements

- Flag a crossing only where a meaningful length of it is reached, rather than
  on any intersection, once the landslide footprints are calibrated.
