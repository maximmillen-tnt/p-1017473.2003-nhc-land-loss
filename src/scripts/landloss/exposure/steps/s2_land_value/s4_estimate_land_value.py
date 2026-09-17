"""Estimate a land value for every address in the spine.

Takes the address spine from step 1, tags each address as flat or hill against
the National Liquefaction Model's flatland layer, and spreads each territorial
authority's published average residential land value across its addresses in
proportion to a landform multiplier. A per-TA normalising constant pulls the
modelled mean back onto the published average, so the landform judgement moves
value between properties without changing what any authority is worth in total.
That is what the per-TA table this run prints is there to show.

    uv run --frozen python src/scripts/landloss/exposure/steps/s2_land_value/s4_estimate_land_value.py

The script is numbered s4 within this step, not s1, because terrain,
accessibility and amenity are s1 to s3 of the same step in later phases. Land
value is the only one of the four that Phase 1 models, so the gap in the numbers
is deliberate and the later scripts drop into it without anything being renamed.

Phase 1 classifies only hill and flat. The elevated flat class -- flat land
raised above the surrounding floodplain -- has a factor in the land value asset
and is read by the model, but nothing assigns it, because separating it from
ordinary flat land needs the DEM that arrives in Phase 2.

The address spine is rebuilt from LINZ if it is not already on disk, so this can
be run on its own. Pass --pilot to work over the small Wellington box.

Requires TNT_KOORDINATES_API_KEY in .env for the flatland layer, and LINZ_API_KEY
if the address spine has to be rebuilt.
"""

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import requests

from landloss.domain import constants
from landloss.exposure.addresses import get_addresses
from landloss.exposure.land_value import (
    COMMON_VALUATION_DATE,
    estimate_land_value,
    index_base_rates,
    load_base_rates,
    load_factors,
    summarise_by_suburb,
)
from landloss.exposure.landform import (
    LANDFORM_COLUMN,
    classify_landform,
    get_flatland,
)
from landloss.io.area_of_interest import SMALL_WLG_PILOT, get_study_areas

# Wellington suburb names are macronised -- Ōwhiro Bay, Pāuatahanui -- which the
# default cp1252 Windows console cannot encode, so printing one raises. Ask for
# UTF-8 rather than stripping the macrons, because the names are worth getting
# right.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Repo root, from src/scripts/landloss/exposure/steps/s2_land_value/ -- six
# levels up. Printed by every run, because a miscounted parents[N] silently
# writes the outputs somewhere nobody looks for them.
REPO_ROOT = Path(__file__).resolve().parents[6]

# temp/ is gitignored. These are working layers, rebuildable from the source and
# the packaged assets, so they have no business in a diff.
WORK_DIR = REPO_ROOT / "temp" / "exposure"
SPINE_NAME = "address-spine.geoparquet"
PILOT_SPINE_NAME = "address-spine-pilot.geoparquet"
OUT_NAME = "land-value-by-address.geoparquet"
PILOT_OUT_NAME = "land-value-by-address-pilot.geoparquet"
COHORTS_NAME = "land-value-by-suburb.csv"
PILOT_COHORTS_NAME = "land-value-by-suburb-pilot.csv"

SUBURB_LIMIT = 10
RULE = "-" * 72


