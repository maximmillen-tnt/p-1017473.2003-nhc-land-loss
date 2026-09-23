"""Turn the supplied landslide probability grid into one realisation of landslides.

A probability grid says how likely each cell is to fail -- 32 m cells in the file
supplied so far, though the cell size is read off the grid rather than assumed
anywhere here. It cannot say how much land a claim covers, or whose land the
debris lands on, because it holds no landslides, only a chance of one. This
script draws a set of them:

    uv run --frozen python src/scripts/landloss/hazard/landslide/steps/s1_landslide_realisation/s1_simulate_landslides.py

What it runs over, and with what seed, comes from ``config.py`` beside it, read
at the bottom of this file and passed into :func:`main`. Change it there rather
than passing flags, so that what a run did can be read off the source.

Six stages, each of which is a stated assumption rather than a measurement. They
are laid out here because the output is only as good as the weakest of them, and
the weakest is not the one that looks most technical.

1. **Sample each cell independently.** A cell fails with its own probability,
   with no regard for whether its neighbours did. Real failures cluster: they
   share a hillside, a geology and a shaking level, so a real event produces
   fewer, larger clusters than independent sampling does. This is the largest
   known error in the run, and it biases the *shape* of the loss distribution --
   too few very bad days, too few very quiet ones -- much more than it biases
   the average.
2. **Sample a size for each failure**, from a bounded power law between
   :data:`MIN_SOURCE_AREA_M2` and :data:`MAX_SOURCE_AREA_M2`. Small failures are
   common and large ones rare, which is what every landslide inventory shows;
   the exponent is a placeholder until one is fitted.
3. **Put the failure in the middle of its cell, as a circle.** Real source areas
   are elongated down the slope. A circle of the right area is the crudest shape
   that gets the area right, and area is what the loss model reads.
4. **Drop overlapping failures, keeping the largest.** Two landslides cannot
   occupy the same ground, and the alternative -- merging them -- would invent a
   single failure larger than anything that was sampled.
5. **Read the slope and the downhill direction** off the LINZ elevation model,
   resampled onto the probability grid so the two line up cell for cell.
6. **Move the failure downhill**, by a distance that grows with the slope,
   between :data:`MIN_DISPLACEMENT_M` and :data:`MAX_DISPLACEMENT_M`. The
   displaced circle is where the material ends up.

The output is one GeoParquet holding two polygons per landslide: **evacuated
land**, the source the material left, and **inundated land**, where it came to
rest. They are kept apart rather than merged because NHC settles loss of support
and runout differently, so the vulnerability model needs to know which is which.
Where the displacement is small next to the landslide the two overlap, and that
is real: the ground is stripped and then buried again.

Leave ``PILOT`` set in ``config.py`` while the model is being changed. The full
study area is 59 by 54 km, and the slow part is assembling the elevation model
over it.
"""

import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rioxarray
import xarray as xr
from rasterio.enums import Resampling
from shapely import STRtree

from landloss.common.utils.terrain import (
    azimuth_offsets,
    cell_size,
    downhill_azimuth_degrees,
    slope_degrees,
)
from landloss.domain import constants
from landloss.hazard.landslide.geometry import landslide_volume_m3, mean_depth_m
from landloss.hazard.realisation import realisation_seed
from landloss.io.area_of_interest import SMALL_WLG_PILOT, get_study_areas
from landloss.io.readers import get_dem
from landloss.io.source_material import get_eil_landslide_probability
from scripts.landloss.hazard.landslide.steps.s1_landslide_realisation import config
from scripts.landloss.paths import TEMP_DIR

# Wellington place names are macronised -- Owhiro Bay, Pauatahanui -- which the
# default cp1252 Windows console cannot encode, so printing one raises. Ask for
# UTF-8 rather than stripping the macrons, because the names are worth getting
# right.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# temp/ is gitignored. This is a working layer, rebuildable from the source grid
# and the elevation model, so it has no business in a diff.
WORK_DIR = TEMP_DIR / "hazard" / "landslide"

# Separate names, so a pilot run cannot overwrite a full one.
OUT_STEM = "landslide-realisation"

