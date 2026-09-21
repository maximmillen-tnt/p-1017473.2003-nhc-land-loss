# Liquefaction vulnerability, land: status

**Status:** Canterbury observed damage database built. The cost rates are
packaged; nothing reads them yet.

**Updated:** 2026-09-21

## Approach

- Settle liquefaction land damage from an **observed land damage category**, and
  attach a **cost to each category**, rather than modelling a damage ratio and
  multiplying it by land value. Canterbury gives observed categories and settled
  costs for the same properties, which is the strongest evidence the study has.
- Take the category costs from the **Dec 2016 ILVR land liability rates**,
  packaged under `src/landloss/vul/liquefaction/assets/` as
  `costs_liq_ld_refined_cats_2011.csv` with its own README. They are
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
  recording their source, units and limitations. No code reads the file, and the
  join from a category to a cost is not implemented.
- Nothing in the module produces a Wellington result yet; everything built so
  far is the Canterbury evidence the Wellington relationship will be fitted to.

## Next

1. Read the packaged cost rates and join them to the observed damage categories.
2. Check the resulting costs against the settled losses already in the observed
   damage database, which is the test of whether the 2016 rates reproduce what
   was actually paid.
3. Escalate the 2010/2011 rates to the study's valuation basis, holding the
   index as a named constant rather than in the asset.
4. Carry the 15th, 50th and 85th percentiles through rather than collapsing to
   the median, so the uncertainty reaches the loss module.

## Validation

- Modelled category costs against the settled Canterbury losses per property, on
  the same properties. The observed damage database holds both, so this is a
  direct comparison rather than a proxy.
- Distribution of properties across categories 1 to 6, against the observed
  distribution in the Canterbury data.

## Open decisions

- **Whether retaining walls are handled explicitly or left inside the land
  damage cost.** The Canterbury rates may already include retaining wall,
  culvert and bridge damage, in which case modelling those assets separately
  would double count them. **T-27** covers confirming it, and the answer decides
  whether this module needs a retaining wall term at all.
- **T-17**, **T-18** — NHC land damage claim costs for Wellington, which would
  let the Canterbury-derived rates be checked against a second population.
- The source description for the ILVR rates is still to be supplied by Virginie
  Lacrosse and added to the asset README.

Step-level detail lives in each step's implementation plan and method file under
`steps/`.