def get_spine(path, bbox, clip_to, *, use_cache):
    """Read the address spine from disk, or build it from LINZ if it is absent.

    Args:
        path: The geoparquet step 1 writes.
        bbox: The extent to read, if the spine has to be rebuilt.
        clip_to: The boundary to cut a rebuilt spine back to.
        use_cache: Whether to use the extent cache when rebuilding.

    Returns:
        The address spine.
    """
    if path.exists():
        print(f"Reading the address spine from {path} ...")
        return gpd.read_parquet(path)

    # Rebuilt rather than refused, so that this script runs on a clean checkout.
    # It is written back out to the step 1 path, so the next run of either script
    # finds it there.
    print(f"No address spine at {path}; rebuilding it from LINZ ...")
    spine = get_addresses(
        bbox=bbox, crs=constants.DEFAULT_CRS, clip_to=clip_to, use_cache=use_cache
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    spine.to_parquet(path)
    print(f"Wrote the rebuilt spine to {path}")
    return spine


def describe_landform(classified):
    """Print the flat/hill split, which is the only judgement input to the model."""
    print(RULE)
    print("Landform classification")
    print(f"{'Territorial authority':<24}{'Flat':>10}{'Hill':>10}{'Flat %':>10}")

    grouped = classified.groupby("territorial_authority", sort=True)
    for ta_name, rows in grouped:
        counts = rows[LANDFORM_COLUMN].value_counts()
        flat = int(counts.get("flat", 0))
        hill = int(counts.get("hill", 0))
        share = 100 * flat / (flat + hill) if flat + hill else 0.0
        print(f"{ta_name:<24}{flat:>10,}{hill:>10,}{share:>9.1f}%")


def describe_calibration(valued, base_rates):
    """Print the modelled TA mean against the published average it is anchored on.

    This is the table that makes the normalisation visible. If a modelled mean
    does not equal the indexed published average, the clip bound every address in
    that authority and the residual had nowhere to go -- which means the clip
    multiples and the landform factors in the asset disagree with each other.
    """
    indexed = index_base_rates(base_rates).set_index("ta_name")

    print(RULE)
    print(
        f"Calibration against the published averages, indexed to {COMMON_VALUATION_DATE}"
    )
    print(
        f"{'Territorial authority':<24}{'Addresses':>11}"
        f"{'Modelled mean':>16}{'Published':>14}{'Diff':>9}"
    )

    grouped = valued.groupby("territorial_authority", sort=True)
    for ta_name, rows in grouped:
        modelled = float(rows["land_value_nzd"].mean())
        published = float(indexed.loc[ta_name, "indexed_land_value_nzd"])

        # Relative rather than absolute, because a few dollars on a $621,000
        # average is floating point and several thousand is a broken clip. The
        # zero is normalised because an exact hit lands on -0.0 as often as 0.0,
        # and a minus sign in front of the number that proves the calibration
        # worked reads like a fault.
        diff = round(100 * (modelled - published) / published, 2)
        diff = 0.0 if diff == 0 else diff
        print(
            f"{ta_name:<24}{len(rows):>11,}"
            f"{modelled:>16,.0f}{published:>14,.0f}{diff:>8.2f}%"
        )


def describe_suburbs(cohorts, limit=SUBURB_LIMIT):
    """Print the highest and lowest value suburbs by modelled rate."""
    ranked = cohorts.sort_values("median_land_rate_nzd_per_m2", ascending=False)

    # A pilot produces fewer cohorts than the two tables would show between them,
    # and printing the same rows twice under two headings reads like a bug rather
    # than like a short list. So below that many, the whole thing is printed once.
    if len(ranked) <= 2 * limit:
        tables = [(f"All {len(ranked)} suburb cohorts by median land rate", ranked)]
    else:
        tables = [
            (f"Top {limit} suburb cohorts by median land rate", ranked.head(limit)),
            (f"Bottom {limit} suburb cohorts by median land rate", ranked.tail(limit)),
        ]

    for heading, rows in tables:
        print(RULE)
        print(heading)
        print(f"{'Suburb':<28}{'TA':<18}{'Landform':<14}{'Rate $/m2':>11}{'Count':>9}")
        for _, row in rows.iterrows():
            print(
                f"{row['suburb_locality']!s:<28}"
                f"{row['territorial_authority']!s:<18}"
                f"{row[LANDFORM_COLUMN]!s:<14}"
                f"{row['median_land_rate_nzd_per_m2']:>11,.0f}"
                f"{row['address_count']:>9,}"
            )


def parse_args():
    """Read the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="Use the small Wellington pilot box instead of the full study area.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore the extent cache and re-read from the source layers.",
    )
    parser.add_argument(
        "--spine",
        type=Path,
        default=None,
        help=(
            f"The address spine from step 1. Defaults to {WORK_DIR / SPINE_NAME}, "
            f"or to {WORK_DIR / PILOT_SPINE_NAME} under --pilot. Rebuilt from "
            "LINZ if it is not there."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            f"Where to write the valued addresses. Defaults to "
            f"{WORK_DIR / OUT_NAME}, or to {WORK_DIR / PILOT_OUT_NAME} under "
            "--pilot."
        ),
    )
    parser.add_argument(
        "--cohorts",
        type=Path,
        default=None,
        help=(
            f"Where to write the per-suburb cohort table. Defaults to "
            f"{WORK_DIR / COHORTS_NAME}, or to {WORK_DIR / PILOT_COHORTS_NAME} "
            "under --pilot."
        ),
    )
    return parser.parse_args()


def resolve_outputs(args):
    """Choose where the spine is read from and where the two outputs are written.

    Resolved here rather than as argparse defaults, so that a pilot run cannot
    overwrite the full outputs with a few streets of Wellington and leave
    everything downstream reading them without noticing.

    Args:
        args: The parsed command line.

    Returns:
        The spine path, the valued address path and the cohort table path.
    """
    spine_path = args.spine or WORK_DIR / (
        PILOT_SPINE_NAME if args.pilot else SPINE_NAME
    )
    out = args.out or WORK_DIR / (PILOT_OUT_NAME if args.pilot else OUT_NAME)
    cohorts_out = args.cohorts or WORK_DIR / (
        PILOT_COHORTS_NAME if args.pilot else COHORTS_NAME
    )
    return spine_path, out, cohorts_out


def resolve_extent(study_areas, *, pilot):
    """Return the bounding box, clip boundary and name of the extent to run over.

    The clip matters as much as the box. The four authorities sit in a rectangle
    that also contains most of the Wairarapa, so the full run is cut back to the
    real boundaries; a pilot is a rectangle already and needs no clip.
    """
    if pilot:
        return SMALL_WLG_PILOT.bbox(constants.DEFAULT_CRS), None, SMALL_WLG_PILOT.name

    bbox = tuple(float(value) for value in study_areas.total_bounds)
    return bbox, study_areas, ", ".join(study_areas["name"])


def describe_extent(name, bbox):
    """Print the extent being read, so a mistaken study area is obvious at once."""
    minx, miny, maxx, maxy = bbox

    print(RULE)
    print(f"Repo root : {REPO_ROOT}")
    print(f"Extent    : {name}")
    print(f"  NZTM    : {minx:,.0f}, {miny:,.0f} to {maxx:,.0f}, {maxy:,.0f}")
    print(f"  Size    : {(maxx - minx) / 1000:.1f} x {(maxy - miny) / 1000:.1f} km")
    print()


def read_spine(path, bbox, clip_to, *, use_cache):
    """Read or rebuild the spine, or print why it could not be had and return None."""
    try:
        return get_spine(path, bbox, clip_to, use_cache=use_cache)
    except ValueError as exc:
        # Raised by resolve_api_key when LINZ_API_KEY is missing.
        print(f"\nCould not build the address spine: {exc}")
        return None
    except requests.exceptions.RequestException as exc:
        print(f"\nThe request to LINZ failed: {exc}")
        return None


def read_flatland(bbox, clip_to, *, use_cache):
    """Read the flatland layer, or print why it could not be read and return None."""
    try:
        return get_flatland(
            bbox=bbox,
            crs=constants.DEFAULT_CRS,
            clip_to=clip_to,
            use_cache=use_cache,
        )
    except ValueError as exc:
        # Raised by resolve_api_key when TNT_KOORDINATES_API_KEY is missing.
        print(f"\nCould not read the flatland layer: {exc}")
        return None
    except requests.exceptions.RequestException as exc:
        print(f"\nThe request to Koordinates failed: {exc}")
        print(
            "\nThe NLM flatland layer is a national export, so the first request "
            "takes\nmany minutes to build server side and an occasional status poll "
            "returns a\n502 during that wait, which ttpy treats as fatal. Re-running "
            "starts the\nwait over; the export usually completes regardless."
        )
        return None


def write_outputs(valued, cohorts, out, cohorts_out):
    """Write the valued addresses and the cohort table, and print what was written."""
    out.parent.mkdir(parents=True, exist_ok=True)
    valued.to_parquet(out)

    cohorts_out.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel on Windows opens the macronised suburb names correctly
    # rather than mangling them; plain utf-8 is read as cp1252 on a double click.
    cohorts.to_csv(cohorts_out, index=False, encoding="utf-8-sig")

    print(RULE)
    print(f"Wrote {out}")
    print(f"  Rows    : {len(valued):,}")
    print(f"  Columns : {', '.join(valued.columns)}")
    print(f"Wrote {cohorts_out}")
    print(f"  Rows    : {len(cohorts):,} suburb/landform cohorts")


def main():
    args = parse_args()
    spine_path, out, cohorts_out = resolve_outputs(args)

    study_areas = get_study_areas(constants.DEFAULT_CRS)
    bbox, clip_to, extent_name = resolve_extent(study_areas, pilot=args.pilot)
    describe_extent(extent_name, bbox)

    spine = read_spine(spine_path, bbox, clip_to, use_cache=not args.fresh)
    if spine is None:
        return 1
    if spine.empty:
        print("\nThe address spine is empty; there is nothing to value.")
        return 1

    print(f"Addresses in the spine: {len(spine):,}")
    print("\nReading the NLM flatland layer ...")
    flatland = read_flatland(bbox, clip_to, use_cache=not args.fresh)
    if flatland is None:
        return 1

    print(f"Flatland polygons: {len(flatland):,}")

    classified = classify_landform(spine, flatland)
    describe_landform(classified)

    base_rates = load_base_rates()
    factors = load_factors()
    valued = estimate_land_value(classified, base_rates=base_rates, factors=factors)
    describe_calibration(valued, base_rates)

    cohorts = summarise_by_suburb(valued)
    describe_suburbs(cohorts)

    write_outputs(valued, cohorts, out, cohorts_out)
    return 0


if __name__ == "__main__":
    status = main()
    if status:
        raise SystemExit(status)
