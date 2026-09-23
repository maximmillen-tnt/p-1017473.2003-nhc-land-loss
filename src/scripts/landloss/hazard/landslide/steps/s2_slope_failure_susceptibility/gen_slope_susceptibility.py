"""Score earthquake-induced slope failure susceptibility on Kingsbury's scheme.

Greater Wellington's published slope failure layer is CC BY-ND, so nothing may
be derived from it. This rebuilds the scheme behind it -- Kingsbury (1995),
WRC/PP-T-95/06 to /10 -- from its own inputs, so the result is ours to use:

    uv run --frozen python src/scripts/landloss/hazard/landslide/steps/s2_slope_failure_susceptibility/gen_slope_susceptibility.py

What it runs over, and with what settings, comes from ``config.py`` beside it,
read at the bottom of this file and passed into :func:`main`. Change it there
rather than passing flags, so that what a run did can be read off the source.

Needs ``LINZ_API_KEY`` for the elevation model and ``TNT_KOORDINATES_API_KEY``
for the earthworks records, both in ``.env``.

The rating is a weighted sum of six factors, each scored 0 to 10::

    Rs = 4*F_slope + 4*F_modification + 2*F_height + 2*F_geology
         + 2*F_landslides + 1*F_groundwater

and bands into five zones at 20, 60, 100 and 140. The scoring lives in
``landloss.hazard.landslide.susceptibility``; this script supplies the inputs.

Three of the six are constants set in ``config.py`` rather than mapped, and one
of the three matters more than it looks. **The landslide factor is zero
everywhere**, because no inventory is held -- that is the honest value, not a
statement that there are no landslides, and it removes up to 20 of the 150
points. Geology and groundwater are fixed at the values Kingsbury used in his
own worked examples, so they shift every cell equally and change no ranking.

The two that are mapped are read at two different resolutions, and that is
deliberate rather than an optimisation:

- **Slope angle** comes off the elevation model at the coarse working
  resolution, because Kingsbury's class boundaries were calibrated against a
  terrain model built from 20 m contours and Horn's kernel at 10 m measures
  gradient over about the same length.
- **Cut angle and face height** come off the elevation model at the fine
  resolution, inside the mapped earthworks polygons only. A subdivision cut face
  is one coarse cell wide and averages away to a gentle slope; at the fine
  resolution it resolves. Kingsbury split the scales the same way -- slope at
  1:25,000, cut slopes at 1:10,000 to 1:20,000 in urban areas.

The fine factors are then aggregated onto the coarse grid by **maximum**, which
is the source's own rule: "if a slope contains an extremely steep component,
then that will generally control the stability of the entire slope".

What this does not do is reproduce the 1995 *map*. That was generalised
polygons drawn under the rules in section 4.4.2 of the booklets -- steep facets
expanded to the whole slope, a runout allowance added, every modified slope
forced into the high or very high zone. None of those is applied here, so this
grid is systematically less severe than the published layer. See the
implementation plan beside this file, and
``.agents/plans/rebuilding-gwrc-slope-failure-susceptibility.md``.
"""

import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rioxarray
import xarray as xr
from rasterio.enums import Resampling
from rasterio.features import rasterize

from landloss.common.utils.terrain import (
    cell_size,
    local_relief,
    slope_degrees,
    window_in_cells,
    write_raster,
)
from landloss.domain import constants
from landloss.hazard.landslide import susceptibility
from landloss.io.area_of_interest import WLG_EARTHWORKS_PILOT, get_study_areas
from landloss.io.readers import get_dem, get_wcc_cut_areas, get_wcc_fill_areas
from scripts.landloss.hazard.landslide.steps.s2_slope_failure_susceptibility import (
    config,
)
from scripts.landloss.paths import TEMP_DIR

# Wellington place names are macronised, which the default cp1252 Windows
# console cannot encode.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# temp/ is gitignored. These are working layers, rebuildable from the elevation
# model and the earthworks records, so they have no business in a diff.
WORK_DIR = TEMP_DIR / "hazard" / "landslide"

RATING_STEM = "slope-susceptibility-rating"
ZONE_STEM = "slope-susceptibility-zone"

RULE = "-" * 72


def rating_path(*, pilot):
    """Return the file a run writes the susceptibility rating to."""
    suffix = "-pilot" if pilot else ""
    return WORK_DIR / f"{RATING_STEM}{suffix}.tif"


