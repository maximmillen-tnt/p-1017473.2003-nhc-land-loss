# Asset pricing and settlement approach

How every insured asset is priced against every hazard, and how those prices
become a settlement. This is the plan for the `loss` module, and it is what
**T-34** asks to be run past John Leeves.

Marks: **[confirmed]** is settled by a source in the repository, named at the
point of use. **[proposed]** is this document's suggestion and needs a decision.

Two sources carry most of the weight, and they do not agree with each other in
every place:

- `.agents/context/nhi-act-land-cover-explainer.md` — the Act's own mechanics,
  from Bridget Attwood at NHC. **Authoritative.** Where it conflicts with the
  team's working understanding, it wins.
- `.agents/context/nhc-costing-tool.md` — how NHC actually prices a repair,
  from Chris Ewens. Authoritative on the cost build-up, silent on policy.

## 1. What `loss` receives

**[confirmed]** — `.agents/plans/beta-build.md`, "What `loss` receives".

- **Land** — several rows per `address_id`, each `cause`, `area_m2`,
  `land_rate_nzd_per_m2`, `rate_basis`, `cost_year`. Multiple areas, each with
  its own rate and its own hazard.
- **Retaining walls, culverts and bridges** — a **damage state only**:
  `no damage` or `replace`. No repair cost and no repair state.
- `address_id` throughout. A claim-level key is minted **at the `loss`
  boundary**, not upstream (**L-11**).

The consequence is the thing to be clear about: **every dollar attached to a
retaining wall, culvert or bridge is `loss`'s to compute.** `vul` hands over a
verdict, not a price. Land arrives half-priced — an area and a market rate —
and `loss` still has to produce its repair cost.

## 2. The settlement calculation

**[confirmed]** — `nhi-act-land-cover-explainer.md`, with three worked examples.
This is the spine; the pricing sections below exist to feed it.

- A **land cover cap** is assembled per residential building:

  ```text
  land_cover_cap = market_value(damaged insured land areas)
                 + min(udv_retaining_walls,  n_dwellings x $50,000 + GST)
                 + min(udv_bridges_culverts, n_dwellings x $25,000 + GST)
  ```

- **Entitlement = the lesser of the total repair cost and the land cover cap**,
  less the excess.
- **Excess** is $500 per dwelling, capped at $5,000.
- The multiplier is the **number of dwellings in the residential building** —
  not the number of walls, not the number of owners.
- **Two residential buildings on a site means two caps**, worked out separately.
  An appurtenant structure (garage, shed) extends the insured footprint but adds
  no cap.
- Undamaged and uninsured structures are excluded from the calculation.

Three things follow that the model has to get right:

- **The sub-cap is not the wall's contribution.** The contribution is the
  *lesser* of undepreciated value and the sub-cap. A modest timber pole wall
  with a $30,000 undepreciated value contributes $30,000, and the $57,500 limit
  never binds (explainer, Example 3).
- **"Value or repair, not both" is looser than the Act.** The team's working
  note describes an election; the Act describes `min(repair, cap)` where the cap
  is *built from* market value. **[proposed]** implement the Act's arithmetic and
  treat the election language as shorthand for it. Worth confirming with John,
  because it changes what a claim settles at whenever repair cost sits between
  market value and the cap.
- **Land is insured on an indemnity basis**, not replacement. Market value is
  the *prior* value — immediately before the damage, at the date of loss.

### Area cap on the land valued

- Area cap = **the lesser of the district plan minimum area and 4,000 m²**; with
  no district plan minimum it is 4,000 m².
- Damaged area ≤ area cap → value the actual damaged area.
- Damaged area > area cap → value a hypothetical area **equal to the area cap**,
  in the same place with the same features.
- **[proposed]** hold the four territorial authorities' district plan minimum
  lot sizes as a constant table. Nothing in the repository carries them yet.

## 3. The two costings for a land structure

**[confirmed]** — the explainer is explicit, and it is what Chris was describing
from the other side.

Every damaged wall, culvert and bridge needs **both** numbers. They are not
alternatives:

