"""Readers for the vector datasets the landloss models are built from.

Downloads are cached twice over. ttpy caches the whole downloaded layer, keyed by
layer ID, version and a hash of its details, so a layer is fetched from
Koordinates once. On top of that, this module caches the clipped extent, so
asking for the same extent of the same layer version a second time skips reading
and clipping the source.

Measured against the 809 MB NZ Addresses layer, that second cache saves little:
GeoPackage is spatially indexed, so pushing the bounding box down into the read
is already about as fast as reading a small cached copy back. The download is the
expensive step, and ttpy already caches it.

The extent cache only applies when a bounding box is given. Without one there is
no clip to skip, and caching would store a second full copy of a layer ttpy has
already cached.
"""

import hashlib
import os
from pathlib import Path

import dotenv
import geopandas as gpd
from shapely import box, make_valid
from ttpy.gis.koop import KoordinatesConnection, get_latest_layer

from landloss.domain import constants
from landloss.io import koopcache_dir

dotenv.load_dotenv()


def resolve_api_key(domain: str) -> str:
    """Return the API key for a Koordinates domain.

    Each domain has its own key, so the key is chosen by domain rather than read
    from a single variable.

    Args:
        domain: The Koordinates domain the key is needed for.

    Returns:
        The API key.

    Raises:
        ValueError: If the domain is unknown, or its variable is not set.
    """
    env_var = constants.API_KEY_ENV_VARS.get(domain)
    if env_var is None:
        known = ", ".join(sorted(constants.API_KEY_ENV_VARS))
        msg = (
            f"No API key variable is configured for {domain!r}. Known domains: {known}"
        )
        raise ValueError(msg)

    api_key = os.environ.get(env_var)
    if not api_key:
        msg = f"Set {env_var} in the .env file to read layers from {domain}."
        raise ValueError(msg)

    return api_key


def extent_cache_dir() -> Path:
    """Return the directory clipped extents are cached in, creating it if needed."""
    return koopcache_dir("extents")


def extent_cache_path(
    source: Path, crs: int | str, bbox: tuple[float, float, float, float] | None
) -> Path:
    """Return the cache file for one clipped extent of one layer.

    The source file name encodes the layer ID, its version and a hash of its
    details, so a cache entry cannot outlive the layer version it came from.

    Args:
        source: The file the extent was clipped out of.
        crs: The CRS the extent was reprojected to.
        bbox: The bounding box the extent was clipped to, if any.

    Returns:
        The path the clipped extent is cached at.
    """
    key = f"{source.name}|{crs}|{bbox}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return extent_cache_dir() / f"{source.stem}_{digest}.gpkg"


def get_koordinates_layer_extent(
    layer: int | Path,
    crs: int | str = constants.DEFAULT_CRS,
    bbox: tuple[float, float, float, float] | None = None,
    domain: str = constants.TTGROUP_DOMAIN,
    *,
    use_cache: bool = True,
) -> gpd.GeoDataFrame:
    """Load a Koordinates vector layer, reprojected and clipped to an extent.

    Args:
        layer: The Koordinates ID of the layer to download, or a path to a local
            file to read instead. An integer is treated as a layer ID.
        crs: The coordinate reference system to reproject the layer to.
        bbox: Optionally, clip to this bounding box (minx, miny, maxx, maxy),
            expressed in ``crs``. Geometries straddling the edge are cut at it.
        domain: The Koordinates domain to download from. Only used when ``layer``
            is a layer ID; the matching API key is chosen from it.
        use_cache: Whether to read and write the clipped extent cache. Pass False
            to force the clip to be recomputed from the source.

    Returns:
        A GeoDataFrame containing the layer, in ``crs`` and clipped to ``bbox``.

    Raises:
        ValueError: If a layer ID is given and no API key is set for ``domain``.
    """
    if isinstance(layer, int):
        conn = KoordinatesConnection(api_key=resolve_api_key(domain), domain=domain)
        try:
            layer_path = get_latest_layer(conn=conn, layer_id=layer)
        finally:
            conn.close()
    else:
        layer_path = Path(layer)

    # Only an actual clip is worth caching. Without a bbox the cache would hold a
    # full duplicate of a layer ttpy has already cached — gigabytes, for a
    # national layer — to save only the reprojection, which measured slower than
    # reading the duplicate back.
    cache_wanted = use_cache and bbox is not None

    cache_path = extent_cache_path(layer_path, crs, bbox)
    if cache_wanted and cache_path.exists():
        return gpd.read_file(cache_path)

    layer_gdf = _read_extent(layer_path, crs, bbox)

    # An empty frame has no geometry type for the driver to write, so there is
    # nothing worth caching; recomputing an empty result is cheap anyway.
    if cache_wanted and not layer_gdf.empty:
        layer_gdf.to_file(cache_path)

    return layer_gdf


