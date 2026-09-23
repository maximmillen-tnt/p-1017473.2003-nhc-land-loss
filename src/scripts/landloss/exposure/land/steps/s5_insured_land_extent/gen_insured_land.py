"""Build the insured land polygon for every address, from the building outlines.

Up to here the land exposure is a point with a rate per square metre on it. A
point cannot be intersected with a landslide, so nothing downstream can say how
much of a property's land was lost. This script turns each address into the
ground NHC cover actually attaches to -- an 8 metre buffer of the buildings on
it -- and carries the rate onto that polygon:

    uv run --frozen python src/scripts/landloss/exposure/land/steps/s5_insured_land_extent/gen_insured_land.py

What it runs over comes from ``config.py`` beside it, read at the bottom of this
file and passed into :func:`main`. Change it there rather than passing flags, so
that what a run did can be read off the source.

Needs ``LINZ_API_KEY`` in ``.env`` for the building outline layer, and the land
value output of step 2 on disk -- run
``src/scripts/landloss/exposure/land/steps/s2_land_value/s4_estimate_land_value.py``
first if it is not there.

Three things are worth watching in the run output.

- **Addresses with no building.** They get no polygon and so carry no insured
  land at all downstream. Vacant sections belong in that group; addresses whose
  building the outline layer has not captured do not, and only the count makes
  the second case visible.
- **The insured area against the assumed lot size.** Step 2 divides a modelled
  land value by a per-authority ``median_lot_size_m2`` to get its rate, so a
  measured insured area far from that assumption says the rate and the area it
  is multiplied by are describing different pieces of ground. That is register
  task T-25.
- **Shared ground.** The run says how much of the buffered area two properties
  had between them, and confirms the extents no longer overlap after it was
  split. Area is summed per address downstream, so an overlap here would be paid
  for twice.
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
    BUILDING_COUNT_COLUMN,
    DWELLING_COUNT_COLUMN,
    INSURED_LAND_BUFFER_M,
    MAX_BUILDING_TO_ADDRESS_M,
    MAX_SHARED_BUILDING_TO_ADDRESS_M,
    OUTLINE_ID_COLUMN,
    attach_buildings_to_addresses,
    buffer_buildings,
    build_insured_land_extent,
    collapse_coincident_addresses,
)
from landloss.io.readers import get_nz_address_roads, get_nz_building_outlines
from scripts.landloss.exposure.land.steps.s5_insured_land_extent import config
from scripts.landloss.paths import TEMP_DIR

# Wellington place names are macronised -- Ōwhiro Bay, Pāuatahanui -- which the
# default cp1252 Windows console cannot encode, so printing one raises. Ask for
# UTF-8 rather than stripping the macrons, because the names are worth getting
# right.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# temp/ is gitignored. This is a working layer, rebuildable from the land value
# output and the building outlines, so it has no business in a diff.
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

# The building outlines are fetched over the addresses' own bounding box grown
# by this much. A building belonging to an address just inside the box can stand
# outside it, and so can the part of the buffer that reaches back in, so the
# margin is the join distance plus the buffer.
FETCH_MARGIN_M = MAX_BUILDING_TO_ADDRESS_M + INSURED_LAND_BUFFER_M

# The quantiles the area distribution is described at. Deciles rather than a
# mean and a standard deviation, because insured area is bounded below by the
# building footprint and has a long tail of large properties.
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
    """Return the bounding box to fetch building outlines over.

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


def describe_inputs(addresses, buildings, bbox):
    """Print what the extent is being built from."""
    west, south, east, north = bbox
    print(RULE)
    print(f"Addresses: {len(addresses):,}")
    print(f"Building outlines: {len(buildings):,}")
    print(f"  fetched over {west:,.0f} - {east:,.0f} E, {south:,.0f} - {north:,.0f} N")
    print(
        f"  which is the addresses' own extent grown by {FETCH_MARGIN_M:,.0f} m, "
        "so a building just outside it still reaches its address"
    )


def describe_coverage(addresses, attached, buildings, extent):
    """Print which addresses and which buildings found each other.

    An address with no building carries no insured land at all downstream, and a
    building with no address is a structure the model has nowhere to put, so both
    counts are worth seeing on every run.

    ``attached`` carries one row per building per address, so a block of flats
    appears once for each unit on it. The counts below are taken over distinct
    outlines where that is what is meant.
    """
    dwellings = int(extent[DWELLING_COUNT_COLUMN].sum())
    properties = collapse_coincident_addresses(addresses)

    print(RULE)
    print(
        f"Addresses: {len(addresses):,}, on {len(properties):,} distinct locations. "
        "Units of one block share a coordinate and become one property carrying a "
        "dwelling count."
    )
    print(
        f"Properties with insured land: {len(extent):,} of {len(properties):,}, "
        f"covering {dwellings:,} dwellings"
    )

    # Where an address carries no land, the distance from its point to the
    # nearest outline is the whole diagnosis. Inside the sharing tolerance it is
    # a unit the partition could not separate from another on the same block;
    # outside it, the point does not stand on a building at all, and it is a
    # vacant section, a gap in the outline layer or an address point placed off
    # its dwelling. The three are not distinguishable here and should not be
    # reported as though they were.
    missing = properties[~properties[ADDRESS_ID_COLUMN].isin(extent[ADDRESS_ID_COLUMN])]
    if len(missing):
        nearest = missing.geometry.apply(lambda point: buildings.distance(point).min())
        unseparated = int((nearest <= MAX_SHARED_BUILDING_TO_ADDRESS_M).sum())
        off_building = len(missing) - unseparated
        print(
            f"  {off_building:,} stand more than "
            f"{MAX_SHARED_BUILDING_TO_ADDRESS_M:,.0f} m from any outline: a vacant "
            "section, a gap in the outline layer, or a point placed off its "
            "dwelling (T-23)"
        )
        if unseparated:
            print(f"  {unseparated:,} stand on an outline but took no share of it")

    outlines = attached[OUTLINE_ID_COLUMN].nunique()
    per_outline = attached.groupby(OUTLINE_ID_COLUMN)[ADDRESS_ID_COLUMN].nunique()
    multi = per_outline[per_outline > 1]
    print(f"Outlines attributed to an address: {outlines:,} of {len(buildings):,}")
    print(
        f"  {len(buildings) - outlines:,} had no address point near enough to attach to"
    )
    print(
        f"  {len(multi):,} carry more than one address -- flats and cross-leases "
        f"-- covering {int(multi.sum()):,} addresses between them (T-23)"
    )

    counts = extent[BUILDING_COUNT_COLUMN]
    print(
        f"Buildings per address: median {counts.median():,.0f}, max {counts.max():,.0f}"
    )


