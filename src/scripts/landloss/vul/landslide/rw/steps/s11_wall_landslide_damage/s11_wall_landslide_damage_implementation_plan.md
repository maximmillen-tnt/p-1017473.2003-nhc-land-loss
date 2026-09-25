# Step 11 — Retaining wall landslide damage: implementation plan

**Status:** Phase 1 complete. Walls are flagged; nothing is priced.

## Phase 1 — Evacuated and inundated flags per wall (complete)

- [x] Read the insured wall population from exposure step 6 and the landslide
      realisation from hazard step 1, each through its own step's path function.
- [x] Intersect each wall with the realisation's evacuated and inundated
      polygons and flag it for each kind of ground separately.
- [x] Key the output on `rw_id` and carry `claim_id` from the wall population.
- [x] Print the count of walls, evacuated, inundated and both on every run.

## Phase 2 — Run on the pilot

- [ ] Run over the pilot once exposure step 6 has been rerun, so the wall
      population carries `rw_id`.

## Potential future improvements

- Flag a wall by the share of its length inside the landslide rather than by
  any intersection, so a wall clipped at one end is not written off whole.
