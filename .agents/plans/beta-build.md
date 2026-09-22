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
| `exposure.land` | Insured land extent | polygons | `address_id`, `land_rate_nzd_per_m2`, `area_m2` |
| `exposure.rw` | Retaining walls | lines | `claim_id`, `size_class`, `initial_condition` |
| `exposure.culverts_bridges` | Culverts, bridges | lines | `claim_id`, `structure` |
| `vul.*` | Damage | table | `realisation_id`, `claim_id`, `cause`, `damage`, `quantity` |
| repair cost | Cost | table | `realisation_id`, `claim_id`, `cause`, `repair_cost_nzd` |

**Shaking** is a raster of PGA. **Liquefaction** is a raster of land damage
states, one per realisation. **Landslide** is polygons of evacuated and
inundated ground.

**Evacuated polygons may not overlap each other; inundated polygons may.** Two
failures running into the same gully floor do land on top of one another, and
that is allowed. What is not allowed is an orphan: if an evacuated polygon is
dropped, its paired inundated polygon goes with it. The existing step already
satisfies both — `drop_overlapping()` runs on the source frame *before*
`to_polygons()` builds the two rows, so a dropped failure takes its runout with
it, and the pair share a `landslide_id`.

A landslide polygon carries a **depth** as well as an area, from the volume–area
power law `V = αA^γ` (Massey et al. 2020 give γ ≈ 1.46 for Kaikōura), so mean
depth is `V/A`. The parent landslide's total evacuated area is simply
`source_area_m2` — one evacuated polygon per landslide, nothing to aggregate.
Note that the beta rebuilds the runout circle at the *same radius* as the
source, so the two depths come out identical; that is correct for the structure
and wrong for the world.

### How exposure reads a hazard

- **From a raster** — sample **one value per address**. An address carries a
  single `ld_state` and a single PGA.
- **From the landslide polygons** — intersect with the insured land polygon and
  keep the **evacuated and inundated areas separately**. Those areas *are* the
  damage measure.

### Realisations

A `realisation_id` is **one modelled earthquake**, with one seed stream shared
across the hazards, so a claim's causes can be summed within a realisation.

### The identifier

`address_id` throughout. `claim_id` exists in no Python today; renaming happens
at the `loss` boundary when a real claim key arrives.

### What `loss` receives

- **Land** — several rows per address: `cause`, `area_m2`, `land_rate_nzd_per_m2`,
  plus `rate_basis` and `cost_year`. Multiple areas, each with its own rate and
  its own hazard.
- **Retaining walls, culverts and bridges** — a **damage state** only, no repair
  cost and no repair state. `loss` receives `no damage` or `replace`.

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

## Naming what gets deleted

Anything that exists **because** of the beta carries `beta` in its name, so a
grep finds everything the beta has to give back. `beta_expand_ld_probabilities`,
`BETA_NONE_SHARES` and `BETA_MAJOR_SHARES` manufacture land damage states the
National Liquefaction Model does not supply, and go when it does.

Mark only what is genuinely temporary. In the same module `exceedance_to_bands`
and `draw_ld_states` carry no prefix, because differencing an exceedance pair
and drawing a state from probabilities are correct whatever supplies the bands.
The test is not "was this written during the beta" but "will this be deleted
when the real input arrives".

## What is still open

- ~~Exceedance or band probabilities~~ — **settled.** The NLM grids are
  exceedance probabilities, so the Moderate band is `p_moderate − p_major` and
  the None band is `1 − p_moderate`. `expand_ld_probabilities` differences them
  itself rather than trusting a caller, and refuses a swapped pair. The Major
  reader is `nlm.get_nlm_scenario_rp2500y_gwd_med_p_ld_major_fu()`.
- **Landslide land repair rates.** The T+T remediation schedule is not packaged,
  so the beta uses flagged placeholders.
- **Wall, culvert and bridge repair costs** are out of scope for the beta by
  decision, not by omission.

The sequenced build order, the new library functions and the verification steps
are in the approved implementation plan rather than repeated here.
