# Step 2 — Liquefaction land damage: implementation plan

**Status:** Phases 1 and 1a complete. Costs are the packaged Canterbury
settlements.

## Phase 1 — A priced state on every property (complete)

- [x] Read the insured land extent and the realised land damage state raster.
- [x] Sample one state per property at its representative point.
- [x] Read the packaged Canterbury cost rates, keeping the state named "None"
      from being parsed as a missing value.
- [x] Look a cost up per property at the run's percentile.
- [x] Carry `rate_basis`, `cost_year` and `cost_percentile` on every row, so a
      loss table cannot silently mix bases or vintages.
- [x] Report the properties the hazard grid does not reach, which over the
      pilot is the model covering flat land only.

## Phase 1a — land_id for the loss contract (complete)

- [x] Carry `land_id` from the insured land onto every row, after
      `realisation_id` and before `claim_id`, so step 10 can join the state to
      its land polygon.
- [x] Import the key names from `landloss.domain.loss_contract` rather than
      retyping them.
- [x] Leave the output without geometry; step 10 takes the coordinates from the
      insured land.

## Phase 2 — Beyond the Canterbury lookup

- [ ] Index the 2011 costs to the study's valuation date, rather than leaving
      two vintages for the loss module to reconcile.
- [ ] Gross the rates up for GST at the loss boundary — they arrive excluding
      it and the Act compares on a GST-inclusive basis.
- [ ] Decide whether a property larger than the Canterbury median should cost
      more than the lookup says. The rates have no size term at all, which is
      right for the ILVR total and probably wrong for a large section.
- [ ] Separate states 5 and 6, which currently share one estimate.
- [ ] Sample more than one point per property once the hazard grid is finer
      than the properties, and decide how a mixture of states settles.

## Phase 3 — Lateral spreading

- [ ] Take the lateral spreading zones from the hazard module once they exist,
      and check whether the Canterbury rates need a separate lookup inside
      them. The Canterbury settlements include spreading damage, so applying a
      zone modifier to the hazard and then the same cost table may double count.

## Potential future improvements

- Distinguish the cost of land damage from the cost of the services under it.
  The settled figures bundle both.
- Carry the uncertainty rather than the percentile: the three columns are a
  distribution over properties and are currently used as three scenarios.