# The stream this step draws from. One name per hazard, not per script, so every
# script in the module draws from the same sequence for a given realisation.
RNG_STREAM = "landslide"

# Carried on every polygon so a layer can be paired with the shaking and
# liquefaction layers of the same modelled earthquake.
REALISATION_ID_COLUMN = "realisation_id"

# The size distribution. A bounded power law: the probability density of a
# source area falls as area to the power -SIZE_EXPONENT, between the two limits.
# The limits are the range asked for -- a failure too small to be worth a claim
# at one end, a whole hillside at the other.
#
# The exponent is calibrated to total area, not fitted to a size inventory, and
# that is the single most important thing to know about this step.
#
# The count of failures is set by the supplied grid and is faithful to it: over
# the full study area the grid implies 66,644 and the model draws within one
# binomial standard deviation, band by band across two orders of magnitude of
# probability. The *area* is then whatever the size distribution makes it, and
# nothing in the grid constrains that. At the published exponent of 2.1 the model
# delivered 0.063% areal coverage, about sixteen times below the order of 1% that
# Nowicki Jessee et al. (2018) give for strong shaking in steep terrain, because
# a median source area of 5.7 m2 was being placed inside a 1,024 m2 cell.
#
# So the exponent is solved backwards from that cross-check: 1.19 puts the mean
# source area at 258 m2 and the areal coverage at 0.99%. It is deliberately *not*
# anchored to the other available reading -- that a failing 32 m cell fails
# whole, which would need 1,028 m2 and an exponent near 0.5. That reading is
# rejected on physical grounds: it would make 43% of modelled landslides larger
# than 1,000 m2 and put the median at 791 m2, which is not a landslide population
# any inventory resembles, and it would put areal coverage at 3.9%, four times
# the literature.
#
# The cost is that 1.19 is far shallower than any published fit (Massey et al.
# 2020 give 2.1 for the Kaikoura greywacke source polygons, Malamud et al. 2004
# give 2.3 to 2.5 generally). That is not a disagreement with those fits: they
# hold above a cutoff near 500 m2, and a single power law stretched two decades
# below it cannot carry both a published slope and the right total area. Real
# inventories roll over below the cutoff instead. The honest fix is two
# populations -- small modified-slope failures and natural-slope landslides --
# which is phase 2 of the plan; until then this exponent buys the right total
# area at the price of the right shape, and a size distribution quoted from this
# step should say so.
#
# At these limits: median 34 m2, mean 258 m2, about one failure in twelve over
# 1,000 m2.
MIN_SOURCE_AREA_M2 = 3.0
MAX_SOURCE_AREA_M2 = 3000.0
SIZE_EXPONENT = 1.19

# How far the material travels, as a function of slope alone. A straight ramp:
# MIN_DISPLACEMENT_M at or below MIN_DISPLACEMENT_SLOPE_DEG, MAX_DISPLACEMENT_M
# at or above MAX_DISPLACEMENT_SLOPE_DEG, linear between them. This stands in
# for a Newmark displacement, which would take the yield acceleration and the
# shaking rather than the slope on its own; the range is the one asked for. The
# anchors say a 10 degree slope barely moves its debris and a 45 degree one
# moves it the full distance, which is the right direction and is not calibrated.
MIN_DISPLACEMENT_M = 1.0
MAX_DISPLACEMENT_M = 40.0
MIN_DISPLACEMENT_SLOPE_DEG = 10.0
MAX_DISPLACEMENT_SLOPE_DEG = 45.0

# The two polygons every landslide produces, in the words the loss model reads
# them by.
EVACUATED = "evacuated land"
INUNDATED = "inundated land"
LAND_CLASS_COLUMN = "land_class"

# How much material the failure involved, and how deep it lies over the polygon
# that carries it. Both come from the volume-area power law rather than from the
# simulation, which samples areas and nothing else. The vulnerability step needs
# the depth because what a repair costs depends on how much has to be moved and
# not only on the footprint.
VOLUME_COLUMN = "volume_m3"
DEPTH_COLUMN = "depth_m"

