# Step 9 — Retaining wall damage state: implementation plan

**Status:** Phase 1 complete. The fragility is a flat 70%.

## Phase 1 — A damage state on every wall (complete)

- [x] Read the wall population and the realisation's PGA field.
- [x] Sample PGA at each wall's midpoint and carry it onto the output.
- [x] Draw no damage or replace against a failure probability.
- [x] Seed the draw from the realisation's vulnerability stream, so it
      reproduces and pairs with the hazards of the same modelled earthquake.
- [x] Report the split, the PGA range, and how many properties carry a wall to
      replace.

## Phase 2 — A real fragility

- [ ] Define the fragility curves, as a probability of failure against ground
      motion. Replaces `beta_failure_probability` with a function of the wall
      and the shaking; nothing downstream changes.
- [ ] Index the curve on size class and initial condition. Both already ride on
      every row and are currently ignored.
- [ ] Name the wall classes the curves are defined for. This is still the open
      decision in the retaining wall exposure status file.

## Phase 3 — Once the shaking field varies

- [ ] Rerun when the Vs30 model drives the site class, which is where the
      spatial variation in PGA is meant to come from. Today the whole pilot
      reads one acceleration, so the fragility has nothing to discriminate on
      even once it is a function of PGA.
- [ ] Decide whether walls on one property fail together. They are drawn
      independently, and two walls on the same slope are not independent.

## Potential future improvements

- Allow a landslide to write off a wall directly, rather than shaking alone.
- Carry the failure probability forward as a probability rather than a draw, so
  the portfolio can be evaluated in expectation as well as by realisation.
