# Step 10 — Property damage: method

- The step joins every hazard's damage onto **one row per property per
  realisation**. It is run by `gen_property_damage.py` and adds no modelling of
  its own: every number it writes was decided by the step it came from.
- It reads five files, each through its own step's path function: the insured
  land extent (step 5), the liquefaction land damage (step 2), the landslide
  damaged area (step 3), the retaining wall damage states (step 9) and the
  culvert and bridge damage states (step 9).
- The spine is the **insured land extent**, so every property with insured land
  appears whether or not anything damaged it, and a property that no hazard
  reached carries zeros rather than being absent.
- **The key is the property, not the address.** Units sharing a coordinate were
  collapsed into one property carrying a `dwelling_count` by the insured land
  step, because NHC's sub-caps and excess are per dwelling. That count rides on
  every row here.
- Quantities default to **zero** where a hazard did not reach a property,
  because undamaged ground is zero damaged area. States and depths default to
  **missing**, because there is no state to report rather than a state of none.
- Retaining walls, culverts and bridges are counted per property as a total and
  a number to replace, by `count_structures()`. A property with three walls of
  which two failed carries `retaining_walls = 3` and
  `retaining_walls_to_replace = 2`.
- **Nothing is settled and nothing is converted.** Costs stay in the units their
  own step recorded — 2011 dollars excluding GST for the liquefaction component
  — and `cost_year`, `rate_basis` and `cost_percentile` ride on the row so the
  loss module can reconcile them. Caps, excesses, GST and the market value of
  the damaged land belong to the loss module, which this step does not touch.
- The run prints the two things four separate files cannot show:
  - **Causes per property.** Over the Wellington pilot 3,858 of 5,765
    properties carry damage, of which 173 carry two causes. That overlap is what
    decides whether a cap binds, and it is invisible in the separate files.
  - **The T-27 double count, sized.** 148 properties carry both a liquefaction
    land damage state and a wall to replace. If the Canterbury land damage rates
    already include retaining wall damage, every one of those is charged for its
    wall twice.
- Output is `temp/vul/property-damage-r<nnn>[-pilot].parquet`.

Potential future improvements see `s10_property_damage_implementation_plan.md`.
