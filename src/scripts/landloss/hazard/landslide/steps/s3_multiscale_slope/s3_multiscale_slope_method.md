# Step 3 — Multiscale slope: method

- The step builds a DEM and a slope raster at each cell size in `RESOLUTIONS_M`
  in `config.py` — 10, 30 and 100 m — and is run by `gen_multiscale_slope.py`.
  The script takes no command line arguments; `config.py` is read in its
  `if __name__ == "__main__":` block and passed into `main()`.
- `PILOT` is `True`, so runs go over `SMALL_WLG_PILOT` from
  `landloss.io.area_of_interest`. With it `False` the extent is the bounding box
  of the four territorial authorities from `get_study_areas()`.
- The extent is snapped outward in `snap_outward()` to a whole multiple of the
  least common multiple of the cell sizes — 300 m for 10, 30 and 100 — so every
  grid tiles it exactly and all of them share its top-left corner. It is padded
  by the same step on every side for the fetch. The padding holds the one cell
  border Horn's kernel cannot compute, and is trimmed off in `trim_to_extent()`
  before anything is written. `trim_to_extent()` selects on cell centres, so it
  never keeps a cell that only touches the box.
- The fetched DEM is cut to the padded extent before any averaging. `get_dem`
  sends the extent to LINZ in WGS84 and the rectangle grows on the round trip,
  so the DEM comes back larger than asked, with its corner off the round
  coordinate the blocks have to be counted from.
- Only the finest cell size is fetched, by `landloss.io.readers.get_dem`, which
  reads LINZ's STAC elevation catalogue: LiDAR where flown, the 8 m
  contour-derived model elsewhere. It carries limitation L-12, the mixed
  LiDAR vintage across the study area.
- Every coarser DEM is the block mean of the finest, from
  `landloss.common.utils.terrain.block_mean()`. Blocks are counted from the
  grid's top-left corner, so the grids nest; part blocks along the bottom and
  right edges are dropped; and a block less than half real ground is NaN. This
  is done here rather than by asking LINZ for the coarse size, because LINZ's
  loader resamples bilinearly and would sample rather than average the ground.
  `check_resolutions()` refuses a cell size that is not a whole multiple of the
  finest.
- Slope is Horn's method, `landloss.common.utils.terrain.slope_degrees()`, the
  same as every other slope in the study, computed on each DEM at its own cell
  size. A 100 m slope is the gradient over about 300 m, not a smoothed 10 m
  slope.
- The run prints, per cell size, the grid, its top-left origin, the elevation
  range, the slope deciles and the share of the extent in Kingsbury's slope
  classes (`SLOPE_CLASS_EDGES`).
- Outputs are `dem-<n>m.tif` and `slope-<n>m.tif` under `temp/hazard/landslide/`,
  with a `-pilot` suffix for pilot runs. They are working layers and are not
  committed.

Potential future improvements: see `s3_multiscale_slope_implementation_plan.md`.
