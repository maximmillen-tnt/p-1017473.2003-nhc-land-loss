# Step 2 — Slope failure susceptibility: implementation plan

**Status:** Phase 1 and Phase 2 complete. The step runs over the Johnsonville
and Newlands pilot and writes a rating and a zone raster.

## Background

Greater Wellington's earthquake-induced slope failure layer is published
CC BY-ND, so nothing may be derived from it. This step rebuilds the scheme
behind it — Kingsbury (1995), WRC/PP-T-95/06 to /10 — from its own inputs, so
that the result is ours to use. The full method extraction, the licence
position, and what is and is not obtainable are in
`.agents/plans/rebuilding-gwrc-slope-failure-susceptibility.md`. Read that
before changing anything here.

Three scope decisions made on 23 September 2026 shape what is built:

1. **Residential land only.** Quarries, state highway and rail corridor cuts are
   out. Suburban subdivision earthworks are in, which is what the Wellington
   City Council layers hold.
2. **The geology factor is a constant.** The source itself says geology mattered
   least, and Kingsbury's own worked examples use a single value for everything
   moderate and above. Weathering state and crushed/shattered mapping are not
   chased.
3. **Validation is by visual comparison** against the published layer displayed
   unchanged. The published weightings are adopted as they stand and never
   re-tuned, so the unlocated Hancox et al. (1994) calibration report is not a
   blocker.

## Phase 1 — The scoring scheme (complete)

- [x] Implement Table 4's factor values and weightings and Table 5's zone bands
      in `landloss.hazard.landslide.susceptibility`.
- [x] Verify against Kingsbury's own worked examples in Table 6.
- [x] Band onto the same 1–5 ranks as the published layer's `SEVERITY`, so the
      two are directly comparable.
- [x] Record that the two lowest worked examples do not decompose into published
      class values, and reproduce only the three that do.

## Phase 2 — The factor grids and the rating (complete)

- [x] Add `local_relief` to `landloss.common.utils.terrain`, for the height of a
      steep face.
- [x] Add `WLG_EARTHWORKS_PILOT` to `landloss.io.area_of_interest`. The existing
      `SMALL_WLG_PILOT` sits over Mt Victoria and holds no earthworks polygons at
      all, so it cannot exercise the modification factor.
- [x] Slope angle from the elevation model at the coarse working resolution.
- [x] Cut angle and face height from the elevation model at the fine resolution,
      inside the mapped cut and fill polygons.
- [x] Aggregate the fine factors onto the coarse grid by maximum.
- [x] Geology, landslides and groundwater as constants from `config.py`.
- [x] Write the rating and the zone rasters, and print the zone areas.

## Phase 3 — Visual comparison against the published layer

- [x] Figure putting the rebuilt zones beside the GWRC layer over the same
      extent, drawn by `fig_slope_susceptibility.py`.
- [ ] Decide, from that figure, whether the arithmetic alone is close enough to
      be useful, or whether Phase 4 is needed.

## Phase 4 — The 1995 generalisation rules

Not started. The published map is generalised polygons, not a scored grid, and
section 4.4.2 of the booklets sets out the rules used. Without them the rebuilt
grid is systematically less severe than the published map. Each rule is a
separate piece of work:

- [ ] Expand a steep facet to the whole slope it occupies.
- [ ] Add the downslope runout allowance.
- [ ] The tear-drop rule for a small steep area high on a gentle slope.
- [ ] Force every modified slope into the high or very high zone, which is what
      the source does regardless of the arithmetic.

## Phase 5 — Coverage

Not started. The cut and fill records reach about a tenth of insured land, and
only in Wellington City.

- [ ] Chase the equivalent earthworks records from Porirua, Lower Hutt and Upper
      Hutt.
- [ ] Detect cut faces and sidling fills from the elevation model over the
      insured land extent, for the nine tenths of Wellington City the records do
      not reach. This is the same terrain work the retaining wall exposure needs.
- [ ] Run over the full earthworks extent rather than the pilot. The fine pass is
      240 km² at the pilot's resolution, so this needs the fetch chunking before
      it is attempted.

## Phase 6 — A score per property

Not started. The scope decision is that the product is a susceptibility score on
insured land, not a regional map.

- [ ] Reduce the zone raster onto the insured land extent, one score per
      property.
- [ ] Decide the reduction: the maximum zone under the insured land, the area
      weighted mean, or the share of insured land in each zone.

## Known limitations carried by the current build

- The landslide factor is zero everywhere, because no inventory is held. That
  removes up to 20 of the 150 points and flattens the distinction the source
  drew between ground with old slides, ground with active slides, and ground
  with neither.
- The geology and groundwater factors are constants, so they shift every cell
  equally and change no ranking. The values chosen are the ones Kingsbury used in
  the worked examples, and the sensitivity to them has not been run.
- Slope modification is scored only inside mapped earthworks polygons. Everywhere
  else scores zero, which under this scheme means it cannot reach the high or
  very high zone on modification at all.
- The face height is local relief in a moving window, not a measured toe to crest
  height. A window wider than the face overstates it; a window narrower
  understates it.
- Fine factors are aggregated to the coarse grid by maximum, which follows the
  source's own statement that a steep component controls the stability of the
  whole slope, but it does mean a single steep cell lifts its whole coarse cell.

## Potential future improvements

- Fit the slope support length rather than assuming the coarse resolution
  matches the 1995 terrain model, and report how the zone areas move with it.
- Use the GNS SLIDE morphology layer's scarps and breaks in slope as a partial
  landslide inventory, and its retaining walls against the source's rule that
  adequately retained slopes are excluded from the high zone.
- Run the geology and groundwater constants at their other class values and
  report how many properties change zone. One line, and it settles how much the
  two simplifications cost.
