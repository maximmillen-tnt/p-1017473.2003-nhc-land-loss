# Step 10 — Property damage: implementation plan

**Status:** Phase 1 complete and Phase 1a built, with its pilot run open. The
step writes the four contract tables; what the join exposed is not yet fully
resolved.

The step is numbered `s10` because step numbers run across the `vul` module
rather than across one `steps/` folder, and it sits at module level rather than
under a hazard because it is the only step that reads all of them.

## Phase 1 — One row per property (complete, superseded by Phase 1a)

- [x] Read the four vulnerability outputs and the insured land extent through
      their own steps' path functions, so the join cannot drift from what the
      steps actually wrote.
- [x] Spine the join on the insured land, so an undamaged property is present
      with zeros rather than absent.
- [x] Default a quantity to zero and a state to missing, which are different
      statements and should not be collapsed.
- [x] Count structures per property as a total and a number to replace.
- [x] Carry `dwelling_count`, `cost_year`, `rate_basis` and `cost_percentile`
      through, so the basis of every number stays with it.
- [x] Report causes per property, and size the T-27 double count.

## Phase 1a — Four contract tables (complete except the pilot run)

- [x] Replace the one-row-per-property join with the four tables of section 1
      of `.agents/plans/asset-pricing-approach.md`: land, retaining walls,
      culverts and bridges, assembled by `landloss.vul.loss_input`.
- [x] Key every row on its asset id and `claim_id`, both minted in exposure.
- [x] Read the wall and crossing landslide flags from the two new step 11
      landslide steps.
- [x] Split the crossings into culverts and bridges by structure kind.
- [x] Write each table as GeoParquet in EPSG:2193 with a `realisation_id`,
      through `loss_input_path()`.
- [x] Carry `dwelling_count` on land (Q-07) and `is_evacuated` on culverts
      (Q-09) as extra columns.
- [x] Keep the T-27 overlap print, now per claim.
- [ ] Run on the pilot once exposure steps 5 to 7 and the vul steps it reads
      are rerun, and record the counts in the method document.

## Phase 2 — Resolve what the join exposed

- [ ] Close **T-27**: confirm whether the Canterbury land damage rates already
      include retaining wall, culvert and bridge damage. If they do, a claim
      carrying both a liquefaction state and a wall damaged by shaking is
      charged for its wall twice.
- [ ] Decide how two causes on one property combine. They are currently written
      side by side and summed nowhere, which is correct while the landslide side
      is unpriced and will not be once it is.
- [x] Decide whether evacuated and inundated ground on one property are added or
      taken on their union. Resolved: the union, computed in vul step 3 and
      written as `land_slide_total_insured_land_area`.

## Phase 3 — More than one realisation

- [ ] Run the chain over enough realisations to have a distribution rather than
      a point, and write one file per realisation as now.
- [ ] Add a summary across realisations, so the portfolio can be read as an
      exceedance curve rather than a single scenario.

## Potential future improvements

- Emit one row per dwelling rather than one per property, if that turns out to
  be the shape the settlement wants. Today only the representative identifier of
  a block reaches this table, with its dwelling count beside it.
- Carry the cause of each quantity as its own column rather than folding it into
  the column name, once there is more than one hazard per asset class.