def describe_shared_ground(attached, extent):
    """Print how much ground neighbouring properties had between them.

    The buffers are rebuilt here without the split, so the difference between
    the two totals is the ground that two or more properties shared. It is the
    one number that says how much the splitting rule is deciding, and summing
    the unsplit areas per address is exactly the double count the split exists
    to prevent.
    """
    unsplit = buffer_buildings(attached)
    overlapped = float(unsplit.geometry.area.sum()) - float(extent[AREA_COLUMN].sum())

    print(RULE)
    print(
        f"Insured land: {extent[AREA_COLUMN].sum() / HECTARE_M2:,.1f} ha over "
        f"{len(extent):,} properties"
    )
    print(
        f"  {overlapped / HECTARE_M2:,.1f} ha of that was within "
        f"{INSURED_LAND_BUFFER_M:,.0f} m of two properties' buildings and has "
        "been given to the nearer one"
    )

    # Confirmed rather than assumed, because everything downstream sums area per
    # address and would double count silently if it were not true.
    dissolved = extent.geometry.union_all().area
    summed = float(extent[AREA_COLUMN].sum())
    print(
        f"  summed area {summed / HECTARE_M2:,.1f} ha against "
        f"{dissolved / HECTARE_M2:,.1f} ha of distinct ground, so the extents do "
        "not overlap"
    )


def describe_areas(extent, addresses):
    """Print the insured area distribution, against the lot size step 2 assumed."""
    print(RULE)
    quantiles = extent[AREA_COLUMN].quantile(DECILES)
    print("Insured area per property (m2):")
    print(
        "  " + "  ".join(f"{int(q * 100):>3}%={v:,.0f}" for q, v in quantiles.items())
    )

    if ASSUMED_LOT_SIZE_COLUMN not in addresses.columns:
        return

    assumed = addresses[ASSUMED_LOT_SIZE_COLUMN].median()
    measured = extent[AREA_COLUMN].median()
    print(
        f"  median {measured:,.0f} m2 against the {assumed:,.0f} m2 lot size "
        f"step 2 assumed to build its rate -- {measured / assumed:.2f} times it"
    )
    print(
        "  the rate per square metre is still built on the assumption, so the "
        "two describe different pieces of ground until T-25 closes"
    )


def main(*, pilot, use_cached_extent):
    """Build the insured land extent for every valued address and write it out.

    Args:
        pilot: Whether to run over the small Wellington pilot box rather than
            the four territorial authorities.
        use_cached_extent: Whether to reuse the already-clipped building
            outlines for this extent.
    """
    in_path = land_value_path(pilot=pilot)
    out_path = insured_land_path(pilot=pilot)

    print(f"Reading the valued addresses from {in_path} ...", flush=True)
    addresses = gpd.read_parquet(in_path).to_crs(constants.DEFAULT_CRS)

    bbox = fetch_extent(addresses)
    print("Fetching the building outlines ...", flush=True)
    buildings = get_nz_building_outlines(
        bbox=bbox, crs=constants.DEFAULT_CRS, use_cache=use_cached_extent
    )
    describe_inputs(addresses, buildings, bbox)

    attached = attach_buildings_to_addresses(buildings, addresses)

    # The insured land is the ground around the dwelling AND the driveway, so an
    # extent of building buffers alone is short of NHC's own definition.
    print("Fetching the roads to route driveways to ...", flush=True)
    roads = get_nz_address_roads(
        bbox=bbox, crs=constants.DEFAULT_CRS, use_cache=use_cached_extent
    )
    driveways = generate_driveways(attached, roads)

    extent = build_insured_land_extent(addresses, buildings, driveways=driveways)

    describe_coverage(addresses, attached, buildings, extent)
    print(RULE)
    print(f"Roads: {len(roads):,}")
    print(describe_driveways(driveways, len(attached)).to_string())
    describe_shared_ground(attached, extent)
    describe_areas(extent, addresses)

    # The rate rides along with the polygon so that the vulnerability step reads
    # one layer rather than joining two. It is the same rate step 2 modelled;
    # nothing here revalues anything.
    rates = addresses[[ADDRESS_ID_COLUMN, RATE_COLUMN]]
    insured = extent.merge(rates, on=ADDRESS_ID_COLUMN, how="left", validate="1:1")
    insured = insured[
        [
            ADDRESS_ID_COLUMN,
            RATE_COLUMN,
            AREA_COLUMN,
            BUILDING_COUNT_COLUMN,
            # The dwellings this one row stands for. NHC's sub-caps and excess
            # are per dwelling, so a block of flats settling as one property
            # still settles on several.
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
