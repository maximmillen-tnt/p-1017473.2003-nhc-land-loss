"""Build the insured land polygon for every claim, from the property boundaries.

The claim is the **property**, not the address. This script reads the LINZ
property boundaries, counts the address points standing inside each one to get
its dwellings, buffers every building on it by 8 m, unions the driveways in and
clips the result back to the property:

    uv run --frozen python src/scripts/landloss/exposure/land/steps/s5_insured_land_extent/gen_insured_land.py

What it runs over comes from ``config.py`` beside it, read at the bottom of this
file and passed into :func:`main`. Change it there rather than passing flags, so
that what a run did can be read off the source.

Needs ``LINZ_API_KEY`` in ``.env`` for the property boundary, building outline
and roadway layers, and the land value output of step 2 on disk -- run
``src/scripts/landloss/exposure/land/steps/s2_land_value/s4_estimate_land_value.py``
first if it is not there.

Four things are worth watching in the run output.

- **Properties with no dwelling.** They carry no insured land, because cover
  follows a residential building. A bare section belongs in that group; a
  property whose address point LINZ placed outside its own boundary does not,
  and only the count makes the second case visible.
- **Buildings split across a boundary.** A terrace captured as one outline is
  two buildings on two properties, and the run says how many were split.
- **The insured area against the property area.** The 8 m buffer reaches the
  boundary on a small section, so the two converge; where they do not, the
  difference is the back of the section.
- **Overlap.** The extents are clipped to their own properties, so they should
  not overlap at all. The run measures it rather than assuming it, because area
  is summed per claim downstream.
"""

import sys

import geopandas as gpd

from landloss.domain import constants
from landloss.exposure.land.driveways import (
    describe_driveways,
    generate_driveways,
)
from landloss.exposure.land.extent import (
    ADDRESS_ID_COLUMN,
    AREA_COLUMN,
    BOUNDARY_ROW_COLUMN,
    BUILDING_COUNT_COLUMN,
    CLAIM_ID_COLUMN,
    DWELLING_COUNT_COLUMN,
    MIN_CROSSING_AREA_M2,
    MIN_CROSSING_SHARE,
    OUTLINE_ID_COLUMN,
    PROPERTY_AREA_COLUMN,
    TITLE_TYPE_COLUMN,
    assign_buildings_to_properties,
    build_claim_properties,
    build_insured_land_extent,
    count_dwellings,
)
from landloss.io.readers import (
    get_nz_address_roads,
    get_nz_building_outlines,
    get_nz_property_boundaries,
)
from scripts.landloss.exposure.land.steps.s5_insured_land_extent import config
from scripts.landloss.paths import TEMP_DIR

# Wellington place names are macronised -- Ōwhiro Bay, Pāuatahanui -- which the
# default cp1252 Windows console cannot encode, so printing one raises. Ask for
# UTF-8 rather than stripping the macrons, because the names are worth getting
# right.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# temp/ is gitignored. This is a working layer, rebuildable from the land value
# output and the LINZ layers, so it has no business in a diff.
WORK_DIR = TEMP_DIR / "exposure"

# The step 2 output this reads, and the layer this writes. Separate names under
# the pilot, so a pilot run cannot overwrite a full one.
LAND_VALUE_NAME = "land-value-by-address.geoparquet"
PILOT_LAND_VALUE_NAME = "land-value-by-address-pilot.geoparquet"
OUT_NAME = "insured-land.geoparquet"
PILOT_OUT_NAME = "insured-land-pilot.geoparquet"

# The rate the extent carries forward, and the lot size assumption it is there
# to be checked against.
RATE_COLUMN = "land_rate_nzd_per_m2"
ASSUMED_LOT_SIZE_COLUMN = "assumed_lot_size_m2"

# The LINZ layers are fetched over the addresses' own bounding box grown by this
# much, so a property or a building belonging to an address just inside the box
# is still in the read. A property boundary is the widest of the three, and a
# rural rating unit can run a long way back from the address point on it.
FETCH_MARGIN_M = 500.0

# The quantiles the area distributions are described at.
DECILES = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]

HECTARE_M2 = 10_000.0
RULE = "-" * 72


def land_value_path(*, pilot):
    """Return the step 2 output this step reads.

    Args:
        pilot: Whether the run is over the pilot box.

    Returns:
        The path to the valued addresses, under ``temp/exposure/``.
    """
    return WORK_DIR / (PILOT_LAND_VALUE_NAME if pilot else LAND_VALUE_NAME)


def driveway_path(*, pilot):
    """Return the file a run writes the driveway corridors to.

    The driveways are unioned into the insured land extent, but step 7 tests
    watercourse crossings against the accessway itself rather than against the
    whole property, so they are also written out on their own.

    Args:
        pilot: Whether the run is over the pilot box.

    Returns:
        The output path, under ``temp/exposure/``.
    """
    suffix = "-pilot" if pilot else ""
    return WORK_DIR / f"driveways{suffix}.geoparquet"