def zone_path(*, pilot):
    """Return the file a run writes the banded susceptibility zone to."""
    suffix = "-pilot" if pilot else ""
    return WORK_DIR / f"{ZONE_STEM}{suffix}.tif"


def earthworks_extent(earthworks, study_areas):
    """Return the extent the earthworks records actually cover.

    The full run goes over this rather than over the four territorial
    authorities, because the modification factor is only scoreable where a cut
    or fill has been mapped, and that is Wellington City's hill suburbs alone.

    Args:
        earthworks: The mapped cut and fill polygons.
        study_areas: The four territorial authorities, used to trim the one
            stray polygon that crosses out of Wellington City.

    Returns:
        ``(west, south, east, north)`` in the study's own projection.
    """
    inside = earthworks.clip(study_areas.union_all())
    return tuple(float(value) for value in inside.total_bounds)


def resolve_extent(earthworks, study_areas, *, pilot):
    """Choose the extent to run over, and say which one it is.

    Args:
        earthworks: The mapped cut and fill polygons.
        study_areas: The four territorial authorities.
        pilot: Whether to use the Johnsonville and Newlands pilot box instead of
            the whole earthworks extent.

    Returns:
        ``(bbox, name)``: the extent in the study's own projection, and a label
        for the run output.
    """
    if pilot:
        return WLG_EARTHWORKS_PILOT.bbox(constants.DEFAULT_CRS), (
            WLG_EARTHWORKS_PILOT.name
        )

    return earthworks_extent(earthworks, study_areas), (
        "the Wellington City earthworks extent"
    )


def read_earthworks(bbox=None):
    """Read the mapped cut and fill areas as one frame, labelled by kind.

    Read together because the two are scored by the same factor and differ only
    in how: a cut is scored on the angle of its face, a sidling fill at the top
    of the scale whatever its angle, because the failure is on the contact the
    fill was placed on.

    Args:
        bbox: The extent to clip to, or None for everything mapped.

    Returns:
        A GeoDataFrame carrying a ``kind`` column of "cut" or "fill".
    """
    cut = get_wcc_cut_areas(bbox=bbox).assign(kind="cut")
    fill = get_wcc_fill_areas(bbox=bbox).assign(kind="fill")

    both = pd.concat([cut, fill], ignore_index=True)
    return gpd.GeoDataFrame(both, geometry="geometry", crs=cut.crs)


def buffer_cells(*, fine_resolution_m, slope_height_window_m):
    """Return how many fine cells to fetch beyond the extent.

    The rolling window that measures face height has no complete neighbourhood
    within half a window of the edge, and a coarse cell straddling the boundary
    needs its fine cells too. Fetching the ring and trimming it afterwards is
    what keeps the edge of the run from coming back as nodata.

    Args:
        fine_resolution_m: The fine cell size in metres.
        slope_height_window_m: The width of the face height window in metres.

    Returns:
        The number of fine cells to add on every side.
    """
    window = window_in_cells(slope_height_window_m, fine_resolution_m)
    return window // 2 + 1


def fetch_dem(bbox, *, fine_resolution_m, padding_m, use_cache):
    """Fetch the elevation model over an extent plus a working margin.

    Args:
        bbox: The extent to cover, in the study's own projection.
        fine_resolution_m: The cell size to fetch at, in metres.
        padding_m: How far beyond the extent to fetch, in metres.
        use_cache: Whether to reuse an already-fetched model for this extent.

    Returns:
        The elevation model, loaded, oriented (y, x) and carrying NaN nodata.
    """
    west, south, east, north = bbox
    padded = (west - padding_m, south - padding_m, east + padding_m, north + padding_m)

    print(
        f"Fetching the elevation model at {fine_resolution_m:g} m over the extent "
        f"plus {padding_m:g} m ...",
        flush=True,
    )
    dem_path = get_dem(
        padded,
        resolution=fine_resolution_m,
        crs=constants.DEFAULT_CRS,
        use_cache=use_cache,
    )
    print(f"  {dem_path}")

    # Read through a context manager and load into memory, so that no lazily
    # opened GDAL handle is left to be finalised during interpreter shutdown.
    with rioxarray.open_rasterio(dem_path, masked=True) as opened:
        dem = opened.squeeze(drop=True).load()

    return dem.rio.write_nodata(np.nan)


