"""Whether a structure is caught by a landslide, shared by walls and crossings.

A retaining wall, culvert or bridge is not priced by how much ground a landslide
takes from it, as land is, but by whether a landslide reached it at all. The
flag is kept per kind of ground, because the policy settles the two differently:

- **Evacuated** -- the structure sits on ground the failure removed.
- **Inundated** -- the structure sits under ground where the debris came to rest.

A structure touching both kinds of ground carries both flags.

This sits at the landslide level rather than under an asset submodule because it
reads no asset-specific attribute: it needs only an identifier and a geometry,
whatever the structure is.
"""

import geopandas as gpd
import pandas as pd

from landloss.domain.loss_contract import IS_EVACUATED_COLUMN, IS_INUNDATED_COLUMN
from landloss.vul.landslide.land.damaged_area import (
    EVACUATED,
    INUNDATED,
    LAND_CLASS_COLUMN,
)

# Which flag each kind of damaged ground sets.
FLAG_COLUMNS = {
    EVACUATED: IS_EVACUATED_COLUMN,
    INUNDATED: IS_INUNDATED_COLUMN,
}


def _caught_ids(
    assets: gpd.GeoDataFrame,
    landslides: gpd.GeoDataFrame,
    land_class: str,
    id_column: str,
) -> pd.Index:
    """Return the ids of the assets any landslide of one kind intersects."""
    slides = landslides[landslides[LAND_CLASS_COLUMN] == land_class]
    if slides.empty:
        return pd.Index([])
    joined = gpd.sjoin(
        assets[[id_column, assets.geometry.name]],
        slides[[slides.geometry.name]],
        predicate="intersects",
        how="inner",
    )
    return pd.Index(joined[id_column].unique())


def landslide_flags(
    assets: gpd.GeoDataFrame,
    landslides: gpd.GeoDataFrame,
    *,
    id_column: str,
) -> pd.DataFrame:
    """Return whether each asset is caught by evacuated or inundated ground.

    Args:
        assets: One row per structure, carrying ``id_column``. Any geometry type
            works, lines, polygons and collections alike.
        landslides: The hazard module's polygons, carrying
            :data:`~landloss.vul.landslide.land.damaged_area.LAND_CLASS_COLUMN`.
        id_column: The asset identifier, unique per row.

    Returns:
        One row per asset in the order given, carrying ``id_column`` and the
        boolean :data:`~landloss.domain.loss_contract.IS_EVACUATED_COLUMN` and
        :data:`~landloss.domain.loss_contract.IS_INUNDATED_COLUMN`. An asset no
        landslide reached is present with both flags False.

    Raises:
        ValueError: If the landslides carry no land class, the asset ids repeat,
            or the frames disagree on their coordinate reference system.
    """
    if LAND_CLASS_COLUMN not in landslides.columns:
        msg = f"landslides carry no {LAND_CLASS_COLUMN!r} column"
        raise ValueError(msg)
    repeated = assets[id_column][assets[id_column].duplicated()].unique()
    if len(repeated):
        msg = f"asset ids repeat: {sorted(map(str, repeated))}"
        raise ValueError(msg)
    if not landslides.empty and not assets.empty and assets.crs != landslides.crs:
        msg = f"assets are {assets.crs} and landslides are {landslides.crs}"
        raise ValueError(msg)

    flags = pd.DataFrame({id_column: assets[id_column].to_numpy()})
    for land_class, column in FLAG_COLUMNS.items():
        if assets.empty:
            flags[column] = pd.Series([], dtype=bool)
            continue
        caught = _caught_ids(assets, landslides, land_class, id_column)
        flags[column] = flags[id_column].isin(caught).astype(bool)
    return flags
