"""Whether the land under an address is flat or sloping, and why that matters.

Land loss behaves differently on the two. A flat site loses land to liquefaction,
lateral spreading and inundation; a sloping site loses it to slope failure, and
carries a different land value per square metre in the first place. Splitting the
exposure population on this one attribute is the cheapest cut that separates
those two stories, so it is the first attribute attached to an address.

The split is taken from the National Liquefaction Model's flatland layer rather
than rebuilt from a DEM. That is a deliberate reuse: the NLM is the model the
rest of the industry is working to, and rebuilding the same surface from scratch
would produce a second, differently-wrong answer to argue about.

Limitation L-16 in the project register records what that reuse costs. The NLM
flatland representation is simplified -- it is a national-scale flat-versus-
sloping generalisation, not a site-specific slope assessment -- and the team
accepted it as a sensible base model rather than an accurate one. Anything
downstream that is reported per landform class inherits that.

Phase 1 assigns only :data:`HILL` and :data:`FLAT`. :data:`ELEVATED_FLAT` -- flat
land raised above the surrounding floodplain, which is flat for shaking but not
exposed to inundation -- needs a DEM to separate from ordinary flat land, and
arrives in Phase 2. The class is declared here, and its factor sits in the land
value asset, so that the plumbing is already in place; nothing assigns it yet.
"""

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from landloss.domain import constants
from landloss.io.readers import get_koordinates_layer_extent

# The landform classes the exposure model recognises. Phase 1 assigns the first
# two only; see the module docstring for why the third is declared but unused.
LANDFORM_CLASSES = ("hill", "flat", "elevated_flat")

HILL = "hill"
FLAT = "flat"
ELEVATED_FLAT = "elevated_flat"

# The column ``classify_landform`` writes its answer into.
LANDFORM_COLUMN = "landform_class"


def classify_landform(
    addresses: gpd.GeoDataFrame, flatland: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Tag each address as sitting on flat land or on a hill.

    An address falling inside a flatland polygon is :data:`FLAT`; anything else
    is :data:`HILL`. There is no third answer in Phase 1 -- :data:`ELEVATED_FLAT`
    is declared but never assigned, because telling raised flat land apart from
    ordinary flat land needs the DEM, which is Phase 2 work.

    The join is deliberately ``within`` rather than ``intersects``: an address is
    a point, so the two agree except on a point lying exactly on a polygon edge,
    and a point on the boundary of the flat land is better treated as the hill it
    is about to climb than as flat.

    Kept separate from :func:`get_flatland` so that the classification can be
    exercised without reaching for the network.

    Args:
        addresses: Address points, in the same CRS as ``flatland``.
        flatland: The flat land polygons to test the addresses against. Only the
            geometry is used; any attributes on the layer are ignored.

    Returns:
        A new GeoDataFrame with a single :data:`LANDFORM_COLUMN` column added,
        holding one of :data:`LANDFORM_CLASSES` on every row, and re-indexed from
        zero. The caller's frame is left untouched.
    """
    # Re-indexed up front so that the spatial join's left index is unique, which
    # is what lets a match be collapsed back to a row without ambiguity.
    classified = addresses.copy().reset_index(drop=True)

    # Carry only the geometry across, so a column on the flatland layer cannot
    # collide with a column on the addresses and be silently renamed by the join.
    polygons = gpd.GeoDataFrame(geometry=flatland.geometry)

    # The join emits one row per address/polygon pair, so an address covered by
    # two overlapping flatland polygons appears twice. Reducing to the set of
    # matched left-hand labels is what keeps the result one row per address; the
    # question being asked is only "did it match anything", not "what did it
    # match".
    matches = classified.sjoin(polygons, how="inner", predicate="within")
    is_flat = classified.index.isin(matches.index)

    classified[LANDFORM_COLUMN] = HILL
    classified.loc[is_flat, LANDFORM_COLUMN] = FLAT

    return classified


def get_flatland(
    bbox: tuple[float, float, float, float] | None = None,
    crs: int | str = constants.DEFAULT_CRS,
    clip_to: gpd.GeoDataFrame | gpd.GeoSeries | BaseGeometry | None = None,
    *,
    use_cache: bool = True,
) -> gpd.GeoDataFrame:
    """Load the National Liquefaction Model flatland polygons for an extent.

    The layer is the NLM's flat-versus-sloping split, mirrored on the T+T
    Koordinates instance as layer
    :data:`landloss.domain.constants.NLM_FLATLAND_LAYER_ID`.

    The first call downloads a national layer and is slow -- minutes, not
    seconds. It is cached by ttpy afterwards, so the cost is paid once per
    machine, but a pilot extent is still the right way to exercise a script the
    first time.

    The representation is simplified. The NLM draws flat land at national scale,
    so a small terrace or a steep pocket inside a flat suburb is generalised
    away. The team accepted this as a sensible base model rather than an accurate
    one, and it is carried as limitation L-16 in the project register; results
    reported per landform class should be read with that in mind.

    Args:
        bbox: The extent to read (minx, miny, maxx, maxy) in ``crs``. Omitting it
            reads the whole national layer, which is rarely wanted.
        crs: The coordinate reference system to return the polygons in.
        clip_to: Optionally, a boundary to cut the polygons back to, in ``crs``.
            Anything ``geopandas.clip`` accepts. A bounding box is a rectangle
            and the study area is not, so pass this as well to cut the read back
            to the real boundary.
        use_cache: Whether to read and write the clipped extent cache.

    Returns:
        A GeoDataFrame of flat land polygons.
    """
    flatland = get_koordinates_layer_extent(
        layer=constants.NLM_FLATLAND_LAYER_ID,
        crs=crs,
        bbox=bbox,
        domain=constants.TTGROUP_DOMAIN,
        use_cache=use_cache,
    )

    if clip_to is not None:
        flatland = flatland.clip(clip_to)

    return flatland
