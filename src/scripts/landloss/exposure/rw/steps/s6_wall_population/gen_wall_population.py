"""Draw a stand-in retaining wall population over the insured properties.

Reads the insured land extent step 5 wrote, samples the slope and downhill
direction at each property off the LINZ elevation model, and draws at most one
wall per property against a slope-driven prevalence. Each wall is written as a
line lying along the contour, carrying the property it belongs to, its size
class and its initial condition.

    uv run --frozen python src/scripts/landloss/exposure/rw/steps/s6_wall_population/gen_wall_population.py

**This is a beta stand-in and none of it is evidence about Wellington.** The
real population is inferred from a model over the DEM, geomorphology and road
and dwelling locations, trained on the ICNZ database, a manual mapping study,
T+T SME estimates and remote sensing. None of those is in the repository, and
the SME estimate of prevalence by suburb (**T-19**) is what the real model would
be calibrated against. What this step buys is the structure the vulnerability
work reads: a line per wall with a size class and an initial condition.

The reasoning behind every number is in
`landloss.exposure.rw.beta_population`, which is where they are deleted from
when the real inference lands.

What it runs over, and for which realisations, comes from ``config.py`` beside
it.
"""

import sys

import geopandas as gpd
import numpy as np
import rioxarray

from landloss.common.utils.terrain import (
    DOWNHILL_AZIMUTH_NAME,
    SLOPE_NAME,
    cell_size,
    downhill_azimuth_degrees,
    sample_at_points,
    slope_degrees,
    write_raster,
)
from landloss.domain import constants
from landloss.exposure.rw.beta_population import (
    beta_wall_population,
    beta_wall_prevalence,
    describe_population,
)
from landloss.hazard.realisation import realisation_seed
from landloss.io.readers import get_dem
from scripts.landloss.exposure.land.steps.s5_insured_land_extent.gen_insured_land import (
    insured_land_path,
)
from scripts.landloss.exposure.rw.steps.s6_wall_population import config
from scripts.landloss.paths import TEMP_DIR

# Wellington suburb names are macronised, which the default cp1252 Windows
# console cannot encode, so printing one raises without this.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORK_DIR = TEMP_DIR / "exposure"
OUT_STEM = "beta-wall-population"

# The stream these draws come from. One name per module, so the walls of
# realisation 3 belong to the same modelled earthquake as its hazards.
RNG_STREAM = "exposure"

# The property's own point is where the slope is sampled, so the extent grows by
# enough that a property on the edge still sits inside the elevation model.
DEM_MARGIN_M = 200.0

SLOPE_COLUMN = "slope_deg"
AZIMUTH_COLUMN = "downhill_azimuth_deg"

RULE = "-" * 72


def wall_population_path(realisation_id, *, pilot):
    """Return the file a run writes one realisation's walls to.

    Args:
        realisation_id: Which modelled earthquake this is.
        pilot: Whether the run is over the pilot box.

    Returns:
        The output path, under ``temp/exposure/``.
    """
    suffix = "-pilot" if pilot else ""
    return WORK_DIR / f"{OUT_STEM}-r{realisation_id:03d}{suffix}.geoparquet"


def sample_terrain(properties, *, use_cached_dem):
    """Return the properties with slope and downhill azimuth attached.

    The two are derived from the elevation model over the properties' own
    extent and sampled at each property's representative point. A property whose
    point falls outside the elevation model comes back with NaN rather than a
    guess, and draws no wall.

    Args:
        properties: The insured land extent, one row per property.
        use_cached_dem: Whether to reuse an already-fetched elevation model.

    Returns:
        A copy carrying the slope and azimuth columns, with point geometry.
    """
    points = properties.geometry.representative_point()
    minx, miny, maxx, maxy = points.total_bounds
    bbox = (
        minx - DEM_MARGIN_M,
        miny - DEM_MARGIN_M,
        maxx + DEM_MARGIN_M,
        maxy + DEM_MARGIN_M,
    )

    print("Fetching the elevation model over the properties ...", flush=True)
    dem_path = get_dem(bbox, crs=constants.DEFAULT_CRS, use_cache=use_cached_dem)
    print(f"  {dem_path}")

    # Loaded rather than left lazy: an open GDAL handle finalised during
    # interpreter shutdown surfaces as a bare "Error in sys.excepthook".
    with rioxarray.open_rasterio(dem_path, masked=True) as opened:
        dem = opened.squeeze(drop=True).load()
    resolution = cell_size(dem)

    # Written then sampled, because the sampler reads from a file.
    slope_path = WORK_DIR / f"{OUT_STEM}-slope.tif"
    azimuth_path = WORK_DIR / f"{OUT_STEM}-azimuth.tif"
    write_raster(slope_degrees(dem, resolution).rename(SLOPE_NAME), slope_path)
    write_raster(
        downhill_azimuth_degrees(dem, resolution).rename(DOWNHILL_AZIMUTH_NAME),
        azimuth_path,
    )

    attached = properties.copy()
    attached[SLOPE_COLUMN] = sample_at_points(slope_path, points).to_numpy()
    attached[AZIMUTH_COLUMN] = sample_at_points(azimuth_path, points).to_numpy()
    attached = attached.set_geometry(points)
    return attached, resolution


