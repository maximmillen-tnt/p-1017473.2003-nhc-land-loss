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

## Shared support code

Two packages sit outside the four modules because all of them need them:

- `src/landloss/domain/` — constants shared across the model: the default CRS
  (NZTM, `EPSG:2193`), the Koordinates domains and their API key variables, and
  layer IDs.
- `src/landloss/io/` — readers for the datasets the models are built from, and
  `area_of_interest.py`, which holds the named study extents.

### Areas of interest

An extent is defined once, in WGS84, and converted to whatever CRS a caller needs
via `.bbox(crs)`. Defining them in one place stops an extent being re-typed from a
map into each script. `SMALL_WLG_PILOT` is a roughly 2.9 by 1.7 km box in central
Wellington, about 4.7 km², for exercising the workflow end to end before it is run
over the full study area.

### Koordinates access and caching

Layers come from two Koordinates domains, each with its own API key read from
`.env`: `ttgroup.koordinates.com` via `TNT_KOORDINATES_API_KEY` for T+T's own
layers, and `data.linz.govt.nz` via `LINZ_API_KEY` for LINZ layers. The key is
chosen from the domain rather than a single shared variable.

Caching happens at two levels, which matters because layers such as NZ Addresses
are national:

1. ttpy caches the whole downloaded layer under `KOOPCACHE_DIR`, keyed by layer
   ID, version and a hash of the layer details. A layer is downloaded once.
2. `landloss.io.readers` caches the clipped extent under `KOOPCACHE_DIR/extents`,
   keyed by the source file name — which encodes the layer version — plus the CRS
   and bounding box. Asking for the same extent again skips reading and clipping
   the source.

The extent cache applies only when a bounding box is given, because without a clip
it would store a second full copy of a layer ttpy has already cached.

**On measurement, the extent cache is not currently earning its keep.** Reading
the Wellington pilot extent (8,591 addresses) out of the 809 MB NZ Addresses
layer, alternating five times each way, gave a median of 1.68 s cached against
1.79 s uncached, with the ranges overlapping. GeoPackage carries a spatial index,
so pushing the bounding box down into the read is already fast whatever the size
of the source, and reading a small cached copy back costs about the same.

The expensive step is the download, and ttpy already caches that. Keep this in
mind before relying on the extent cache for performance; it may be worth removing
in favour of the pushdown alone.

Because the extent cache key includes the layer version, a new version of a layer
upstream produces a new key rather than a stale hit. Pass `use_cache=False` to
force a re-read.

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