# Quarter-circle segments in the buffered circles. 16 gives a 64 sided polygon,
# within a tenth of a percent of a true circle -- and the radius is corrected
# for even that, so each polygon carries the area that was sampled.
CIRCLE_SEGMENTS = 16

# The elevation model is fetched over the extent plus this many cells, so that
# the slope and the downhill direction have a complete window at every cell of
# the probability grid, including the ones on its outside edge.
DEM_BUFFER_CELLS = 3

# The quantiles the distributions are described at. Deciles rather than a mean
# and a standard deviation, because none of these are symmetric -- a power law
# least of all -- and the shape is the thing worth looking at.
DECILES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

HECTARE_M2 = 10_000.0

# How much of a polygon set has to lie over itself before the run says so. Set
# just below the smallest share that rounds to a tenth of a per cent, so the
# line appears when there is really something to dissolve and not when there is
# only rounding.
MIN_REPORTED_OVERLAP_PERCENT = 0.05

RULE = "-" * 72


def realisation_path(*, pilot, realisation_id):
    """Return the file a run writes one realisation to.

    A function rather than a constant because the name depends on the extent and
    on which realisation it is. ``fig_landslide_realisation.py`` calls this too,
    which is what keeps the figure drawing the realisation the simulation
    actually wrote.

    Args:
        pilot: Whether the run is over the pilot box.
        realisation_id: Which modelled earthquake this is.

    Returns:
        The output path, under ``temp/hazard/landslide/``.
    """
    suffix = "-pilot" if pilot else ""
    return WORK_DIR / f"{OUT_STEM}-r{realisation_id:03d}{suffix}.geoparquet"


def resolve_extent(study_areas, *, pilot):
    """Choose the extent to run over, and say which one it is.

    Args:
        study_areas: The four territorial authorities.
        pilot: Whether to use the small Wellington pilot box instead.

    Returns:
        ``(bbox, name)``: the extent in the study's own projection, and a label
        for the run output.
    """
    if pilot:
        return SMALL_WLG_PILOT.bbox(constants.DEFAULT_CRS), SMALL_WLG_PILOT.name

    west, south, east, north = (float(value) for value in study_areas.total_bounds)
    return (west, south, east, north), "the four territorial authorities"


def check_probabilities(probability):
    """Check the grid holds probabilities, and hand back the ones it has.

    A grid in percent, or one carrying a nodata marker that was never declared,
    reads as a perfectly ordinary array of numbers and would produce a perfectly
    ordinary looking set of landslides -- a hundred times too many of them. It is
    refused here rather than corrected, because which of the two it is changes
    the answer and only the supplier knows.

    Args:
        probability: The probability grid.

    Returns:
        The finite values in the grid, flattened.

    Raises:
        ValueError: If the grid is empty over this extent, or any value falls
            outside [0, 1].
    """
    values = probability.to_numpy()
    finite = values[np.isfinite(values)]

    if finite.size == 0:
        msg = (
            "The probability grid has no data at all over this extent. Check "
            "that the extent and the grid cover the same ground."
        )
        raise ValueError(msg)

    if finite.min() < 0 or finite.max() > 1:
        msg = (
            f"The probability grid runs from {finite.min():g} to "
            f"{finite.max():g}, which is not a probability. If it is in per "
            "cent, or carries an undeclared nodata marker, confirm which with "
            "the supplier and convert it there rather than here."
        )
        raise ValueError(msg)

    return finite


def expand_grid(grid, cells=DEM_BUFFER_CELLS):
    """Build an empty grid matching another, extended by a ring of cells.

    The terrain derivatives have no answer within one cell of the edge of the
    grid they are computed on, so computing them directly on the probability
    grid would lose its outermost ring -- which on any extent is the coastline.
    Computing them on a wider grid and trimming back gives an answer everywhere.

    Args:
        grid: The raster to match, carrying x and y coordinates and a projection.
        cells: How many cells to extend by on every side.

    Returns:
        An empty raster on the extended grid, ready to reproject onto.

    Raises:
        ValueError: If the grid is too small to read a cell spacing off.
    """
    x = grid["x"].to_numpy()
    y = grid["y"].to_numpy()

    if x.size < 2 or y.size < 2:
        msg = (
            f"The grid is {y.size} by {x.size} cells, which is too small to "
            "extend or to compute a gradient on."
        )
        raise ValueError(msg)

    x_step = x[1] - x[0]
    y_step = y[1] - y[0]
    steps = np.arange(1, cells + 1)

    x_wide = np.concatenate([x[0] - x_step * steps[::-1], x, x[-1] + x_step * steps])
    y_wide = np.concatenate([y[0] - y_step * steps[::-1], y, y[-1] + y_step * steps])

    template = xr.DataArray(
        np.zeros((y_wide.size, x_wide.size)),
        dims=("y", "x"),
        coords={"y": y_wide, "x": x_wide},
    )
    return template.rio.write_crs(grid.rio.crs)