def insured_land_path(*, pilot):
    """Return the file a run writes the insured land extent to.

    A function rather than a constant because the name depends on the extent,
    and the extent is an argument. ``fig_insured_land.py`` calls this too, which
    is what keeps the figure drawing the layer this script actually wrote.

    Args:
        pilot: Whether the run is over the pilot box.

    Returns:
        The output path, under ``temp/exposure/``.
    """
    return WORK_DIR / (PILOT_OUT_NAME if pilot else OUT_NAME)


def fetch_extent(addresses):
    """Return the bounding box to fetch the LINZ layers over.

    Args:
        addresses: The valued addresses.

    Returns:
        ``(minx, miny, maxx, maxy)`` in the study's own projection, grown by
        :data:`FETCH_MARGIN_M`.
    """
    minx, miny, maxx, maxy = (float(value) for value in addresses.total_bounds)
    return (
        minx - FETCH_MARGIN_M,
        miny - FETCH_MARGIN_M,
        maxx + FETCH_MARGIN_M,
        maxy + FETCH_MARGIN_M,
    )


def describe_properties(boundaries, properties):
    """Print what the boundaries were reduced to, and what was dropped."""
    print(RULE)
    print(f"Property boundaries read: {len(boundaries):,}")
    print(
        f"  {len(boundaries) - len(properties):,} dropped as road and water "
        "parcels, or dissolved as titles stacked on one footprint"
    )
    print(f"Claim properties: {len(properties):,}")

    stacked = properties[properties[BOUNDARY_ROW_COLUMN] > 1]
    print(
        f"  {len(stacked):,} are a block of titles on one footprint, standing "
        f"for {int(stacked[BOUNDARY_ROW_COLUMN].sum()):,} boundary rows between "
        "them"
    )
    if TITLE_TYPE_COLUMN in properties.columns:
        titles = properties[TITLE_TYPE_COLUMN].fillna("no title type").value_counts()
        print("  by title type: " + ", ".join(f"{k} {v:,}" for k, v in titles.items()))

    # Clipping makes the extents disjoint only if the properties themselves are.
    # Exact duplicates are already dissolved; this is what is left.
    summed = float(properties.geometry.area.sum())
    distinct = properties.geometry.union_all().area
    share = 100 * (summed - distinct) / summed if summed else 0.0
    print(
        f"  {summed / HECTARE_M2:,.1f} ha of property against "
        f"{distinct / HECTARE_M2:,.1f} ha of distinct ground, "
        f"{share:.2f}% still overlapping"
    )


def describe_dwellings(addresses, dwellings, properties):
    """Print how the address points fell into the properties."""
    print(RULE)
    print(f"Addresses: {len(addresses):,}")
    outside = len(addresses) - len(dwellings)
    print(
        f"  {outside:,} stand outside every claim property, so they count "
        "towards no dwelling"
    )

    counts = dwellings.groupby(CLAIM_ID_COLUMN).size()
    print(f"Properties with at least one dwelling: {len(counts):,}")
    print(
        f"  {len(properties) - len(counts):,} have none, so they carry no "
        "insured land: bare sections, and address points placed outside their "
        "own boundary"
    )
    print(
        f"  dwellings per property: median {counts.median():,.0f}, "
        f"max {counts.max():,.0f}, {int(counts.sum()):,} in total"
    )


def describe_buildings(buildings, parts):
    """Print how the building outlines were cut to the properties."""
    print(RULE)
    print(f"Building outlines: {len(buildings):,}")

    per_outline = parts.groupby(OUTLINE_ID_COLUMN)[CLAIM_ID_COLUMN].nunique()
    split = per_outline[per_outline > 1]
    print(f"  {len(per_outline):,} stand on an occupied claim property")
    print(
        f"  {len(split):,} of those were split across {int(split.sum()):,} "
        f"properties, being at least {MIN_CROSSING_AREA_M2:,.0f} m2 and "
        f"{MIN_CROSSING_SHARE:.0%} on each -- semi detached and terraced houses "
        "captured as one outline"
    )
    print(
        "  smaller overhangs were dropped as the outline and boundary layers "
        "disagreeing along a shared edge"
    )


