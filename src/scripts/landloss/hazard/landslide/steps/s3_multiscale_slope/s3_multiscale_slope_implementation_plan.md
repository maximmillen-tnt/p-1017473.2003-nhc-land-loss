# Step 3 — Multiscale slope: implementation plan

**Status:** Phase 1 complete over the pilot. The full study area has not been
run.

## Background

Slope is a property of the length it is measured over, and the models the
landslide hazard draws on were calibrated at different ones: Kingsbury's slope
classes against a 20 m contour model, and the global earthquake-induced
landslide models against 30 m and coarser grids. This step builds the DEM and
the slope at 10, 30 and 100 m so the hazard work can read whichever its
calibration needs, and so the effect of the cell size is visible.

The coarse DEMs are block means of the 10 m fetch rather than separate fetches
from LINZ, because LINZ's elevation loader resamples bilinearly and reads a
handful of points per 100 m cell rather than the ground under it.

## Phase 1 — Build the DEM and slope at each cell size (complete)

- [x] Add `block_mean()` to `landloss.common.utils.terrain`, averaging whole
      blocks and masking blocks under half real ground.
- [x] Fetch the 10 m DEM once over the extent, snapped to the coarsest cell and
      padded by one, and block-average it to 30 and 100 m.
- [x] Compute Horn's slope at each cell size, trim the margin, and write the DEM
      and slope per cell size.
- [x] Print the grid, the slope deciles and the share in Kingsbury's slope
      classes per cell size.

## Phase 2 — Full study area

- [ ] Run with `PILOT = False` over the four territorial authorities. The 10 m
      fetch is a background job of tens of minutes.
- [ ] Decide whether the 10 m DEM here should replace the one the land value
      step fetches separately, so the study holds one 10 m DEM rather than two
      over slightly different extents.

## Phase 3 — Comparison

- [ ] A `fig_multiscale_slope.py` figure of the three slopes side by side over
      a hillside, and the slope class shares against cell size.
- [ ] Decide which cell size each hazard consumer reads — the susceptibility
      step's slope factor, the realisation step's failure probability — and
      record it in their method documents.