def build_terrain(grid, resolution, *, use_cache):
    """Fetch the elevation model, and derive slope and downhill direction on the grid.

    The elevation model is resampled onto the probability grid rather than the
    other way round. The probability grid is the thing being sampled and its
    cells are the units the answer is counted in, so moving it would change what
    is being modelled; the elevation model is a continuous surface, and
    resampling it is what choosing a resolution always is.

    Args:
        grid: The probability grid to match.
        resolution: Its cell size in metres.
        use_cache: Whether to reuse an already-fetched elevation model.

    Returns:
        ``(slope, azimuth)``, both on exactly ``grid``'s cells: slope in degrees,
        and the downhill bearing in degrees clockwise from north.

    Raises:
        ValueError: If the derived terrain does not line up with ``grid``.
    """
    template = expand_grid(grid)
    west, south, east, north = template.rio.bounds()

    print(
        f"Fetching the elevation model at {resolution:g} m over the extent plus "
        f"{DEM_BUFFER_CELLS} cells ...",
        flush=True,
    )
    dem_path = get_dem(
        (west, south, east, north),
        resolution=round(resolution),
        crs=constants.DEFAULT_CRS,
        use_cache=use_cache,
    )
    print(f"  {dem_path}")

    # Read through a context manager and load into memory. A lazily-opened
    # GDAL handle is finalised during interpreter shutdown, which on Windows
    # surfaces as a bare "Error in sys.excepthook" after an otherwise clean
    # run -- and the array is small enough that holding it costs nothing.
    with rioxarray.open_rasterio(dem_path, masked=True) as opened:
        dem = opened.squeeze(drop=True).load()

    # Bilinear rather than nearest: elevation is a continuous surface, and
    # nearest neighbour would step it, putting a false cliff between every pair
    # of cells for the slope to find.
    on_template = dem.rio.reproject_match(template, resampling=Resampling.bilinear)

    slope = slope_degrees(on_template, resolution)
    azimuth = downhill_azimuth_degrees(on_template, resolution)

    # Trim the ring back off, so both line up with the probability grid cell for
    # cell. Anything else silently pairs a probability with the slope of the
    # wrong hillside.
    trim = slice(DEM_BUFFER_CELLS, -DEM_BUFFER_CELLS)
    slope = slope.isel(y=trim, x=trim)
    azimuth = azimuth.isel(y=trim, x=trim)

    if slope.shape != grid.shape:
        msg = (
            f"The terrain came back {slope.shape} against a probability grid of "
            f"{grid.shape}, so the two cannot be paired up. That is a bug in the "
            "grid extension rather than something to work around."
        )
        raise ValueError(msg)

    return slope, azimuth


def sample_areas(count, rng):
    """Draw source areas from the bounded power law.

    Drawn by inverting the cumulative distribution, so every draw costs one
    uniform variate and the limits are exact rather than approached by
    rejection.

    Args:
        count: How many areas to draw.
        rng: The random number generator.

    Returns:
        Source areas in square metres, between :data:`MIN_SOURCE_AREA_M2` and
        :data:`MAX_SOURCE_AREA_M2`.
    """
    power = 1.0 - SIZE_EXPONENT
    low = MIN_SOURCE_AREA_M2**power
    high = MAX_SOURCE_AREA_M2**power
    uniform = rng.random(count)
    return (low + uniform * (high - low)) ** (1.0 / power)