def rasterise(polygons, template, value):
    """Burn a constant onto a template grid wherever a polygon covers it.

    Args:
        polygons: The geometries to burn.
        template: The grid to burn onto, used for its transform and shape.
        value: What to write inside the polygons.

    Returns:
        An array on ``template``'s grid, ``value`` inside and 0 outside.
    """
    if polygons.empty:
        return np.zeros(template.shape, dtype=float)

    return rasterize(
        ((geometry, value) for geometry in polygons.geometry),
        out_shape=template.shape,
        transform=template.rio.transform(),
        fill=0.0,
        dtype="float64",
    )


def modification_factor(earthworks, fine_slope):
    """Score the slope modification factor on the fine grid.

    A cut is scored on how steep its face stands; a sidling fill is scored at
    the top of the scale whatever its angle. Where a cut and a fill polygon
    overlap -- which happens, because a subdivision cuts one part of a site to
    fill another -- the higher of the two wins, following the source's rule that
    the steepest component controls the slope.

    Args:
        earthworks: The mapped polygons, carrying a ``kind`` column.
        fine_slope: Slope in degrees on the fine grid.

    Returns:
        The factor value on the fine grid, 0 outside every mapped polygon.
    """
    cut_score = susceptibility.cut_angle_value(fine_slope.to_numpy())
    cut_score = np.nan_to_num(cut_score)

    in_cut = rasterise(earthworks.loc[earthworks["kind"] == "cut"], fine_slope, 1.0)
    in_fill = rasterise(earthworks.loc[earthworks["kind"] == "fill"], fine_slope, 1.0)

    scored = np.maximum(
        np.where(in_cut > 0, cut_score, 0.0),
        np.where(in_fill > 0, susceptibility.SIDLING_FILL_VALUE, 0.0),
    )
    return _as_grid(scored, fine_slope, "modification_value")


def height_factor(dem, fine_slope, *, fine_resolution_m, slope_height_window_m):
    """Score the slope height factor on the fine grid.

    The height of a steep face is taken as the elevation range in a moving
    window, which is a proxy for a measured toe-to-crest height rather than the
    thing itself. The factor is only scored where the face is steeper than the
    angle Kingsbury restricts it to; see
    :func:`landloss.hazard.landslide.susceptibility.slope_height_value`.

    Args:
        dem: The elevation model on the fine grid.
        fine_slope: Slope in degrees on the same grid.
        fine_resolution_m: The fine cell size in metres.
        slope_height_window_m: The width of the window in metres.

    Returns:
        The factor value on the fine grid.
    """
    relief = local_relief(dem, fine_resolution_m, slope_height_window_m)
    scored = susceptibility.slope_height_value(relief.to_numpy(), fine_slope.to_numpy())
    return _as_grid(scored, fine_slope, "height_value")


def _as_grid(values, template, name):
    """Wrap an array back onto a template's coordinates and spatial reference."""
    grid = xr.DataArray(values, coords=template.coords, dims=template.dims, name=name)
    return grid.rio.write_crs(template.rio.crs).rio.write_nodata(np.nan)


def coarse_template(dem, *, coarse_resolution_m):
    """Resample the fine elevation model down to the reporting resolution.

    Averaging rather than sampling, because a coarse cell stands for all the
    ground inside it and nearest neighbour would hand back whichever fine cell
    happened to fall on the centre.

    Args:
        dem: The elevation model on the fine grid.
        coarse_resolution_m: The cell size to resample to, in metres.

    Returns:
        The elevation model on the coarse grid.
    """
    return dem.rio.reproject(
        dem.rio.crs,
        resolution=coarse_resolution_m,
        resampling=Resampling.average,
    )


def to_coarse_maximum(fine, template):
    """Aggregate a fine factor grid onto the coarse grid, taking the maximum.

    The maximum rather than the mean, because Kingsbury's section 4.4.2 says a
    steep component controls the stability of the whole slope it sits on. It
    does mean one steep fine cell lifts its whole coarse cell, which is the
    behaviour the source describes.

    Args:
        fine: The factor grid at the fine resolution.
        template: The coarse grid to match.

    Returns:
        The factor grid on ``template``'s cells.
    """
    return fine.rio.reproject_match(template, resampling=Resampling.max)


