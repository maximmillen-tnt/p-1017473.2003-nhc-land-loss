# Retaining walls, landslide: status

**Status:** Evacuated and inundated flags are written per wall. Not yet run on
the pilot.

**Updated:** 2026-09-24

## Approach

Marks: `[x]` done, `[~]` partly done, `[>]` next, `[ ]` planned.

- [x] Intersect each insured wall with the realisation's evacuated and inundated
  polygons, and flag the two kinds of ground separately because the policy
  settles them differently.

## Loss contract

What this module owes the retaining wall table `loss` reads, as set in
`.agents/plans/asset-pricing-approach.md` section 1.

Marks: `[x]` done, `[~]` partly done, `[>]` next, `[ ]` planned.

- [x] Supply `is_evacuated`.
- [x] Supply `is_inundated`.
- [x] Key every row on `rw_id`, carrying `claim_id` beside it.

## Where it is now

- `steps/s11_wall_landslide_damage/` reads the wall population and the landslide
  realisation and writes both flags per wall. It has not yet been run on the
  pilot: the wall population on disk predates `rw_id`, so exposure step 6 has to
  be rerun first.

## Next

Not yet defined.

## Validation

Not yet defined.

## Open decisions

Not yet defined.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
