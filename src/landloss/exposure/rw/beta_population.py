"""A stand-in retaining wall population for the beta, driven by slope alone.

The real population is inferred from a model over the DEM, geomorphology and
road and dwelling locations, trained on the ICNZ database, a manual mapping
study, T+T Wellington SME estimates and remote sensing detection. None of those
inputs is in the repository yet, and the SME estimate of wall prevalence by
suburb (**T-19**) is the measure the real model would be calibrated against.

So this module manufactures a population instead. **Everything here carries a
``beta`` name and is deleted when the real inference arrives** -- nothing in it
is evidence about Wellington. What it does buy is the structure the rest of the
chain reads: a line per wall, keyed to a claim, carrying a size class and an
initial condition.

Slope is the only driver, because it is the only one of the real model's inputs
already attached to every insured property. That is defensible as far as it goes -- a
wall exists to hold up ground that will not stand at its own angle, so steep
ground carries more walls and taller ones -- and it is nowhere near enough: it
knows nothing about cut-and-fill, road batters, section shape or the age of the
subdivision.

The numbers below are engineering judgement with no fit behind them. They are
tuned to put wall prevalence in the range the team expects from Wellington --
roughly one property in two on the steep hill suburbs, very few on the flat --
and that expectation is itself what **T-19** exists to replace.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from landloss.common.utils.terrain import azimuth_offsets
from landloss.domain.loss_contract import CLAIM_ID_COLUMN

# The size class boundaries, in metres of retained height. Set by what the
# costing can tell apart rather than by engineering interest: above the sub-cap
# the settlement stops depending on height, so a three metre and a six metre
# wall settle the same and do not need separating.
SMALL_MAX_HEIGHT_M = 1.0
MEDIUM_MAX_HEIGHT_M = 2.5
SIZE_CLASSES = ("small", "medium", "large")

# The two initial condition classes. The real model reads these off the age of
# the dwelling; no dwelling age is held, so the beta draws them.
INITIAL_CONDITIONS = ("modern", "poor")
BETA_POOR_SHARE = 0.5

# Prevalence against slope. Below the first, effectively no walls; above the
# second, most properties carry one. A smooth ramp between, because there is no
# threshold in the world and pretending otherwise would put a visible edge
# across the map at whatever angle was chosen.
BETA_MIN_SLOPE_DEG = 3.0
BETA_MAX_SLOPE_DEG = 25.0
BETA_MAX_PREVALENCE = 0.8

# Retained height against slope, over the same range. A wall on gentle ground is
# a garden edge; one on a steep section is holding up the driveway.
BETA_MIN_HEIGHT_M = 0.4
BETA_MAX_HEIGHT_M = 3.0

# Wall length against the property. A wall runs across part of the section
# rather than around it, so the length is a fraction of the width of a square of
# the same area.
BETA_LENGTH_SHARE = 0.5

# The columns the population is keyed and sized on, fixed by the layer step 5
# writes rather than varying per caller.
ID_COLUMN = CLAIM_ID_COLUMN
AREA_COLUMN = "area_m2"

COLUMNS = (ID_COLUMN, "size_class", "initial_condition", "height_m", "length_m")


def _ramp(values: np.ndarray, low: float, high: float) -> np.ndarray:
    """Return values mapped onto 0 to 1 across a range, clipped at both ends."""
    if high <= low:
        msg = f"the ramp needs high above low, got {low} to {high}"
        raise ValueError(msg)
    return np.clip((np.asarray(values, dtype=float) - low) / (high - low), 0.0, 1.0)


def beta_wall_prevalence(slope_deg: np.ndarray | float) -> np.ndarray:
    """Return the probability that a property carries a wall, from its slope.

    Args:
        slope_deg: Ground slope at the property, in degrees.

    Returns:
        A probability per property, zero on flat ground rising to
        :data:`BETA_MAX_PREVALENCE` on steep ground.
    """
    return (
        _ramp(slope_deg, BETA_MIN_SLOPE_DEG, BETA_MAX_SLOPE_DEG) * BETA_MAX_PREVALENCE
    )


def beta_wall_height_m(slope_deg: np.ndarray | float) -> np.ndarray:
    """Return the retained height of a wall, from the slope it sits on.

    Args:
        slope_deg: Ground slope at the property, in degrees.

    Returns:
        Retained height in metres.
    """
    share = _ramp(slope_deg, BETA_MIN_SLOPE_DEG, BETA_MAX_SLOPE_DEG)
    return BETA_MIN_HEIGHT_M + share * (BETA_MAX_HEIGHT_M - BETA_MIN_HEIGHT_M)


def classify_wall_size(height_m: np.ndarray | float) -> np.ndarray:
    """Return the size class of a wall from its retained height.

    Args:
        height_m: Retained height in metres.

    Returns:
        ``"small"``, ``"medium"`` or ``"large"`` per wall.
    """
    heights = np.asarray(height_m, dtype=float)
    return np.select(
        [heights < SMALL_MAX_HEIGHT_M, heights < MEDIUM_MAX_HEIGHT_M],
        [SIZE_CLASSES[0], SIZE_CLASSES[1]],
        default=SIZE_CLASSES[2],
    )


def wall_lines(
    points: gpd.GeoSeries,
    downhill_azimuth_deg: np.ndarray,
    length_m: np.ndarray,
) -> gpd.GeoSeries:
    """Return a wall line per property, lying along the contour.

    A retaining wall runs across the slope rather than down it, so each line is
    drawn perpendicular to the downhill direction and centred on the
    representative point of the claim's insured land polygon. That is the
    crudest placement that puts a wall where one could be: it is the right
    orientation and the wrong position, since nothing here knows where on the
    section the wall actually sits.

    Args:
        points: One point per property, in a projected CRS.
        downhill_azimuth_deg: The downhill bearing at each point, degrees
            clockwise from grid north.
        length_m: The length of each wall, in metres.

    Returns:
        A GeoSeries of lines, on the index and CRS of ``points``.

    Raises:
        ValueError: If the three inputs are not the same length.
    """
    if not len(points) == len(downhill_azimuth_deg) == len(length_m):
        msg = (
            f"points, azimuths and lengths must match: got {len(points)}, "
            f"{len(downhill_azimuth_deg)} and {len(length_m)}"
        )
        raise ValueError(msg)

    # A contour runs at right angles to the downhill direction.
    along_contour = np.asarray(downhill_azimuth_deg, dtype=float) + 90.0
    half = np.asarray(length_m, dtype=float) / 2.0
    eastings, northings = azimuth_offsets(along_contour, half)

    lines = [
        LineString(
            [
                (point.x - east, point.y - north),
                (point.x + east, point.y + north),
            ]
        )
        for point, east, north in zip(points, eastings, northings, strict=True)
    ]
    return gpd.GeoSeries(lines, index=points.index, crs=points.crs)


def beta_wall_population(
    properties: gpd.GeoDataFrame,
    rng: np.random.Generator,
    *,
    slope_column: str = "slope_deg",
    azimuth_column: str = "downhill_azimuth_deg",
) -> gpd.GeoDataFrame:
    """Draw a stand-in wall population over a set of properties.

    One wall at most per property, drawn against the slope-driven prevalence,
    then sized, conditioned and placed along the contour.

    Args:
        properties: One row per claim, carrying the slope, downhill azimuth,
            insured area and claim id columns named below, with point geometry
            at the representative point of the claim's insured land.
        rng: The generator for this realisation's exposure stream.
        slope_column: Ground slope in degrees.
        azimuth_column: Downhill bearing in degrees clockwise from grid north.

    Returns:
        One row per wall, carrying :data:`COLUMNS` and a line geometry. A
        property that drew no wall has no row.

    Raises:
        ValueError: If a required column is missing.
    """
    required = (slope_column, azimuth_column, AREA_COLUMN, ID_COLUMN)
    missing = [column for column in required if column not in properties.columns]
    if missing:
        msg = f"properties is missing {missing}"
        raise ValueError(msg)

    slope = properties[slope_column].to_numpy(dtype=float)
    prevalence = beta_wall_prevalence(slope)

    # A property with no slope sampled cannot be placed, so it draws no wall
    # rather than being treated as flat.
    known = np.isfinite(slope) & np.isfinite(
        properties[azimuth_column].to_numpy(dtype=float)
    )
    has_wall = known & (rng.random(len(properties)) < prevalence)
    walls = properties.loc[has_wall].copy()
    if walls.empty:
        return gpd.GeoDataFrame(
            {column: [] for column in COLUMNS},
            geometry=gpd.GeoSeries([], crs=properties.crs),
            crs=properties.crs,
        )

    height = beta_wall_height_m(walls[slope_column].to_numpy(dtype=float))
    length = np.sqrt(walls[AREA_COLUMN].to_numpy(dtype=float)) * BETA_LENGTH_SHARE
    condition = np.where(
        rng.random(len(walls)) < BETA_POOR_SHARE,
        INITIAL_CONDITIONS[1],
        INITIAL_CONDITIONS[0],
    )

    return gpd.GeoDataFrame(
        {
            ID_COLUMN: walls[ID_COLUMN].to_numpy(),
            "size_class": classify_wall_size(height),
            "initial_condition": condition,
            "height_m": height,
            "length_m": length,
        },
        geometry=wall_lines(
            walls.geometry,
            walls[azimuth_column].to_numpy(dtype=float),
            length,
        ).to_numpy(),
        crs=properties.crs,
    )


def describe_population(walls: pd.DataFrame) -> pd.DataFrame:
    """Return the wall count by size class and initial condition.

    Args:
        walls: The drawn wall population.

    Returns:
        A table of counts, one row per size class, one column per condition.
    """
    if walls.empty:
        return pd.DataFrame(index=list(SIZE_CLASSES), columns=list(INITIAL_CONDITIONS))
    counts = walls.pivot_table(
        index="size_class",
        columns="initial_condition",
        values="height_m",
        aggfunc="size",
        fill_value=0,
    )
    return counts.reindex(index=list(SIZE_CLASSES), fill_value=0)
