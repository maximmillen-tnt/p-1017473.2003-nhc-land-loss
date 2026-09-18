# Landslide hazard: status

**Status:** Two candidate routes, neither chosen.

**Updated:** 2026-09-18

## Approach

Intended, not implemented, and the route is not yet chosen — see
`## Open decisions`.

**The starting point.** ESNZ's probabilistic landslide model is in hand: a 25 m
grid carrying failure probability at discrete shaking levels. Three gaps in it
matter for this study.

- **No spatial correlation factor.** Cell probabilities are independent, so
  aggregating them across the portfolio misses the clustering that decides how
  many claims one event produces.
- **No smaller landslides.** Much of the loss here is expected from small
  failures on modified slopes; the register carries this as **I-08**.
- **No runout.** Loss of support and runout are settled differently, so a model
  without runout cannot answer the policy question.

**The two routes**, either of which closes those gaps.

- **Build a new model and compare it against ESNZ.** Drafted in full in
  `.agents/plans/estimating-eq-landslide-extent-wellington.md` — explicit source
  and runout polygons, Newmark displacement, an absolute rate calibrated against
  Nowicki Jessee (2018), and discrete failures sampled from a Kaikōura v3 size
  distribution. That plan has not been reviewed or agreed with the project team.
  ESNZ becomes the cross-comparison rather than an input.
- **Extend the ESNZ model.** Keep the 25 m probability grid as the base rate and
  add correlation, small failures and runout on top of it. Cheaper, and starts
  from a model that has already been through review, but inherits its 25 m
  resolution and its discrete shaking levels.

## Where it is now

Nothing is implemented. The folder holds
`validations/fig_landslide_vulnerability_model_gwrc.py` and nothing else. The
ESNZ grid is held by the team but is not read by anything in this repository
yet.

## Next

1. Choose between building a new model and extending ESNZ, reviewing the
   drafted plan with the project team as part of that. Everything else rests on
   it.
2. Read the ESNZ grid over the study extent and check its shaking levels,
   resolution and coverage against what the loss model needs. Required either
   way — as the base rate on one route, as the comparison on the other.
3. Add the three missing pieces — spatial correlation, small failures, runout —
   on whichever base the decision settles on.
4. Intersect the result with insured land per claim, keeping loss of support and
   runout separate because `vul` needs them per cause.

The phased build for the new-model route is in
`.agents/plans/estimating-eq-landslide-extent-wellington.md`, not here.

## Validation

- Failure probability and total areal coverage against the ESNZ 25 m grid at
  matching shaking levels. This is the comparison the build-new route exists to
  support, and on the extend route it is the check that the base rate survived
  the extensions.
- Simulated landslide density against the GWRC `SEVERITY` 1–5 zonation, as a
  rank correlation rather than an absolute one — the layer is a susceptibility
  zonation, not a rate. A script under `validations/`.
- Total areal coverage against the Nowicki Jessee (2018) estimate for the same
  shaking.
- Simulated size distribution and reach angles against the Kaikōura inventory.
- Proportion of landslides confined to a single property. Local expectation in
  `.agents/context/land-damage-mechanisms.md` is that most are, with
  multi-property failures concentrated in gullies; if the model does not
  reproduce that it is wrong regardless of how well it matches the literature.

## Open decisions

- **Build new against extend ESNZ.** Undecided, and the decision the rest of
  the module waits on.
- **L-08 against using ESNZ as the primary model.** The ESNZ model is
  confirmed to be the same GNS slope failure model held in PRUE that **L-08**
  restricts to cross-comparison only. The team may still adopt it as the primary
  model, so the register entry needs revisiting if the extend route is chosen.
- **T-22** — explicit extent against per-property classification. The drafted
  plan takes the explicit route, and the decision closes when the plan is
  agreed.
- **T-15** — the site class. Carried as a parameter rather than blocking on it.
- **T-11**, **T-19**, **T-20** — retaining wall and cut-and-fill data. The
  Kaikōura inventory is natural slopes, and the losses here are expected on
  modified ones, so a second population conditioned on this data is the plan's
  own largest technical risk.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
