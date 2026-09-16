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
from shapely import box
from ttpy.gis.koop import KoordinatesConnection, get_latest_layer

from landloss.domain.constants import (
    API_KEY_ENV_VARS,
    DEFAULT_CRS,
    LINZ_DOMAIN,
    NZ_ADDRESSES_LAYER_ID,
    NZ_RIVER_NAME_LINES_LAYER_ID,
    TTGROUP_DOMAIN,
)

dotenv.load_dotenv()

DEFAULT_CACHE_DIR = Path(".koopcache")


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
    env_var = API_KEY_ENV_VARS.get(domain)
    if env_var is None:
        known = ", ".join(sorted(API_KEY_ENV_VARS))
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
    root = Path(os.environ.get("KOOPCACHE_DIR", DEFAULT_CACHE_DIR))
    cache_dir = root / "extents"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


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


def load_koordinates_layer_extent(
    layer: int | Path,
    crs: int | str = DEFAULT_CRS,
    bbox: tuple[float, float, float, float] | None = None,
    domain: str = TTGROUP_DOMAIN,
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
    crs: int | str = DEFAULT_CRS,
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
    return load_koordinates_layer_extent(
        layer=NZ_ADDRESSES_LAYER_ID,
        crs=crs,
        bbox=bbox,
        domain=LINZ_DOMAIN,
        use_cache=use_cache,
    )


def get_nz_river_name_lines(
    bbox: tuple[float, float, float, float] | None = None,
    crs: int | str = DEFAULT_CRS,
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
    return load_koordinates_layer_extent(
        layer=NZ_RIVER_NAME_LINES_LAYER_ID,
        crs=crs,
        bbox=bbox,
        domain=LINZ_DOMAIN,
        use_cache=use_cache,
    )
