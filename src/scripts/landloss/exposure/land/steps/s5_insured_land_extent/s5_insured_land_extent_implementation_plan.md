# Step 5 — Insured land extent: implementation plan

**Status:** Phases 1 and 2b complete. Phase 2 is the driveway, which is the part
of the insured land definition the beta leaves out; Phase 3 and Phase 4 wait on
the property boundary layer and on the District Valuation Roll data.

The step is numbered `s5` because step numbers run across the `exposure` module
rather than across one `steps/` folder. `s1` is the address spine at module
level, `s2` the land value, and `s3` and `s4` are reserved for the property
boundary and the driveway work that Phases 2 and 3 below build.

## Phase 1 — The 8 metre buffer (complete)

- [x] Read the LINZ NZ Building Outlines layer for an extent, with the licence
      and publisher on the reader
      (`landloss.io.readers.get_nz_building_outlines`).
- [x] Attach every building outline to its nearest address point, with a
      distance beyond which no address is claimed
      (`landloss.exposure.land.extent.attach_buildings_to_addresses`).
- [x] Buffer the outlines by the insured land distance and merge them into one
      polygon per address
      (`landloss.exposure.land.extent.buffer_buildings`).
- [x] Split ground shared between two properties on which building is nearer, so
      that the extents do not overlap and area cannot be counted twice
      (`landloss.exposure.land.extent.split_shared_ground`).
- [x] Write the layer with the rate per square metre carried onto it
      (`gen_insured_land.py`).
- [x] Print the addresses that found no building, the buildings that found no
      address, the ground two properties shared, and the measured area against
      the lot size step 2 assumed (`describe_*` in `gen_insured_land.py`).
- [x] Draw the close-up the buffer is judged by eye against
      (`fig_insured_land.py`).
- [x] Cover the arithmetic with synthetic geometries
      (`tests/landloss/exposure/land/test_extent.py`).

## Phase 2 — Driveways

The insured land definition includes the driveway, and the beta does not build
it. Driveways are where most retaining walls sit, so the gap matters more than
the area it covers.

- [x] Read the LINZ roadway layer over the study extent, and pin it as a named
      constant beside `NZ_BUILDING_OUTLINES_LAYER_ID`.
- [ ] Generate a driveway as the shortest path from each building outline to the
      roadway. This resolves **I-10**, which proposed mapping them by remote
      sensing.
- [ ] Decide the gradient above which a generated route is not a credible
      driveway, and what happens to a building with no route below it.
- [ ] Combine the driveway with the 8 metre buffer before the shared ground is
      split, so a driveway running between two houses is allocated by the same
      rule as the rest of the ground.

## Phase 2b — Multi-unit properties (complete)

Taken out of Phase 3 because it was the single largest distortion in the beta:
a building went to exactly one address, so 3,827 of the pilot's 8,591 addresses
carried no insured land at all and passed through the whole chain contributing
nothing.

- [x] Collapse addresses sharing a coordinate into one property carrying a
      `dwelling_count`, which is what NHC's per-dwelling sub-caps and excess
      multiply (`landloss.exposure.land.extent.collapse_coincident_addresses`).
- [x] Share one outline with every further address whose own point stands on it,
      within a tolerance tight enough to decline a vacant section next door.
- [x] Partition the ground around a shared outline by the nearest of the
      addresses on it, so the units' shares are disjoint and sum to that
      building's buffer.
- [x] Report the properties still carrying no land by how far their point stands
      from the nearest outline, which is what separates a vacant section from a
      gap in the outline layer.

Over the pilot this takes coverage from 4,764 addresses of 8,591 to 5,765
properties of 6,351, covering 7,862 of the 8,591 dwellings.

- [ ] Decide whether the representative identifier is the right key, or whether
      the loss module should receive one row per dwelling. Only the lowest
      identifier of a block reaches the extent today, so a join on address will
      not find the others.
- [ ] Recover the 572 properties whose point stands more than a metre from any
      outline. Some are vacant sections and should stay out; some are address
      points placed off their dwelling and should not.
- [ ] Stop assuming a building outline belongs to one property.
      `validations/check_outlines_against_boundaries.py` finds 241 of the
      pilot's 6,927 outlines with at least 5 m2 and 10% of their footprint
      outside their best-covering property, and **77% of those span two
      freehold titles** — semi-detached and terraced houses captured as one
      polygon. 92 of them carry more than one address, which is 16% of every
      shared outline and the direct cause of the bad merges below. A further
      3,227 outlines poke out by a median of 0.30 m2, which is the two layers
      disagreeing and not a building on two titles.
- [ ] Use `title_type` from the LINZ property boundaries to decide the merges
      rather than only to audit them.
      `validations/check_multi_unit_titles.py` measures the gap: of the 562
      groups sharing one building outline, 339 sit inside a single property and
      142 span unit titles stacked on one footprint, but **81 reach across
      ground LINZ holds apart** and should not have been merged. On the
      coincident-address collapse, 1,278 of the 2,815 addresses involved carry a
      freehold title, which is where a genuine multi-dwelling freehold property
      and a bad join are indistinguishable without the boundaries.

## Phase 3 — Attribute against the property boundaries

- [ ] Read the property boundary layer over the study extent, and pin it as a
      named constant.
- [ ] Clip the extent to the property it belongs to, so that a buffer does not
      reach across a boundary onto land the policy does not cover.
- [ ] Decide what happens to a building that straddles a boundary.
- [ ] Check the multi-unit and cross-lease handling of Phase 2b against the
      parcels, which are the only evidence of which units actually share land.
      The ground around a block is currently divided between its units by
      proximity alone, and how those settle in practice is still **T-23**.

## Phase 4 — Close the loop on land value

- [ ] Feed the measured insured area back into step 2 in place of the
      per-authority `median_lot_size_m2`, which closes most of **T-25**.
- [ ] Apply the premium on land within 2 m of a building, once the District
      Valuation Roll data of **T-20** is there to size it against.
- [ ] Extend `validations/check_land_value_totals.py` to check total modelled
      insured land value against the published rating valuation totals, now that
      area is measured rather than assumed.

## Phase 5 — Validate the extent

- [ ] Insured land area per property against the parcel area it sits inside, per
      territorial authority. A distribution that is a plausible share of the
      section is the check that the buffer is behaving.
- [ ] Count of properties with no building outline, per territorial authority,
      as a validation rather than as a line of run output.

## Potential future improvements

- Distinguish a dwelling from a garage or a shed. The outline layer's `use`
  column is populated for very few residential buildings, so the extent is
  currently buffered off every structure on a property, including ones a
  dwelling-triggered cover might not reach.
- Partition the shared ground on distance to the *parcel* rather than to the
  building, once the property boundaries are read. Nearest building is a good
  rule where the boundary is unknown and the wrong one where it is known.
- Speed. `split_shared_ground` builds a Voronoi diagram over points spaced along
  every contested building outline, which is most of the buildings in a suburb.
  It is comfortable over the pilot box and has not been run over the four
  territorial authorities; clustering the contested properties and partitioning
  each cluster separately is the obvious answer if it turns out to matter.