def _read_extent(
    layer_path: Path, crs: int | str, bbox: tuple[float, float, float, float] | None
) -> gpd.GeoDataFrame:
    """Read a layer from disk, reprojecting and clipping it to an extent."""
    if bbox is None:
        return gpd.read_file(layer_path).to_crs(crs)

    minx, miny, maxx, maxy = bbox

    # Push the bounding box down into the read so that a national layer is never
    # loaded whole. Passing a GeoSeries lets geopandas transform it into the
    # source CRS, which we do not otherwise need to know.
    bbox_filter = gpd.GeoSeries([box(minx, miny, maxx, maxy)], crs=crs)
    layer_gdf: gpd.GeoDataFrame = gpd.read_file(layer_path, bbox=bbox_filter)

    # Reproject before the final clip so the box is applied in the CRS asked for
    # rather than whatever the layer happened to be published in.
    layer_gdf = layer_gdf.to_crs(crs)

    # Cut the geometries at the bounding box; the read filter above is only a
    # coarse intersection test.
    return layer_gdf.clip(box(minx, miny, maxx, maxy))


def get_nz_addresses(
    bbox: tuple[float, float, float, float] | None = None,
    crs: int | str = constants.DEFAULT_CRS,
    *,
    use_cache: bool = True,
) -> gpd.GeoDataFrame:
    """Load the LINZ NZ Addresses layer for an extent.

    This is the address point layer at
    https://data.linz.govt.nz/layer/123113-nz-addresses/, used as the starting
    point for the exposure model.

    The layer covers the whole country, so passing a bounding box is strongly
    preferred; the first call for a given extent downloads and clips the layer,
    and later calls for the same extent are served from the cache.

    Args:
        bbox: The extent to clip to (minx, miny, maxx, maxy) in ``crs``. Omitting
            it returns every address in New Zealand.
        crs: The coordinate reference system to return the addresses in.
        use_cache: Whether to read and write the clipped extent cache.

    Returns:
        A GeoDataFrame of address points.
    """
    return get_koordinates_layer_extent(
        layer=constants.NZ_ADDRESSES_LAYER_ID,
        crs=crs,
        bbox=bbox,
        domain=constants.LINZ_DOMAIN,
        use_cache=use_cache,
    )


def get_nz_building_outlines(
    bbox: tuple[float, float, float, float] | None = None,
    crs: int | str = constants.DEFAULT_CRS,
    *,
    use_cache: bool = True,
) -> gpd.GeoDataFrame:
    """Load the LINZ NZ Building Outlines layer for an extent.

    The building footprint layer at
    https://data.linz.govt.nz/layer/101290-nz-building-outlines/, captured from
    aerial imagery. The insured land extent is buffered off these outlines,
    because NHC land cover attaches to the ground around the dwelling rather
    than to the whole parcel, so the building is what the extent is measured
    from.

    Each outline carries a ``building_id``, a ``use``, the suburb, town and
    territorial authority it sits in, and the capture source and date it was
    digitised from. Nothing distinguishes a dwelling from a garage or a shed, so
    an extent built from the layer covers every structure on a property.

    Licence:
        Creative Commons Attribution 4.0 International (CC BY 4.0),
        https://data.linz.govt.nz/license/attribution-4-0-international/. The
        data may be shared and adapted, including commercially, provided Land
        Information New Zealand is credited as the source, a link to the licence
        is given, and any changes made are indicated. So every figure, table or
        layer published from the insured land extent -- which is derived from
        these outlines -- has to carry that attribution with it.

    Source:
        Land Information New Zealand, National Topographic Office. No DOI is
        published for the layer.

    The layer covers the whole country at 3.2 million buildings, so passing a
    bounding box is strongly preferred; the first call for a given extent
    downloads and clips the layer, and later calls for the same extent are
    served from the cache.

    Args:
        bbox: The extent to clip to (minx, miny, maxx, maxy) in ``crs``. Omitting
            it returns every building outline in New Zealand.
        crs: The coordinate reference system to return the outlines in.
        use_cache: Whether to read and write the clipped extent cache.

    Returns:
        A GeoDataFrame of building footprint polygons.
    """
    return get_koordinates_layer_extent(
        layer=constants.NZ_BUILDING_OUTLINES_LAYER_ID,
        crs=crs,
        bbox=bbox,
        domain=constants.LINZ_DOMAIN,
        use_cache=use_cache,
    )


