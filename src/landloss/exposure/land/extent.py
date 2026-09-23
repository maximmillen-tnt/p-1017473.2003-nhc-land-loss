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

Four decisions the module makes, each of which costs something:

- **Addresses at the same location are one property with several dwellings.**
  LINZ gives each unit of a block its own address and places several of them on
  one coordinate; in the Wellington pilot 2,523 addresses of 8,591 sit on a
  coordinate shared with at least one other. Nothing geometric can separate
  them, so :func:`collapse_coincident_addresses` reduces them to one row
  carrying :data:`DWELLING_COUNT_COLUMN`, which is what NHC's per-dwelling
  sub-caps and excess multiply. The cost is that only the lowest identifier of a
  block survives into the extent, so a downstream join on address will not find
  the others.
- **A building belongs to the nearest address point, but may serve more than
  one.** LINZ addresses are points and no key joins a building outline to one,
  so nearest is the rule. Taken alone it loses every flat: a block carrying
  several address points on one outline gives that outline to whichever point is
  nearest and leaves the rest with nothing, which over the Wellington pilot was
  3,827 addresses of 8,591. So an address the first pass left empty is attached
  to a building **whose outline its point sits on**, within
  :data:`MAX_SHARED_BUILDING_TO_ADDRESS_M`. That is register task T-23,
  multi-unit and cross-lease properties.
  The tolerance is deliberately tight. An address point standing on a building
  is a unit in it; an address point ten metres from the neighbour's house is a
  vacant section, and attaching it would hand that section insured land it does
  not have. The rule buys the unambiguous cases and declines the rest.
- **An address with no building near it carries no insured land.** It gets no
  row, so it contributes zero area to every hazard intersection downstream
  rather than a polygon nobody can defend. Vacant sections, addresses whose
  building the outline layer has not captured, and units whose address point
  stands off its building all land in that group; the count is worth printing on
  any run, because it is the only visible sign of the last two.
- **Ground within 8 metres of two addresses' buildings goes to the nearer
  building.** Left overlapping, two neighbouring extents would each count the
  strip between the houses, and the vulnerability step sums area per address, so
  the same square metre would be paid for twice.
  :func:`split_shared_ground` partitions the shared ground on which building is
  nearest, which is symmetric between two neighbours and independent of the
  order the addresses arrive in. Where one building serves several addresses its
  outline cannot break the tie, because they share it, so each point along that
  outline is labelled with the **nearest of the addresses on it** and the
  partition falls out of the same diagram. Units whose address points coincide
  exactly never reach this stage, having been collapsed into one property
  above.

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

# How far an address point may be from a building that already belongs to
# another address and still be taken as a second address on the same building.
# Far tighter than the join above, because this rule runs after the first pass
# has failed and the two readings of a nearby building are opposite: a point
# standing on the outline is a unit in that building, a point a few metres off
# it is just as likely a vacant section beside it. One metre is the capture
# difference between two LINZ layers, not a search radius. Over the Wellington
# pilot 70% of the addresses this rule recovers sit exactly on their outline.
MAX_SHARED_BUILDING_TO_ADDRESS_M = 1.0

# How finely a building outline is broken into points before the shared ground
# is partitioned between neighbours. One metre against an 8 metre buffer, so the
# partition boundary is accurate to well inside the precision of the outlines
# themselves; finer costs time on every contested property and settles nothing.
PARTITION_DENSIFY_M = 1.0

ADDRESS_ID_COLUMN = "address_id"
AREA_COLUMN = "area_m2"
BUILDING_COUNT_COLUMN = "building_count"

# How many dwellings the row's insured land serves. One for a house; more for a
# block of flats, whose units share both the building and the ground around it.
# Carried because NHC's sub-caps and excess are per dwelling, so the count is
# what the settlement is built on -- and because it is the only record that the
# addresses collapsed into this row exist at all.
DWELLING_COUNT_COLUMN = "dwelling_count"

# How close two address points have to be to be taken as the same location.
# LINZ gives each unit of a block its own address, and in the Wellington pilot
# 2,523 of 8,591 addresses sit on a coordinate shared with at least one other.
# Rounding to a grid this fine will split a pair straddling a grid line, which
# is a beta-grade approximation of clustering and is worth replacing.
COINCIDENT_ADDRESS_TOLERANCE_M = 0.1

# Which outline a row came from, kept because one outline can now appear once
# per address that sits on it. Without it a shared building is indistinguishable
# from two buildings that happen to coincide, and the partition would densify
# the same outline twice and throw half of it away as duplicate coordinates.
# Named for the outline rather than the building because the LINZ building
# outlines layer carries a ``building_id`` of its own, which this must not
# overwrite -- several outlines can belong to one building.
OUTLINE_ID_COLUMN = "outline_id"

