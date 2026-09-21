# Retaining wall exposure: status

**Status:** Approach agreed. Input datasets being collected; nothing implemented
in this repository.

**Updated:** 2026-09-21

## Approach

Intended, not implemented.

- Classify every wall on three axes: **six wall classes**, **three size
  subclasses** — small below 1 m, medium 1 to 2.5 m, large above 2.5 m — and
  **two initial state classes** (modern, poor). The axes match how the published
  fragility sets are parameterised — wall type, height and initial condition —
  so each cell can carry a curve from
  `.agents/context/retaining-wall-fragility.md`.
- Carry **two damage states only: no damage, and replace.** A wall either
  survives or is written off, which is how the policy settles it — on
  replacement value up to the sub-cap. The initial state class is a separate
  axis and is not a damage state.
- Size the three subclasses by what the costing can tell apart rather than by
  engineering interest. Above the cap the settlement stops depending on height,
  so a three metre and a six metre wall cost the same to settle and do not need
  separating.
- **Predict where walls are and how big they are** from a model over the DEM,
  geomorphology, and road and dwelling locations. No retaining wall dataset
  exists for the study area, so the population has to be inferred rather than
  looked up (**L-04**).
- **Set the initial state from the age of the dwelling**, as the available proxy
  for whether a wall is modern or poor.
- **Train the model on four sources** — the ICNZ database, a manual mapping
  study, estimates from T+T Wellington SMEs, and automated detection from remote
  sensing. Each covers a different part of the population and none covers it
  alone.
- Treat the **remote sensing detection as a pilot** rather than a primary
  source. Dense vegetation obscures walls in exactly the suburbs of interest and
  the detection rate is itself unknown (**L-05**).

## Where it is now

Nothing is implemented. This file and `__init__.py` are the only things in the
folder, and no script in the repository reads a retaining wall dataset.

- Some of the input datasets have been collected. They are held outside the
  repository, so nothing here reads them yet.
- The manual mapping and the remote sensing detection have both been started
  with Sophia. That work also sits outside the repository and cannot be re-run
  from here.

## Next

1. Name the six wall classes. The height thresholds are set: small below 1 m,
   medium 1 to 2.5 m, large above 2.5 m.
2. Bring the collected input datasets into the repository, or record where they
   are held and how they are read, so the inputs are reproducible.
3. Bring the manual mapping and the remote sensing pilot into the repository on
   the same basis.
4. Obtain the ICNZ database.
5. Attach a dwelling age attribute to the address spine, which the initial state
   class reads.
6. Train the predictive model and write a wall population per property.

## Validation

- Predicted wall prevalence by suburb against the SME suburb-by-suburb estimate
  (**T-19**). That estimate is the only independent measure of prevalence the
  study will have, so it is the primary check rather than one of several.
- Predicted locations against the manual mapping study, held out of training
  rather than trained on.
- Detection rate of the remote sensing pilot against the same manual mapping, so
  that the unknown detection rate behind **L-05** is measured rather than
  assumed.
- Size distribution against the ICNZ database.

## Open decisions

- The six wall classes are not yet named. They should map onto the wall types
  that carry published fragility curves, or the classification will not be able
  to attach one.
- Whether repair cost scales with wall length or wall height, and what the fixed
  per-job costs are (**T-32**).
- What separates "modern" from "poor", and the dwelling age that divides them.
- Access to the ICNZ database, which is not covered by a register task.
- **T-19** — the SME estimate of wall prevalence by suburb.
- **T-11**, **T-20** — the Wellington City Council retaining wall database and
  the council cut-and-fill models.
- **T-09**, **T-10** — reuse of the Auckland Council cut-and-fill slope tool,
  and how remote sensing can support the detection.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
