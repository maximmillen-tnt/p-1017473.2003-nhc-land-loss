# Step 3 — Landslide land damage: implementation plan

**Status:** Phase 1 complete. The quantity is measured; nothing is priced.

## Phase 1 — Damaged area and depth per property (complete)

- [x] Intersect the realisation's landslide polygons with the insured land.
- [x] Keep evacuated and inundated ground apart, as the policy does.
- [x] Union the inundated pieces per property rather than summing them, so
      ground two landslides both reached is counted once.
- [x] Carry the depth of the material, weighted by how much of the property
      each landslide contributed.
- [x] Check no property carries more damaged ground of either kind than it has
      insured land, and report it on every run.

## Phase 2 — Pricing

- [ ] Obtain the T+T landslip remediation schedule (**L-28**) and attach a rate.
      Volume, not area, is expected to select the rate — a shovel-scale repair
      and an excavator-scale one are different jobs on the same footprint.
- [ ] Decide whether evacuated and inundated ground are priced by the same
      schedule. Reinstating support and clearing debris are different works.
- [ ] Settle how a property carrying both kinds is settled, given they overlap.

## Phase 3 — Once the hazard is calibrated

- [ ] Rerun when the landslide size distribution is refitted. The realisation
      currently produces two orders of magnitude less damaged ground than the
      ESNZ grid's own expectation, because the size power law is sampled far
      below the scale it was fitted at. Everything this step reports scales
      directly with that, so the areas here are structurally right and
      numerically not to be quoted.
- [ ] Take the inundated footprint from a runout model rather than the source
      circle moved downhill, at which point the evacuated and inundated depths
      stop being equal.

## Potential future improvements

- Report the share of each property's insured land that was damaged, not only
  the area. The settlement compares against the value of the damaged land, so
  the fraction is what the loss module ultimately wants.
- Intersect against retaining walls and crossings as well as land, so a
  landslide can write off a structure rather than only the ground.