# How far the building was from the address point it was attached to. Kept
# because it is the one number that says how much to trust that join.
ADDRESS_DISTANCE_COLUMN = "address_distance_m"


def collapse_coincident_addresses(
    addresses: gpd.GeoDataFrame,
    *,
    id_column: str = ADDRESS_ID_COLUMN,
    tolerance_m: float = COINCIDENT_ADDRESS_TOLERANCE_M,
) -> gpd.GeoDataFrame:
    """Reduce address points at the same location to one, counting the dwellings.

    LINZ gives each unit of a block of flats its own address, and places several
    of them on the same coordinate. Nothing geometric can separate those: they
    share the building, they share the ground around it, and a partition of that
    ground between them would be invented rather than measured.

    So they become one row. The lowest identifier represents them and carries
    :data:`DWELLING_COUNT_COLUMN`, which is the number NHC's per-dwelling
    sub-caps and excess are multiplied by. Left uncollapsed, all but one of those
    units simply falls out of the model holding nothing.

    Args:
        addresses: The address points, carrying ``id_column``.
        id_column: The address identifier.
        tolerance_m: How close two points must be to count as one location.

    Returns:
        One row per distinct location, carrying ``id_column`` and
        :data:`DWELLING_COUNT_COLUMN`, in the input's column order.
    """
    if addresses.empty:
        return addresses.assign(**{DWELLING_COUNT_COLUMN: []})

    grid = np.column_stack(
        [
            np.round(addresses.geometry.x.to_numpy() / tolerance_m),
            np.round(addresses.geometry.y.to_numpy() / tolerance_m),
        ]
    )
    located = addresses.assign(_east=grid[:, 0], _north=grid[:, 1])
    counts = located.groupby(["_east", "_north"])[id_column].transform("size")

    # The lowest identifier represents its location, so which unit stands for a
    # block does not depend on the order the addresses arrived in.
    ordered = located.assign(**{DWELLING_COUNT_COLUMN: counts}).sort_values(
        [id_column], kind="stable"
    )
    kept = ordered.drop_duplicates(subset=["_east", "_north"], keep="first")
    return kept.drop(columns=["_east", "_north"]).sort_index()


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


def _share_with_further_addresses(
    buildings: gpd.GeoDataFrame,
    addresses: gpd.GeoDataFrame,
    owned: gpd.GeoDataFrame,
    *,
    id_column: str,
    max_distance_m: float,
) -> gpd.GeoDataFrame:
    """Attach a building again for each further address standing on it.

    The nearest-address pass gives an outline to exactly one address, which
    leaves every flat but one of a block with nothing. This pass looks at the
    addresses that came away empty and gives each of them the outline its own
    point sits on, so one building can serve several addresses.

    Args:
        buildings: The building outlines, carrying :data:`OUTLINE_ID_COLUMN`.
        addresses: The address points, carrying ``id_column``.
        owned: The buildings the nearest-address pass attached.
        id_column: The address identifier.
        max_distance_m: How far an address point may stand from the outline.
            Tight on purpose: see :data:`MAX_SHARED_BUILDING_TO_ADDRESS_M`.

    Returns:
        Building rows, one per further address, carrying ``id_column`` and
        :data:`ADDRESS_DISTANCE_COLUMN`. Empty when every address already has a
        building.
    """
    empty = buildings.iloc[:0].assign(**{id_column: [], ADDRESS_DISTANCE_COLUMN: []})
    orphans = addresses[~addresses[id_column].isin(owned[id_column])]
    if orphans.empty:
        return empty

    joined = gpd.sjoin_nearest(
        orphans[[id_column, orphans.geometry.name]].reset_index(drop=True),
        buildings[[buildings.geometry.name]],
        how="inner",
        max_distance=max_distance_m,
        distance_col=ADDRESS_DISTANCE_COLUMN,
    )
    if joined.empty:
        return empty

    # An address standing on the seam between two outlines matches both. The
    # building index breaks the tie, so the answer does not depend on how the
    # spatial index happened to order them.
    joined = joined.sort_values("index_right", kind="stable")
    joined = joined[~joined.index.duplicated(keep="first")]

    shared = buildings.iloc[joined["index_right"].to_numpy()].reset_index(drop=True)
    shared[id_column] = joined[id_column].to_numpy()
    shared[ADDRESS_DISTANCE_COLUMN] = joined[ADDRESS_DISTANCE_COLUMN].to_numpy()
    return shared