def describe_terrain(properties, resolution):
    """Print the slope the population is drawn against."""
    slope = properties[SLOPE_COLUMN].to_numpy(dtype=float)
    known = np.isfinite(slope)
    print(RULE)
    print(f"Properties: {len(properties):,}")
    print(
        f"  slope sampled at {int(known.sum()):,} of them, off a {resolution:.0f} m DEM"
    )
    if known.any():
        deciles = np.percentile(slope[known], [0, 25, 50, 75, 100])
        labels = ("min", "25%", "median", "75%", "max")
        joined = "   ".join(
            f"{label}={value:.1f}" for label, value in zip(labels, deciles, strict=True)
        )
        print(f"  slope (degrees): {joined}")
        print(
            "  expected wall prevalence at the median slope: "
            f"{beta_wall_prevalence(float(np.median(slope[known]))):.1%}"
        )


def describe_walls(walls, properties):
    """Print what was drawn, against what it was drawn from."""
    print(RULE)
    share = len(walls) / len(properties) if len(properties) else 0.0
    print(
        f"Walls drawn: {len(walls):,} over {len(properties):,} properties ({share:.1%})"
    )
    if walls.empty:
        return
    print(RULE)
    print("Walls by size class and initial condition:")
    print(describe_population(walls).to_string())
    length = walls["length_m"].to_numpy(dtype=float)
    height = walls["height_m"].to_numpy(dtype=float)
    print(
        f"  length {length.min():.1f} to {length.max():.1f} m, "
        f"median {np.median(length):.1f}"
    )
    print(
        f"  retained height {height.min():.1f} to {height.max():.1f} m, "
        f"median {np.median(height):.1f}"
    )


def main(*, pilot, realisation_ids, use_cached_dem):
    """Draw a wall population per realisation and write each one out.

    Args:
        pilot: Whether to run over the small Wellington pilot box.
        realisation_ids: Which modelled earthquakes to draw for.
        use_cached_dem: Whether to reuse an already-fetched elevation model.
    """
    extent_path = insured_land_path(pilot=pilot)
    print(f"Reading the insured land from {extent_path} ...")
    properties = gpd.read_parquet(extent_path)

    attached, resolution = sample_terrain(properties, use_cached_dem=use_cached_dem)
    describe_terrain(attached, resolution)

    for realisation_id in realisation_ids:
        print(RULE)
        print(f"Realisation {realisation_id}, stream {RNG_STREAM!r}")
        rng = realisation_seed(constants.BASE_SEED, realisation_id, RNG_STREAM)
        walls = beta_wall_population(
            attached,
            rng,
            slope_column=SLOPE_COLUMN,
            azimuth_column=AZIMUTH_COLUMN,
        )
        describe_walls(walls, attached)

        out_path = wall_population_path(realisation_id, pilot=pilot)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        walls.to_parquet(out_path)
        print(f"Wrote {len(walls):,} walls to {out_path}")

    print(RULE)
    print(
        "This population is a beta stand-in drawn from slope alone. It is not "
        "evidence about Wellington; see T-19 for what replaces it."
    )


if __name__ == "__main__":
    main(
        pilot=config.PILOT,
        realisation_ids=config.REALISATION_IDS,
        use_cached_dem=config.USE_CACHED_DEM,
    )