| | Reinstatement / repair cost (SOW) | Undepreciated value (UDV) |
| --- | --- | --- |
| Question | What will it cost to fix? | What would it have cost to build new? |
| Scope | The real remedial solution | The whole insured structure, even if only part is damaged |
| Age | n/a | No deduction for age |
| Includes | Demolition, enabling works, site access, compliance with current standards | **None of those** |
| Feeds | The repair-cost side of `min(repair, cap)` | The cap, via `min(udv, sub-cap)` |

- This is exactly why Chris said under-depreciated value comes out lower than
  the Land SOW, and it settles that question: the gap is the excluded items, not
  depreciation.
- **[proposed]** carry `repair_cost_nzd` and `udv_nzd` as separate columns on
  every structure row. A single "wall cost" cannot serve both sides.
- **Note the asymmetry**: UDV is costed across the *whole insured wall* even
  where only part failed. Since `vul` emits a binary `replace` per wall, the
  beta gets this right by construction — but if a partial-damage state is ever
  added, UDV must not follow it down.

## 4. The pricing matrix

| Asset | Liquefaction | Landslide | Shaking |
| --- | --- | --- | --- |
| **Land** | `ld_state` → cost per property | Evacuated + inundated area → repair scheme | — none |
| **Retaining walls** | Deferred (**T-27**) | Loss of support → `replace` **[proposed]** | Fragility → `replace` **[confirmed]** |
| **Culverts, bridges** | Deferred (**T-27**) | Runout or washout → `replace` **[proposed]** | Fragility → `replace` **[confirmed]** |

Three of the nine cells are empty or deferred, deliberately:

- **Land × shaking** — shaking does not damage land directly. It reaches land
  through liquefaction and landslide, both of which are modelled as their own
  hazards. Leaving this blank is a decision, not an omission.
- **Structures × liquefaction** — settlement and lateral spread do fail walls,
  but the Canterbury land rates may already carry wall, culvert and bridge
  damage inside the per-property figure (**T-27**). **[proposed]** leave these
  cells empty until T-27 closes, because adding them now risks double counting
  the same damage. Reopen the moment the answer arrives.

### 4.1 Land × liquefaction **[confirmed]**

Source: `src/scripts/landloss/vul/liquefaction/land/status.md` and the packaged
asset's README.

- **Damage measure** — `ld_state` 1–6, one value sampled per address.
- **Quantity** — **one per property.** The packaged rates are a cost per
  property per state, not a rate per square metre.
- **Rate** — `costs_liq_ld_refined_states_2011.csv`, 15th / 50th / 85th
  percentiles, 2010/2011 NZD, **excluding GST**.
- **The percentile is a run-level parameter, not a column.** See section 5.1;
  the whole model runs once per percentile rather than carrying three costs down
  every row.
- **Escalate** 2010/2011 dollars to the study's valuation basis (**L-23**),
  with the index as a named constant.
- **States 5 and 6 carry identical costs**, both read from the source band
  "5 or 6". They are one estimate wearing two hats, not two independent ones, so
  the spread at the severe end is thinner evidence than it looks.
- **Flat land only.** These rates must not be applied to hill land or to
  landslide damage.
- **Excludes ILV and IFV** (**L-25**), both of which were large in Canterbury,
  so a total built from this file alone understates what was paid.

> **Discrepancy to resolve.** `beta-build.md` prices this cell as "Dec 2016 ILVR
> rate per m²" applied to "whole insured area". The packaged asset is a flat
> cost per property. One of the two has to change — **[proposed]** the asset is
> right and the beta-build row should read "cost per property".

### 4.2 Land × landslide **[proposed]**

Source: `src/scripts/landloss/vul/landslide/land/status.md`.

- **Damage measure** — evacuated area and inundated area within the insured land
  polygon, kept **separately**, each carrying its parent landslide's depth from
  `V = αA^γ` (γ ≈ 1.46, Massey et al. 2020).
- **Quantity** — the **union** of the two footprints, not their sum. Where
  evacuated and inundated ground overlap, that ground is damaged once.
  Inundated polygons may also overlap each other, so they must be dissolved
  before area is summed or a property under two landslides is charged twice.
- **Evacuated ground** — priced from the T+T landslip remediation schedule
  (`EQCcostestimatesRev10.xlsx` Rev 10, 4 December 2023), sizing the works from
  geometry: wall face area from crown length × scarp height, spoil and backfill
  volume from slip volume.
