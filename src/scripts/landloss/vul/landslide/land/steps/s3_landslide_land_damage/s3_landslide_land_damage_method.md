# Step 3 — Landslide land damage: method

- The step measures **how much of each property's insured land a landslide
  took, and from where**. It is run by `gen_landslide_land_damage.py`, and the
  arithmetic is in `landloss.vul.landslide.land.damaged_area`.
- The damage measure is **geometric, not a damage state**. A landslide either
  covers part of a property or it does not, and how much it covers is the whole
  question — unlike liquefaction, where the property carries a state.
- Properties come from `temp/exposure/insured-land[-pilot].geoparquet` and
  landslides from the hazard module's
  `temp/hazard/landslide/landslide-realisation-r<nnn>[-pilot].geoparquet`, each
  read through its own step's path function.
- The two kinds of ground stay apart all the way through, because the policy
  settles them differently: **evacuated** ground is what the failure removed,
  **inundated** ground is where the debris came to rest, which may have started
  on somebody else's property.
- **Inundated area is measured on the union** of the landslides that reached a
  property, not summed across them. Evacuated polygons are pairwise disjoint by
  construction; inundated ones are not, because two failures either side of a
  gully both land in its floor, and ground buried twice is buried once.
- Each kind carries the **depth** of the material, area-weighted where more than
  one landslide reached the property. Depth comes from the volume–area power
  law in `landloss.hazard.landslide.geometry` and is written onto the polygons
  by the hazard step, not computed here.
- **The two depths come out identical in the beta.** Volume is conserved through
  the runout and the runout circle is rebuilt at the source radius, so the two
  footprints are equal. That is a property of the beta's geometry, not a bug.
- `check_within_insured_area()` asserts that neither kind of damaged ground
  exceeds the property's own insured area, and the run prints the result. The
  two together may legitimately exceed it, because evacuated and inundated
  ground can overlap each other.
- A property no landslide reached is **absent from the output**, rather than
  present with zeros.
- **No cost is attached.** The T+T landslip remediation schedule is not
  packaged, so this step stops at area and depth and the pricing is left to the
  loss module.
- Output is `temp/vul/landslide-land-damage-r<nnn>[-pilot].parquet`.

Potential future improvements see
`s3_landslide_land_damage_implementation_plan.md`.
