# Step 7 — Culvert and bridge crossings: implementation plan

**Status:** Phase 1 complete. Empty over the pilot box, by geography.

## Phase 1 — Crossings of the right shape (complete)

- [x] Pin the LINZ river name polygons layer as a constant and add a reader
      beside `get_nz_river_name_lines`.
- [x] Have step 5 write the driveway corridors out, so the accessway survives as
      its own layer rather than only inside the insured land extent.
- [x] Detect crossings by intersecting the accessways against both river layers,
      recording which layer found each one.
- [x] Draw a culvert or a bridge at each crossing under the project realisation
      seed, and write one file per realisation.

## Phase 2 — Make the population mean something

- [ ] Run over the four territorial authorities. The pilot box holds no named
      watercourse at all, so nothing about the detection has been exercised
      against real crossings yet — only against synthetic geometry in the tests.
- [ ] Add the unnamed streams. Both LINZ layers carry named watercourses only,
      and the small accessway crossings this step exists to find are mostly on
      unnamed ones, so the count is a floor. The topo50 centrelines are the
      obvious source; whether they are needed is the open decision on
      `../../status.md`.
- [ ] Confirm the coverage of both layers over the study area. They are
      published as pilots, so a crossing rate derived from them should not be
      quoted until that is checked.

## Phase 3 — Beyond the generated accessway

- [ ] Re-detect once driveways are routed rather than drawn straight. A crossing
      is currently found where a straight line from the building to the road
      meets water, which is not where a real driveway crosses.

## Potential future improvements

- Replace the 80/20 split with something fitted. The figures are engineering
  judgement and will need disclosing in the report; no register limitation
  covers them yet.
- Carry the width of the watercourse onto the crossing, so a structure's size
  follows the span it has to cross rather than being uniform.
