# Beta build: hazard through to repair cost

The aim of the beta is **an end-to-end run that produces the right data
structures**, not the right numbers. Every module takes the structure the
upstream module emits and emits the structure the downstream one expects, with
whatever shortcut gets it there. Settlement is out: the chain stops at **repair
cost**, so caps, sub-caps and the value-versus-repair election are not in it.

The value of this is that the shortcuts can then be replaced one at a time
without anything else moving.

Marks below: **[confirmed]** was specified by the project lead, **[proposed]** is
this document's suggestion and still needs a decision.

## The data structures

One `realisation_id` runs through the whole chain. A hazard layer is produced
per realisation; exposure does not vary by realisation.

| Layer | Object | Geometry | Key fields |
| --- | --- | --- | --- |
| `hazard.shaking` | PGA surface | raster | `pga_g` |
| `hazard.liquefaction` | Land damage state | raster | `ld_state` 1–6 |
| `hazard.landslide` | Evacuated ground | polygons | `landslide_id`, `area_m2`, `depth_m` |
| `hazard.landslide` | Inundated ground | polygons | `landslide_id`, `area_m2`, `depth_m` |
| `exposure.land` | Insured land extent | polygons | `claim_id`, `rate_nzd_per_m2` |
| `exposure.rw` | Retaining walls | lines | `claim_id`, `size_class`, `initial_condition` |
| `exposure.culverts_bridges` | Culverts, bridges | lines | `claim_id`, `structure` |
| `vul.*` | Damage | table | `realisation_id`, `claim_id`, `cause`, `damage`, `quantity` |
| repair cost | Cost | table | `realisation_id`, `claim_id`, `cause`, `repair_cost_nzd` |

**[confirmed]** Shaking is a raster of PGA. Liquefaction is a raster of land
damage states, one raster per realisation. Landslide is polygons of evacuated
and inundated ground, where **the two types may overlap each other but polygons
of the same type may not**. Retaining walls, culverts and bridges are lines;
walls carry size and initial condition.

**The landslide step does not currently meet that last rule.**
`drop_overlapping()` enforces non-overlap among evacuated polygons only.
Inundated polygons are the same circles translated downslope, so two failures
running into the same gully floor overlap — and ground buried twice is buried
once. Either the step dissolves them before emitting, or the consumer dissolves
on the way in; see the open questions.

**[confirmed]** A landslide polygon carries a **depth** as well as an area.
Depth is approximated from the **total evacuated area of the landslide it
belongs to** — a bigger failure is a deeper one — so it is an attribute of the
landslide, not of the piece that happens to fall inside one claim.

**[proposed]** Land damage states are the 1–6 severity scale already defined in
`vul/liquefaction/land/status.md` — None, Minor, Moderate, Major, Severe, Very
Severe — and not the NHC damage *categories*. Keeping that straight is what the
`ld_state` name is for.

### How exposure reads a hazard **[confirmed]**

- **From a raster** — sample **one value per claim**. A claim carries a single
  `ld_state` and a single PGA, and its whole insured area is costed at that
  state's rate.
- **From the landslide polygons** — intersect them with the insured land polygon
  and keep the **area of evacuated and the area of inundated ground separately**.
  Those areas *are* the damage measure; there is no damage state in between.
  Each carries the depth of its parent landslide.

The two are deliberately different. A land damage state is a classification that
a claim either has or does not; a landslide is a piece of geometry that covers
part of a property, and how much of it is covered is the whole question.

### Realisations **[confirmed]**

A `realisation_id` is **one modelled earthquake**. Every hazard layer carrying
that id belongs to the same event, from one seed stream, so a claim's shaking,
liquefaction and landslide damage can be summed within a realisation.

## Module betas

### Shaking **[confirmed]**

Read the NLM TS1170.5 PGA raster directly. No Vs30, no site class, no porting of
`gen_pga_layer`. Realisations come from a **10% coefficient of variation** on
PGA. PGV is not produced — it may be dropped from the study entirely.

### Liquefaction **[confirmed]**

Two steps, replacing lateral spreading entirely.

1. `gen_liq_ld_probabilities` — read the current NLM 2500-year probability
   layer, which carries **Moderate** and **Major** only, and expand it to all
   six states by subdividing what is there.
2. `gen_liq_ld_states` — draw a state per cell from those probabilities and
   write one raster per realisation. **One realisation for the beta.**

The beta skips lateral spreading, so no river buffers and no zone modifier. It
still ends at a raster of `ld_state`, which is the structure the real version
produces.

### Landslide

Already further along than the others: `steps/s1_landslide_realisation/`
produces the evacuated and inundated polygons, resolving same-type overlaps
largest-first. **[proposed]** the beta takes it as it stands, including its two
known shortcuts — independent per-cell sampling with no spatial correlation, and
circular source polygons.

### Exposure **[proposed]**

- `land` — the insured land extent is not built. The beta needs a polygon per
  `claim_id`; the shortcut is a fixed-radius buffer of the building outline,
  skipping driveway generation.
- `rw` — no wall population exists. The beta needs lines with `size_class` and
  `initial_condition`; the shortcut is to place a wall on a fixed share of
  properties by suburb steepness.
- `culverts_bridges` — depends on the insured accessway, which the land
  shortcut above does not produce. The beta may have to place crossings against
  the property boundary instead.

### Vulnerability and repair cost **[proposed]**

| Cause | Asset | Damage measure | Quantity | Rate |
| --- | --- | --- | --- | --- |
| Liquefaction | Land | `ld_state` at the claim | Whole insured area | Dec 2016 ILVR rate per m² |
| Landslide | Land | Evacuated area, inundated area, each with a depth | Area per type | Two rates per m² (**L-28**) |
| Shaking | Retaining wall | No damage / replace | Wall length | Cost per metre |
| Shaking | Culvert, bridge | No damage / replace | One per structure | Cost per structure |

Repair cost is the last column times the quantity. No caps, no election, no GST.

## What still has to be decided

These are the questions the build cannot start without. They are tracked in the
register's `Questions` sheet where they need someone outside the team, and here
where they are ours to settle.

1. **The depth relationship.** Depth is approximated from a landslide's total
   evacuated area, but the function is not set, and evacuated depth and
   inundated depth may not be the same function of it.
2. **Overlapping inundated polygons.** Dissolving them satisfies the same-type
   rule but discards the `landslide_id` that depth hangs off. Keeping them keeps
   depth but makes the consumer responsible for not double counting, and leaves
   open what depth applies where two landslides bury the same ground.
2. **What the insured land polygon is in the beta.** The real extent needs
   driveway generation, which is not built. A fixed buffer of the building
   outline is the obvious shortcut, but it leaves `culverts_bridges` with no
   accessway to test crossings against.
3. **What the retaining wall, culvert and bridge repair costs are.** Nothing is
   packaged, and **T-32** — whether wall cost scales with length or height — is
   still open.
4. **Which percentile of the liquefaction cost rates the beta uses.** The
   packaged rates carry 15th, 50th and 85th.
5. **Whether the hazard layers share a grid.** Proposed: each stays on its
   native grid and exposure samples each separately, since sampling one value
   per claim makes a common grid unnecessary.
