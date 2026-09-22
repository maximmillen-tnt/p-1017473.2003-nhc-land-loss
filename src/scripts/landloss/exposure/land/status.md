# Land exposure: status

**Status:** Land value modelled per square metre, and applied to an insured land
extent buffered off the building outlines. The driveway part of that extent is
not built.

**Updated:** 2026-09-22

## Approach

Marks: `[x]` done, `[~]` partly done, `[>]` next, `[ ]` planned.

The module ends at one layer, `insured-land`, carrying one row per `address_id`
with a rate per square metre and the insured land polygon. Everything below
exists to produce that layer.

- [~] Take the insured extent as an **8 m buffer of the building outlines, combined
  with the driveway**, rather than the whole parcel. That is the land NHC
  settles on, so it is the extent the hazard modules intersect against. The
  buffer is built; the driveway is not.
- [>] **Generate driveways** as the shortest path from each building outline to the
  roadway, since no driveway dataset exists for the study area. This resolves
  **I-10**, which proposed mapping them by remote sensing.
- [ ] Attribute the extent against the **property boundaries**, which supply the
  identifier and the property each piece of insured land belongs to.
- [~] Apply the modelled **rate per square metre** to the insured extent, with a
  **premium on land within 2 m of a building** — the land immediately supporting
  the dwelling is worth more than the rest of the section, and it is also the
  land whose loss matters most.
- [x] Key on `address_id`, which is what the address spine carries. A claim-level
      identifier is introduced at the `loss` boundary rather than minted here,
      so nothing upstream has to be rewritten when one arrives (**L-11**).

Land value per square metre is a step in its own right and is already built; see
`steps/s2_land_value/`.

## Where it is now

The rate per square metre and the polygon it is applied to both exist. The
polygon is the buffer alone, so it is short of the driveway.

- `../steps/s1_address_spine/` builds the address spine that this and every other
  asset hangs off. It sits at module level because retaining walls, culverts
  and bridges
  read it too.
- `steps/s2_land_value/` values every address — landform class, DEM slope and
  topographic position, and the indexed rating valuations — and writes
  `land-value-by-address.geoparquet` under `temp/exposure/`. That layer is the
  `land-value` input the rest of the chain consumes.
- `validations/check_land_value_totals.py` checks those outputs against the
  published anchors.
- `steps/s5_insured_land_extent/` buffers the LINZ building outlines by 8 m,
  attaches each building to its nearest address point, splits ground shared
  between two properties on which building is nearer so nothing is counted
  twice, and writes `insured-land.geoparquet` under `temp/exposure/` carrying
  `address_id`, `land_rate_nzd_per_m2`, `area_m2` and the polygon. That layer is
  what the hazard modules intersect against.
- The building outlines are read by `landloss.io.readers.get_nz_building_outlines`
  against `NZ_BUILDING_OUTLINES_LAYER_ID`. The property boundary and roadway
  layers are still not read by anything in the repository, and neither is
  covered by a constant in `src/landloss/domain/constants.py`.
- Neither the driveway generation nor the 2 m premium is implemented.
- Land area is measured on the insured land layer, but the rate per square metre
  is still built on the per-authority `median_lot_size_m2` assumption, so the
  two describe different pieces of ground. The run prints one against the other.

## Next

1. Read the property boundary and roadway layers over the study extent, and pin
   both as named constants beside `NZ_BUILDING_OUTLINES_LAYER_ID`.
2. Generate driveways as the shortest building-to-roadway path, and decide how a
   route that is too steep to be a driveway is handled.
3. Combine the driveways with the 8 m buffer, before the shared ground is split,
   so a driveway between two houses is allocated by the same rule.
4. Clip the extent to the property boundaries, so a buffer cannot reach across a
   boundary onto land the policy does not cover.
5. Add the 2 m premium to the rate per square metre.
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

- **T-07** — the remaining LINZ datasets. Building outlines are read; the parcel
  and roadway layers are not confirmed.
- **T-25** — the assumed lot size, which a measured insured area replaces.
- **L-11** — the claim-level identifier. The layer is keyed on `address_id`; a
  claim key is mapped in at the `loss` boundary when one is agreed.
- **T-23** — multi-unit, cross-lease and shared-land properties. An 8 m buffer
  around a block of flats is one extent over several claims, and the split has
  not been decided.
- The gradient above which a generated driveway route is not a credible
  driveway, and what happens to the building when no route below it exists.
- The size of the 2 m premium, which is engineering judgement until the District
  Valuation Roll data lands under **T-20**.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
