"""How much of a property's insured land a landslide takes, and from where.

The damage measure for a landslide on land is **geometric**, not a damage state.
A landslide either covers part of a property or it does not, and how much it
covers is the whole question, so this module intersects the hazard module's
polygons with the insured land and returns areas.

The two kinds of ground are kept apart all the way through, because the policy
settles them differently:

- **Evacuated** ground is what the failure removed -- loss of support, where the
  land under or beside the property went.
- **Inundated** ground is where the debris came to rest, which may have started
  on somebody else's property entirely.

Each carries the **depth** of the landslide it belongs to, from the volume-area
power law in :mod:`landloss.hazard.landslide.geometry`, because what a repair
costs depends on how much material has to be moved and not only on the footprint.

One asymmetry in the inputs drives the arithmetic here. Evacuated polygons are
guaranteed not to overlap one another; inundated polygons are not, because two
failures running into the same gully floor both land on it. Ground buried twice
is buried once, so **inundated area is measured on the union** rather than
summed across landslides. Doing otherwise would charge a property twice for the
same square metre.
"""

import geopandas as gpd
import numpy as np
import pandas as pd

ADDRESS_ID_COLUMN = "address_id"
LAND_CLASS_COLUMN = "land_class"
DEPTH_COLUMN = "depth_m"

EVACUATED = "evacuated land"
INUNDATED = "inundated land"

# What the output calls each kind of damaged ground, matching the causes the
# vulnerability rows are keyed on.
AREA_COLUMNS = {
    EVACUATED: "evacuated_area_m2",
    INUNDATED: "inundated_area_m2",
}
DEPTH_COLUMNS = {
    EVACUATED: "evacuated_depth_m",
    INUNDATED: "inundated_depth_m",
}


def _overlay(
    insured: gpd.GeoDataFrame, slides: gpd.GeoDataFrame, id_column: str
) -> gpd.GeoDataFrame:
    """Return the parts of the insured land each landslide covers."""
    columns = [id_column, insured.geometry.name]
    pieces = gpd.overlay(
        insured[columns],
        slides,
        how="intersection",
        keep_geom_type=True,
    )
    return pieces[~pieces.geometry.is_empty]


def _accumulate_class(
    rows: dict[str, dict],
    insured: gpd.GeoDataFrame,
    landslides: gpd.GeoDataFrame,
    land_class: str,
    id_column: str,
) -> None:
    """Add one kind of damaged ground to the per-property rows, in place.

    Args:
        rows: The rows built so far, keyed by property, added to in place.
        insured: The insured land polygons.
        landslides: Every landslide polygon of every kind.
        land_class: The kind of ground to accumulate, a key of
            :data:`AREA_COLUMNS`.
        id_column: The property identifier.
    """
    slides = landslides[landslides[LAND_CLASS_COLUMN] == land_class]
    if slides.empty:
        return

    keep = [LAND_CLASS_COLUMN, DEPTH_COLUMN, slides.geometry.name]
    pieces = _overlay(insured, slides[keep], id_column)
    if pieces.empty:
        return
    pieces = pieces.assign(_piece_area=pieces.geometry.area)

    for address, group in pieces.groupby(id_column):
        row = rows.setdefault(address, {id_column: address})
        # Summing across landslides would double count ground two of them both
        # reached, which inundated polygons are allowed to do.
        row[AREA_COLUMNS[land_class]] = group.geometry.union_all().area
        # Depth belongs to a landslide, so a property covered by two takes the
        # depth each contributed, weighted by how much it contributed.
        weights = group["_piece_area"].to_numpy()
        depths = group[DEPTH_COLUMN].to_numpy(dtype=float)
        usable = np.isfinite(depths) & (weights > 0)
        row[DEPTH_COLUMNS[land_class]] = (
            float(np.average(depths[usable], weights=weights[usable]))
            if usable.any()
            else np.nan
        )


def damaged_area_per_property(
    insured: gpd.GeoDataFrame,
    landslides: gpd.GeoDataFrame,
    *,
    id_column: str = ADDRESS_ID_COLUMN,
) -> pd.DataFrame:
    """Return the evacuated and inundated area on each property.

    Args:
        insured: One insured land polygon per property, carrying ``id_column``.
            These must not overlap one another, which the exposure step
            guarantees; if they did, a landslide would be counted on two
            properties at once.
        landslides: The hazard module's polygons, carrying
            :data:`LAND_CLASS_COLUMN` and :data:`DEPTH_COLUMN`.
        id_column: The property identifier.

    Returns:
        One row per property that any landslide touched, carrying the area of
        each kind of ground and its mean depth weighted by area. A property no
        landslide reached is absent rather than present with zeros.

    Raises:
        ValueError: If the frames disagree on their coordinate reference system,
            or the landslides carry no land class.
    """
    if LAND_CLASS_COLUMN not in landslides.columns:
        msg = f"landslides carry no {LAND_CLASS_COLUMN!r} column"
        raise ValueError(msg)
    if not landslides.empty and insured.crs != landslides.crs:
        msg = f"insured land is {insured.crs} and landslides are {landslides.crs}"
        raise ValueError(msg)

    rows: dict[str, dict] = {}
    for land_class in AREA_COLUMNS:
        _accumulate_class(rows, insured, landslides, land_class, id_column)

    if not rows:
        columns = [id_column, *AREA_COLUMNS.values(), *DEPTH_COLUMNS.values()]
        return pd.DataFrame({column: [] for column in columns})

    damaged = pd.DataFrame(list(rows.values()))
    for column in (*AREA_COLUMNS.values(), *DEPTH_COLUMNS.values()):
        if column not in damaged.columns:
            damaged[column] = np.nan
    # An untouched kind of ground is zero area, not unknown area.
    for column in AREA_COLUMNS.values():
        damaged[column] = damaged[column].fillna(0.0)
    order = [id_column, *AREA_COLUMNS.values(), *DEPTH_COLUMNS.values()]
    return damaged[order].sort_values(id_column, kind="stable").reset_index(drop=True)


def check_within_insured_area(
    damaged: pd.DataFrame,
    insured: gpd.GeoDataFrame,
    *,
    id_column: str = ADDRESS_ID_COLUMN,
    area_column: str = "area_m2",
) -> pd.DataFrame:
    """Return any property whose damaged ground exceeds its insured land.

    Evacuated and inundated ground may legitimately overlap each other, so the
    two summed can pass a property's own area without anything being wrong. What
    cannot happen is either one alone exceeding it.

    Args:
        damaged: The per-property areas.
        insured: The insured land, carrying ``area_column``.
        id_column: The property identifier.
        area_column: The insured area on ``insured``.

    Returns:
        The offending rows, empty when every property is within its own land.
    """
    merged = damaged.merge(
        insured[[id_column, area_column]], on=id_column, how="left", validate="1:1"
    )
    # A rounding tolerance, not a modelling one: these are polygon areas.
    tolerance = 1e-6
    over = pd.Series(np.zeros(len(merged), dtype=bool), index=merged.index)
    for column in AREA_COLUMNS.values():
        over |= merged[column] > merged[area_column] * (1 + tolerance)
    return merged[over]
