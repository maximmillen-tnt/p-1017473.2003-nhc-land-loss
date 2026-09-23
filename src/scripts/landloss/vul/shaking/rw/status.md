# Shaking vulnerability, retaining walls: status

**Status:** A damage state is drawn on every wall. The fragility is a flat 70%.

**Updated:** 2026-09-22

## Approach

- Express the vulnerability of a wall as a **fragility curve giving the
  probability of failure at a given ground motion**, and draw a damage state
  against it. The probability is intrinsic to the curve -- nominally identical
  walls differ in capacity and respond variably to the same shaking -- so it is
  never replaced by a comparison of demand against capacity, however well the
  hazard is resolved.
- Carry **two damage states only, no damage and replace**. Very few damaged
  walls are repaired in practice, so a middle state would hold almost nothing.
- Keep the **initial condition separate from the damage state**. Condition
  describes the wall before the earthquake and is an input to the fragility; the
  damage state is the outcome.
- Index the curves on the wall classes the exposure module draws — size class
  and initial condition — so the two modules share one vocabulary.
- Emit **states, not costs**. A written-off wall is priced from its
  undepreciated value in the loss module, against the $50,000-per-dwelling
  sub-cap.

## Where it is now

- `steps/s9_wall_damage_state/` reads the wall population and the realisation's
  PGA field, draws a state per wall, and writes it with the wall's size class,
  condition, height, length and sampled PGA.
- The fragility is `BETA_FAILURE_PROBABILITY = 0.7` in
  `landloss.vul.shaking.fragility` — one number for every wall, whatever its
  size, condition or the acceleration it saw. Over the pilot's 754 walls, 523
  are written off, which is the 70% reproduced.
- `draw_damage_states()` takes probabilities rather than computing them, so the
  published curves replace the constant without the step changing.
- Every wall in the pilot reads the same PGA, 0.962 g. The spatial variation is
  meant to come from the Vs30 model driving the site class, which the shaking
  hazard does not do yet.

## Next

1. Define the fragility curves and replace the flat probability.
2. Index them on size class and initial condition, both of which already ride on
   every row.
3. Rerun once the Vs30 model varies the site class, so the curves have something
   to discriminate on.
4. Decide whether walls on the same property fail independently. They are drawn
   that way, and two walls on one slope are not independent.

## Validation

- The realised share written off against the fragility it was drawn from, which
  is what the run prints each time.
- Modelled wall damage against observed retaining wall damage in Canterbury and
  Kaikōura, once a comparable population is available.

## Open decisions

- **The wall classes the curves are defined for are still unnamed.** This is the
  same open decision the retaining wall exposure module carries, and it blocks
  indexing the fragility.
- **Whether the Canterbury land damage rates already include retaining wall
  damage** (**T-27**). If they do, pricing walls separately double counts them
  on flat land.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
