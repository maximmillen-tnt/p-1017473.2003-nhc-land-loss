# Step 10 — Property damage: implementation plan

**Status:** Phase 1 complete. The join runs; what it exposes is not yet resolved.

The step is numbered `s10` because step numbers run across the `vul` module
rather than across one `steps/` folder, and it sits at module level rather than
under a hazard because it is the only step that reads all of them.

## Phase 1 — One row per property (complete)

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

## Phase 2 — Resolve what the join exposed

- [ ] Close **T-27**: confirm whether the Canterbury land damage rates already
      include retaining wall, culvert and bridge damage. Over the pilot, 148
      properties carry both a liquefaction state and a wall to replace, and if
      they do, each is charged for its wall twice.
- [ ] Decide how two causes on one property combine. They are currently written
      side by side and summed nowhere, which is correct while the landslide side
      is unpriced and will not be once it is.
- [ ] Decide whether evacuated and inundated ground on one property are added or
      taken on their union. They may overlap each other, and the answer is the
      one recorded for the total footprint rather than the two independently.

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
