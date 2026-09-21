# Liquefaction hazard: status

**Status:** Prototype under way; the NLM output in hand is still on draft
demands.

**Updated:** 2026-09-21

## Approach

Marks: `[x]` done, `[~]` partly done, `[>]` next, `[ ]` planned.

Prototype:

- [~] Get land damage (LD) probabilities for the 2500-year event using the
  TS1170.5 demands.
- [~] Buffer rivers to obtain the lateral spreading (LS) zones.
- [>] Modify the LD probabilities inside the LS zones.
- [ ] Generate realisations of LD from the modified probabilities.

Beyond the prototype:

- [ ] Switch the National Liquefaction Model (NLM) output to LD categories 1–6.
- [ ] Refine the LS buffer zones.


## Beta build

A first end-to-end run is being assembled that produces the right data
structures rather than the right numbers; see
`.agents/plans/beta-build.md` for the whole chain.

The liquefaction beta replaces the lateral spreading work entirely with two
steps, and still ends at the structure the full version produces:

- [ ] `gen_liq_ld_probabilities` — read the current NLM 2500-year probability
      layer, which carries Moderate and Major only, and expand it to all six
      land damage states by subdividing those masses.
- [ ] `gen_liq_ld_states` — draw a state per cell and write one raster of
      `ld_state` per realisation. One realisation for the beta.

No river buffers, no LS zone modifier. Output is a raster of `ld_state` values
1 to 6, which is what the full version emits too.

## Where it is now

- The NLM output in hand is built on **draft** TS1170.5, not the published
  version, so every probability downstream of it is provisional.
- Some progress on the buffers and the probabilities, in the NLM work rather
  than in this repository.
- This repository holds the named river against other watercourse split in
  `landloss.hazard.liquefaction.waterways`, with a map and a table over it.

## Next

1. Decide on the river layer — every published layer has oddities.
2. Build the lateral spreading probability modifier for the prototype.

## Validation

Not yet defined.

## Open decisions

- **The river layer.** Every published option has oddities, and the choice sets
  the lateral spreading zones.
- **T-26** — TS1170.5 or NSHM (2022) demands. The approach above assumes
  TS1170.5.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
