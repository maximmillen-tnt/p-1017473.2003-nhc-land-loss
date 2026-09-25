r"""Write a peak ground acceleration field per realisation.

Reads the National Liquefaction Model's 2500-year PGA grid, clips it to the
extent, and scales it by one lognormal draw per realisation so the chain carries
a spread in its shaking rather than one fixed field.

    uv run --frozen python src/scripts/landloss/hazard/shaking/steps/s1_pga_realisation/gen_pga_realisations.py

Two beta shortcuts sit in this step, both named in
`landloss.hazard.shaking.pga`. The grid is the NLM's **site class 5** field,
read as delivered rather than assembled per point from a V\ :sub:`s`\ 30 model,
so every property in the study is treated as the same ground. And the spread is
a flat 10% coefficient of variation applied as one multiplier over the whole
field, rather than the ground motion model's own sigma over a spatially
correlated field.

PGV is not produced. It may be dropped from the study, so nothing downstream
should depend on it yet.

What it runs over, and for which realisations, comes from ``config.py`` beside
it.
"""

import sys

import numpy as np

from landloss.common.utils.raster import bbox_in_crs
from landloss.common.utils.terrain import cell_size, write_raster
from landloss.domain import constants
from landloss.hazard.realisation import realisation_seed
from landloss.hazard.shaking.pga import BETA_PGA_COV, beta_pga_realisation
from landloss.io.area_of_interest import SMALL_WLG_PILOT, get_study_areas
from landloss.io.nlm import get_nlm_scenario_pga_2500yr_site_class_5
from scripts.landloss.hazard.shaking.steps.s1_pga_realisation import config
from scripts.landloss.paths import TEMP_DIR

# Wellington place names are macronised, which the default cp1252 Windows
# console cannot encode, so printing one raises without this.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORK_DIR = TEMP_DIR / "hazard" / "shaking"
OUT_STEM = "beta-pga"

# The stream this step draws from. One name per hazard, so realisation 3's
# shaking belongs to the same modelled earthquake as its liquefaction.
RNG_STREAM = "shaking"

RULE = "-" * 72


def pga_path(realisation_id, *, pilot):
    """Return the file a run writes one realisation's PGA field to.

    Args:
        realisation_id: Which modelled earthquake this is.
        pilot: Whether the run is over the pilot box.

    Returns:
        The output path, under ``temp/hazard/shaking/``.
    """
    suffix = "-pilot" if pilot else ""
    return WORK_DIR / f"{OUT_STEM}-r{realisation_id:03d}{suffix}.tif"


def resolve_extent(*, pilot):
    """Return the bounding box and its name for this run."""
    if pilot:
        return SMALL_WLG_PILOT.bbox(constants.DEFAULT_CRS), "Small Wellington pilot"
    areas = get_study_areas(constants.DEFAULT_CRS)
    return tuple(areas.total_bounds), "Four territorial authorities"


def clip_to_extent(grid, bbox):
    """Clip the supplied grid to the extent, in its own CRS, then reproject."""
    native = bbox_in_crs(bbox, constants.DEFAULT_CRS, grid.rio.crs)
    clipped = grid.rio.clip_box(*native, allow_one_dimensional_raster=True)
    if str(clipped.rio.crs) != str(constants.DEFAULT_CRS):
        clipped = clipped.rio.reproject(constants.DEFAULT_CRS)
    return clipped


def describe_grid(name, grid, resolution):
    """Print the field the realisations are drawn from."""
    values = grid.values
    finite = values[np.isfinite(values)]
    print(RULE)
    print(f"Extent: {name}, as far as the NLM release reaches")
    print(f"Grid: {grid.shape[0]} by {grid.shape[1]} cells at {resolution:.0f} m")
    print(f"  {grid.size:,} cells, {finite.size:,} of them carrying a PGA")
    if finite.size:
        print(
            f"  PGA (g): min {finite.min():.3f}   median {np.median(finite):.3f}   "
            f"max {finite.max():.3f}"
        )
    print(f"Spread put on it: {BETA_PGA_COV:.0%} coefficient of variation")


def main(*, pilot, realisation_ids):
    """Write a PGA field per realisation.

    Args:
        pilot: Whether to clip to the small Wellington pilot box.
        realisation_ids: Which modelled earthquakes to draw.
    """
    bbox, extent_name = resolve_extent(pilot=pilot)

    print("Reading the NLM PGA grid ...", flush=True)
    supplied = clip_to_extent(get_nlm_scenario_pga_2500yr_site_class_5(), bbox)
    describe_grid(extent_name, supplied, cell_size(supplied))

    for realisation_id in realisation_ids:
        rng = realisation_seed(constants.BASE_SEED, realisation_id, RNG_STREAM)
        field, factor = beta_pga_realisation(supplied, rng)
        values = field.values
        finite = values[np.isfinite(values)]

        print(RULE)
        print(f"Realisation {realisation_id}, stream {RNG_STREAM!r}")
        print(f"  scaled by {factor:.4f}")
        if finite.size:
            print(f"  median PGA {np.median(finite):.3f} g, max {finite.max():.3f} g")

        out_path = pga_path(realisation_id, pilot=pilot)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_raster(field, out_path)
        print(f"Wrote {out_path}")

    print(RULE)
    print(
        "The grid is the NLM's site class 5 field and the spread is one factor "
        "over the whole extent, so every property shakes as the same ground and "
        "moves together. Both are beta shortcuts."
    )


if __name__ == "__main__":
    main(pilot=config.PILOT, realisation_ids=config.REALISATION_IDS)
