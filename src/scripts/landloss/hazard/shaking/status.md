# Shaking hazard: status

**Status:** Not started.

**Updated:** 2026-09-18

## Approach

Intended, not implemented.

- Port `gen_pga_layer` from the National Liquefaction Model repository
  (`p-1017473-nlm-loss-modelling`) rather than rewriting it, so both studies
  compute their demand the same way.
- Take the site class from the **Foster V<sub>s</sub>30 model** instead of a
  single assumed class. This resolves **T-15** by mapping the class per point
  rather than assigning one per landform.
- Generate **PGA** and **Sa(T₁)** across the study extent, both at the
  **2500-year return period**.
- Derive **PGV** from Sa(T₁) through an empirical relationship rather than
  generating it independently; several of the retaining wall fragility curves in
  `.agents/context/retaining-wall-fragility.md` are velocity-based.

## Where it is now

Nothing is implemented. This file is the only thing in the folder.

## Next

1. Port `gen_pga_layer` into a step under `steps/`, and confirm it reproduces
   the NLM's own output before modifying it.
2. Swap the site class input for the Foster V<sub>s</sub>30 model.
3. Write Sa(T₁) alongside PGA, both at the 2500-year return period.
4. Add the empirical Sa(T₁) → PGV conversion, naming the relationship used.

## Validation

- Mean PGA per site class against the NSHM values for that class — the check
  that the Foster classes are paired with the right demand. A script under
  `validations/`, not a unit test.

## Open decisions

- **T-15** — the site class decision above. Adopting Foster closes it.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
