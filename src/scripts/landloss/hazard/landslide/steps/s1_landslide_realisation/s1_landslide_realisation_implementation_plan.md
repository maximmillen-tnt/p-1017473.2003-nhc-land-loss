# Step 1 — Landslide realisation: implementation plan

**Status:** Phase 1 complete and runnable. Phases 2 to 5 replace the placeholder
assumptions in it, one at a time, and none of them has been started.

This step takes the "extend the ESNZ model" route described in the module's
`status.md`: the supplied 32 m probability grid stays as the base rate, and the
three things it does not carry — clustering, individual failures, runout — are
added on top of it. The alternative route, a model built from the ground up, is
drafted in `.agents/plans/estimating-eq-landslide-extent-wellington.md`. Choosing
between them is still open; this step exists so that there is something concrete
to choose against.

## Phase 1 — A runnable realisation, with every assumption stated (complete)

- [x] Read the supplied probability grid through
      `landloss.io.source_material.get_eil_landslide_probability`, with the path
      as a constant and the raster's projection read off the file rather than
      assumed.
- [x] Refuse a grid holding anything outside [0, 1], rather than guessing
      whether it is in per cent or carrying an undeclared nodata marker.
- [x] Sample each cell independently against its own probability.
- [x] Draw a source area per failure from a bounded power law between 3 m² and
      3000 m².
- [x] Place each failure as an area-exact circle at its cell centre.
- [x] Drop every failure overlapping a larger surviving one, largest first.
- [x] Add slope and downhill direction to `landloss.common.utils.terrain`,
      sharing one Horn gradient with the existing slope so the steepness and the
      bearing cannot drift apart, and reading the y axis direction off the
      coordinates so a raster stored either way up gives the same bearing.
- [x] Resample the LINZ DEM onto the probability grid, over an extent buffered
      by three cells so the outermost ring of the grid still gets a slope.
- [x] Displace each failure downhill by a distance ramping from 1 m to 40 m with
      slope, and emit the source and the displaced circle as `evacuated land`
      and `inundated land`.
- [x] Cover the reusable pieces with tests that do not touch the network or the
      T: drive.
- [x] Draw the realisation — where, close up, how big, how far — in
      `fig_landslide_realisation.py`.

## Phase 2 — Fit the size distribution to an inventory

- [ ] Fit the exponent and the bounds to the Kaikōura v3 source polygons
      (DesignSafe PRJ-5827), filtered to greywacke, rather than borrowing
      Massey's 2.1 as the code does now. Massey et al. (2020) report α ≈ 2.10
      above x_min ≈ 500 m², which says nothing about the 3–500 m² range this
      study cares most about, so the fit has to be made over the range being
      sampled — and if the inventory cannot support a fit that low, the honest
      answer may be a second population rather than a single exponent.
- [ ] Decide whether to keep a second population for modified slopes — cuts
      behind houses, fill behind retaining walls — which Kaikōura, an inventory
      of natural slopes, cannot supply. This is the largest technical risk in
      the whole landslide module and is carried in the module's `status.md`.
- [ ] Commit the fitted parameters as a packaged asset, following
      `landloss/io/one_offs/gen_study_extent.py`, so the 31k-polygon inventory is
      not needed day to day.
- [ ] Check the realised size distribution against the inventory's, in the
      figure this step already draws.

## Phase 3 — Replace the displacement ramp with a Newmark displacement

- [ ] Derive a yield acceleration per cell from an infinite-slope factor of
      safety, with strength parameters assigned by geological unit.
- [ ] Compute displacement from the yield acceleration and the shaking, splitting
      by source mechanism — Bray & Macedo (2019) for the crustal faults, Bray,
      Macedo & Travasarou (2018) for Hikurangi — rather than one regression for
      both.
- [ ] Make displacement depend on the size of the failure as well as the slope.
      A 3 m² slip and a 3000 m² one on the same hillside currently travel the
      same distance, which no inventory supports.
- [ ] Reconcile whatever comes out with the 1–40 m range the current ramp
      assumes, and say in the method document which one the results used.

## Phase 4 — Runout that is more than a rigid translation

- [ ] Convert source area to volume (`V = αA^γ`; Massey et al. 2020 give
      γ ≈ 1.46–1.47 for the slide types of interest).
- [ ] Sample a reach angle conditioned on volume from the Kaikōura debris-trail
      polygons, and route the debris down the steepest-descent path rather than
      along a single bearing, widening it as a function of volume.
- [ ] Keep the source and the trail as separate polygon sets, which the current
      output already does, so that nothing downstream has to change.
- [ ] Check reach angles against the inventory.

## Phase 5 — Spatial correlation, and many realisations

- [ ] Correlate failures between neighbouring cells, so that one event produces
      clusters on a hillside rather than a scatter. Independent sampling is the
      largest known error in Phase 1, and it biases the shape of the loss
      distribution rather than its mean.
- [ ] Run N realisations and carry a distribution of affected area per property
      per cause, instead of the single realisation this step produces.
- [ ] Seed from `realisation_seed(BASE_SEED, realisation_id, "landslide")` rather
      than from this step's own `SEED`, and put the realisation id in the output
      file name the way `gen_liq_ld_states.py` writes `ld-state-rNNN.tif`. A
      realisation is one modelled earthquake across all three hazards, so a
      landslide layer and a liquefaction layer can only be summed per address
      once both carry the same `realisation_id`; today the landslide draw is
      independent of it and the single output file cannot be paired with one.
      The beta takes this step as it stands, so this lands with the item above.
- [ ] Check the proportion of landslides confined to a single property against
      the local expectation in `.agents/context/land-damage-mechanisms.md`: most
      confined to one property, with multi-property failures concentrated in
      gullies. If the model does not reproduce that it is wrong regardless of how
      well it matches the literature.

## Open questions

- **What a failing cell means, which is the question that most moves the
  answer.** The grid gives a probability per 32 m cell, which is 1024 m² of
  ground, and this step responds by putting a single failure of a few square
  metres somewhere in it. Over the full study area the probabilities sum to
  66,644 failing cells — 6,824 ha if a failing cell meant the whole cell went —
  while the sampled sizes turn that into 106 ha of source area, 1.6% of it.
  Those are answers to two different questions and only the supplier can say
  which one the grid asks. Until it is settled, no total area from this step
  should be quoted, and the choice between them moves the loss by a factor of
  sixty.
- **What shaking level the grid is conditioned on.** Taken from the file name
  and unconfirmed. The step runs either way; the report cannot describe the
  result without it.
- **Whether the grid's probabilities are conditional on shaking, or already
  include a rate.** Changes what a realisation is a realisation *of*.
- **Why the grid puts any failure probability on flat ground.** Over the full
  study area the result looks right: the sampled failures have a median slope of
  28° and only a tenth sit below 11°, which is the hill country the study cares
  about. The pilot box does not, because it is largely flat suburb — its
  failures have a median slope of 3° and the grid still carries probabilities of
  0.3% to 7.6% across Newtown, Kilbirnie and Rongotai, including reclaimed land
  beside the airport. That is a small share of the total but it is not nothing,
  and it is worth asking whether the grid covers mechanisms other than classic
  slope failure, or is smoothed across the hill margin. **Use the full extent,
  not the pilot box, to judge this step** — the pilot exercises the code, not the
  model.
- **Whether to keep the ESNZ grid as the base rate at all.** This is the module
  level decision in `status.md`, and register entry **L-08** restricts the
  GNS/PRUE model — confirmed to be the same model — to cross-comparison. If the
  team adopts it as the primary model that entry needs revisiting.