def attach_buildings_to_addresses(
    buildings: gpd.GeoDataFrame,
    addresses: gpd.GeoDataFrame,
    *,
    id_column: str = ADDRESS_ID_COLUMN,
    max_distance_m: float = MAX_BUILDING_TO_ADDRESS_M,
    max_shared_distance_m: float = MAX_SHARED_BUILDING_TO_ADDRESS_M,
) -> gpd.GeoDataFrame:
    """Attribute building outlines to addresses, sharing one where several sit on it.

    Two passes. The first gives every building to the address point nearest to
    it. The second gives a building to each address that came away empty and
    whose own point stands on that outline, which is what a block of flats looks
    like and is the only way those addresses get any insured land at all.

    Args:
        buildings: The building outlines.
        addresses: The address points, carrying ``id_column``.
        id_column: The address identifier to carry onto the buildings.
        max_distance_m: How far a building may be from an address point and
            still be attached to it in the first pass. Buildings with no address
            point inside this distance are dropped.
        max_shared_distance_m: How far an address point may stand from an
            already-attached outline and still be taken as a second address on
            it.

    Returns:
        The buildings that found an address, carrying ``id_column``,
        :data:`OUTLINE_ID_COLUMN` and :data:`ADDRESS_DISTANCE_COLUMN`, indexed
        from zero. One row per building per address, so a shared outline appears
        more than once.
    """
    if buildings.empty or addresses.empty:
        return buildings.iloc[:0].assign(
            **{id_column: [], OUTLINE_ID_COLUMN: [], ADDRESS_DISTANCE_COLUMN: []}
        )

    indexed = buildings.reset_index(drop=True)
    indexed[OUTLINE_ID_COLUMN] = np.arange(len(indexed))

    joined = gpd.sjoin_nearest(
        indexed,
        addresses[[id_column, addresses.geometry.name]],
        how="inner",
        max_distance=max_distance_m,
        distance_col=ADDRESS_DISTANCE_COLUMN,
    )
    joined = _keep_nearest(joined, id_column)
    owned = joined.drop(columns="index_right").reset_index(drop=True)

    shared = _share_with_further_addresses(
        indexed,
        addresses,
        owned,
        id_column=id_column,
        max_distance_m=max_shared_distance_m,
    )
    if shared.empty:
        return owned
    return gpd.GeoDataFrame(
        pd.concat([owned, shared[owned.columns]], ignore_index=True),
        geometry=owned.geometry.name,
        crs=buildings.crs,
    )


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


def _label_by_nearest_address(
    coords: np.ndarray,
    building_ids: np.ndarray,
    buildings: gpd.GeoDataFrame,
    addresses: gpd.GeoDataFrame,
    id_column: str,
) -> np.ndarray:
    """Label each outline point with the nearest address standing on its building.

    A building serving one address labels all of its points with that address,
    which is what the partition did before any building was shared. A building
    serving several cannot be told apart by its own outline, so each point along
    it goes to whichever of those addresses is nearest -- which gives each unit
    the ground outside its own part of the block.

    Args:
        coords: The densified outline points, one row per point.
        building_ids: The :data:`OUTLINE_ID_COLUMN` each point came from.
        buildings: The attached buildings, one row per building per address.
        addresses: The address points, carrying ``id_column``.
        id_column: The address identifier.

    Returns:
        The address identifier for each point, in the order ``coords`` is in.
    """
    links = buildings[[OUTLINE_ID_COLUMN, id_column]].drop_duplicates()
    pairs = pd.DataFrame(
        {"_coord": np.arange(len(coords)), OUTLINE_ID_COLUMN: building_ids}
    ).merge(links, on=OUTLINE_ID_COLUMN, how="left")

    points = addresses.drop_duplicates(subset=id_column).set_index(id_column).geometry
    address_x = points.x.reindex(pairs[id_column]).to_numpy()
    address_y = points.y.reindex(pairs[id_column]).to_numpy()
    taken = coords[pairs["_coord"].to_numpy()]
    # Squared distance: the ordering is the same and the square root is not.
    # An address the frame does not carry sorts last rather than poisoning the
    # comparison with NaN.
    pairs["_distance"] = np.nan_to_num(
        (taken[:, 0] - address_x) ** 2 + (taken[:, 1] - address_y) ** 2,
        nan=np.inf,
    )

    best = pairs.loc[pairs.groupby("_coord")["_distance"].idxmin()]
    return best.sort_values("_coord", kind="stable")[id_column].to_numpy()


