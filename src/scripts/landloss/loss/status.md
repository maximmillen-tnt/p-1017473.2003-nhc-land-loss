# Loss: status

**Status:** Settlement arithmetic implemented and tested against the Act's
worked examples. Nothing reads real data yet — no upstream module emits what it
consumes.

**Updated:** 2026-09-22

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
- [>] **Price the land structures**, which this module owns: `vul` emits a
  damage state for walls, culverts and bridges rather than a cost, so both the
  repair cost and the undepreciated value are worked out here.
- [ ] **Mint the claim key.** `address_id` runs the length of the chain and a
  claim-level identifier is introduced at this boundary (**L-11**), behind one
  named function so **Q-01** can change it without touching anything else.
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
- `tests/landloss/loss/test_settlement.py` runs the three worked examples in
  `.agents/context/nhi-act-land-cover-explainer.md` plus the misreadings the
  module exists to prevent.
- Nothing reads a real layer. No module upstream emits the damage rows this one
  consumes: `vul` produces nothing for Wellington yet, `exposure.rw` and
  `exposure.culverts_bridges` are empty, and the shaking hazard has no code at
  all, so the structures half of the pricing matrix has no input.

## Next

1. Price the retaining walls, culverts and bridges — repair cost and
   undepreciated value as separate quantities, against flagged placeholder rates
   until the NHC costing tool arrives (**T-37**, **T-38**).
2. Build a stub input generator matching the contract in
   `.agents/plans/beta-build.md`, so the module can run end to end before the
   upstream modules emit anything.
3. Mint the claim key and aggregate the per-cause rows to a claim.
4. Wire to the real layers as each lands, structures last since shaking gates
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

- **The dwelling count.** Every sub-cap multiplies by dwellings in the
  residential building, and no layer produces one — `insured-land.geoparquet`
  carries `building_count`. `settle` refuses a count below one rather than
  reading a zero as "no cover", so the gap fails loudly instead of quietly
  halving caps.
- **Q-01** — whether a property can carry more than one claim, which decides
  whether the claim key is the identity of `address_id`.
- **Q-02** — how the sub-caps interact where a property carries more than one,
  and how a total cap sits over them. The total cap is currently applied to the
  land cover cap, which is equivalent to applying it to the entitlement.
- **Whether a total cap binds before or after the excess.** Applied before, on
  the reading that it caps cover rather than payment. Not confirmed.
- The rest are in `.agents/plans/asset-pricing-approach.md`, section 8.
