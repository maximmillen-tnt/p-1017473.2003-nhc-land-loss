"""The insured land extent: the ground around a dwelling that NHC cover pays for.

Every hazard in this study is read against a polygon rather than against a
point. A liquefaction land damage state is sampled at the address, but a
landslide is intersected with the ground a claim actually covers, and the area
that falls inside it is the damage measure the repair cost is built from. So the
whole chain needs one polygon per address, and this module builds it.

The extent is an 8 metre buffer of the building outlines, taken from
`.agents/context/nhc-land-cover-and-settlement.md`: NHC settles on the land
around the dwelling, in practice the 8 metre line from it, not on the whole
parcel. Whether a landslide lands inside that line or outside it is one of the
variables the study exists to test, which is why the extent is modelled rather
than approximated by the section.

**Driveways are part of the real definition and are not built here.** They
matter out of proportion to their area, because they are where most retaining
walls sit, and no driveway dataset covers the study area, so generating them
from the building to the roadway is its own piece of work. Until it lands, a
property whose driveway runs beyond the 8 metre line has that part of its
insured land missing. The saving grace recorded in the same context note is that
many sections in the study area are small enough that the 8 metre line reaches
the boundary anyway.

Three decisions the module makes, each of which costs something:

- **A building belongs to the nearest address point.** LINZ addresses are
  points, usually at the road frontage, and no key joins a building outline to
  one. Nearest is the obvious rule and is wrong in the two places you would
  expect: on a deep section a rear building can sit closer to the neighbour's
  frontage point than to its own, and a block of flats carrying several address
  points has its buildings split between those points by nothing more than which
  one each is nearest. That second case is register task T-23, multi-unit and
  cross-lease properties, and it is not resolved here.
- **An address with no building near it carries no insured land.** It gets no
  row, so it contributes zero area to every hazard intersection downstream
  rather than a polygon nobody can defend. Vacant sections, and addresses whose
  building the outline layer has not captured, both land in that group; the
  count is worth printing on any run, because it is the only visible sign of the
  second case.
- **Ground within 8 metres of two addresses' buildings goes to the nearer
  building.** Left overlapping, two neighbouring extents would each count the
  strip between the houses, and the vulnerability step sums area per address, so
  the same square metre would be paid for twice.
  :func:`split_shared_ground` partitions the shared ground on which building is
  nearest, which is symmetric between two neighbours and independent of the
  order the addresses arrive in.

That partition is built as a Voronoi diagram of points spaced along the building
outlines rather than of the outlines themselves, because Voronoi cells are
defined for points and not for polygons. :data:`PARTITION_DENSIFY_M` is the
spacing, and it is what the partition's accuracy is bounded by: between two
parallel house walls the boundary lands exactly halfway, and around a corner it
is out by at most half that spacing.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely import STRtree
from shapely.ops import polygonize

# The insured land definition: metres from the building outline. Not a tuning
# parameter -- it is NHC's own line, so it belongs here rather than in a step's
# config.py.
INSURED_LAND_BUFFER_M = 8.0

# How far a building may be from an address point and still be taken as that
# address's. Beyond this the nearest address is a guess rather than a join: a
# farm shed or a pump house half a kilometre up a valley is not part of the
# insured land of the house at the bottom of it.
MAX_BUILDING_TO_ADDRESS_M = 100.0

# How finely a building outline is broken into points before the shared ground
# is partitioned between neighbours. One metre against an 8 metre buffer, so the
# partition boundary is accurate to well inside the precision of the outlines
# themselves; finer costs time on every contested property and settles nothing.
PARTITION_DENSIFY_M = 1.0

ADDRESS_ID_COLUMN = "address_id"
AREA_COLUMN = "area_m2"
BUILDING_COUNT_COLUMN = "building_count"

# How far the building was from the address point it was attached to. Kept
# because it is the one number that says how much to trust that join.
ADDRESS_DISTANCE_COLUMN = "address_distance_m"


def _check_frames(
    addresses: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame, id_column: str
) -> None:
    """Refuse inputs the buffer arithmetic would silently get wrong.

    Args:
        addresses: The address points.
        buildings: The building outlines.
        id_column: The address identifier column.

    Raises:
        ValueError: If the address identifier is missing, if the two frames are
            in different coordinate reference systems, or if that system is
            geographic, where a buffer of 8 would be 8 degrees.
    """
    if id_column not in addresses.columns:
        msg = (
            f"The addresses carry no {id_column!r} column, so a building cannot "
            f"be attributed to one. Columns: {list(addresses.columns)}"
        )
        raise ValueError(msg)

    if addresses.crs != buildings.crs:
        msg = (
            f"The addresses are in {addresses.crs} and the buildings in "
            f"{buildings.crs}. Reproject one onto the other before building the "
            "extent, rather than letting the join compare coordinates in two "
            "different systems."
        )
        raise ValueError(msg)

    if addresses.crs is not None and addresses.crs.is_geographic:
        msg = (
            f"{addresses.crs} is a geographic system, so a buffer of "
            f"{INSURED_LAND_BUFFER_M} would be that many degrees. Work in a "
            "projected system such as NZGD2000 / NZTM."
        )
        raise ValueError(msg)


def _keep_nearest(joined: gpd.GeoDataFrame, id_column: str) -> gpd.GeoDataFrame:
    """Keep one row per left feature, breaking ties on the address identifier.

    ``sjoin_nearest`` returns every tied match, so a building equidistant from
    two address points comes back twice. Resolving on the identifier makes the
    answer the same on every run rather than however the spatial index happened
    to order the two.

    Args:
        joined: The result of a nearest join, indexed by the left frame.
        id_column: The address identifier column to break ties on.

    Returns:
        The join with one row per left feature.
    """
    ordered = joined.sort_values(id_column, kind="stable")
    return ordered[~ordered.index.duplicated(keep="first")].sort_index()


def attach_buildings_to_addresses(
    buildings: gpd.GeoDataFrame,
    addresses: gpd.GeoDataFrame,
    *,
    id_column: str = ADDRESS_ID_COLUMN,
    max_distance_m: float = MAX_BUILDING_TO_ADDRESS_M,
) -> gpd.GeoDataFrame:
    """Attribute every building outline to the address point nearest to it.

    Args:
        buildings: The building outlines.
        addresses: The address points, carrying ``id_column``.
        id_column: The address identifier to carry onto the buildings.
        max_distance_m: How far a building may be from an address point and
            still be attached to it. Buildings with no address point inside this
            distance are dropped.

    Returns:
        The buildings that found an address, carrying ``id_column`` and
        :data:`ADDRESS_DISTANCE_COLUMN`, indexed from zero.
    """
    if buildings.empty or addresses.empty:
        return buildings.iloc[:0].assign(**{id_column: [], ADDRESS_DISTANCE_COLUMN: []})

    joined = gpd.sjoin_nearest(
        buildings.reset_index(drop=True),
        addresses[[id_column, addresses.geometry.name]],
        how="inner",
        max_distance=max_distance_m,
        distance_col=ADDRESS_DISTANCE_COLUMN,
    )
    joined = _keep_nearest(joined, id_column)
    return joined.drop(columns="index_right").reset_index(drop=True)


def buffer_buildings(
    buildings: gpd.GeoDataFrame,
    *,
    buffer_m: float = INSURED_LAND_BUFFER_M,
    id_column: str = ADDRESS_ID_COLUMN,
) -> gpd.GeoDataFrame:
    """Buffer the outlines and merge them into one polygon per address.

    A property with a house and a garage has two overlapping buffers, and the
    insured land around it is one piece of ground rather than two, so they are
    dissolved before anything measures an area.

    Args:
        buildings: The building outlines, carrying ``id_column``.
        buffer_m: How far the insured land reaches from the outline.
        id_column: The address identifier to dissolve on.

    Returns:
        One row per address, carrying ``id_column``,
        :data:`BUILDING_COUNT_COLUMN` and the buffered polygon.
    """
    buffered = gpd.GeoDataFrame(
        buildings[[id_column]].copy(),
        geometry=buildings.geometry.buffer(buffer_m),
        crs=buildings.crs,
    )

    counts = buffered.groupby(id_column).size().rename(BUILDING_COUNT_COLUMN)
    dissolved = buffered.dissolve(by=id_column)
    return dissolved.join(counts).reset_index()


def nearest_building_cells(
    buildings: gpd.GeoDataFrame,
    extend_to: shapely.Geometry,
    *,
    id_column: str = ADDRESS_ID_COLUMN,
    densify_m: float = PARTITION_DENSIFY_M,
) -> gpd.GeoDataFrame:
    """Divide the plane into the ground nearest each address's buildings.

    Voronoi cells are defined for points, so each outline is broken into points
    spaced ``densify_m`` apart along it and the diagram is built from those. The
    cells of one address's points, taken together, are the ground nearer to that
    address's buildings than to anyone else's, to within half that spacing.

    The diagram is taken as its edges and rebuilt into faces, with a frame
    closing the outermost cells, rather than asked for as polygons. The faces
    are then disjoint by construction and share exact edges, which is the
    property the whole split rests on -- and GEOS returns some of the polygons
    with pinched rings, which are invalid and cannot be merged at all.

    Args:
        buildings: The building outlines, carrying ``id_column``.
        extend_to: The ground the diagram has to reach over. Its bounding box,
            grown by ``densify_m``, is the frame the outer cells close against.
        id_column: The address identifier each cell is labelled with.
        densify_m: The spacing of the points taken along each outline.

    Returns:
        One row per face of the diagram, carrying the ``id_column`` of the
        address whose building is nearest to it.
    """
    outlines = shapely.segmentize(buildings.geometry.boundary.to_numpy(), densify_m)
    coords, source = shapely.get_coordinates(outlines, return_index=True)

    # A ring repeats its first coordinate at the end, and two buildings can
    # share a corner. Voronoi refuses a repeated generator, so duplicates are
    # dropped -- first occurrence kept, so the result does not depend on how
    # numpy happened to sort them.
    _, first = np.unique(coords, axis=0, return_index=True)
    keep = np.sort(first)
    coords, source = coords[keep], source[keep]

    minx, miny, maxx, maxy = shapely.bounds(extend_to)
    frame = shapely.box(
        minx - densify_m, miny - densify_m, maxx + densify_m, maxy + densify_m
    )
    edges = shapely.voronoi_polygons(
        shapely.multipoints(coords), extend_to=frame, only_edges=True
    )
    faces = gpd.GeoDataFrame(
        geometry=list(polygonize(shapely.union_all([edges, frame.boundary]))),
        crs=buildings.crs,
    )

    # Every point inside a face has that face's own generator as its nearest,
    # so one point per face settles the whole face.
    generators = gpd.GeoDataFrame(
        {id_column: buildings[id_column].to_numpy()[source]},
        geometry=shapely.points(coords),
        crs=buildings.crs,
    )
    owners = gpd.sjoin_nearest(
        faces.set_geometry(faces.geometry.representative_point()),
        generators,
        how="inner",
    )
    owners = _keep_nearest(owners, id_column)

    return faces.loc[owners.index].assign(**{id_column: owners[id_column].to_numpy()})


def add_driveways(
    parts: gpd.GeoDataFrame,
    driveways: gpd.GeoDataFrame,
    *,
    id_column: str = ADDRESS_ID_COLUMN,
) -> gpd.GeoDataFrame:
    """Union each property's driveway corridors into its buffered extent.

    Called before :func:`split_shared_ground`, so that a driveway running past a
    neighbour's house is contested ground like any other and is partitioned by
    the same rule. Merging driveways into a finished extent instead would leave
    two properties holding the same strip.

    Args:
        parts: One buffered polygon per address, as :func:`buffer_buildings`
            returns.
        driveways: The driveway corridors, keyed on ``id_column``.
        id_column: The address identifier both are keyed on.

    Returns:
        ``parts`` with each property's driveways unioned into its polygon.
    """
    corridors = driveways.dissolve(by=id_column).geometry
    merged = parts.copy()
    additions = merged[id_column].map(corridors)
    has_driveway = additions.notna()
    merged.loc[has_driveway, merged.geometry.name] = [
        polygon.union(addition)
        for polygon, addition in zip(
            merged.loc[has_driveway, merged.geometry.name],
            additions[has_driveway],
            strict=True,
        )
    ]
    return merged


def split_shared_ground(
    parts: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    *,
    id_column: str = ADDRESS_ID_COLUMN,
    densify_m: float = PARTITION_DENSIFY_M,
) -> gpd.GeoDataFrame:
    """Cut overlapping extents apart so no square metre belongs to two addresses.

    The buffers of two houses eight metres apart share the strip between them.
    Downstream the vulnerability step sums area per address, so that strip would
    be paid for twice unless it is given to one of them here.

    Only the extents that actually touch another are rebuilt. The rest pass
    through untouched, which is most of them and keeps the Voronoi diagram down
    to the properties that need it.

    Args:
        parts: One buffered polygon per address, as :func:`buffer_buildings`
            returns.
        buildings: The building outlines, carrying ``id_column``, that those
            buffers were built from.
        id_column: The address identifier.
        densify_m: Passed to :func:`nearest_building_cells`.

    Returns:
        ``parts`` with the shared ground reassigned to the nearest building, so
        that the polygons are pairwise disjoint and their areas sum to the
        ground the buffers covered between them.
    """
    if len(parts) < 2:
        return parts

    parts = parts.reset_index(drop=True)
    geometries = parts.geometry.to_numpy()
    tree = STRtree(geometries)
    left, right = tree.query(geometries, predicate="intersects")
    contested = np.unique(left[left != right])

    if contested.size == 0:
        return parts

    shared = parts.iloc[contested]
    shared_buildings = buildings[buildings[id_column].isin(set(shared[id_column]))]

    cells = nearest_building_cells(
        shared_buildings,
        shared.geometry.union_all(),
        id_column=id_column,
        densify_m=densify_m,
    )

    # Clipping the partition back to insured land. An address's share is cut
    # against its *own* buffer rather than against the union of all of them, and
    # the two are the same set: a point in this address's cells is nearer to its
    # buildings than to anyone else's, so if it is inside any buffer at all it is
    # inside this one. Cutting against the one polygon keeps the operation on
    # simple geometry, which is what the union of a suburb's buffers is not.
    merged_cells = cells.dissolve(by=id_column)
    own_buffer = shared.set_index(id_column).geometry
    clipped = merged_cells.geometry.intersection(own_buffer)

    resolved = gpd.GeoDataFrame(
        shared.drop(columns=shared.geometry.name).set_index(id_column),
        geometry=clipped,
        crs=parts.crs,
    )
    resolved = resolved[~(resolved.geometry.isna() | resolved.geometry.is_empty)]
    resolved = resolved.reset_index()

    untouched = parts.drop(index=parts.index[contested])
    combined = pd.concat([untouched, resolved[untouched.columns]], ignore_index=True)
    return gpd.GeoDataFrame(combined, geometry=untouched.geometry.name, crs=parts.crs)


def build_insured_land_extent(
    addresses: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    *,
    driveways: gpd.GeoDataFrame | None = None,
    buffer_m: float = INSURED_LAND_BUFFER_M,
    id_column: str = ADDRESS_ID_COLUMN,
) -> gpd.GeoDataFrame:
    """Build one insured land polygon per address from the building outlines.

    Every building is attached to its nearest address point, the outlines are
    buffered by ``buffer_m`` and merged per address, and ground shared between
    two addresses goes to the nearer building, so the returned polygons do not
    overlap one another. The module docstring sets out what each of those three
    steps costs, and records that driveways are not part of the extent this
    builds.

    Args:
        addresses: The address points, carrying ``id_column``.
        buildings: The building outlines over the same extent.
        driveways: The driveway corridors, keyed on ``id_column``. Unioned in
            before the ground is partitioned, not after: a driveway merged into
            a finished extent would overlap the neighbour's and reintroduce the
            double counting the partition exists to remove.
        buffer_m: How far the insured land reaches from a building outline.
        id_column: The address identifier the extent is keyed on. A building
            further than :data:`MAX_BUILDING_TO_ADDRESS_M` from every address
            point is attached to none of them.

    Returns:
        One row per address that has a building, carrying ``id_column``,
        :data:`BUILDING_COUNT_COLUMN`, :data:`AREA_COLUMN` and the polygon,
        ordered by ``id_column``. Addresses with no building near them are
        absent rather than present with an empty geometry.

    Raises:
        ValueError: If the two frames disagree on their coordinate reference
            system, if that system is geographic, or if the addresses carry no
            ``id_column``.
    """
    _check_frames(addresses, buildings, id_column)

    attached = attach_buildings_to_addresses(
        buildings,
        addresses,
        id_column=id_column,
        max_distance_m=MAX_BUILDING_TO_ADDRESS_M,
    )
    if attached.empty:
        return gpd.GeoDataFrame(
            {id_column: [], BUILDING_COUNT_COLUMN: [], AREA_COLUMN: []},
            geometry=[],
            crs=addresses.crs,
        )

    parts = buffer_buildings(attached, buffer_m=buffer_m, id_column=id_column)
    if driveways is not None and not driveways.empty:
        parts = add_driveways(parts, driveways, id_column=id_column)
    parts = split_shared_ground(parts, attached, id_column=id_column)

    parts[AREA_COLUMN] = parts.geometry.area
    columns = [id_column, BUILDING_COUNT_COLUMN, AREA_COLUMN, parts.geometry.name]
    return parts[columns].sort_values(id_column, kind="stable").reset_index(drop=True)