def describe_extent(extent, occupied, addresses):
    """Print the insured land, and confirm the extents do not overlap."""
    print(RULE)
    print(
        f"Insured land: {extent[AREA_COLUMN].sum() / HECTARE_M2:,.1f} ha over "
        f"{len(extent):,} claims, {int(extent[DWELLING_COUNT_COLUMN].sum()):,} "
        "dwellings"
    )
    print(f"  {len(occupied) - len(extent):,} occupied properties carry no building")

    # Confirmed rather than assumed, because everything downstream sums area per
    # claim and would double count silently if it were not true.
    dissolved = extent.geometry.union_all().area
    summed = float(extent[AREA_COLUMN].sum())
    # Not asserted: clipping makes the extents disjoint only as far as the
    # properties themselves are, and a handful of boundaries are near duplicates
    # that the exact-equality dissolve does not catch. The residual is the
    # honest number to print.
    overlap = summed - dissolved
    print(
        f"  summed area {summed / HECTARE_M2:,.1f} ha against "
        f"{dissolved / HECTARE_M2:,.1f} ha of distinct ground, so "
        f"{overlap / HECTARE_M2:,.2f} ha ({100 * overlap / summed:.2f}%) is "
        "claimed by two properties that overlap each other"
    )

    quantiles = extent[AREA_COLUMN].quantile(DECILES)
    print("Insured area per claim (m2):")
    print(
        "  " + "  ".join(f"{int(q * 100):>3}%={v:,.0f}" for q, v in quantiles.items())
    )
    covered = extent[AREA_COLUMN] / extent[PROPERTY_AREA_COLUMN]
    print(
        f"  which is {covered.median():.0%} of the property at the median and "
        f"{covered.quantile(0.9):.0%} at the 90th percentile -- the 8 m line "
        "reaches the boundary on a small section and stops short on a large one"
    )

    if ASSUMED_LOT_SIZE_COLUMN not in addresses.columns:
        return
    assumed = float(addresses[ASSUMED_LOT_SIZE_COLUMN].median())
    measured = float(extent[AREA_COLUMN].median())
    print(
        f"  median {measured:,.0f} m2 against the {assumed:,.0f} m2 lot size "
        f"step 2 assumed to build its rate -- {measured / assumed:,.2f} times it"
    )
    print(
        "  the rate per square metre is still built on the assumption, so the "
        "two describe different pieces of ground until T-25 closes"
    )


def main(*, pilot, use_cached_extent):
    """Build the insured land extent per claim and write it out.

    Args:
        pilot: Whether to run over the small Wellington pilot box.
        use_cached_extent: Whether to reuse already-fetched LINZ layers.
    """
    out_path = insured_land_path(pilot=pilot)
    value_path = land_value_path(pilot=pilot)
    print(f"Reading the valued addresses from {value_path} ...", flush=True)
    addresses = gpd.read_parquet(value_path)
    bbox = fetch_extent(addresses)

    print("Fetching the property boundaries ...", flush=True)
    boundaries = get_nz_property_boundaries(
        bbox=bbox, crs=constants.DEFAULT_CRS, use_cache=use_cached_extent
    )
    boundaries = boundaries.set_geometry(boundaries.geometry.make_valid())
    print("Fetching the building outlines ...", flush=True)
    buildings = get_nz_building_outlines(
        bbox=bbox, crs=constants.DEFAULT_CRS, use_cache=use_cached_extent
    )
    buildings = buildings.set_geometry(buildings.geometry.make_valid())

    properties = build_claim_properties(boundaries)
    describe_properties(boundaries, properties)

    dwellings = count_dwellings(properties, addresses)
    describe_dwellings(addresses, dwellings, properties)

    occupied = properties[
        properties[CLAIM_ID_COLUMN].isin(set(dwellings[CLAIM_ID_COLUMN]))
    ]
    parts = assign_buildings_to_properties(buildings, occupied)
    describe_buildings(buildings, parts)

    # The insured land is the ground around the dwelling AND the driveway, so an
    # extent of building buffers alone is short of NHC's own definition. Routed
    # from the building parts, so a split terrace routes one driveway per half.
    print("Fetching the roads to route driveways to ...", flush=True)
    roads = get_nz_address_roads(
        bbox=bbox, crs=constants.DEFAULT_CRS, use_cache=use_cached_extent
    )
    driveways = generate_driveways(parts, roads)

    extent = build_insured_land_extent(
        properties, buildings, dwellings, driveways=driveways
    )
    print(RULE)
    print(f"Roads: {len(roads):,}")
    print(describe_driveways(driveways, len(parts)).to_string())
    describe_extent(extent, occupied, addresses)

    # The rate rides along with the polygon so that the vulnerability step reads
    # one layer rather than joining two. It is the same rate step 2 modelled;
    # nothing here revalues anything. A property takes the mean of the rates of
    # the addresses standing on it, which for a block of flats is the rate its
    # units were each modelled at.
    rates = (
        dwellings.merge(
            addresses[[ADDRESS_ID_COLUMN, RATE_COLUMN]], on=ADDRESS_ID_COLUMN
        )
        .groupby(CLAIM_ID_COLUMN)[RATE_COLUMN]
        .mean()
    )
    insured = extent.assign(**{RATE_COLUMN: extent[CLAIM_ID_COLUMN].map(rates)})
    insured = insured[
        [
            CLAIM_ID_COLUMN,
            RATE_COLUMN,
            AREA_COLUMN,
            PROPERTY_AREA_COLUMN,
            BUILDING_COUNT_COLUMN,
            # The dwellings the claim covers. NHC's sub-caps and excess are per
            # dwelling, so a block of flats settling as one claim still settles
            # on several.
            DWELLING_COUNT_COLUMN,
            insured.geometry.name,
        ]
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    insured.to_parquet(out_path)
    print(RULE)
    print(f"Wrote {len(insured):,} insured land polygons to {out_path}")

    driveway_out = driveway_path(pilot=pilot)
    driveways.to_parquet(driveway_out)
    print(f"Wrote {len(driveways):,} driveway corridors to {driveway_out}")


if __name__ == "__main__":
    main(pilot=config.PILOT, use_cached_extent=config.USE_CACHED_EXTENT)