- **Inundated ground** — two rates per m², one for volumes a shovel and truck
  can clear and one for volumes needing an excavator, varied by access
  (**L-28**).
- **Select the repair scheme as the cheapest feasible** for the retained height
  and slope, so the scheme is a checkable output rather than an input.
- **Per-job items** — survey, geotechnical investigation, consents, inspections
  — apply **once per landslide** and are apportioned across the claims it
  crosses. Charged per claim they would dominate every small slip.
- For the largest landslides the cost exceeds the cap regardless, so precision
  stops paying for itself.

### 4.3 Retaining walls × shaking **[confirmed]**

Source: `src/scripts/landloss/exposure/rw/status.md`.

- **Damage measure** — `no damage` or `replace`, from a fragility curve keyed on
  wall class × size subclass × initial condition, against PGA.
- **Size subclasses** — small below 1 m, medium 1 to 2.5 m, large above 2.5 m.
- **Initial condition** — modern or poor, proxied from dwelling age.
- **Quantity** — one wall.
- **Rate basis** — **[proposed]** square metres of wall face (length × height)
  using the costing tool's *simple* calculator, which the team agreed to use
  over the detailed build-up. This bears directly on **T-32**, which asks
  whether cost scales with length or height: a face-area rate says **both**, and
  `beta-build.md`'s "cost per metre × wall length" quietly drops height. Flag it
  rather than letting the two documents diverge.
- **Add on top of the base rate**: enabling works and reinstatement (**Q-03**),
  excess earthworks and constructability (**Q-04**), and the compliance items —
  council stormwater connection and fall-from-height barrier (**Q-05**).
- **UDV excludes every one of those add-ons.** Same wall, two very different
  numbers. See section 3.
- Partial repair is not modelled; John put it at about 1% of cases (**L-31**).
- Walls qualify within **60 m** of the building, not 8 m, where necessary to
  support or protect the building or the insured land areas.

### 4.4 Retaining walls × landslide **[proposed]**

Nothing in the repository covers this cell, and it is a real gap:

- A wall standing in ground that has evacuated has lost its support and is gone,
  whatever the shaking did to it.
- **[proposed]** a wall whose line intersects an evacuated polygon is `replace`,
  independent of its shaking fragility. A wall under an inundated polygon is
  **[proposed]** also `replace`, since it is buried and would be rebuilt.
- Resolve to a **single** `replace` per wall per realisation. A wall failed by
  both shaking and landslide is one wall and one replacement.
- This needs a decision from Maxim: it is `vul`'s to emit, not `loss`'s to
  infer, so if it is wanted the landslide-to-wall path has to exist upstream.

### 4.5 Culverts and bridges × shaking **[confirmed]**

Source: `src/scripts/landloss/exposure/culverts_bridges/status.md`.

- **Damage measure** — `no damage` or `replace`, no intermediate state. John's
  reasoning: almost every bridge caps out anyway, and there are few enough that
  the choice barely moves the total.
- **Quantity** — one per structure. 80% of crossings are culverts, 20% bridges,
  sampled per realisation under a fixed seed.
- **Coverage filter, applied before any costing** — the **whole structure** must
  qualify. A bridge partly beyond 8 m is not insured unless it qualifies via the
  access way route, and a bridge with one abutment outside the property is not
  covered at all. Structures failing this test cost nothing.
- **Rate** — replacement cost per structure. Not packaged; **[proposed]** two
  flat figures, one per structure type, from the costing tool's `lists` sheet
  when it arrives (**T-38**).
- **T-36** — fragility curves for bridges and culverts are not obtained, so the
  `no damage` / `replace` split has nothing behind it yet.

### 4.6 Culverts and bridges × landslide **[proposed]**

- A culvert buried by runout or a bridge taken out by a slip is `replace`, on
  the same logic as 4.4.
- **[proposed]** structure intersects an evacuated or inundated polygon →
  `replace`, resolved to one replacement per structure per realisation.

## 5. Cost uncertainty and GST

### 5.1 The cost percentiles are a scenario, not a distribution