def get_nz_river_name_lines(
    bbox: tuple[float, float, float, float] | None = None,
    crs: int | str = constants.DEFAULT_CRS,
    *,
    use_cache: bool = True,
) -> gpd.GeoDataFrame:
    """Load the LINZ NZ River Name Lines layer for an extent.

    This is the named watercourse centreline layer at
    https://data.linz.govt.nz/layer/103632-nz-river-name-lines-pilot/. Unlike the
    topo50 river centrelines it carries a ``name`` and a ``feat_type`` per
    feature, which is what allows the major named rivers to be separated from the
    streams and creeks.

    The layer covers the whole country, so passing a bounding box is strongly
    preferred; the first call for a given extent downloads and clips the layer,
    and later calls for the same extent are served from the cache.

    Args:
        bbox: The extent to clip to (minx, miny, maxx, maxy) in ``crs``. Omitting
            it returns every river name line in New Zealand.
        crs: The coordinate reference system to return the lines in.
        use_cache: Whether to read and write the clipped extent cache.

    Returns:
        A GeoDataFrame of watercourse centrelines.
    """
    return get_koordinates_layer_extent(
        layer=constants.NZ_RIVER_NAME_LINES_LAYER_ID,
        crs=crs,
        bbox=bbox,
        domain=constants.LINZ_DOMAIN,
        use_cache=use_cache,
    )


