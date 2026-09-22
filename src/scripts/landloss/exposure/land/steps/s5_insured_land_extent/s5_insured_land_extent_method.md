# Step 5 — Insured land extent: method

- The step turns each valued address into the polygon the hazard modules are
  intersected against. `gen_insured_land.py` reads
  `temp/exposure/land-value-by-address.geoparquet` from step 2, fetches the
  building outlines over its extent, builds the insured land and writes
  `temp/exposure/insured-land.geoparquet`. Both take a `-pilot` suffix when
  `config.PILOT` is set, so a pilot run cannot overwrite the full outputs.
- The written layer carries `address_id`, `land_rate_nzd_per_m2`, `area_m2`,
  `building_count` and the polygon. The rate is step 2's, merged on
  `address_id` and not recomputed here.
- Building outlines come from the LINZ NZ Building Outlines layer through
  `landloss.io.readers.get_nz_building_outlines`, whose docstring carries the
  CC BY 4.0 licence and what attribution it obliges anything published from this
  layer to carry. The layer ID is
  `landloss.domain.constants.NZ_BUILDING_OUTLINES_LAYER_ID`.
- They are fetched over the addresses' own bounding box grown by
  `FETCH_MARGIN_M` in `gen_insured_land.py` — the join distance plus the buffer
  — so a building belonging to an address near the edge is still in the read.
- The insured land is an 8 metre buffer of the building outlines. The distance
  is `landloss.exposure.land.extent.INSURED_LAND_BUFFER_M`, and the module
  docstring records that it is NHC's own definition from
  `.agents/context/nhc-land-cover-and-settlement.md` rather than a setting of
  this run, which is why it is not in `config.py`.
- **Driveways are part of that definition and are not built.** The module
  docstring of `src/landloss/exposure/land/extent.py` says so and says what it
  costs: driveways are where most retaining walls sit, and a property whose
  driveway runs past the 8 metre line has that part of its insured land missing.
- Each building is attached to the nearest address point by
  `landloss.exposure.land.extent.attach_buildings_to_addresses`, a nearest join
  capped at `MAX_BUILDING_TO_ADDRESS_M`. The two cases the rule gets wrong — a
  rear building nearer the neighbour's frontage point, and a block of flats split
  between its own address points — are written out in the module docstring, the
  second being register task T-23.
- An address with no building inside that distance gets no row, so it carries no
  insured land and contributes zero area downstream rather than a polygon nobody
  can defend. `describe_coverage()` in `gen_insured_land.py` prints how many
  addresses that is, which is the only visible sign of a building the outline
  layer has not captured.
- A property's buildings are buffered and then merged into a single polygon by
  `landloss.exposure.land.extent.buffer_buildings`, so a house and a garage give
  one piece of insured land and one `building_count` of two.
- Ground within 8 metres of two properties' buildings is given to the nearer
  building by `landloss.exposure.land.extent.split_shared_ground`, so no square
  metre belongs to two addresses. The vulnerability step sums area per address,
  and without the split the strip between two houses would be paid for twice.
- That split is built as a Voronoi diagram of points spaced
  `PARTITION_DENSIFY_M` apart along the contested building outlines
  (`landloss.exposure.land.extent.nearest_building_cells`), taken as its edges
  and rebuilt into faces so that the cells are disjoint by construction, then
  clipped back to each address's own buffer. Only extents that touch another are
  rebuilt; the rest pass through untouched.
- `describe_shared_ground()` in `gen_insured_land.py` prints how much ground was
  shared and re-measures the result against its own dissolve, so a run states
  rather than assumes that the extents do not overlap.
- `describe_areas()` prints the insured area distribution against the
  per-authority `assumed_lot_size_m2` step 2 divided by to get its rate. The two
  describe different pieces of ground until register task T-25 closes, and the
  run says so.
- The extent is judged by eye in the figure produced by `fig_insured_land.py`,
  written to `report/exposure/land/insured-land/fig/`: the busiest neighbourhood
  in the run at `config.CLOSE_UP_M` across, one colour per property with the
  building outlines over the top, beside the insured area distribution across
  the whole run.
- Run settings live in `config.py` beside the scripts — the pilot extent,
  whether to reuse the clipped building outlines, and the close-up width. Both
  scripts read the same file, and `fig_insured_land.py` asks
  `gen_insured_land.insured_land_path` for the layer to draw.
- The arithmetic is covered by `tests/landloss/exposure/land/test_extent.py`
  against synthetic squares: the buffered area of a single building, two
  buildings on one address dissolving into one row, an address with no building
  dropping out, two neighbours' extents summing to the ground they cover between
  them without overlapping, nine houses on a grid partitioning that ground
  between them, a small building inside a neighbour's buffer keeping its own
  ground, and the refusals on a mismatched or geographic coordinate reference
  system.

- The insured land is the 8 m building buffer **combined with the driveway**, as
  NHC's definition has it. Driveways are generated by
  `landloss.exposure.land.driveways.generate_driveways`: the straight line from
  each building to the nearest point on the nearest road, buffered to a corridor
  `2 * DRIVEWAY_HALF_WIDTH_M` wide. That is the shortest path in the plane, which
  is what the approach asks for, and the module docstring sets out the three
  things it therefore is not.
- Roads come from the LINZ **NZ Addresses: Roads** layer through
  `landloss.io.readers.get_nz_address_roads`, rather than the topographic
  centrelines, because it belongs to the same addressing dataset as the address
  spine, so a property's road and its address point already agree.
- A building already touching a road gets no driveway, since the building buffer
  already covers that ground, and one further than `MAX_DRIVEWAY_LENGTH_M` from
  any road is taken to reach none.
- **Driveways are unioned in before the ground is partitioned, not after.** A
  driveway running past a neighbour's house is contested ground like any other,
  and merging it into a finished extent would leave two properties holding the
  same strip. `add_driveways` runs between `buffer_buildings` and
  `split_shared_ground`, so the summed area still equals the distinct ground the
  run prints.
- Over the pilot box 6,726 of 6,735 attached buildings reach a road, with a
  median driveway of 12.7 m, and the insured land totals 290.1 ha with zero
  overlap.

Potential future improvements: see `s5_insured_land_extent_implementation_plan.md`.