def trim_to_extent(grid, bbox):
    """Clip a grid back to the extent asked for, dropping the working margin."""
    west, south, east, north = bbox
    return grid.rio.clip_box(minx=west, miny=south, maxx=east, maxy=north)


def describe_extent(name, bbox, earthworks):
    """Print what the run covers and how much of it carries mapped earthworks."""
    west, south, east, north = bbox

    print(RULE)
    print(f"Extent: {name}")
    print(f"  {west:,.0f}-{east:,.0f} E, {south:,.0f}-{north:,.0f} N (NZTM)")
    print(f"  {(east - west) / 1000:.1f} by {(north - south) / 1000:.1f} km")

    counts = earthworks["kind"].value_counts()
    areas = earthworks.groupby("kind").apply(
        lambda frame: frame.area.sum() / 1e6, include_groups=False
    )
    for kind in ("cut", "fill"):
        print(
            f"  {kind + ' areas':<12} {counts.get(kind, 0):>4,} polygons, "
            f"{areas.get(kind, 0.0):>6.2f} km2"
        )


def describe_constants(*, geology_value, landslide_value, groundwater_value):
    """Print the three factors supplied as constants and what they contribute."""
    baseline = susceptibility.susceptibility_rating(
        slope=np.zeros(1),
        modification=np.zeros(1),
        height=np.zeros(1),
        geology=np.full(1, geology_value),
        landslides=np.full(1, landslide_value),
        groundwater=np.full(1, groundwater_value),
    )[0]

    print(RULE)
    print("Factors supplied as constants rather than mapped:")
    print(
        f"  geology      F = {geology_value:>4.0f}  weighted {geology_value * 2:>4.0f}"
    )
    print(
        f"  landslides   F = {landslide_value:>4.0f}  weighted "
        f"{landslide_value * 2:>4.0f}   (no inventory held)"
    )
    print(
        f"  groundwater  F = {groundwater_value:>4.0f}  weighted "
        f"{groundwater_value * 1:>4.0f}"
    )
    print(
        f"  every cell therefore starts at {baseline:.0f} of "
        f"{susceptibility.MAX_RATING}"
    )

    # A baseline above the first band means no cell can land in it, whatever the
    # terrain does. That is a consequence of holding three factors constant, not
    # a reading of the ground, and it shows up as flat land coming back one zone
    # more severe than the published map puts it.
    lowest_band = susceptibility.ZONE_BREAKS[0]
    if baseline >= lowest_band:
        unreachable = susceptibility.ZONE_LABELS[susceptibility.ZONE_RANKS[0]]
        print(
            f"  which is above the {lowest_band:.0f} point band, so the "
            f"'{unreachable.lower()}' zone is unreachable:"
        )
        print("  flat ground scores one zone more severe than the published map.")


def describe_zones(zone, resolution):
    """Print how much ground falls in each susceptibility zone."""
    values = zone.to_numpy()
    scored = np.isfinite(values)
    cell_area_km2 = resolution**2 / 1e6

    print(RULE)
    print("Rebuilt susceptibility zones:")
    total = scored.sum()
    for rank in susceptibility.ZONE_RANKS:
        cells = int((values == rank).sum())
        share = cells / total if total else 0.0
        label = susceptibility.ZONE_LABELS[rank]
        print(f"  {rank} {label:<10} {cells * cell_area_km2:>7.2f} km2  {share:>6.1%}")
    print(f"  {'scored':<12} {total * cell_area_km2:>7.2f} km2")


def describe_modification(modification, resolution):
    """Print how much of the extent the modification factor actually reaches.

    Worth printing on every run: everywhere it does not reach scores zero, and
    under this scheme zero modification means a cell cannot reach the high or
    very high zone on modification at all. A rebuilt map that looks tame is
    usually saying this rather than saying the ground is safe.
    """
    values = modification.to_numpy()
    scored = np.isfinite(values)
    reached = scored & (values > 0)
    cell_area_km2 = resolution**2 / 1e6

    print(RULE)
    share = reached.sum() / scored.sum() if scored.sum() else 0.0
    print(
        f"Slope modification scores above zero over "
        f"{reached.sum() * cell_area_km2:.2f} km2, {share:.1%} of the extent."
    )
    print("  The rest scores nil, which is an absence of records, not of earthworks.")