def get_gwrc_slope_failure(
    bbox: tuple[float, float, float, float] | None = None,
    crs: int | str = constants.DEFAULT_CRS,
    *,
    use_cache: bool = True,
) -> gpd.GeoDataFrame:
    """Load Greater Wellington's earthquake-induced slope failure zones.

    Source
    ------
    "Wellington Region Earthquake Induced Slope Failure", published by Greater
    Wellington Regional Council on the public Koordinates catalogue as layer
    4069:
    https://koordinates.com/layer/4069-wellington-region-earthquake-induced-slope-failure/

    The catalogue describes it as "Earthquake induced slope failure
    susceptibility zones for the Wellington Region. This dataset is compiled from
    the 'slope failure series' ArcInfo coverages. Refer to Publication
    WRC/PP-T-95/06 for accompanying notes." Those notes are Kingsbury (1995),
    which derived five susceptibility zones from slope angle and slope
    modification, and which excluded failures caused by liquefaction. The
    underlying mapping is therefore 1995 regional-scale work, published to
    Koordinates in 2012 — a qualitative zonation rather than a rate, and no
    substitute for site assessment.

    4,682 polygons covering the Wellington region in NZGD2000 / NZTM
    (EPSG:2193). Licensed Creative Commons Attribution-No Derivative Works 3.0,
    so reproducing it requires attribution to Greater Wellington, and publishing
    a modified version may require their permission.

    Reading it needs ``KOORDINATES_PUBLIC_API_KEY``; the T+T and LINZ keys do not
    work on this domain. The same data is also mirrored on a public ArcGIS
    FeatureServer that needs no key, which is a fallback if the Koordinates
    export stalls:
    https://services5.arcgis.com/n4qyP7iVOnJlCVth/arcgis/rest/services/WR_SlopeFailure/FeatureServer/0

    Notes:
    -----
    Two quirks of the source are corrected here. ``SEVERITY`` is a string whose
    labels are inconsistent — ``1 Low``, ``2``, ``3 Moderate``, ``4``,
    ``5 High`` — so a ``severity_rank`` integer is added for sorting and
    colouring. A minority of the polygons are invalid, which breaks clipping and
    overlays, so geometries are repaired on the way through.

    Args:
        bbox: The extent to clip to (minx, miny, maxx, maxy) in ``crs``. Omitting
            it returns the whole region.
        crs: The coordinate reference system to return the zones in.
        use_cache: Whether to read and write the clipped extent cache.

    Returns:
        A GeoDataFrame of susceptibility polygons carrying the original
        ``SEVERITY`` and ``LSKEY``, plus a ``severity_rank`` of 1 (low) to 5
        (high).

    Raises:
        ValueError: If a ``SEVERITY`` value is not one of the five known classes,
            which would mean the source has changed.
    """
    zones = get_koordinates_layer_extent(
        layer=constants.GWRC_SLOPE_FAILURE_LAYER_ID,
        crs=crs,
        bbox=bbox,
        domain=constants.KOORDINATES_PUBLIC_DOMAIN,
        use_cache=use_cache,
    )

    if zones.empty:
        return zones

    unknown = set(zones["SEVERITY"]) - set(constants.GWRC_SEVERITY_RANKS)
    if unknown:
        known = ", ".join(repr(value) for value in constants.GWRC_SEVERITY_RANKS)
        msg = (
            f"Unrecognised SEVERITY values in layer "
            f"{constants.GWRC_SLOPE_FAILURE_LAYER_ID}: "
            f"{', '.join(repr(value) for value in sorted(unknown))}. Known: {known}"
        )
        raise ValueError(msg)

    zones = zones.copy()
    zones["severity_rank"] = zones["SEVERITY"].map(constants.GWRC_SEVERITY_RANKS)

    # A minority of the source polygons are self-intersecting, which makes any
    # later clip or overlay fail. Repairing only the broken ones leaves the rest
    # bit-identical to the source.
    invalid = ~zones.geometry.is_valid
    if invalid.any():
        zones.loc[invalid, "geometry"] = zones.loc[invalid, "geometry"].apply(
            make_valid
        )

    return zones


def get_nz_land_cover(
    bbox: tuple[float, float, float, float] | None = None,
    crs: int | str = constants.DEFAULT_CRS,
    *,
    use_cache: bool = True,
) -> gpd.GeoDataFrame:
    """Load the LCDB v6.0 land cover polygons for an extent.

    The New Zealand Land Cover Database, version 6.0 (mainland), at
    https://lris.scinfo.org.nz/layer/123148-lcdb-v60-land-cover-database-version-60-mainland-new-zealand/.
    Each polygon carries a land cover class and name at six time steps -- summer
    1996/97, 2001/02, 2007/08, 2012/13, 2018/19 and 2023/24 -- in the paired
    ``Class_<year>`` and ``Name_<year>`` columns, so change over time is read
    across the columns of one feature rather than by joining separate layers.
    ``Wetland_<yy>`` and ``Onshore_<yy>`` flag wetland and coastal change.

    Licence:
        Creative Commons Attribution 4.0 International (CC BY 4.0),
        https://creativecommons.org/licenses/by/4.0/. The data may be shared and
        adapted, including commercially, provided Landcare Research is credited
        as the source, a link to the licence is given, and any changes made are
        indicated. Anything derived from this layer and published -- a figure in
        the report, a table, a layer handed to NHC -- therefore needs that
        attribution carried with it.

    Source:
        Landcare Research, via the LRIS portal. Cite as
        https://doi.org/10.26060/WM99-RY32.

    The layer covers the whole mainland (542,789 polygons), so passing a
    bounding box is strongly preferred; the first call for a given extent
    downloads and clips the layer, and later calls for the same extent are
    served from the cache.

    Args:
        bbox: The extent to clip to (minx, miny, maxx, maxy) in ``crs``. Omitting
            it returns land cover for the whole mainland.
        crs: The coordinate reference system to return the polygons in.
        use_cache: Whether to read and write the clipped extent cache.

    Returns:
        A GeoDataFrame of land cover polygons.

    Raises:
        ValueError: If LRIS_API_KEY is not set. LRIS is a separate Koordinates
            instance from LINZ and T+T's, with its own account and key.
    """
    return get_koordinates_layer_extent(
        layer=constants.NZ_LCDB_V60_LAYER_ID,
        crs=crs,
        bbox=bbox,
        domain=constants.LRIS_DOMAIN,
        use_cache=use_cache,
    )