`costs_liq_ld_refined_states_2011.csv` carries a 15th, 50th and 85th percentile
for every land damage state. They are the spread of **actual settled costs
between Canterbury properties assessed at the same state** — not a confidence
interval on an estimate.

- The spread is large enough to dominate the result: the 85th percentile runs
  between **2 and 4 times the median** depending on the state, so the choice
  moves the liquefaction land component by more than most of the modelling
  decisions in this document.
- **The percentile cannot be applied after the caps.** `min(repair, cap)` is
  non-linear, so a settlement computed from a median cost is not the median
  settlement. Cost varies first; the cap truncates second. This is the reason
  `vul/liquefaction/land/status.md` insists the uncertainty reaches `loss`
  rather than being collapsed upstream.
- **[proposed]** carry the percentile as a **run-level parameter**: one scalar
  in the run configuration, the whole model run once per value, three portfolio
  totals reported as a cost-assumption band.
- The alternative — a `cost_percentile` column on every row — buys nothing here.
  Percentiles exist for **one of the nine cells** in section 4. Landslide land
  interpolates between the remediation schedule's easy and difficult columns,
  which is site difficulty rather than a cost distribution, and the structure
  costs carry no packaged uncertainty at all. The column would be null or
  meaningless nearly everywhere.

Two things to be careful of when the results are written up:

- **Running every property at the 85th percentile does not give the 85th
  percentile of the portfolio total.** It assumes every property errs high
  together. Report it as a systematic cost assumption, not a probabilistic
  bound, or it will be read as one.
- **Drawing each property independently is the opposite error.** The portfolio
  total would converge to a narrow band by the central limit theorem and imply
  precision the data does not support, because real costs correlate — the same
  contractors, the same ground conditions, the same assessors.

### 5.2 GST and cost basis

Every input arrives on a different basis, and the Act mixes them:

| Input | Basis |
| --- | --- |
| Canterbury liquefaction land costs | 2010/2011 NZD, **excluding** GST |
| Market value of damaged land | **Including** GST, at the date of loss |
| Retaining wall sub-cap | $50,000 **+ GST** per dwelling |
| Bridge and culvert sub-cap | $25,000 **+ GST** per dwelling |

- **[proposed]** hold every intermediate quantity **excluding GST**, with a
  single GST rate as a named constant, and convert at the points the Act
  specifies. Market value is the one input that has to be *de*-grossed on the
  way in.
- Escalate the Canterbury rates to the study's valuation basis before anything
  is compared with a present-day market value (**L-23**).
- If results are ever presented excluding GST, say so explicitly to NHC
  (**L-24**).

## 6. Imminent risk

**[confirmed]** that it is in scope — the Act counts imminent damage as damage,
and NHC are considering removing the provision under a land cap, so the study
has to be able to quantify what removing it does.

- The test is that a natural hazard has occurred and the loss is **more likely
  than not to occur within 12 months**, assuming normal weather and no
  remediation of the original damage.
- Entitlement must factor in **either** the cost to prevent the imminent damage
  (mitigation) **or** the cost to repair it once it occurs (future
  reinstatement). **[proposed]** take the lesser of the two, consistent with how
  the rest of the settlement resolves.
- Three forms, all following the evacuated/inundated principle: imminent damage
  of **evacuation**, of **inundation**, and of **re-inundation**.
- **[proposed]** carry it as its own `cause` value on every row it generates, so
  the whole of it can be switched off with a filter and the policy comparison
  becomes a single re-run. This is the headline number NHC has asked for; it
  should not require a code change to produce.
- Extent for evacuation comes from a general rule, not a model — the working
  suggestion is that the scarp regresses another half a metre on average, or a
  metre on slopes steeper than 30°, to be agreed (**T-44**).
- Price it at the baseline evacuated and inundated rates to start, while noting
  that the one NHC report the team has read needed an excavator to peel back a
  head scarp, which suggests imminent risk costs *more* than damage that has
  already happened.

## 7. Metrics and plots

What the module should produce, beyond the settlement table. Everything is per
realisation unless it says otherwise.

**Answering the policy question** — these are what the study is for:

- **Portfolio total against total cap**, swept across the range of total cap
  values under test. This is the single most useful output: one curve, the
  policy dial on the x-axis.
