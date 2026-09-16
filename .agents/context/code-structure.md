# Code structure

The analysis is split into four modules that run in sequence: **hazard** defines
what the ground does, **exposure** defines what is on it, **vul** works out how
badly each asset is damaged, and **loss** turns that damage into money. Each
depends only on the ones before it, so a change to the policy settings re-runs
`loss` alone, while a change to the seismic demand re-runs everything.

## The four modules

| Module | Responsibility |
| --- | --- |
| `hazard` | Defines the shaking, liquefaction and landslide extents. |
| `exposure` | Defines the assets in terms of location, extent and attributes. |
| `vul` | Vulnerability calculations for each asset against each hazard. |
| `loss` | Combines damage ratios with replacement ratios and policy settings to give financial loss. |

`hazard` is the demand side and knows nothing about properties. `exposure` is
where a property's insured land extent and its attributes — slope, retaining
walls, services, land value — are assembled. `vul` is the only place the two meet,
producing a damage ratio per asset per hazard. `loss` is the only place money and
policy wording enter, which is what keeps the policy settings a parameter of the
study rather than something baked through the model.

## Where the code lives

Each module appears twice, and the split is deliberate:

```text
src/landloss/{hazard,exposure,vul,loss}/
src/scripts/landloss/{hazard,exposure,vul,loss}/
    steps/
    validations/
```

- `src/landloss/<module>/` is the **library**: reusable, tested logic with no
  assumptions about a particular run. This is the code handed to NHC.
- `src/scripts/landloss/<module>/` is the **run**: the orchestration that points
  the library at this study's datasets and settings.
  - `steps/` builds the model or models for that module. A step is a stage of the
    build, ordered and re-runnable.
  - `validations/` checks the intermediate and final outputs of that module.

Validations exist as their own layer because most of what can go wrong in this
work is a silently wrong input rather than a crash — a DEM merged across survey
years, a property with no insured land area, a damage ratio above one. A
validation is a check on an output, not a unit test of a function; unit tests
belong in `tests/`.

Every folder carries an `__init__.py`.

## Causes of financial land loss

These are the distinct causes the model has to represent. They are not
interchangeable: each has its own hazard input, its own vulnerability
relationship, and its own treatment under the policy, so `vul` carries a damage
ratio per cause rather than one aggregate figure per asset.

- **Land settlement and cracking** — liquefaction-induced settlement and
  differential movement of the land itself.
- **Ejecta** — material ejected to the surface, and the cost of clearing it.
- **Landslide loss of support** — land removed from beneath or beside the
  property by a failure originating on it.
- **Landslide runout** — material arriving from a failure originating elsewhere,
  including from council land above.
- **Underground services damaged** — damage to the private services within the
  property.
- **Retaining walls fail** — failure of the walls themselves, settled on
  replacement value up to the cap rather than on the value of the land.

The distinction between loss of support and runout matters for the policy
question, because it decides whose insured land the damage falls on. See
`nhc-land-cover-and-settlement.md` for how each is settled and
`land-damage-mechanisms.md` for the physical processes behind them.
