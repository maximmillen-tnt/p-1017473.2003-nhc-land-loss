# Step 9 — Culvert and bridge damage state: implementation plan

**Status:** Phase 1 complete, but unexercised — the pilot holds no crossings.

## Phase 1 — A damage state on every structure (complete)

- [x] Read the crossing population and the realisation's PGA field.
- [x] Sample PGA at each structure's midpoint and carry it onto the output.
- [x] Draw no damage or replace against a failure probability.
- [x] Carry the kind of structure through as the asset, so the loss module can
      price a culvert and a bridge differently under their shared sub-cap.
- [x] Seed the draw from the realisation's vulnerability stream.
- [x] Report an empty population as a coverage fact rather than a blank table.

## Phase 2 — A population worth running over

- [ ] Run over the full study area, where the named watercourse layers do
      produce crossings. The pilot box contains none, so nothing here has been
      exercised against real rows.
- [ ] Widen the population beyond named watercourses. Most private crossings
      are over unnamed drains and gullies, which is most of what is missing.

## Phase 3 — A real fragility

- [ ] Define separate fragility curves for culverts and bridges. They fail
      differently and the flat 70% treats them as one.
- [ ] Index the curve on span, material and age once the population carries
      them.

## Potential future improvements

- Let a landslide take out a crossing, which in the hill suburbs is the more
  likely cause than shaking alone.
- Model the access consequence. A written-off crossing can strand a property
  whose land is otherwise undamaged, which the current chain cannot express.