def displacement_from_slope(slope_values):
    """Convert slope in degrees to how far the material travels, in metres.

    Args:
        slope_values: Slope at each failure, in degrees.

    Returns:
        Displacement in metres, between :data:`MIN_DISPLACEMENT_M` and
        :data:`MAX_DISPLACEMENT_M`. NaN slope carries through as NaN.
    """
    span = MAX_DISPLACEMENT_SLOPE_DEG - MIN_DISPLACEMENT_SLOPE_DEG
    fraction = np.clip((slope_values - MIN_DISPLACEMENT_SLOPE_DEG) / span, 0.0, 1.0)
    return MIN_DISPLACEMENT_M + fraction * (MAX_DISPLACEMENT_M - MIN_DISPLACEMENT_M)


def circle_radius(area_m2):
    """Return the radius a buffered circle needs in order to enclose an area.

    A buffer is a polygon, not a circle: with :data:`CIRCLE_SEGMENTS` quarter
    segments it is a 64 sided figure inscribed in the radius asked for, so it
    encloses slightly less than pi r squared. The correction is under a tenth of
    a per cent and nothing downstream would notice it -- but area is the quantity
    the loss model reads, and a polygon that does not carry the area that was
    sampled is a small lie that would have to be explained every time the two
    were compared.

    Args:
        area_m2: The area the polygon should enclose.

    Returns:
        The radius to buffer by.
    """
    sides = 4 * CIRCLE_SEGMENTS
    inscribed_ratio = 0.5 * sides * np.sin(2 * np.pi / sides) / np.pi
    return np.sqrt(area_m2 / (np.pi * inscribed_ratio))


def circles(eastings, northings, radii, crs):
    """Build one circular polygon per centre, each of its own radius."""
    centres = gpd.GeoSeries(gpd.points_from_xy(eastings, northings), crs=crs)
    return centres.buffer(radii, resolution=CIRCLE_SEGMENTS)


def build_failures(probability, slope, azimuth, rng):
    """Sample which cells fail, how big each failure is, and where it ends up.

    Args:
        probability: The probability grid.
        slope: Slope in degrees, on the same cells.
        azimuth: Downhill bearing in degrees, on the same cells.
        rng: The random number generator.

    Returns:
        ``(failures, drawn, without_terrain)``: a GeoDataFrame of failures whose
        geometry is the source circle, the number of cells that failed before
        any were dropped, and the number dropped for having no slope or no
        downhill direction.
    """
    values = probability.to_numpy()

    # A cell with no probability cannot fail, and comparing NaN against a
    # uniform variate would quietly answer False anyway. Saying so explicitly
    # keeps the count of cells that were never in play visible.
    chance = np.where(np.isfinite(values), values, 0.0)
    failed = rng.random(values.shape) < chance

    rows, columns = np.nonzero(failed)
    drawn = int(rows.size)

    eastings = probability["x"].to_numpy()[columns]
    northings = probability["y"].to_numpy()[rows]
    probabilities = values[rows, columns]
    slope_values = slope.to_numpy()[rows, columns]
    azimuth_values = azimuth.to_numpy()[rows, columns]

    # Level ground and the outermost cells of the elevation model have no
    # downhill direction, so there is nowhere to put the debris. Dropped rather
    # than left in place with no runout, because a landslide that does not move
    # is not one of the things being modelled here.
    usable = np.isfinite(slope_values) & np.isfinite(azimuth_values)
    without_terrain = int((~usable).sum())

    eastings = eastings[usable]
    northings = northings[usable]
    probabilities = probabilities[usable]
    slope_values = slope_values[usable]
    azimuth_values = azimuth_values[usable]

    areas = sample_areas(eastings.size, rng)
    radii = circle_radius(areas)
    displacement = displacement_from_slope(slope_values)
    east_offset, north_offset = azimuth_offsets(azimuth_values, displacement)

    failures = gpd.GeoDataFrame(
        {
            "landslide_id": np.arange(eastings.size),
            "easting": eastings,
            "northing": northings,
            "failure_probability": probabilities,
            "source_area_m2": areas,
            "radius_m": radii,
            "slope_degrees": slope_values,
            "downhill_azimuth_degrees": azimuth_values,
            "displacement_m": displacement,
            "runout_easting": eastings + east_offset,
            "runout_northing": northings + north_offset,
        },
        geometry=circles(eastings, northings, radii, probability.rio.crs),
        crs=probability.rio.crs,
    )
    return failures, drawn, without_terrain


