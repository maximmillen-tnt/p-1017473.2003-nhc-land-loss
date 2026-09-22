# Landslide hazard: status

**Status:** A first cut of the extend-ESNZ route is running; the route is still
not formally chosen.

**Updated:** 2026-09-22

## Approach

The route is not yet formally chosen — see `## Open decisions` — but the
cheapest of the three has now been built end to end, so that there is something
concrete to choose against rather than three descriptions. No progress marks
against the module as a whole until the decision is made; the step that exists
carries its own marked plan under `steps/`.

**The starting point.** ESNZ's probabilistic landslide model is in hand: a 32 m
grid carrying failure probability at discrete shaking levels. Three gaps in it
matter for this study.

- **No spatial correlation factor.** Cell probabilities are independent, so
  aggregating them across the portfolio misses the clustering that decides how
  many claims one event produces.
- **No smaller landslides.** Much of the loss here is expected from small
  failures on modified slopes; the register carries this as **I-08**.
- **No runout.** Loss of support and runout are settled differently, so a model
  without runout cannot answer the policy question.

**The three routes.** The first keeps the ESNZ model as the primary model; the
others replace or extend it.

- **Validate or recalibrate the ESNZ model** and keep it as the primary model.
  The cheapest route: check it against observed failures and the Greater
  Wellington zonation, and recalibrate the rate where it disagrees, rather than
  changing its structure. It leaves the three gaps above unclosed, so it only
  stands if they matter less than the calibration does.
- **Build a new model and compare it against ESNZ.** Drafted in full in
  `.agents/plans/estimating-eq-landslide-extent-wellington.md` — explicit source
  and runout polygons, Newmark displacement, an absolute rate calibrated against
  Nowicki Jessee (2018), and discrete failures sampled from a Kaikōura v3 size
  distribution. That plan has not been reviewed or agreed with the project team.
  ESNZ becomes the cross-comparison rather than an input.
- **Extend the ESNZ model.** Keep the 32 m probability grid as the base rate and
  add correlation, small failures and runout on top of it. Cheaper, and starts
  from a model that has already been through review, but inherits its 32 m
  resolution and its discrete shaking levels.


## Beta build

A first end-to-end run is being assembled that produces the right data
structures rather than the right numbers; see
`.agents/plans/beta-build.md` for the whole chain.

Landslide is the module the beta needs least from: `steps/s1_landslide_realisation/`
already emits the structure the chain expects — **polygons of evacuated ground
and polygons of inundated ground**, one set per realisation. The two types may
overlap each other.

One caveat on the structure, because the chain downstream would double count
without it. `drop_overlapping()` enforces non-overlap among the **evacuated**
polygons only. The inundated polygons are those same circles translated
different distances in different directions, so two of them can and do land on
top of one another — most obviously where two failures on opposite sides of a
gully both run into its floor. Ground buried by two landslides is buried once,
so anything summing inundated area has to dissolve first. The run output prints
both the summed and the dissolved area for each type, so the gap is visible
every run.

This is a **conflict with the stated beta contract**, which says polygons of the
same type may not overlap. Evacuated ground meets it; inundated ground does not.
It has to be settled before the intersect downstream is written, and the depth
attribute makes it sharper: where two landslides bury the same ground, it is not
obvious whether the depth there is the deeper of the two or the sum.

Each polygon also still needs a **depth**, approximated from the **total
evacuated area of the landslide it belongs to** — a bigger failure is a deeper
one. Depth belongs to the landslide rather than to the piece of it inside any
one claim, so it is attached here and carried through the intersect. Dissolving
the inundated polygons to satisfy the contract would discard the
`landslide_id` that depth hangs off, which is why the two questions are one
question.

## Where it is now

`steps/s1_landslide_realisation/` holds a runnable first cut of the extend-ESNZ
route. It reads the supplied 32 m probability grid, samples every cell
independently, gives each failure a size from a bounded power law and a circular
footprint, drops the smaller of any overlapping pair, and moves each one downhill
by a distance that grows with the slope — emitting the source polygon as
`evacuated land` and the displaced polygon as `inundated land`. The slope and
downhill direction it uses are in `landloss.common.utils.terrain`, and the reader
for the grid is `landloss.io.source_material`; both are library code with tests,
because they will outlive whatever the model turns into. Its method and its
phased plan are in the step folder.

It has now been run against the real grid over both the pilot box and the full
study area. The full run produces **66,126 landslides over 106 ha of evacuated
ground**, at a median slope of 28°, with a median runout of 21 m. The pattern is
right — the hills either side of the Hutt Valley and around Porirua are dense
and the valley floors are clear — and the figure under
`report/hazard/landslide/landslide-realisation/fig/` is how that was checked.

Two numbers from that run need settling before any of it is quoted. The grid's
probabilities sum to 66,644 failing **cells**, which at 32 m is 6,824 ha if a
failing cell means the cell went; the sampled sizes make it 106 ha, 1.6% of
that. Which of the two the grid means is a question for the supplier, and the
answer moves the loss by a factor of sixty. And the pilot box is flat suburb, so
it exercises the code rather than the model — judge the step on the full extent.

Two of the three gaps are closed only nominally. There are small failures now,
but their size distribution is fitted to nothing; there is runout, but it is a
rigid translation along one bearing. Spatial correlation is not addressed at all.

The folder also holds `validations/fig_landslide_vulnerability_model_gwrc.py`,
which draws the Greater Wellington zonation the result gets checked against.

## Next

1. Choose between building a new model and extending ESNZ, reviewing the
   drafted plan with the project team as part of that. The first cut is intended
   to inform that decision, not to pre-empt it.
2. Confirm with the supplier what shaking level the grid is conditioned on, and
   whether its probabilities are conditional on that shaking or already carry a
   rate. Nothing in the code depends on the answer, and nothing can be written up
   without it.
3. Fit the size distribution to an inventory, and replace the displacement ramp
   with a Newmark displacement. Both are placeholders and both move the answer.
4. Add spatial correlation, which is the largest remaining error and the one that
   most affects the shape of the loss distribution rather than its average.
5. Intersect the result with insured land per claim, keeping loss of support and
   runout separate because `vul` needs them per cause.

The phased build for the new-model route is in
`.agents/plans/estimating-eq-landslide-extent-wellington.md`, not here.

## Validation

- Failure probability and total areal coverage against the ESNZ 32 m grid at
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
  the module waits on. The extend route now exists in runnable form, which
  changes what the comparison costs but not what it is.
- **What the supplied grid is conditioned on.** The shaking level is read from
  the file name (`EILProb_PGA2g.tif`) and has not been confirmed, and neither has
  whether the probabilities are conditional on that shaking or already include a
  rate. Both have to come from the supplier.
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
