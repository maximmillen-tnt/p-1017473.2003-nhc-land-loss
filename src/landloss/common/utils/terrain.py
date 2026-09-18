"""Terrain derivatives computed from a digital elevation model.

Slope and topographic position are the two numbers that most of this study's
judgement hangs off. A steep section is worth less and is the one that fails in
an earthquake; a spur or a terrace standing above the land around it is worth
more and drains better than the gully beside it. Both are read straight off the
DEM, so both belong here rather than beside any one model that happens to want
them.

Nothing in this module knows about addresses, land value or property. That is
deliberate: the land value model in :mod:`landloss.exposure` and the earthquake
landslide extent work need the same two derivatives computed the same way, and a
second implementation would eventually disagree with the first. Anything that is
specific to what a derivative is *used for* belongs in the module that uses it.

Two things are worth stating plainly before any of these numbers are quoted.

Every derivative here is a property of the grid it was computed on, not of the
land. Slope at 10 m is the average gradient across a 30 m window; slope at 1 m
is the gradient across a 3 m window, and on a terraced Wellington hillside those
are different quantities rather than the same quantity at different precisions.
A 10 m slope is not a 1 m slope smoothed, and the two should not be substituted
for one another in a model calibrated on either. See
:data:`landloss.domain.constants.DEM_RESOLUTION_M` for the resolution this study
works at and why.

And nodata is the caller's problem. These functions treat every finite cell as
real ground, so a DEM still carrying -9999 in the sea will grow cliffs around
the coastline. Mask nodata to NaN before calling; NaN then propagates through
both derivatives as it should.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

# Imported for the side effect of registering the ``.rio`` accessor that
# write_raster uses; the name itself is never referenced.
import rioxarray  # noqa: F401
import xarray as xr
from ttpy.gis.raster.aggregation import get_rolling_aggregation
from ttpy.gis.raster.io import save_raster
from ttpy.gis.raster.utils import extract_point_values

# The dimension order every function here expects, and the order
# ``ttpy.gis.raster.aggregation.get_rolling_aggregation`` insists on. A raster
# read by ``ttpy.gis.raster.io.load_raster`` already arrives this way.
RASTER_DIMS = ("y", "x")

# The narrowest neighbourhood a topographic position can be measured over: one
# ring of cells around the centre.
MIN_WINDOW_CELLS = 3

# The names the returned rasters carry, so that a layer written to disk says
# what it holds without the file name having to.
SLOPE_NAME = "slope_degrees"
TOPOGRAPHIC_POSITION_NAME = "topographic_position_m"


def _check_dims(raster: xr.DataArray) -> None:
    """Raise unless a raster is two dimensional and oriented (y, x).

    Args:
        raster: The raster to check.

    Raises:
        ValueError: If the dimensions are anything other than
            :data:`RASTER_DIMS`. A band dimension left on a GeoTIFF is the usual
            cause, and squeezing it away is the usual fix.
    """
    if tuple(raster.dims) != RASTER_DIMS:
        msg = (
            f"The raster has dimensions {tuple(raster.dims)}, but the terrain "
            f"derivatives need exactly {RASTER_DIMS}. If this came from a "
            "GeoTIFF, squeeze the band dimension away first."
        )
        raise ValueError(msg)


def window_in_cells(window_m: float, resolution: float) -> int:
    """Convert a neighbourhood width in metres to an odd number of cells.

    The rolling window has to be an odd number of cells wide so that it has a
    centre cell to report against. An even request is widened by one rather than
    rejected, because the caller is expressing a length scale in metres and has
    no reason to care that the grid cannot represent it exactly.

    Args:
        window_m: The width of the neighbourhood, in metres.
        resolution: The cell size of the grid, in metres.

    Returns:
        The window width in cells, always odd and never under
        :data:`MIN_WINDOW_CELLS`.

    Raises:
        ValueError: If the requested width is under :data:`MIN_WINDOW_CELLS`
            cells. A one or two cell window has no ring of neighbours to compare
            its centre against, so the answer would be near zero everywhere;
            asking for one means the window and the resolution disagree.
    """
    cells = round(window_m / resolution)

    # Checked before the widening below, so that a two cell request fails rather
    # than being quietly rounded up into a legal three cell window.
    if cells < MIN_WINDOW_CELLS:
        msg = (
            f"A {window_m} m window is {cells} cell(s) at {resolution} m "
            f"resolution, but a topographic position needs at least "
            f"{MIN_WINDOW_CELLS} cells. Widen the window or use a finer grid."
        )
        raise ValueError(msg)

    if cells % 2 == 0:
        cells += 1

    return cells


def slope_degrees(dem: xr.DataArray, resolution: float) -> xr.DataArray:
    """Compute slope in degrees by Horn's method.

    Horn's 3x3 kernel is the one GDAL, ArcGIS and the National Liquefaction
    Model all use, so a slope from here is comparable with a slope quoted from
    any of them. It fits a plane through the eight neighbours of a cell,
    weighting the four that share an edge twice as heavily as the four that
    share only a corner::

        dz/dx = ((ne + 2e + se) - (nw + 2w + sw)) / (8 * resolution)
        dz/dy = ((sw + 2s + se) - (nw + 2n + ne)) / (8 * resolution)
        slope = degrees(arctan(hypot(dz/dx, dz/dy)))

    Written out in numpy rather than taken from a library, because every
    packaged implementation reachable from here pulls in numba, and numba forces
    a numpy downgrade that the rest of this project will not tolerate.

    Slope is a property of the cell size it is computed at. This is the average
    gradient over 30 m when ``resolution`` is 10 m, and over 3 m when it is 1 m
    -- a 10 m slope is not a 1 m slope smoothed, and the two are not
    interchangeable.

    Args:
        dem: Ground elevation in metres, with dimensions :data:`RASTER_DIMS`.
        resolution: The cell size of ``dem``, in metres. Passed explicitly
            rather than read off the transform, so that the answer cannot
            silently change with how the raster happened to be loaded.

    Returns:
        Slope in degrees on the same grid as ``dem``, from 0 (flat) to 90
        (vertical). The one cell border has no complete 3x3 window and comes
        back as NaN rather than as a one-sided gradient, which would read as a
        plausible small number and quietly flatten every edge of the study area.

    Raises:
        ValueError: If ``dem`` is not oriented (y, x), or if ``resolution`` is
            not positive.
    """
    _check_dims(dem)

    if resolution <= 0:
        msg = f"The cell size has to be positive, but {resolution} was given."
        raise ValueError(msg)

    elevation = np.asarray(dem.to_numpy(), dtype=float)
    slope = np.full(elevation.shape, np.nan)

    rows, columns = elevation.shape
    if rows >= MIN_WINDOW_CELLS and columns >= MIN_WINDOW_CELLS:
        # The eight neighbours of every interior cell at once, named as they sit
        # on a north-up raster, which is how a GeoTIFF is stored.
        north_west = elevation[:-2, :-2]
        north = elevation[:-2, 1:-1]
        north_east = elevation[:-2, 2:]
        west = elevation[1:-1, :-2]
        east = elevation[1:-1, 2:]
        south_west = elevation[2:, :-2]
        south = elevation[2:, 1:-1]
        south_east = elevation[2:, 2:]

        rise_east = (north_east + 2 * east + south_east) - (
            north_west + 2 * west + south_west
        )
        rise_south = (south_west + 2 * south + south_east) - (
            north_west + 2 * north + north_east
        )

        # Only the magnitude of the gradient is wanted, so which way the y axis
        # runs does not matter: a raster stored south-up gives the same slope.
        run = 8 * resolution
        gradient = np.hypot(rise_east / run, rise_south / run)

        # Horn's kernel gives the centre cell no weight, so a cell that is
        # itself nodata would otherwise come back with a perfectly reasonable
        # slope interpolated across the hole. There is no ground there to have a
        # gradient, so it is masked out -- which is what GDAL does too.
        centre = elevation[1:-1, 1:-1]
        gradient = np.where(np.isnan(centre), np.nan, gradient)
        slope[1:-1, 1:-1] = np.degrees(np.arctan(gradient))

    # copy(data=...) keeps the coordinates, and with them the spatial reference,
    # so the result can be written straight back out. The fill value is dropped
    # on the way through: the DEM's nodata marker is an elevation, and leaving
    # it on a raster of degrees would one day blank out a real slope that
    # happened to match it.
    result = dem.copy(data=slope)
    result.attrs.pop("_FillValue", None)
    result.name = SLOPE_NAME
    return result


def topographic_position(
    dem: xr.DataArray, resolution: float, window_m: float
) -> xr.DataArray:
    """Compute how far each cell stands above or below the land around it.

    The topographic position index is elevation minus the mean elevation of a
    square neighbourhood centred on the cell, in metres. It is positive on
    ridges, spurs and terraces, negative in gullies and on valley floors, and
    near zero both on a plain and on the even part of a uniform hillside -- a
    constant slope has as much ground above it as below it, so it has no
    position to report.

    The window is the whole parameter. A narrow one picks out the local
    micro-terrace; a wide one picks out where the cell sits in the valley.
    Choose it for the landform being looked for, and quote it with the result.

    Args:
        dem: Ground elevation in metres, with dimensions :data:`RASTER_DIMS`.
        resolution: The cell size of ``dem``, in metres.
        window_m: The width of the neighbourhood to compare against, in metres.
            Converted to an odd number of cells by :func:`window_in_cells`.

    Returns:
        Metres above (positive) or below (negative) the neighbourhood mean, on
        the same grid as ``dem``. The border half a window wide has no complete
        neighbourhood and comes back as NaN.

    Raises:
        ValueError: If ``dem`` is not oriented (y, x), or if ``window_m`` is
            narrower than :data:`MIN_WINDOW_CELLS` cells.
    """
    _check_dims(dem)

    window_cells = window_in_cells(window_m, resolution)
    neighbourhood_mean = get_rolling_aggregation(
        dem, aggregate_func="mean", window_size=window_cells
    )

    # Subtracting drops the DEM's attributes, which is what is wanted here: the
    # elevation units and the nodata marker do not describe a difference.
    result = dem - neighbourhood_mean
    result.name = TOPOGRAPHIC_POSITION_NAME
    return result


def sample_at_points(raster_path: Path | str, points: gpd.GeoSeries) -> pd.Series:
    """Read a raster value at each of a set of points.

    A thin wrapper over :func:`ttpy.gis.raster.utils.extract_point_values`,
    which returns a bare list. Every caller wants to assign the result onto the
    frame the points came from, and a list aligns by position -- which is the
    same as aligning by label right up until the frame has been filtered, at
    which point it is silently wrong. Returning a Series on the caller's own
    index removes that failure mode.

    Args:
        raster_path: The raster to read, as a GeoTIFF on disk.
        points: The points to sample at. Reprojected to the raster's coordinate
            reference system if they are not already in it.

    Returns:
        The sampled values, indexed as ``points`` is. NaN where a point falls
        outside the raster, on a nodata cell, or has empty geometry.
    """
    values = extract_point_values(Path(raster_path), points)
    return pd.Series(values, index=points.index, dtype=float)


def write_raster(raster: xr.DataArray, path: Path | str) -> Path:
    """Write a raster to disk, creating the directory it goes in.

    Creating the directory is the point. These derivatives get written and then
    immediately sampled, and a caller that has to make the parent directory
    itself before every write will one day forget to.

    Args:
        raster: The raster to write.
        path: Where to write it. The suffix chooses the format, and
            :func:`ttpy.gis.raster.io.save_raster` accepts ``.tif``, ``.tiff``
            and ``.zarr``.

    Returns:
        The path written to, so that a caller can write and then sample in one
        expression.

    Raises:
        ValueError: If the raster carries no coordinate reference system. It
            would still write, but nothing could be sampled against it
            afterwards, and that failure would surface a long way from here.
    """
    if raster.rio.crs is None:
        msg = (
            f"The raster bound for {path} has no coordinate reference system, "
            "so nothing could be sampled against it once written. Set one with "
            "DataArray.rio.write_crs before writing."
        )
        raise ValueError(msg)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_raster(raster, path)
    return path