def drop_overlapping(failures):
    """Drop every failure whose source overlaps a larger one, keeping the larger.

    The overlap rule is applied to the **source** areas and nowhere else, and
    that is a decision rather than an oversight. Two landslides cannot start
    from the same ground, so overlapping sources are not a thing that happens.
    Two landslides can perfectly well finish on the same ground -- a pair either
    side of a gully both run into its floor -- so overlapping runouts are left
    alone. A failure dropped here takes its runout with it, because
    :func:`to_polygons` only ever sees the survivors.

    Worked largest first, so a failure survives only if nothing bigger than
    itself survived and reached it. A failure that has already been dropped
    cannot drop anything else -- otherwise one large landslide would clear a
    hole far wider than itself, through a chain of failures none of which
    happened.

    Args:
        failures: The sampled failures, indexed from zero, whose geometry is the
            source circle.

    Returns:
        The failures that survive, in their original order.
    """
    if failures.empty:
        return failures

    geometries = failures.geometry.to_numpy()
    areas = failures["source_area_m2"].to_numpy()
    tree = STRtree(geometries)

    # Stable, so that two failures of exactly the same area resolve the same way
    # on every run rather than however the sort happened to order them.
    order = np.argsort(-areas, kind="stable")
    dropped = np.zeros(areas.size, dtype=bool)

    for index in order:
        if dropped[index]:
            continue
        for other in tree.query(geometries[index], predicate="intersects"):
            if other != index:
                dropped[other] = True

    return failures[~dropped]


def to_polygons(failures):
    """Expand each failure into its evacuated and its inundated polygon.

    Only the survivors of :func:`drop_overlapping` reach here, which is how a
    dropped failure loses its runout as well as its source: a landslide that did
    not happen cannot have buried anything. So no two evacuated polygons in the
    result overlap, and inundated ones may.

    Args:
        failures: The surviving failures, whose geometry is the source circle.

    Returns:
        Two rows per failure, told apart by :data:`LAND_CLASS_COLUMN`.
    """
    evacuated = failures.assign(**{LAND_CLASS_COLUMN: EVACUATED})

    # The same circle at the displaced centre. Rebuilt rather than translated
    # because a circle is defined by its centre and its radius, so rebuilding
    # cannot drift from the source polygon the way a separate translation could.
    inundated = gpd.GeoDataFrame(
        failures.drop(columns=[failures.geometry.name]).assign(
            **{LAND_CLASS_COLUMN: INUNDATED}
        ),
        geometry=circles(
            failures["runout_easting"],
            failures["runout_northing"],
            failures["radius_m"].to_numpy(),
            failures.crs,
        ).to_numpy(),
        crs=failures.crs,
    )

    both = pd.concat([evacuated, inundated], ignore_index=True)

    # Volume is conserved through the runout -- the material that left the
    # source is the material that lands -- so it is computed once from the
    # source area and then spread over whichever footprint the row carries.
    # In the beta the runout circle is rebuilt at the source radius, so the two
    # footprints are equal and the two depths come out identical. That is a
    # property of this geometry, not a bug.
    both[VOLUME_COLUMN] = landslide_volume_m3(both["source_area_m2"].to_numpy())
    both[DEPTH_COLUMN] = mean_depth_m(
        both[VOLUME_COLUMN].to_numpy(), both.geometry.area.to_numpy()
    )
    return both.sort_values(["landslide_id", LAND_CLASS_COLUMN]).reset_index(drop=True)


