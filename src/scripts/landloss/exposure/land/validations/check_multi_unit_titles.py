"""Check the multi-unit handling against the titles the properties are held under.

The insured land extent makes two judgements about properties that share a
building, and neither of them reads a title:

- Addresses on the same coordinate are **collapsed** into one property with a
  dwelling count, on the reasoning that units of one block cannot be separated.
- One outline is **shared** with every address standing on it, on the reasoning
  that they are units in that building.

The LINZ property boundaries layer carries ``title_type``, which is the only
statement in the exposure data of how a property is actually held. This script
puts the two side by side:

    uv run --frozen python src/scripts/landloss/exposure/land/validations/check_multi_unit_titles.py

What it is checking for is a mismatch. A **unit title** or a **cross lease** is
exactly the case the merging exists to handle: several dwellings, one piece of
land, and no sensible way to divide the ground between them. A **freehold**
title is the opposite -- separately owned land -- so a merge on freehold titles
is either a genuine multi-dwelling freehold property, or two sections the rule
wrongly joined.

The title type on its own does not settle it, and neither does a count of how
many property boundaries a merge touches: an apartment block carries one unit
title per unit, all on the same footprint, so it spans many boundaries and is
still one piece of land. The last table is the one that discriminates. It
compares the ground a merge group's properties cover between them against the
largest of them alone, which separates titles **stacked on one footprint** from
a group that has **reached onto the neighbour's section**.

It reports rather than asserts, because a multi-dwelling freehold property is a
real thing and no threshold makes the answer right or wrong; the splits are the
finding.

Needs ``LINZ_API_KEY`` in ``.env``, and the insured land extent on disk -- run
``src/scripts/landloss/exposure/land/steps/s5_insured_land_extent/gen_insured_land.py``
first if it is not there.
"""

import sys

import geopandas as gpd
import pandas as pd

