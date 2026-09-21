# Culvert and bridge exposure: status

**Status:** Approach agreed. Not implemented, and waiting on the insured
accessway layer it is defined against.

**Updated:** 2026-09-21

## Approach

Intended, not implemented.

- Take the exposure as **a watercourse crossing the insured accessway**. A
  culvert or a bridge exists to carry the accessway over water, so the crossing
  is the thing to detect and there is nothing to find where the accessway
  crosses nothing.
- Count **any watercourse**, not only the named rivers that
  `classify_waterways` separates out. Most accessway crossings are of small
  streams, so filtering to named rivers would drop the bulk of the population.
- Where a watercourse does cross, assign **a 10% chance of a bridge and a 60%
  chance of a culvert**. The two are mutually exclusive, and the remaining 30%
  carries neither structure. Both figures are engineering judgement.
- **Sample** the structure per realisation rather than carrying an expected
  value, under a **fixed random seed** so a run reproduces. Sampling matches
  the Monte Carlo realisations the landslide module produces.
- Read the rivers from **both LINZ pilot layers** — the name lines
  ([103632](https://data.linz.govt.nz/layer/103632-nz-river-name-lines-pilot/))
  and the name polygons
  ([103631](https://data.linz.govt.nz/layer/103631-nz-river-name-polygons-pilot/)).
  A narrow stream exists only as a centreline, while a wider river has an areal
  extent, so a crossing test against the lines alone would miss the rivers most
  likely to need a bridge.
- Reuse the river layer the liquefaction work already reads rather than
  introducing a second source, so a watercourse is classified the same way
  across the study.

The insured accessway is the driveway component of the insured land extent built
in `../land/`, so this module cannot run before that one does.

## Where it is now

Nothing is implemented. This file and `__init__.py` are the only things in the
folder.

- The river name **lines** layer is already available:
  `NZ_RIVER_NAME_LINES_LAYER_ID` in `src/landloss/domain/constants.py`, read by
  `landloss.io.readers.get_nz_river_name_lines`, with
  `landloss.hazard.liquefaction.waterways.classify_waterways` splitting named
  rivers from other watercourses. It was added for lateral spreading, and this
  module reads the same layer rather than a new one.
- The river name **polygons** layer is not pinned as a constant and has no
  reader.
- The insured accessway does not exist yet. Driveway generation is item 2 of
  `Next` in `../land/status.md`, and the crossing test has nothing to intersect
  until it lands.

## Next

1. Pin the river name polygons layer as a constant and add a reader beside
   `get_nz_river_name_lines`.
2. Detect crossings by intersecting the insured accessway with the river lines
   and polygons, once the accessway exists.
3. Sample a bridge, a culvert or neither at each crossing under a fixed seed,
   and write the result per `claim_id`.

## Validation

- Share of properties with a detected crossing, by territorial authority. An
  implausibly high rate points at the driveway routing crossing water it should
  not, rather than at the crossing test itself, so this checks the upstream
  layer as much as this one.
- Detected crossings against a manual check on aerial imagery for a sample of
  properties. There is no crossing dataset to validate against, so a
  hand-checked sample is the only ground truth available.
- Crossings found on the polygon layer but not the line layer, counted rather
  than merged away, which is the check that reading both layers earns its place.

## Open decisions

- Both source layers carry **named** watercourses only. Counting any
  watercourse therefore still misses the unnamed streams, which is where the
  small accessway crossings mostly are, so whether the topo50 centrelines are
  needed alongside them is open.
- The 10% and 60% figures are engineering judgement and will need disclosing
  in the report. No register limitation covers them yet.
- Sampling is the method for now. Whether an expected value per property
  replaces it later depends on how the loss module consumes the realisations.
- Both LINZ layers are published as pilots, so their coverage over the study
  area should be confirmed before the crossing rate is trusted.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
