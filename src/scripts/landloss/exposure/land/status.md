# Land exposure: status

**Status:** Land value modelled per square metre; the insured land extent it is
applied to is not built yet.

**Updated:** 2026-09-18

## Approach

The module ends at one layer, `insured-land`, carrying one row per `claim_id`
with a rate per square metre and the insured land polygon. Everything below
exists to produce that layer.

- Take the insured extent as an **8 m buffer of the building outlines, combined
  with the driveway**, rather than the whole parcel. That is the land NHC
  settles on, so it is the extent the hazard modules intersect against.
- **Generate driveways** as the shortest path from each building outline to the
  roadway, since no driveway dataset exists for the study area. This resolves
  **I-10**, which proposed mapping them by remote sensing.
- Attribute the extent against the **property boundaries**, which supply the
  identifier and the property each piece of insured land belongs to.
- Apply the modelled **rate per square metre** to the insured extent, with a
  **premium on land within 2 m of a building** — the land immediately supporting
  the dwelling is worth more than the rest of the section, and it is also the
  land whose loss matters most.
- Key on `claim_id`. It currently carries the same value as `address_id` and is
  held as its own column so the two can decouple (**L-11**).

Land value per square metre is a step in its own right and is already built; see
`steps/s2_land_value/`.

## Where it is now

The rate per square metre exists; the geometry it should be applied to does not.

- `../steps/s1_address_spine/` builds the address spine that this and every other
  asset hangs off. It sits at module level because retaining walls and culverts
  read it too.
- `steps/s2_land_value/` values every address — landform class, DEM slope and
  topographic position, and the indexed rating valuations — and writes
  `land-value-by-address.geoparquet` under `temp/exposure/`. That layer is the
  `land-value` input the rest of the chain consumes.
- `validations/check_land_value_totals.py` checks those outputs against the
  published anchors.
- Building outlines are already held. The property boundary and roadway layers
  are not yet read by anything in the repository, and neither is covered by a
  constant in `src/landloss/domain/constants.py`.
- No part of the driveway generation, the 8 m buffer, the insured land extent or
  the 2 m premium is implemented.
- Land area is still the per-authority `median_lot_size_m2` assumption, not a
  measured polygon, so no property yet carries a real insured area.

## Next

1. Read the property boundary and roadway layers over the study extent, and pin
   all three input layers as named constants beside the existing ones.
2. Generate driveways as the shortest building-to-roadway path, and decide how a
   route that is too steep to be a driveway is handled.
3. Buffer the building outlines by 8 m and combine with the driveways to give
   the insured land extent.
4. Attribute the extent to properties against the property boundaries, carrying
   `claim_id`.
5. Assign the rate per square metre, with the 2 m premium, and write
   `insured-land`.
6. Feed the measured insured area back into the land value step, replacing the
   assumed lot size. This closes most of **T-25**.

## Validation

- Insured land area per property against the parcel area it sits inside, per
  territorial authority. A distribution that is a plausible share of the section
  is the check that the buffer and the driveway are behaving.
- Count of properties with no building outline, and of buildings with no route
  to a roadway, printed per territorial authority so the joins are auditable
  rather than silently dropping properties.
- Driveway lengths against the sections they cross — a driveway longer than the
  parcel is a routing failure.
- Total modelled insured land value against the published rating valuation
  totals, extending `validations/check_land_value_totals.py` once area is
  measured rather than assumed.

## Open decisions

- **T-07** — the remaining LINZ datasets. Building outlines are held; the parcel
  and roadway layers are not confirmed.
- **T-25** — the assumed lot size, which a measured insured area replaces.
- **L-11** — the claim-level identifier. `claim_id` is held apart from
  `address_id` in anticipation of decoupling.
- **T-23** — multi-unit, cross-lease and shared-land properties. An 8 m buffer
  around a block of flats is one extent over several claims, and the split has
  not been decided.
- The gradient above which a generated driveway route is not a credible
  driveway, and what happens to the building when no route below it exists.
- The size of the 2 m premium, which is engineering judgement until the District
  Valuation Roll data lands under **T-20**.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