- **Imminent risk on versus off** — portfolio total both ways, and the
  difference as a share.
- **Share of claims binding on each constraint** — repair cost, land cover cap,
  retaining wall sub-cap, bridge and culvert sub-cap. A sub-cap that never
  binds is not doing any work.
- **Settlement with the current scheme against the proposed one**, claim by
  claim, as a scatter with the 1:1 line drawn.

**Understanding the result**:

- Contribution by **cause**, stacked — liquefaction land, landslide loss of
  support, landslide runout, retaining walls, culverts and bridges.
- Contribution by **asset**.
- **Exceedance curve** of settlement per claim.
- **Distribution across realisations** of the portfolio total. Plot the cost
  percentile as three separate curves rather than widening one — it is a
  systematic assumption, not a random variable, and merging the two axes would
  present it as though it were. See section 5.1.
- **Map** of mean settlement per property, and aggregated per suburb.
- Mean settlement and claim count **by suburb** and by territorial authority.

**Checking the result**:

- Claims settling at exactly a sub-cap, counted — a spike is either real or a
  bug, and it is worth knowing which.
- Claims where repair cost is below the excess, so settlement is nil.
- Properties with damage but no cover, from the bridge and wall qualification
  filters, counted rather than dropped silently.

## 8. What has to be decided before this can be built

The settlement core in section 2 needs none of these: it is pure arithmetic and
the explainer's three worked examples test it. Everything below either shapes a
data structure, and so is expensive to retrofit, or supplies a number that a
flagged placeholder can stand in for until it lands.

### Shapes a data structure — decide before writing code

- **The dwelling count.** Every sub-cap is `n_dwellings x $50,000 / $25,000`,
  and the multiplier is dwellings **in the residential building**.
  `insured-land.geoparquet` carries `building_count`, not a dwelling count, and
  nothing upstream produces one. Either the address spine gains the attribute or
  the model assumes one dwelling per building and says so. This touches every
  cap in the study.
- **The claim key.** `beta-build.md` defers minting `claim_id` to the `loss`
  boundary. Claim = address = residential building is a workable placeholder,
  but it has to be one named function rather than an assumption spread across
  the module, because **Q-01** may change it.
- **Whether landslide drives wall and structure damage** — sections 4.4 and
  4.6. This is `vul`'s output to emit, not `loss`'s to infer, so it has to be
  decided before `vul` is built rather than bolted on after.
- **The cost percentile as a run-level parameter** — section 5.1. **[proposed]**
  and not blocking, but it decides whether the percentile is a scalar in the run
  configuration or a column on every row.

### Supplies a number — a flagged placeholder will do meanwhile

Ordered by how much is blocked behind them:

1. **Q-03, Q-04** — the enabling works bands and the excess earthworks and
   constructability percentages. Every structure repair cost scales with these
   and the source contradicts itself. Nothing in section 4.3 is trustworthy
   until they close.
2. **T-27** — whether the Canterbury land rates already include retaining wall,
   culvert and bridge damage. Decides whether the liquefaction column of the
   matrix stays empty, and whether modelling walls separately double counts.
3. ~~**The retaining wall cap.**~~ — **settled.** It is **$50,000 + GST per
   dwelling**, as the explainer states. The flat $25,000 figure in
   `nhc-land-cover-and-settlement.md` was stale and has been corrected, along
   with the explainer's note about the conflict. Remember the sub-cap is a limit
   on the wall's *contribution to the cap*, not a ceiling on the settlement:
   the contribution is the lesser of undepreciated value and the sub-cap.
4. **T-32** — length or height for wall repair cost. Section 4.3 proposes face
   area, which contradicts `beta-build.md`.
5. **Q-01** — whether a property can carry more than one claim. The whole
   settlement is computed per residential building; multiple claims per property
   would change the unit.
6. **Q-02** — how sub-caps interact where a property carries more than one.
7. **The liquefaction land cost basis** — per property or per m². Section 4.1.
8. **Whether landslide drives wall and structure damage** — sections 4.4 and
   4.6. Needs to exist in `vul` if it is wanted.
9. **District plan minimum lot sizes** for the four territorial authorities,
   for the area cap.
