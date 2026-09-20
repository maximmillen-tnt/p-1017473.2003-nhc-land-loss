# Shaking hazard: status

**Status:** TS1170.5 demand built as a raster in the National Liquefaction
Model; not yet ported into this repository.

**Updated:** 2026-09-21

## Approach

Intended, not implemented.

- Port `gen_pga_layer` from the National Liquefaction Model repository
  (`p-1017473-nlm-loss-modelling`) rather than rewriting it, so both studies
  compute their demand the same way.
- Take the site class from the **Foster et al. (2019) V<sub>s</sub>30 model**
  instead of a single assumed class. This resolves **T-15** by mapping the
  class per point rather than assigning one per landform.
- Generate **PGA** and **Sa(T₁)** across the study extent on a **100 m grid**,
  both at the **2500-year return period**.
- Derive **PGV** from the same TS1170.5 spectrum rather than generating it
  independently, as **PGV (mm/s) ≈ 750 · Sa(1.0 s) [g]**. Several of the
  retaining wall fragility curves in
  `.agents/context/retaining-wall-fragility.md` are velocity-based.
- Hold **NSHM (2022) scenario demands, run through a GMPE in OpenQuake**, as
  the alternative to TS1170.5. It would produce the same PGA and PGV layers
  from the same V<sub>s</sub>30 input, so the two routes are interchangeable
  downstream (**T-26**).

## Where it is now

Nothing is implemented here. The folder holds this file and `__init__.py`, and
no script in the repository reads TS1170.5, V<sub>s</sub>30 or the National
Seismic Hazard Model.

The TS1170.5 demand itself is built and proven as a raster in the National
Liquefaction Model repository (`p-1017473-nlm-loss-modelling`). Porting it is
the outstanding work, not writing it.

## Next

1. Obtain the Foster et al. (2019) V<sub>s</sub>30 layer over the study area.
2. Port `gen_pga_layer` into a step under `steps/`, and confirm it reproduces
   the NLM's own output before modifying it.
3. Generate the 100 m grid of PGA and Sa(T₁) over the study area, taking the
   site class from the Foster layer rather than a single assumed class.
4. Add the Sa(1.0 s) → PGV conversion and write the PGV layer.

## Validation

- Mean PGA per site class against the NSHM values for that class — the check
  that the Foster classes are paired with the right demand. A script under
  `validations/`, not a unit test.

## Open decisions

- **T-15** — the site class decision above. Adopting Foster closes it.
- **T-26** — whether the demand comes from TS1170.5 or from NSHM (2022)
  scenarios through OpenQuake. TS1170.5 is the route being built; the
  scenario route has not been ruled out.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