from landloss.domain import constants
from landloss.exposure.land.extent import (
    ADDRESS_ID_COLUMN,
    DWELLING_COUNT_COLUMN,
    MAX_BUILDING_TO_ADDRESS_M,
    MAX_SHARED_BUILDING_TO_ADDRESS_M,
    OUTLINE_ID_COLUMN,
    attach_buildings_to_addresses,
    collapse_coincident_addresses,
)
from landloss.io.readers import get_nz_building_outlines, get_nz_property_boundaries
from scripts.landloss.exposure.land.steps.s5_insured_land_extent import config
from scripts.landloss.exposure.land.steps.s5_insured_land_extent.gen_insured_land import (
    fetch_extent,
    land_value_path,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TITLE_TYPE_COLUMN = "title_type"

# What the boundaries layer calls a property with no title type at all: a parcel
# that filled a gap where there was neither a rating unit nor a spatialised
# title. Named so the tables do not silently drop those rows.
UNTITLED = "no title type"

RULE = "-" * 72


def title_type_at(points, boundaries):
    """Return the title type of the property each point falls in.

    Args:
        points: The address points.
        boundaries: The property boundaries, carrying
            :data:`TITLE_TYPE_COLUMN`.

    Returns:
        The title type per point, indexed as ``points`` is, with
        :data:`UNTITLED` where the property carries none and NaN where the point
        falls outside every boundary.
    """
    located = gpd.sjoin(
        gpd.GeoDataFrame(geometry=points),
        boundaries[[TITLE_TYPE_COLUMN, boundaries.geometry.name]],
        how="left",
        predicate="within",
    )
    # A point on a shared boundary falls in two properties. Keeping the first
    # makes the count reproducible; it is a handful of rows either way.
    located = located[~located.index.duplicated(keep="first")]
    types = located[TITLE_TYPE_COLUMN].reindex(points.index)
    return types.replace("", UNTITLED)


def describe_split(label, types, total):
    """Print the title types of one kind of merge, as counts and shares."""
    print(RULE)
    print(f"{label}: {total:,} addresses")
    if not total:
        return

    counts = types.fillna("outside every property boundary").value_counts()
    counts.index.name = TITLE_TYPE_COLUMN
    table = pd.DataFrame(
        {"addresses": counts, "share": (counts / total).map("{:.1%}".format)}
    )
    print(table.to_string())


def describe_ground_spanned(label, merged, boundaries, id_column):
    """Print whether each merge group's properties are stacked or side by side.

    This is the test the title type cannot do on its own, and a count of
    distinct property boundaries cannot either. An apartment block has one unit
    title polygon per unit, **all on the same footprint**; two freehold sections
    wrongly joined have two polygons **on different ground**. Both span several
    property boundaries, and only the first is a merge that should have
    happened.

    So the polygons of a group are compared by area: the ground they cover
    between them against the largest of them alone. A ratio near one means they
    are stacked on one footprint, which is a block of units. A ratio well above
    one means the group reaches across land LINZ holds apart.

    Args:
        label: What kind of merge this is, for the heading.
        merged: The addresses involved, carrying ``id_column`` as the group key.
        boundaries: The property boundaries.
        id_column: The column the merge groups on.

    Returns:
        None. Prints the split.
    """
    print(RULE)
    print(f"{label}: is the ground one footprint, or several?")
    if merged.empty:
        print("  none")
        return

    located = gpd.sjoin(
        merged[[id_column, merged.geometry.name]],
        boundaries[[boundaries.geometry.name]],
        how="inner",
        predicate="within",
    )
    shapes = boundaries.geometry

    stacked = 0
    spread = 0
    single = 0
    for _, group in located.groupby(id_column):
        found = group["index_right"].dropna().unique()
        if len(found) <= 1:
            single += 1
            continue
        polygons = shapes.loc[found]
        covered = polygons.union_all().area
        largest = polygons.area.max()
        # A tenth more ground than the largest property on its own is the line.
        # Below it the polygons are the same piece of land titled several times;
        # above it the group has reached onto a neighbour.
        if covered <= largest * 1.1:
            stacked += 1
        else:
            spread += 1

    total = single + stacked + spread
    print(f"  {single:,} of {total:,} sit in one property boundary")
    print(
        f"  {stacked:,} span several boundaries stacked on one footprint "
        "-- a block of unit titles, which is the case the merge exists for"
    )
    print(
        f"  {spread:,} reach across ground LINZ holds apart "
        "-- these are the merges to be suspicious of"
    )


def main(*, pilot):
    """Report the title types behind the merges the insured land extent makes."""
    addresses = gpd.read_parquet(land_value_path(pilot=pilot))
    bbox = fetch_extent(addresses)

    print("Fetching the building outlines ...", flush=True)
    buildings = get_nz_building_outlines(bbox=bbox, crs=constants.DEFAULT_CRS)
    print("Fetching the property boundaries ...", flush=True)
    boundaries = get_nz_property_boundaries(bbox=bbox, crs=constants.DEFAULT_CRS)

    types = title_type_at(addresses.geometry, boundaries)
    addresses = addresses.assign(**{TITLE_TYPE_COLUMN: types})

    print(RULE)
    print(f"Addresses: {len(addresses):,}")
    print(f"Property boundaries over the extent: {len(boundaries):,}")
    describe_split("Every address", addresses[TITLE_TYPE_COLUMN], len(addresses))

    # The first merge: addresses on one coordinate, collapsed into one property.
    # Counted over every address involved, not over the surviving representative,
    # because the question is how many addresses the rule acted on.
    collapsed = collapse_coincident_addresses(addresses)
    representatives = collapsed[collapsed[DWELLING_COUNT_COLUMN] > 1]
    merged_ids = set(representatives[ADDRESS_ID_COLUMN])
    coincident = addresses[
        addresses[ADDRESS_ID_COLUMN].isin(merged_ids)
        | ~addresses[ADDRESS_ID_COLUMN].isin(collapsed[ADDRESS_ID_COLUMN])
    ]
    describe_split(
        "Collapsed onto one coordinate, so settled as one property",
        coincident[TITLE_TYPE_COLUMN],
        len(coincident),
    )

    # Collapsed addresses share an exact coordinate, so they sit inside the same
    # property polygons whatever those are. There is nothing to check there --
    # the title type is the whole finding for that merge.

    # The second merge: one outline given to more than one address.
    attached = attach_buildings_to_addresses(
        buildings,
        collapsed,
        max_distance_m=MAX_BUILDING_TO_ADDRESS_M,
        max_shared_distance_m=MAX_SHARED_BUILDING_TO_ADDRESS_M,
    )
    per_outline = attached.groupby(OUTLINE_ID_COLUMN)[ADDRESS_ID_COLUMN].nunique()
    shared_outlines = set(per_outline[per_outline > 1].index)
    sharing = attached[attached[OUTLINE_ID_COLUMN].isin(shared_outlines)]
    sharing_types = addresses.set_index(ADDRESS_ID_COLUMN)[TITLE_TYPE_COLUMN]
    describe_split(
        "Sharing one building outline with another property",
        sharing[ADDRESS_ID_COLUMN].drop_duplicates().map(sharing_types),
        sharing[ADDRESS_ID_COLUMN].nunique(),
    )

    # Unlike the collapsed addresses, these sit at different points, so they can
    # fall in different properties -- and that, not the title type, is the test
    # of whether the outline should have been shared at all.
    sharing_points = collapsed[
        collapsed[ADDRESS_ID_COLUMN].isin(set(sharing[ADDRESS_ID_COLUMN]))
    ].merge(
        sharing[[ADDRESS_ID_COLUMN, OUTLINE_ID_COLUMN]].drop_duplicates(
            subset=ADDRESS_ID_COLUMN
        ),
        on=ADDRESS_ID_COLUMN,
        how="left",
    )
    describe_ground_spanned(
        "Sharing one building outline",
        gpd.GeoDataFrame(sharing_points, geometry=collapsed.geometry.name),
        boundaries,
        OUTLINE_ID_COLUMN,
    )

    print(RULE)
    print(
        "A unit title or a cross lease is the case the merging exists for. A "
        "freehold title is separately owned land, so a merge on one is either a "
        "genuine multi-dwelling freehold property or a join the rule got wrong."
    )
    print(
        "The title type alone cannot tell those apart, and nor can a count of "
        "boundaries -- an apartment block has one unit title per unit, all on "
        "one footprint. Whether the ground is one footprint or several can, "
        "which is what the last table splits."
    )


if __name__ == "__main__":
    main(pilot=config.PILOT)