def describe_extent(name, probability, resolution):
    """Print what is being run over, and what the probability grid holds.

    The extent printed is the grid's own, not the one that was asked for. They
    differ whenever the supplied grid stops short of the study area, and it is
    the ground actually simulated that a result has to be quoted against.
    """
    west, south, east, north = (float(v) for v in probability.rio.bounds())
    print(RULE)
    print(f"Extent: {name}, as far as the supplied grid reaches")
    print(f"  {west:,.0f} - {east:,.0f} E, {south:,.0f} - {north:,.0f} N")
    print(f"  {(east - west) / 1000:,.1f} by {(north - south) / 1000:,.1f} km")
    print(
        f"Probability grid: {probability.shape[0]:,} by {probability.shape[1]:,} "
        f"cells at {resolution:g} m, in {probability.rio.crs}"
    )


def describe_probabilities(finite, resolution, cells):
    """Print the probability distribution, and the failures it implies."""
    expected = float(finite.sum())
    print(RULE)
    print(f"Cells carrying a probability: {finite.size:,} of {cells:,}")
    print(
        f"  min {finite.min():.2e}, median {np.median(finite):.2e}, "
        f"mean {finite.mean():.2e}, max {finite.max():.2e}"
    )
    print("Expected failures, as the sum of the cell probabilities:")
    print(
        f"  {expected:,.0f} cells, which is "
        f"{expected * resolution**2 / HECTARE_M2:,.1f} ha of {resolution:g} m "
        "cells -- the grid's own answer, before any of the sampling below"
    )


def describe_distribution(values, label, units):
    """Print the deciles of a distribution, the shape being the arguable part."""
    values = pd.Series(np.asarray(values, dtype=float)).dropna()
    if values.empty:
        print(f"{label}: nothing to describe.")
        return

    quantiles = values.quantile(DECILES)
    print(f"{label} ({units}):")
    print(
        "  " + "  ".join(f"{int(q * 100):>3}%={v:,.1f}" for q, v in quantiles.items())
    )
    print(f"  mean {values.mean():,.1f}, total {values.sum():,.0f}")


def describe_result(polygons):
    """Print the ground the two polygon sets cover, which is what the loss model reads.

    The two are measured differently on purpose, and the asymmetry is the point.
    :func:`drop_overlapping` has already made the evacuated polygons pairwise
    disjoint, so their summed area *is* the ground they cover and dissolving
    them would cost a minute at full study area size to reproduce a number
    already in hand. Nothing guarantees the same of the inundated polygons: they
    are those same circles moved different distances in different directions, so
    two failures either side of a gully both land in its floor. Ground buried by
    two landslides is buried once, and anything summing inundated area without
    dissolving first counts it twice.
    """
    print(RULE)
    for land_class in (EVACUATED, INUNDATED):
        subset = polygons[polygons[LAND_CLASS_COLUMN] == land_class]
        if subset.empty:
            print(f"{land_class}: none.")
            continue

        summed = subset.geometry.area.sum()
        if land_class == EVACUATED:
            print(
                f"{land_class}: {len(subset):,} polygons, "
                f"{summed / HECTARE_M2:,.2f} ha, none of it overlapping"
            )
            continue

        distinct = subset.geometry.union_all().area
        print(
            f"{land_class}: {len(subset):,} polygons, "
            f"{summed / HECTARE_M2:,.2f} ha summed, "
            f"{distinct / HECTARE_M2:,.2f} ha of distinct ground"
        )

        # Said in words as well as in two numbers, because the difference is a
        # trap rather than a detail. Tested against a threshold rather than
        # against zero: dissolving 64 sided polygons leaves floating point dust
        # behind, and a line reporting "0.0% overlap" on every run would teach
        # everyone to ignore the line.
        share = 100 * (summed - distinct) / summed
        if share >= MIN_REPORTED_OVERLAP_PERCENT:
            print(
                f"  {share:.1f}% of that is runout polygons lying over one "
                "another -- dissolve before summing"
            )

    # Reported because the depth is what the vulnerability step multiplies, and
    # it comes from a power law whose coefficient is still a placeholder. Seeing
    # the numbers each run is the cheapest guard against that going unnoticed.
    source = polygons[polygons[LAND_CLASS_COLUMN] == EVACUATED]
    if not source.empty:
        describe_distribution(source[VOLUME_COLUMN], "landslide volume", "m3")
        describe_distribution(source[DEPTH_COLUMN], "mean depth", "m")


