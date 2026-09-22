"""Where an insured accessway crosses a watercourse, and what carries it over.

The exposure is the **crossing**, not the structure: a culvert or a bridge
exists to take the accessway over water, so finding where the two meet finds the
population. Where an accessway crosses nothing, there is nothing to find.

Two things happen here, and only the first is observed.

**Detecting the crossing** is geometry. The accessway is intersected against
both LINZ river layers -- the name lines and the name polygons -- because a
narrow stream exists only as a centreline while a river wide enough to need a
bridge has an areal extent, and testing the lines alone would miss exactly the
crossings most likely to carry a bridge. Any watercourse counts, not only the
named rivers the liquefaction work separates out, because most accessway
crossings are of small streams.

**Choosing the structure is a draw**, because no crossing dataset exists for the
study area. A crossing takes a culvert with probability
:data:`CULVERT_PROBABILITY` and a bridge otherwise; the two are exhaustive,
since something has to carry the accessway over the water. Both figures are
engineering judgement and neither is fitted to anything, which is why they are
named here rather than buried in a script.

Note what the detection inherits from its inputs. Both LINZ layers carry
**named** watercourses only, so an unnamed stream is invisible to this test --
and unnamed streams are where most small accessway crossings are. The population
this produces is therefore a floor rather than an estimate.
"""

import geopandas as gpd
import numpy as np
import pandas as pd

# The split between the two structures at a crossing. Exhaustive: a crossing
# carries one or the other, because the accessway has to get over the water
# somehow. Engineering judgement, fitted to nothing.
CULVERT_PROBABILITY = 0.8
BRIDGE_PROBABILITY = 1.0 - CULVERT_PROBABILITY

CULVERT = "culvert"
BRIDGE = "bridge"
STRUCTURES = (CULVERT, BRIDGE)

ADDRESS_ID_COLUMN = "address_id"
STRUCTURE_COLUMN = "structure"
WATERCOURSE_SOURCE_COLUMN = "watercourse_source"

# Which layer a crossing was found against, kept so the run can report what
# reading both layers earned over reading the lines alone.
FROM_LINES = "lines"
FROM_POLYGONS = "polygons"


def _crossing_geometry(
    accessways: gpd.GeoDataFrame,
    water: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Return the part of each accessway lying on a watercourse."""
    if water.empty:
        return accessways.iloc[0:0].copy()
    overlay = gpd.overlay(
        accessways,
        water[[water.geometry.name]],
        how="intersection",
        keep_geom_type=False,
    )
    return overlay[~overlay.geometry.is_empty]


def detect_crossings(
    accessways: gpd.GeoDataFrame,
    river_lines: gpd.GeoDataFrame,
    river_polygons: gpd.GeoDataFrame,
    *,
    id_column: str = ADDRESS_ID_COLUMN,
) -> gpd.GeoDataFrame:
    """Find where the accessways cross a watercourse.

    Args:
        accessways: The driveway corridors, carrying ``id_column``.
        river_lines: The river name lines over the same extent.
        river_polygons: The river name polygons over the same extent.
        id_column: The property identifier carried onto each crossing.

    Returns:
        One row per crossing, carrying ``id_column``,
        :data:`WATERCOURSE_SOURCE_COLUMN` and the crossing geometry. A property
        whose accessway crosses nothing has no row.

    Raises:
        ValueError: If the frames disagree on their coordinate reference system,
            or the accessways carry no ``id_column``.
    """
    if id_column not in accessways.columns:
        msg = f"accessways carry no {id_column!r} column"
        raise ValueError(msg)
    for name, frame in (
        ("river_lines", river_lines),
        ("river_polygons", river_polygons),
    ):
        if not frame.empty and frame.crs != accessways.crs:
            msg = f"accessways are {accessways.crs} and {name} are {frame.crs}"
            raise ValueError(msg)

    found = []
    for source, water in ((FROM_LINES, river_lines), (FROM_POLYGONS, river_polygons)):
        crossings = _crossing_geometry(accessways, water)
        if crossings.empty:
            continue
        crossings = crossings[[id_column, crossings.geometry.name]].copy()
        crossings[WATERCOURSE_SOURCE_COLUMN] = source
        found.append(crossings)

    if not found:
        return gpd.GeoDataFrame(
            {id_column: [], WATERCOURSE_SOURCE_COLUMN: []},
            geometry=gpd.GeoSeries([], crs=accessways.crs),
            crs=accessways.crs,
        )

    combined = pd.concat(found, ignore_index=True)
    return gpd.GeoDataFrame(
        combined, geometry=combined.geometry.name, crs=accessways.crs
    )


def sample_structures(
    crossings: gpd.GeoDataFrame,
    rng: np.random.Generator,
) -> gpd.GeoDataFrame:
    """Draw a culvert or a bridge at each crossing.

    Args:
        crossings: The detected crossings, as :func:`detect_crossings` returns.
        rng: The generator for this realisation's exposure stream.

    Returns:
        A copy carrying :data:`STRUCTURE_COLUMN`, one of :data:`STRUCTURES`.
    """
    drawn = crossings.copy()
    if drawn.empty:
        drawn[STRUCTURE_COLUMN] = pd.Series(dtype="object")
        return drawn
    drawn[STRUCTURE_COLUMN] = np.where(
        rng.random(len(drawn)) < CULVERT_PROBABILITY, CULVERT, BRIDGE
    )
    return drawn


def describe_crossings(crossings: gpd.GeoDataFrame, accessways: int) -> pd.Series:
    """Return what was found, for a run to print.

    Args:
        crossings: The drawn crossing population.
        accessways: How many accessways were tested.

    Returns:
        The counts by structure and by which layer found the crossing, and the
        share of accessways that cross anything.
    """
    summary = {
        "accessways tested": accessways,
        "crossings found": len(crossings),
        "share of accessways": len(crossings) / accessways if accessways else 0.0,
    }
    if crossings.empty:
        return pd.Series(summary)
    for structure in STRUCTURES:
        summary[structure] = int((crossings[STRUCTURE_COLUMN] == structure).sum())
    for source in (FROM_LINES, FROM_POLYGONS):
        summary[f"found on {source}"] = int(
            (crossings[WATERCOURSE_SOURCE_COLUMN] == source).sum()
        )
    return pd.Series(summary)
