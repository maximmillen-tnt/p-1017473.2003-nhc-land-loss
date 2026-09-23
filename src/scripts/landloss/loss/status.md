# Loss: status

**Status:** Settlement arithmetic and retaining wall repair pricing implemented
and tested. Nothing reads real data yet — no upstream module emits what it
consumes.

**Updated:** 2026-09-23

## Approach

Marks: `[x]` done, `[~]` partly done, `[>]` next, `[ ]` planned.

The full approach, covering pricing for every asset against every hazard, is
`.agents/plans/asset-pricing-approach.md`. It is drafted and awaiting review by
Maxim Millen and John Leeves (**T-34**); the review is retrospective, so the
build proceeds against it rather than waiting.

- [x] Settle on the **Act's own arithmetic** rather than the "value or repair"
  election the team's working notes describe. The Act builds a land cover cap
  from the market value of the damaged land plus each structure's contribution,
  then pays the lesser of that cap and the repair cost, less the excess.
- [x] Hold the policy settings as a **value, not constants**, so a scenario can
  be passed around and two can run in one process. `total_cap_nzd` and
  `include_imminent_damage` are the settings under test.
- [x] Work **GST-inclusive throughout**, because that is the basis the Act
  compares market value, undepreciated value and repair cost on. The sub-caps
  are stated excluding GST and are grossed up at the point of use.
- [~] **Price the land structures**, which this module owns: `vul` emits a
  damage state for walls, culverts and bridges rather than a cost, so both the
  repair cost and the undepreciated value are worked out here. Retaining wall
  repair cost is built on the costing tool's own rates and site multiplier, on
  a beta flat rate until a wall type mapping is settled. Undepreciated value
  waits on its sheet of set fees, and culverts and bridges are not priced.
- [ ] **Aggregate four tables to a claim.** `vul` hands over land, retaining
  walls, culverts and bridges as separate tables, each carrying `claim_id` and
  coordinates. The key arrives rather than being minted here, which is a change
  from what **L-11** assumed; what this module owes is the roll-up onto it.
- [ ] Carry the **cost percentile as a run-level parameter**, one scalar per
  run, rather than a column on every row. Only one of the nine asset-hazard
  cells has packaged percentiles.
- [ ] Produce the **policy comparison outputs** — portfolio total swept across
  total cap values, and imminent risk on against off.

## Where it is now

The settlement core is built and is the only part that needed no upstream data.

- `landloss.loss.policy` holds `PolicySettings`, defaulting to the current Act:
  the two sub-caps per dwelling excluding GST, the land excess, the 4,000 m²
  area cap and a GST rate confirmed at 15% by the explainer's own worked figure.
- `landloss.loss.settlement` holds `land_cover_cap_nzd`, `settle`,
  `DamagedClaim` and `Settlement`. Arrays in, arrays out, so a portfolio settles
  in one call.
- `landloss.loss.pricing` carries the 29 retaining wall square-metre rates from
  the costing tool's `lists` sheet, excluding GST, and the site multiplier that
  goes on top: three ratings — construction access, earthworks required, and
  constructability and reinstatement — each easy, moderate or difficult, summed
  at 0%, 5% and 10% to a ceiling of 30%. A wall's repair cost is rate × face
  area × (1 + multiplier), grossed up to GST-inclusive. This closed **Q-03** and
  **Q-04**.
- Every wall is priced at `BETA_WALL_RATE_EXCL_GST_NZD_PER_M2`, $766.6375 per m²
  excluding GST — the average of the four non-driven timber pole rates — because
  nothing maps a modelled wall onto a construction type. Size reaches the cost
  through face area rather than through the rate, and initial condition does not
  reach it at all.
- `tests/landloss/loss/test_settlement.py` runs the three worked examples in
  `.agents/context/nhi-act-land-cover-explainer.md` plus the misreadings the
  module exists to prevent. `test_pricing.py` checks the multiplier against all
  27 rows of the tool's combination table, which is why the module computes the
  figure rather than storing the table.
- Nothing reads a real layer. No module upstream emits the damage rows this one
  consumes: `vul` produces nothing for Wellington yet, `exposure.rw` and
  `exposure.culverts_bridges` are empty, and the shaking hazard has no code at
  all, so the structures half of the pricing matrix has no input.

## Next

1. Undepreciated value, from the costing tool's own sheet of set fees. It is
   not derivable from the square-metre rates, and without it `settle` has no
   structure contribution to build the land cover cap from. This is what keeps
   the settlement chain from closing for a wall claim.
2. Replace the beta flat rate with a real mapping from size class and initial
   condition onto a construction type. The rates span a factor of 21, so this
   decides more of the answer than anything else in the module.
3. Price culverts and bridges.
4. Build a stub input generator matching the contract in
   `.agents/plans/beta-build.md`, so the module can run end to end before the
   upstream modules emit anything.
5. Aggregate `vul`'s four tables onto `claim_id`, and apply the area cap, which
   the contract's separate area and rate columns now make possible.
6. Wire to the real layers as each lands, structures last since shaking gates
   them.

## Validation

- The three worked examples in the explainer, as unit tests. They are the only
  fully specified settlements the study has, so they are the primary check
  rather than one of several.
- Share of claims binding on each constraint — repair cost, land cover cap, and
  each sub-cap. A sub-cap that never binds is not doing any work, and a spike of
  claims settling at exactly a cap is either real or a bug.
- Claims where the excess exceeds what would otherwise be paid, counted rather
  than silently settled at zero.

## Open decisions

- **The dwelling count (Q-07).** Every sub-cap multiplies by dwellings in the
  residential building, and no layer produces one — `insured-land.geoparquet`
  carries `building_count`, and `vul`'s contract carries nothing. `settle`
  refuses a count below one rather than
  reading a zero as "no cover", so the gap fails loudly instead of quietly
  halving caps.
- **Which wall types the study runs.** The costing tool prices 29 construction
  types and `vul` hands over a size class, so something has to choose. The team
  agreed at the costing tool demo to run three types with simple numbers; which
  three is not recorded. A flat average of the non-driven timber pole rates
  stands in, which prices a population that is really part concrete and part
  steel below what it would settle at.
- **Whether a set height per size class is enough (I-14).** `vul` sends
  `rw_size` and `rw_length`, and the rate is charged on wall face, so a band has
  to become a height. Settled for now as 0.75 m, 1.75 m and 2.75 m — the middle
  of what each class can contain, given the population draws over 0.4 to 3.0 m.
  A size class therefore carries no variation of its own, so the spread in wall
  cost comes from length and the site ratings alone. Drawing within the band, or
  taking the height off the slope, would add it back.
- **How the per-cause damage flags combine (Q-06, Q-09).** A wall carries a flag
  each for shaking, evacuation and inundation. Since a damaged structure is
  replaced rather than repaired, any flag being true is one replacement, not
  three — but nothing yet says whether the land areas behind those flags are
  already a union or have still to be unioned.
- **What the site ratings are driven by.** The multiplier is implemented and the
  duty geotechnical report supplies all three ratings, but nothing in the model
  generates them yet, so every wall would currently have to be rated by hand or
  by assumption.
- **Q-01** — whether a property can carry more than one claim, which decides
  whether the claim key is the identity of `address_id`.
- **Q-02** — how the sub-caps interact where a property carries more than one,
  and how a total cap sits over them. The total cap is currently applied to the
  land cover cap, which is equivalent to applying it to the entitlement.
- **Whether a total cap binds before or after the excess.** Applied before, on
  the reading that it caps cover rather than payment. Not confirmed.
- The rest are in `.agents/plans/asset-pricing-approach.md`, section 8.