def nearest_building_cells(
    buildings: gpd.GeoDataFrame,
    extend_to: shapely.Geometry,
    *,
    addresses: gpd.GeoDataFrame | None = None,
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
        buildings: The building outlines, carrying ``id_column``. One outline may
            appear once per address that stands on it.
        extend_to: The ground the diagram has to reach over. Its bounding box,
            grown by ``densify_m``, is the frame the outer cells close against.
        addresses: The address points, used only to break the tie along an
            outline shared between several addresses. Without them a shared
            outline goes wholly to whichever address happens to be listed first.
        id_column: The address identifier each cell is labelled with.
        densify_m: The spacing of the points taken along each outline.

    Returns:
        One row per face of the diagram, carrying the ``id_column`` of the
        address whose building is nearest to it.
    """
    # Densified once per outline, not once per address on it. A shared outline
    # densified twice would contribute the same coordinates twice, and the
    # duplicate drop below would then take all of them away from one of its
    # addresses.
    unique = (
        buildings.drop_duplicates(subset=OUTLINE_ID_COLUMN)
        if OUTLINE_ID_COLUMN in buildings.columns
        else buildings
    )
    outlines = shapely.segmentize(unique.geometry.boundary.to_numpy(), densify_m)
    coords, source = shapely.get_coordinates(outlines, return_index=True)

    # A ring repeats its first coordinate at the end, and two buildings can
    # share a corner. Voronoi refuses a repeated generator, so duplicates are
    # dropped -- first occurrence kept, so the result does not depend on how
    # numpy happened to sort them.
    _, first = np.unique(coords, axis=0, return_index=True)
    keep = np.sort(first)
    coords, source = coords[keep], source[keep]

    if addresses is None or OUTLINE_ID_COLUMN not in buildings.columns:
        labels = unique[id_column].to_numpy()[source]
    else:
        labels = _label_by_nearest_address(
            coords,
            unique[OUTLINE_ID_COLUMN].to_numpy()[source],
            buildings,
            addresses,
            id_column,
        )

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
        {id_column: labels},
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
    addresses: gpd.GeoDataFrame | None = None,
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
        addresses: The address points. Needed only where one building serves
            several addresses, whose buffers are identical and so cannot be told
            apart by the outline they share.
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
        addresses=addresses,
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
    # Reindexed onto the cells rather than left to align itself, because an
    # address can now take no cells at all -- a unit whose address point
    # coincides with another on the same block -- and the two indexes then
    # differ. It keeps no land either way; this only says so deliberately.
    own_buffer = shared.set_index(id_column).geometry.reindex(merged_cells.index)
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

    Addresses sharing a location are collapsed to one property carrying a
    dwelling count, every building is attached to its nearest address point and
    shared with any further address standing on it, the outlines are buffered by
    ``buffer_m`` and merged per property, and ground shared between two
    properties goes to the nearer building, so the returned polygons do not
    overlap one another. The module docstring sets out what each of those steps
    costs, and records that driveways are not part of the extent this builds.

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
        One row per property that has a building, carrying ``id_column``,
        :data:`BUILDING_COUNT_COLUMN`, :data:`DWELLING_COUNT_COLUMN`,
        :data:`AREA_COLUMN` and the polygon, ordered by ``id_column``.
        Addresses with no building near them are absent rather than present with
        an empty geometry. Addresses sharing a location are represented by one
        row carrying their count, so they are absent as identifiers but present
        as dwellings.

    Raises:
        ValueError: If the two frames disagree on their coordinate reference
            system, if that system is geographic, or if the addresses carry no
            ``id_column``.
    """
    _check_frames(addresses, buildings, id_column)

    # Units of one block sit on one coordinate and cannot be separated, so they
    # become one property carrying a dwelling count rather than one property and
    # a queue of addresses holding nothing.
    addresses = collapse_coincident_addresses(addresses, id_column=id_column)

    attached = attach_buildings_to_addresses(
        buildings,
        addresses,
        id_column=id_column,
        max_distance_m=MAX_BUILDING_TO_ADDRESS_M,
    )
    if attached.empty:
        return gpd.GeoDataFrame(
            {
                id_column: [],
                BUILDING_COUNT_COLUMN: [],
                DWELLING_COUNT_COLUMN: [],
                AREA_COLUMN: [],
            },
            geometry=[],
            crs=addresses.crs,
        )

    parts = buffer_buildings(attached, buffer_m=buffer_m, id_column=id_column)
    if driveways is not None and not driveways.empty:
        parts = add_driveways(parts, driveways, id_column=id_column)
    parts = split_shared_ground(
        parts, attached, addresses=addresses, id_column=id_column
    )

    parts[AREA_COLUMN] = parts.geometry.area
    dwellings = addresses.set_index(id_column)[DWELLING_COUNT_COLUMN]
    parts[DWELLING_COUNT_COLUMN] = parts[id_column].map(dwellings).astype(int)

    columns = [
        id_column,
        BUILDING_COUNT_COLUMN,
        DWELLING_COUNT_COLUMN,
        AREA_COLUMN,
        parts.geometry.name,
    ]
    return parts[columns].sort_values(id_column, kind="stable").reset_index(drop=True)
