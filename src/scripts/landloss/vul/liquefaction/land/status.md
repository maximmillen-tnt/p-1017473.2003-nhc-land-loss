# Liquefaction vulnerability, land: status

**Status:** Canterbury observed damage database built, and the cost rates now
price a Wellington realisation end to end.

**Updated:** 2026-09-22

## Approach

- Settle liquefaction land damage from an **observed land damage state**, and
  attach a **cost to each state**, rather than modelling a damage ratio and
  multiplying it by land value. Canterbury gives observed states and settled
  costs for the same properties, which is the strongest evidence the study has.
- Keep **states** and **categories** apart. States are the severity scale, 1 to
  6, None through Very Severe. Categories are the nine damage types NHC pays
  out on, 1 to 9, where 8 is ILV and 9 is IFV. The costs are keyed on states
  and cover categories 1 to 7, so **ILV and IFV costs are excluded**.
- Take the category costs from the **Dec 2016 ILVR land liability rates**,
  packaged under `src/landloss/vul/liquefaction/assets/` as
  `costs_liq_ld_refined_states_2011.csv` with its own README. They are
  2010/2011 dollars excluding GST, carried as 15th, 50th and 85th
  percentiles so the spread within a category survives.
- Calibrate against the **Canterbury earthquake sequence**, joining NHC's
  settled losses to the National Liquefaction Model's mapped land damage
  observations (`steps/s1_ces_observed_damage/`).
- Keep to **flat land**. The Canterbury evidence is flat land liquefaction
  damage, the observed damage database is masked to flat land, and the packaged
  costs carry the same restriction.

## Where it is now

- `steps/s1_ces_observed_damage/gen_observed_damage_db.py` builds the observed
  damage database: one row per insured property per event, over the three
  Canterbury events, masked to flat land. Its method is written up in the step
  folder.
- `report/fig_land_damage_maps.py` maps the observed land damage.
- The category cost rates are packaged as a committed asset with a README
  recording their source, units and limitations, and
  `landloss.vul.liquefaction.costs` reads them.
- `steps/s2_liq_land_damage/` samples the hazard module's realised land damage
  state at every insured property and looks a cost up against it, writing one
  priced row per property per realisation. Over the Wellington pilot, 2,721 of
  4,764 properties carry a state; the remainder sit outside the liquefaction
  grid, which covers flat land as expected.
- The percentile is a run-level scenario rather than a column, because
  `min(repair, cap)` is non-linear and a settlement computed from a median cost
  is not the median settlement.

## Next

1. Check the modelled costs against the settled losses already in the observed
   damage database, which is the test of whether the 2016 rates reproduce what
   was actually paid.
2. Escalate the 2010/2011 rates to the study's valuation basis, holding the
   index as a named constant rather than in the asset. `cost_year` rides on
   every row until that lands.
3. Gross the rates up for GST at the loss boundary. They arrive excluding it
   and the Act compares on a GST-inclusive basis.
4. Run all three percentiles and report the portfolio total as a band.

## Validation

- Modelled category costs against the settled Canterbury losses per property, on
  the same properties. The observed damage database holds both, so this is a
  direct comparison rather than a proxy.
- Distribution of properties across states 1 to 6, against the observed
  distribution in the Canterbury data.

## Open decisions

- **Whether retaining walls are handled explicitly or left inside the land
  damage cost.** The Canterbury rates may already include retaining wall,
  culvert and bridge damage, in which case modelling those assets separately
  would double count them. **T-27** covers confirming it, and the answer decides
  whether this module needs a retaining wall term at all.
- **How ILV and IFV are covered.** The packaged rates exclude both, and they
  were a large share of what was paid in Canterbury, so a total built from
  these rates alone understates the loss.
- **T-17**, **T-18** — NHC land damage claim costs for Wellington, which would
  let the Canterbury-derived rates be checked against a second population.
- The source description for the ILVR rates is still to be supplied by Virginie
  Lacrosse and added to the asset README.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
