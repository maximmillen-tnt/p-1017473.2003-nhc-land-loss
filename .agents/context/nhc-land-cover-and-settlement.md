# How NHC land cover and settlement works

Background captured from the kick-off meeting on 16 September 2026, largely from
John Leeves, who holds the policy knowledge in the team. This is working
understanding, not a legal reading: the exact land cover wording still has to be
confirmed with NHC, and the policy settings NHC wants tested have not yet been
supplied. Treat anything here as provisional until that confirmation lands.

## What the cover attaches to

Cover is triggered by the property owner holding a fire insurance policy on their
dwelling, so it arrives via the dwelling. The cover itself is wider than the
dwelling and extends over the whole property, which is why the model works at
property level rather than dwelling level. A property can carry several dwellings;
insurance still generally responds at the property.

This is the reason the LINZ property ID was preferred as the unique identifier.
It is not the identifier the NHC loss modelling team would choose — they work at
claim level — but it is stable and simple, and it matches the unit that is
actually insured.

## Insured land

Insured land is defined by NHC's current policy and, in practice for this study,
by the 8 metre line from the dwelling. Whether a landslide falls inside that
insured area is one of the key variables, and whether a landslide takes the whole
property or only a corner of it makes a large difference to the cost that
follows.

Driveways matter here out of proportion to their area, because they are where most
retaining walls sit. They are not identified in the LINZ data. The saving grace is
that many properties in the study area are small enough that the 8 metre line
reaches the boundary regardless.

## Retaining walls

The treatment of retaining walls changed between the two Acts, and the change
matters for this study:

- Under the **EQC Act**, walls were settled on an indemnity basis — the
  depreciated value of the wall.
- Under the **NHC Act**, walls are settled on **replacement value, capped at
  $25,000**.

The consequence is that the physical condition of a wall no longer affects the
settlement. It still affects the probability of failure, and many walls in the
study area are old and would not take much shaking to fail. So condition enters
the model on the hazard side, not the cost side.

Wellington City Council maintains a retaining wall database, but it covers council
walls rather than the privately owned walls this study is concerned with. Council
walls are not irrelevant, though: in the last round of landslides, failures of
council walls supporting roads inundated private property below. That damage is
driven by the cost of clean-up and remediation rather than by land value, which
does not fit the value-based cost logic used elsewhere in the tool.

## Sub-caps and multiple insured interests

Where a property has multiple land structures, multiple sub-caps apply, and where
several insured interests share land — multi-unit buildings, cross-lease and
shared land — a settlement has to be split between them. NHC asked for this to be
represented because it demonstrates how the policy settings play out in the
hardest cases.

The team has excluded it from the current study on the basis that these properties
are a small proportion of the population, perhaps under 5%, and that no two
multi-unit developments settle the same way. This is a real narrowing of the
brief. The agreed mitigation is to quantify what proportion of the population
falls into the category so the exclusion is evidenced, and to park a dedicated
sub-study for later.

## Open questions

- The exact interpretation of the NHC Act and the land cover wording, to be led by
  John Leeves with Bridget Attwood.
- The specific policy settings NHC wants compared.