def main(
    *,
    pilot,
    coarse_resolution_m,
    fine_resolution_m,
    slope_height_window_m,
    geology_value,
    landslide_value,
    groundwater_value,
    use_cached_dem,
):
    """Score slope failure susceptibility over the extent and write it out.

    Args:
        pilot: Whether to run over the Johnsonville and Newlands pilot box
            rather than the whole Wellington City earthworks extent.
        coarse_resolution_m: The cell size the rating is reported on.
        fine_resolution_m: The cell size the cut angle and face height are
            measured at.
        slope_height_window_m: The neighbourhood the face height is measured
            over.
        geology_value: The geology factor, held constant.
        landslide_value: The existing landslides factor, held constant.
        groundwater_value: The groundwater factor, held constant.
        use_cached_dem: Whether to reuse an already-fetched elevation model.
    """
    study_areas = get_study_areas(constants.DEFAULT_CRS)

    print("Reading the Wellington City earthworks records ...", flush=True)
    all_earthworks = read_earthworks()
    bbox, extent_name = resolve_extent(all_earthworks, study_areas, pilot=pilot)
    earthworks = read_earthworks(bbox=bbox)

    describe_extent(extent_name, bbox, earthworks)
    describe_constants(
        geology_value=geology_value,
        landslide_value=landslide_value,
        groundwater_value=groundwater_value,
    )

    padding_m = (
        buffer_cells(
            fine_resolution_m=fine_resolution_m,
            slope_height_window_m=slope_height_window_m,
        )
        * fine_resolution_m
    )
    dem = fetch_dem(
        bbox,
        fine_resolution_m=fine_resolution_m,
        padding_m=padding_m,
        use_cache=use_cached_dem,
    )

    print("Scoring the fine factors -- cut angle and face height ...", flush=True)
    fine_slope = slope_degrees(dem, cell_size(dem))
    modification = modification_factor(earthworks, fine_slope)
    height = height_factor(
        dem,
        fine_slope,
        fine_resolution_m=fine_resolution_m,
        slope_height_window_m=slope_height_window_m,
    )

    print(
        f"Scoring the slope factor at {coarse_resolution_m:g} m and aggregating "
        "the fine factors up to it ...",
        flush=True,
    )
    coarse_dem = coarse_template(dem, coarse_resolution_m=coarse_resolution_m)
    coarse_slope = slope_degrees(coarse_dem, cell_size(coarse_dem))
    slope_value = _as_grid(
        susceptibility.slope_angle_value(coarse_slope.to_numpy()),
        coarse_slope,
        "slope_value",
    )

    modification = to_coarse_maximum(modification, slope_value)
    height = to_coarse_maximum(height, slope_value)

    rating = susceptibility.susceptibility_rating(
        slope=slope_value.to_numpy(),
        modification=modification.to_numpy(),
        height=height.to_numpy(),
        geology=np.full(slope_value.shape, geology_value),
        landslides=np.full(slope_value.shape, landslide_value),
        groundwater=np.full(slope_value.shape, groundwater_value),
    )
    rating = _as_grid(rating, slope_value, "susceptibility_rating")
    zone = _as_grid(
        susceptibility.susceptibility_zone(rating.to_numpy()),
        slope_value,
        "susceptibility_zone",
    )

    rating = trim_to_extent(rating, bbox)
    zone = trim_to_extent(zone, bbox)
    modification = trim_to_extent(modification, bbox)

    describe_modification(modification, coarse_resolution_m)
    describe_zones(zone, coarse_resolution_m)

    write_raster(rating, rating_path(pilot=pilot))
    write_raster(zone, zone_path(pilot=pilot))

    print(RULE)
    print(f"Wrote {rating_path(pilot=pilot)}")
    print(f"Wrote {zone_path(pilot=pilot)}")
    print(
        "\nThe 1995 generalisation rules are not applied, so this grid is\n"
        "systematically less severe than the published map. See the\n"
        "implementation plan beside this script."
    )


if __name__ == "__main__":
    main(
        pilot=config.PILOT,
        coarse_resolution_m=config.COARSE_RESOLUTION_M,
        fine_resolution_m=config.FINE_RESOLUTION_M,
        slope_height_window_m=config.SLOPE_HEIGHT_WINDOW_M,
        geology_value=config.GEOLOGY_VALUE,
        landslide_value=config.LANDSLIDE_VALUE,
        groundwater_value=config.GROUNDWATER_VALUE,
        use_cached_dem=config.USE_CACHED_DEM,
    )