def main(*, pilot, realisation_ids, use_cached_dem):
    """Draw a realisation of landslides per id and write each one out.

    Args:
        pilot: Whether to run over the small Wellington pilot box rather than
            the four territorial authorities.
        realisation_ids: Which modelled earthquakes to draw.
        use_cached_dem: Whether to reuse an already-fetched elevation model for
            this extent.
    """
    study_areas = get_study_areas(constants.DEFAULT_CRS)
    bbox, extent_name = resolve_extent(study_areas, pilot=pilot)

    print("Reading the landslide probability grid ...", flush=True)
    probability = get_eil_landslide_probability(bbox=bbox, crs=constants.DEFAULT_CRS)
    resolution = cell_size(probability)
    finite = check_probabilities(probability)

    describe_extent(extent_name, probability, resolution)
    describe_probabilities(finite, resolution, probability.size)

    slope, azimuth = build_terrain(probability, resolution, use_cache=use_cached_dem)

    for realisation_id in realisation_ids:
        draw_realisation(
            probability,
            slope,
            azimuth,
            pilot=pilot,
            realisation_id=realisation_id,
        )


def draw_realisation(probability, slope, azimuth, *, pilot, realisation_id):
    """Draw one modelled earthquake's landslides and write them out.

    The generator comes from the project seed and the realisation id rather than
    from a seed of this step's own, so the landslides of realisation 3 belong to
    the same earthquake as the shaking and liquefaction of realisation 3.

    Args:
        probability: The per-cell probability of slope failure.
        slope: Slope in degrees, on the same grid.
        azimuth: Downhill azimuth in degrees, on the same grid.
        pilot: Whether the run is over the pilot box.
        realisation_id: Which modelled earthquake this is.
    """
    out_path = realisation_path(pilot=pilot, realisation_id=realisation_id)
    print(RULE)
    print(f"Realisation {realisation_id}")

    rng = realisation_seed(constants.BASE_SEED, realisation_id, RNG_STREAM)
    failures, drawn, without_terrain = build_failures(probability, slope, azimuth, rng)

    print(RULE)
    print(f"Cells that failed in this realisation: {drawn:,}")
    if without_terrain:
        print(
            f"  {without_terrain:,} dropped for having no slope or no downhill "
            "direction (level ground, or a hole in the elevation model)"
        )

    # Separated from the no-failures case below, because they need different
    # answers. No failures is a result; every failure thrown away for want of a
    # slope means the elevation model did not cover the grid, which is a broken
    # run wearing the same clothes.
    if drawn and failures.empty:
        msg = (
            f"All {drawn:,} failures were dropped for having no slope or no "
            "downhill direction, so the elevation model does not cover the "
            "probability grid over this extent. Check the two line up before "
            "reading anything into the result."
        )
        raise ValueError(msg)

    survivors = drop_overlapping(failures)
    print(
        f"  {len(failures) - len(survivors):,} dropped for overlapping a larger "
        f"failure, leaving {len(survivors):,}"
    )

    polygons = to_polygons(survivors)
    polygons[REALISATION_ID_COLUMN] = realisation_id

    # No failures is a result, and it is written as one: an empty layer with the
    # full schema, so every step reading this realisation finds a file and
    # reports nothing damaged rather than stopping on a missing input.
    if failures.empty:
        print("\nNothing failed in this realisation; writing an empty layer.")
    else:
        print(RULE)
        describe_distribution(survivors["source_area_m2"], "Source area", "m2")
        describe_distribution(survivors["slope_degrees"], "Slope", "degrees")
        describe_distribution(survivors["displacement_m"], "Displacement", "m")
        describe_result(polygons)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    polygons.to_parquet(out_path)
    print(f"Wrote {len(polygons):,} polygons to {out_path}")
    print(
        f"Seed {constants.BASE_SEED}, realisation {realisation_id}, stream "
        f"{RNG_STREAM!r}; the same three reproduce it exactly."
    )


if __name__ == "__main__":
    main(
        pilot=config.PILOT,
        realisation_ids=config.REALISATION_IDS,
        use_cached_dem=config.USE_CACHED_DEM,
    )
