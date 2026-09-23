# Loss: status

**Status:** Settlement arithmetic and retaining wall repair pricing implemented
and tested. Nothing reads real data yet — no upstream module emits what it
consumes.

**Updated:** 2026-09-24

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
  both a wall's repair cost and its undepreciated value are built on the costing
  tool's own rates, on a beta flat rate until a wall type mapping is settled.
  Culverts and bridges are not priced.
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
- The **area cap applies**: `damaged_land_value_nzd` values the lesser of the
  damaged area and `area_cap_m2`. The claim takes an area and a rate rather than
  a pre-multiplied market value, because the cap acts on the area — which is
  also the shape `vul` sends.
- **The dwelling count is wired up.** `landloss.loss.claims.dwelling_counts`
  reads it off the `s3_dwellings_per_property` output onto the claims being
  settled, refusing a claim with no count rather than settling it as one
  dwelling. That closed **Q-07**, which was a hard stop on any real run.
- **Inundation removal** is the first line of the Land SOW to land.
  `inundation_volume_m3` and `classify_inundation_earthworks` turn the inundated
  area and mean depth into an earthworks rating, so that one of the three site
  ratings comes off the claim's own geometry. The volume bands, 20 m³ and
  200 m³, are **assumed and unconfirmed** (**Q-11**), and the clearing is folded
  into that rating rather than costed on its own (**L-33**).
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

1. Replace the beta flat rate with a real mapping from size class and initial
   condition onto a construction type. The rates span a factor of 21, so this
   decides more of the answer than anything else in the module.
2. Generate the three site ratings, without which no wall prices at all
   (**Q-10**).
3. Price culverts and bridges.
4. Build a stub input generator matching the contract in
   `.agents/plans/beta-build.md`, so the module can run end to end before the
   upstream modules emit anything.
5. Aggregate `vul`'s four tables onto `claim_id`.
6. Wire to the real layers as each lands, structures last since shaking gates
   them.

## Validation

- The three worked examples in the explainer, as unit tests. They are the only
  fully specified settlements the study has, so they are the primary check
  rather than one of several.
- Share of claims binding on each constraint — repair cost, land cover cap, and
  each sub-cap. A sub-cap that never binds is not doing any work, and a spike of
  claims settling at exactly a cap is either real or a bug. `Settlement` carries
  `capped` and a flag per sub-cap, so each is read off the result rather than
  reconstructed. On a claim with no damaged land, read the sub-cap flag rather
  than `capped`: the cap is below the repair cost by construction there, so
  `capped` is true of every such claim.
- Claims where the excess exceeds what would otherwise be paid, counted rather
  than silently settled at zero.

## Open decisions

- **What a dwelling is (Q-07, closed).** The count now comes from the
  module-level exposure step `s3_dwellings_per_property`, read on by
  `landloss.loss.claims.dwelling_counts`. A dwelling is an **address point**
  rather than a self-contained dwelling, so the count is a floor on a block of
  flats and an over-count on a mixed-use building. `settle`
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
- **Where the site ratings come from (Q-10).** The multiplier applies to the
  wall construction subtotal alone, which makes the three ratings a per-wall
  figure belonging on the retaining wall table. `earthworks_required` can now be
  derived from the inundation volume, but construction access and
  constructability cannot, and `SiteRatings` has no default, so no wall can be
  priced yet. They cannot be looked up for a synthetic population and have to be
  inferred; the inputs — slope, and the building-to-road path — are already held
  in `exposure`.
- **What the inundation volume bands should be (Q-11).** 20 m³ and 200 m³ are
  assumed and unconfirmed. They set the earthworks rating on every land claim,
  and through it the markup on any wall on the same property.
- **Whether inundation removal is its own cost line (L-33).** Folded into the
  earthworks rating for now. Because the multiplier reaches wall construction
  alone, a claim with inundated ground and no wall is currently charged nothing
  for the clearing.
- **Whether the replacement should be a higher specification than the wall it
  replaces (L-34).** Both numbers come off the same square-metre rate, which is
  how the costing spreadsheet works and is the agreed basis. It assumes the
  replacement matches the wall that failed, where walls are often rebuilt to a
  more substantial current standard that would want a higher rate on the repair
  side. The bias runs one way — understating repair cost can only lower a
  settlement — so the study under-reports rather than over-reports.
- **Q-01** — whether a property can carry more than one claim, which decides
  whether the claim key is the identity of `address_id`.
- **Q-02** — how the sub-caps interact where a property carries more than one,
  and how a total cap sits over them. The total cap is currently applied to the
  land cover cap, which is equivalent to applying it to the entitlement.
- **Whether a total cap binds before or after the excess.** Applied before, on
  the reading that it caps cover rather than payment. Not confirmed.
- The rest are in `.agents/plans/asset-pricing-approach.md`, section 8.

## Questions outstanding

Raised by Perrie Gilbert, 2026-09-24. Not yet numbered in
`.agents/context/register.json`, and not yet put to NHC.

**What the retaining wall rate covers.**

- Is one square-metre rate fair for both *building* a wall and *valuing* one?
  Repair cost and UDV both come off it today, separated only by the site
  multiplier.
- Does the rate carry non-construction costs at all — geotechnical fees, design,
  building and resource consent, survey? If it does not, they are missing from
  both numbers, and it needs saying where they are captured instead.
- Should the Land SOW use a higher rate than UDV, on the basis that a failed wall
  is rebuilt to a more substantial current standard? Recorded as **L-34** and
  still open.

**The site ratings, and the costs that sit outside them.**

- How are constructability, construction access and earthworks required to be
  determined for a synthetic population at all (**Q-10**)?
- Is earthworks difficulty independent of the inundation volume? If it is,
  clearing the spoil belongs as its own cost line rather than as a nudge to a
  multiplier (**L-33**).
- The same question for survey and any other flat cost: are they added, and if
  so **before or after** the multiplier is applied? The two give different
  answers.

**The wall's condition, as a proxy for replacement specification.**

- Should `initial_condition` — modern or poor — set the rate the replacement is
  priced at? The interest is in it as a proxy for **specification, not age**: a
  poor wall is likelier than a modern one to be rebuilt to a higher standard. So
  it is a candidate mechanism for the gap **L-34** describes between the Land SOW
  rate and the UDV rate, rather than a deduction from UDV, which undepreciated
  value does not take.
- Two things stand between it and that job. The attribute is defined as being
  read off the **age of the dwelling** (`landloss.exposure.rw.beta_population`),
  so using it for specification is a second inference laid on an age
  classification — and in the beta it is not read off anything, but drawn at a
  50% poor share. It also changes no number anywhere today: the beta fragility
  is a flat 0.7 whatever the condition, and pricing never reads it. So the
  premise is worth correcting — it is not "only used for vulnerability", it is
  carried and unused, in vulnerability as much as in pricing.

**Land damage and wall damage on the same claim.**

- How is damaged land associated with a damaged wall? A settlement generally
  assumes that repairing the wall also reinstates the land it retained.
- Does that make the claim the right unit — one repair cost for the whole claim,
  compared against the summed UDV and land value across it? That is what `settle`
  does today, and it is an assumption rather than a finding.
- When does land damage with no wall present call for a **new** wall to be built,
  and at what size? Does that need the slope of the land?
- Where one property carries both — a wall damaged in one place, and independent
  land damage elsewhere on the same property that would need a new wall — how are
  the two kept apart?