def dem_cache_path(
    bbox: tuple[float, float, float, float], resolution: int, crs: int | str
) -> Path:
    """Return the file one fetched DEM extent is cached at.

    Args:
        bbox: The extent the DEM covers (minx, miny, maxx, maxy) in ``crs``.
        resolution: The cell size in metres.
        crs: The coordinate reference system the DEM is in.

    Returns:
        The path the DEM is cached at, inside the Koordinates cache directory so
        that everything downloaded for this study sits under one root.
    """
    key = f"{bbox}|{resolution}|{crs}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return koopcache_dir("dem") / f"dem_{resolution}m_{digest}.tif"


def get_dem(
    bbox: tuple[float, float, float, float],
    resolution: int = constants.DEM_RESOLUTION_M,
    crs: int | str = constants.DEFAULT_CRS,
    *,
    use_cache: bool = True,
) -> Path:
    """Fetch the LINZ elevation model for an extent and return the file it is in.

    LINZ does not publish a DEM as a Koordinates layer -- only hillshades -- so
    this is the one dataset in the study that does not come through
    :func:`get_koordinates_layer_extent`. Elevation is served from LINZ's STAC
    catalogue instead, which ``linz_stac_utils`` reads: LiDAR where it has been
    flown, falling back to the 8 m contour-derived model where it has not. That
    is the same route the National Liquefaction Model takes, so the two studies
    stand on the same elevation data.

    A path is returned rather than an array because the sampling helper this
    study uses, ``ttpy.gis.raster.utils.extract_point_values``, reads from a
    file, and because a fetched DEM is worth keeping: the pilot extent alone
    takes over a minute to assemble from the source tiles.

    Carries limitation L-12: the LiDAR is a merge of surveys flown in different
    years across the study area -- Wellington in 2023, Hutt City in 2025, Porirua
    unknown -- so a slope derived from it is not of uniform vintage, and a
    difference across a survey boundary may be an artefact rather than a
    landform.

    Args:
        bbox: The extent to fetch (minx, miny, maxx, maxy), in ``crs``.
        resolution: The cell size in metres. The default is the study's working
            resolution; see :data:`landloss.domain.constants.DEM_RESOLUTION_M`
            for why it is not the native 1 m.
        crs: The coordinate reference system to return the DEM in.
        use_cache: Whether to reuse an already-fetched DEM for the same extent,
            resolution and CRS. Pass False to re-fetch.

    Returns:
        The path to the DEM, as a GeoTIFF.
    """
    # Imported here rather than at module scope because assembling the STAC
    # client is slow and every other reader in this module is a vector reader
    # that never needs it.
    from linz_stac_utils.elevation import load_elevation  # noqa: PLC0415

    cache_path = dem_cache_path(bbox, resolution, crs)
    if use_cache and cache_path.exists():
        return cache_path

    # load_elevation takes its bounding box in WGS84, whatever CRS it is asked to
    # return, so the extent is converted rather than passed through.
    minx, miny, maxx, maxy = bbox
    wgs84_bounds = (
        gpd.GeoSeries([box(minx, miny, maxx, maxy)], crs=crs)
        .to_crs("EPSG:4326")
        .total_bounds
    )

    load_elevation(
        bbox=tuple(float(value) for value in wgs84_bounds),
        resolution=resolution,
        crs=crs,
        output_path=cache_path,
        overwrite=True,
    )
    return cache_path
