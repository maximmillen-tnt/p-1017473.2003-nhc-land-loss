# Step 6 — Retaining wall population: implementation plan

**Status:** Phases 1 and 1b complete. The population is a beta stand-in.

## Phase 1 — A population of the right shape (complete)

- [x] Draw at most one wall per insured property, against a slope-driven
      prevalence (`beta_wall_prevalence`).
- [x] Size each wall by retained height and classify it small, medium or large
      on the agreed 1 m and 2.5 m boundaries (`classify_wall_size`).
- [x] Give each wall an initial condition, modern or poor.
- [x] Place each wall as a line along the contour (`wall_lines`).
- [x] Seed the draw from the project realisation stream so it reproduces and
      pairs with the hazards.
- [x] Write one file per realisation with the columns the vulnerability work
      reads.

## Phase 1b — Coverage filter and wall id for the loss contract (complete)

- [x] Keep only the walls that intersect their own claim's insured land
      buffered by 2 m (`keep_walls_on_insured_land`), and print the counts kept
      and dropped (`describe_coverage`).
- [x] Give each kept wall a stable `rw_id`, minted after the filter on walls
      sorted by location (`sort_by_location`, `mint_asset_ids`).
- [ ] Rerun over the pilot box and record the kept and dropped counts in the
      method file.

## Phase 2 — Replace the stand-in with the real inference

- [ ] Obtain the SME estimate of wall prevalence by suburb (**T-19**) and
      calibrate prevalence against it, per suburb rather than per slope.
- [ ] Bring the manual mapping study and the remote sensing pilot into the
      repository and train against them.
- [ ] Obtain the ICNZ database and fit the size distribution to it, rather than
      ramping height linearly with slope.
- [ ] Attach a dwelling age attribute to the address spine and set the initial
      condition from it, replacing the even split.
- [ ] Read cut-and-fill and road batter geometry, which is where a large share
      of the walls actually are (**T-11**, **T-20**).
- [ ] Allow more than one wall per property. A steep section commonly has
      several, and the sub-cap is per dwelling, so the count matters to the
      settlement.

## Phase 3 — Placement

- [ ] Place a wall where one would actually be — along a cut face, a boundary or
      a driveway edge — rather than centred on the property's own point. The
      current placement gets the orientation right and the position wrong, which
      matters once a wall is intersected against a landslide footprint.

## Potential future improvements

- Name the six wall classes and attach a published fragility curve to each cell
  of the class, size and condition grid. The classes are still unnamed, which is
  the open decision in `../../status.md`.
- Vary wall length with the frontage of the section rather than with the square
  root of its area.
