r"""Build the Canterbury observed land damage database.

Joins NHC's Canterbury earthquake sequence loss records to two National
Liquefaction Model layers -- the mapped land damage observations, and the
modelled LSN grid -- giving one row per insured property per event carrying the
land damage settled, the damage category surveyed on the ground, and the LSN the
model puts at that location.

    uv run --frozen python src/scripts/landloss/vul/steps/s1_ces_observed_damage/gen_observed_damage_db.py

This is the only New Zealand dataset holding both settled land claims and mapped
land damage, so it is what the Wellington land damage relationships are
calibrated against. The figure it feeds is drawn by
``src/scripts/landloss/vul/report/fig_land_damage_v_lsn.py``.

Run ``gen_ces_loss_data.py`` in ``../../static_data_gen`` first; this step reads
the GeoPackage that script writes rather than the source CSV.

Everything it reads lives on T:, so it only runs where that drive is mapped.
Its output is written through ``landloss.io.versioned_store.save_vul``, so it
respects ``DATA_VERSION`` and local-only working mode rather than a fixed T:
path.
"""

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import is_empty, is_missing

from landloss.domain import constants
from landloss.io import versioned_store

# The loss data NHC supplied, geocoded by ../../static_data_gen/gen_ces_loss_data.py.
LOSS_DIR = Path(
    r"T:\Auckland\Projects\1017473\1017473.2003\SourceMaterial\CHC-loss-data-from-NHC"
)
LOSS_FP = LOSS_DIR / "ces_loss_data_with_geometry.gpkg"

# The National Liquefaction Model's versioned core releases. The observations and
# the LSN grids come from different releases on purpose -- see the comments on
# NLM_OBS_VERSION in landloss.domain.constants.
NLM_CORE_DIR = Path(
    r"T:\Auckland\Projects\1017473\WorkingMaterial\new_versioned_releases\core"
)
OBS_DIR = (
    NLM_CORE_DIR / constants.NLM_OBS_VERSION / "fragility" / "event_obs_buffered_no_map"
)
LSN_DIR = NLM_CORE_DIR / constants.NLM_VERSION / "scenario" / "historic"

# Where the database is written: this project's own versioned data store
# (see landloss.io.versioned_store), not a hardcoded T: path. Derived data,
# and large, so it lives with the project's working material rather than in
# the repository.
OUT_SUB_DIRS = ["ces_observed_damage"]
OUT_NAME = "observed_damage_db.parquet"

# The NHC loss columns, Title Case in the source, mapped to snake_case. Taken
# from COLUMN_MAPPINGS in the National Liquefaction Model loss repository so the
# two studies name the same field the same way.
COLUMN_MAPPINGS = {
    "Event Name": "event_name",
    "Event Date": "event_date",
    "Loss Date": "loss_date",
    "qpid": "qpid",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "BuildingExposure": "building_exposure",
    "LandExposure": "land_exposure",
    "BuildingApportionment": "building_apportionment",
    "BuildingAssessment": "building_assessment",
    "LandAssessment": "land_assessment",
    "BuildingPaid": "building_paid",
    "RepairPaid": "repair_paid",
    "LandPaid": "land_paid",
    "BuildingSource": "building_source",
    "LandSource": "land_source",
    "BestBuildingLossEstimateForClaim": "best_building_loss_estimate_for_claim",
}

# Dollar amounts, which arrive as strings carrying "$", thousands separators and
# a bare "-" for nil. Summed when several claims share a property and an event.
MONEY_COLUMNS = (
    "building_assessment",
    "land_assessment",
    "building_paid",
    "repair_paid",
    "land_paid",
    "best_building_loss_estimate_for_claim",
)

# The five standardised land damage categories, worst last. The rank is what
# decides the category where a property falls inside more than one observation
# polygon; "Unknown" ranks below everything so a known category always wins.
UNKNOWN = "Unknown"
NONE_OBSERVED = "None Observed"
MINOR = "Minor"
MODERATE = "Moderate"
MAJOR_PLUS = "Major +"

DAMAGE_RANKS = {
    UNKNOWN: -1,
    NONE_OBSERVED: 0,
    MINOR: 1,
    MODERATE: 2,
    MAJOR_PLUS: 3,
}

# The observation layers were mapped by several teams over six years and their
# ``dissolve_col`` vocabularies never converged: numeric severity codes for one
# event, damage descriptions for another, liquefaction classes for the third.
# Ported from OBS_HAZ_MAP in the National Liquefaction Model loss repository,
# including its "Unkown" typo key, which is a real value in the source.
#
# One deliberate difference: that map sends a raw "Minor" to "None Observed"
# while sending the numeric code "2" to "Minor", so the same damage is reported
# differently depending on which event mapped it. Here "Minor" stays Minor.
OBS_HAZ_MAP = {
    "1": NONE_OBSERVED,
    "2": MINOR,
    "3": MODERATE,
    "4": MAJOR_PLUS,
    "5": MAJOR_PLUS,
    "6": MAJOR_PLUS,
    NONE_OBSERVED: NONE_OBSERVED,
    MINOR: MINOR,
    MODERATE: MODERATE,
    "Major": MAJOR_PLUS,
    "Severe": MAJOR_PLUS,
    "Very Severe": MAJOR_PLUS,
    "noliq_cov": NONE_OBSERVED,
    "No Visible Damage Observed": NONE_OBSERVED,
    "Liquefaction Ejecta": MODERATE,
    "Observed Water": NONE_OBSERVED,
    "Liquefaction": MODERATE,
    "No Liquefaction": NONE_OBSERVED,
    "RoadWorks": NONE_OBSERVED,
    "Lateral Spreading": MAJOR_PLUS,
    "Unknown": UNKNOWN,
    "Unkown": UNKNOWN,
    "borderline": UNKNOWN,
}

# Columns the layers are expected to carry, checked before any join so a renamed
# source fails with a readable message rather than deep inside geopandas.
OBS_CATEGORY_COLUMN = "dissolve_col"
OBS_LIQ_COLUMN = "liq_cats"
LSN_COLUMN = "p50"

# The February 2016 observations hold classes beyond liquefaction presence, which
# the National Liquefaction Model excludes. Kept out for the same reason here:
# the rest describe something other than land damage.
CHCH16_LIQ_CLASSES = frozenset({"Liquefaction", "No Liquefaction"})

# The observation files are named for the event as the mapping teams knew it, and
# the correspondence is not guessable: CESSept is Darfield, CESFeb is February
# 2011, CHCH16 is February 2016.
EVENTS = {
    "darfield": {
        "loss_name": "Christchurch 30km W, 10km, 7.1",
        "obs": "CESSept_buffered.parquet",
        "lsn": "darfield_2010__earthquake_lsn_pl50.parquet",
        "label": "Darfield, September 2010",
    },
    "chch_feb_2011": {
        "loss_name": "Christchurch 10km SE, 5km, 6.3",
        "obs": "CESFeb_buffered.parquet",
        "lsn": "christchurch__feb_2011__earthquake_lsn_pl50.parquet",
        "label": "Christchurch, February 2011",
    },
    "chch_feb_2016": {
        "loss_name": "Christchurch 15km E, 15km, 5.7",
        "obs": "CHCH16_buffered.parquet",
        "lsn": "christchurch__feb_2016__earthquake_lsn_pl50.parquet",
        "label": "Christchurch, February 2016",
    },
}

# The LSN layer is a grid of node points at 50 m spacing. Buffering each node to
# a 50 m square recovers the cell it stands for, which a radial search would not.
LSN_CELL_HALF_WIDTH_M = 50

OUTPUT_COLUMNS = [
    "qpid",
    "simple_event_name",
    "lsn_p50",
    "observed_land_damage_category",
    "land_assessment",
    "land_paid",
    "building_assessment",
    "building_paid",
    "repair_paid",
    "best_building_loss_estimate_for_claim",
    "n_claims",
    "geometry",
]

RULE = "-" * 72


def require_columns(frame, columns, source):
    """Fail early, and by name, when a source layer is not what was expected.

    Args:
        frame: The layer just read.
        columns: The column names the rest of the script relies on.
        source: What to call the layer in the error message.

    Raises:
        ValueError: If any of the columns is absent.
    """
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        msg = (
            f"{source} is missing {', '.join(missing)}. "
            f"It carries: {', '.join(str(column) for column in frame.columns)}"
        )
        raise ValueError(msg)


def to_money(values):
    """Turn the source's dollar strings into floats.

    The amounts come through as text carrying a currency symbol, thousands
    separators and a bare "-" where the amount is nil. Values already numeric --
    which is what a GeoPackage round trip can give back -- are passed through.

    Args:
        values: One dollar column.

    Returns:
        The same column as floats, with nil and blank as NaN.
    """
    if pd.api.types.is_numeric_dtype(values):
        return values.astype("float64")

    cleaned = values.astype("string").str.replace(r"[$,]", "", regex=True).str.strip()
    # A lone "-" means nil, but a leading minus on a number is a real credit, so
    # only the bare dash is blanked.
    cleaned = cleaned.replace({"-": None, "": None})
    return pd.to_numeric(cleaned, errors="coerce").astype("float64")


def get_losses(path):
    """Read the geocoded loss records and reduce them to one row per property-event.

    Args:
        path: The GeoPackage written by ``gen_ces_loss_data.py``.

    Returns:
        One row per ``(qpid, simple_event_name)``, dollar columns summed, with an
        ``n_claims`` count of how many records went into each.
    """
    losses = gpd.read_file(path)
    print(f"Read {len(losses):,} loss records from {path.name}")

    # Some headers in the source CSV carry stray whitespace, which survives into
    # the GeoPackage.
    losses.columns = [str(column).strip() for column in losses.columns]
    require_columns(losses, ["Event Name", "qpid"], str(path))
    losses = losses.rename(columns=COLUMN_MAPPINGS)

    event_names = {event["loss_name"]: name for name, event in EVENTS.items()}
    losses["simple_event_name"] = losses["event_name"].map(event_names)
    unmatched = int(losses["simple_event_name"].isna().sum())
    losses = losses.loc[losses["simple_event_name"].notna()]
    print(f"  dropped {unmatched:,} records outside the three modelled events")

    for column in MONEY_COLUMNS:
        if column in losses.columns:
            losses[column] = to_money(losses[column])

    # A QPID is NHC's property identifier. Null and non-positive values are
    # placeholders rather than properties, and cannot be aggregated on.
    qpid = pd.to_numeric(losses["qpid"], errors="coerce")
    valid_qpid = qpid.notna() & qpid.gt(0)
    print(f"  dropped {int((~valid_qpid).sum()):,} records with no usable QPID")
    losses = losses.loc[valid_qpid]
    losses["qpid"] = qpid.loc[valid_qpid].astype("int64")

    # Tested at the shapely level rather than with GeoSeries.notna, which warns
    # when the series holds empty geometry -- and that is one of the cases being
    # looked for here.
    geometries = losses.geometry.to_numpy()
    located = ~is_missing(geometries) & ~is_empty(geometries)
    print(f"  dropped {int((~located).sum()):,} records with no usable location")
    losses = losses.loc[located]

    # Aggregate before joining, so a property with forty claims is joined once
    # rather than forty times. Its claims all sit at the same point, so taking
    # the first geometry loses nothing.
    money = [column for column in MONEY_COLUMNS if column in losses.columns]
    aggregated = losses.groupby(["qpid", "simple_event_name"], as_index=False).agg(
        **{column: (column, "sum") for column in money},
        n_claims=("qpid", "size"),
        geometry=("geometry", "first"),
    )
    properties = gpd.GeoDataFrame(aggregated, geometry="geometry", crs=losses.crs)
    print(f"  aggregated to {len(properties):,} property-event rows")
    return properties.to_crs(constants.DEFAULT_CRS)


def get_observed_damage(path):
    """Read one event's buffered land damage observations.

    Args:
        path: The buffered observation parquet for the event.

    Returns:
        The observation polygons carrying a single
        ``observed_land_damage_category`` column, in NZTM.
    """
    observations = gpd.read_parquet(path)
    require_columns(observations, [OBS_CATEGORY_COLUMN], str(path))

    # February 2016 was mapped as liquefaction presence rather than as damage
    # severity, alongside classes describing something else entirely.
    if OBS_LIQ_COLUMN in observations.columns:
        observations = observations.loc[
            observations[OBS_LIQ_COLUMN].isin(CHCH16_LIQ_CLASSES)
        ]

    categories = observations[OBS_CATEGORY_COLUMN].astype("string").map(OBS_HAZ_MAP)
    unmapped = sorted(
        set(observations.loc[categories.isna(), OBS_CATEGORY_COLUMN].dropna().unique())
    )
    if unmapped:
        # Not fatal: an unrecognised class is better reported and left out than
        # silently folded into one of the five categories.
        print(f"  {len(unmapped)} unmapped observation classes: {', '.join(unmapped)}")

    observations = observations.assign(observed_land_damage_category=categories)
    observations = observations.loc[categories.notna()]
    return observations[["observed_land_damage_category", "geometry"]].to_crs(
        constants.DEFAULT_CRS
    )


def assign_observed_damage(properties, observations):
    """Attach the observed damage category to each property.

    Where a property falls inside several observation polygons the worst category
    wins. The alternative -- keeping whichever match happens to come last, which
    is what the National Liquefaction Model's build does -- reports a property
    inside both a "None Observed" and a "Lateral Spreading" polygon as undamaged
    about half the time.

    Args:
        properties: One row per property-event, points in NZTM.
        observations: Observation polygons carrying the category.

    Returns:
        A copy of ``properties`` with ``observed_land_damage_category`` added.
    """
    matches = gpd.sjoin(
        properties[["geometry"]], observations, how="left", predicate="intersects"
    )
    ranks = matches["observed_land_damage_category"].map(DAMAGE_RANKS)
    worst = ranks.groupby(level=0).max()

    rank_categories = {rank: category for category, rank in DAMAGE_RANKS.items()}
    categories = worst.map(rank_categories).reindex(properties.index)
    return properties.assign(observed_land_damage_category=categories)


def assign_lsn(properties, lsn_path):
    """Attach the modelled median LSN to each property.

    Args:
        properties: One row per property-event, points in NZTM.
        lsn_path: The event's LSN grid parquet.

    Returns:
        A copy of ``properties`` with ``lsn_p50`` added, NaN outside the grid.
    """
    lsn = gpd.read_parquet(lsn_path)
    require_columns(lsn, [LSN_COLUMN], str(lsn_path))
    lsn = lsn[[LSN_COLUMN, "geometry"]].to_crs(constants.DEFAULT_CRS)

    cells = lsn.buffer(LSN_CELL_HALF_WIDTH_M, cap_style="square").to_frame("geometry")
    matches = gpd.sjoin(
        properties[["geometry"]], cells, how="left", predicate="intersects"
    )

    # A point on a cell boundary intersects both neighbours, so take the higher
    # of the two rather than letting the row be duplicated.
    values = matches["index_right"].map(lsn[LSN_COLUMN])
    highest = values.groupby(level=0).max().reindex(properties.index)
    return properties.assign(lsn_p50=highest.astype("float64"))


def build_observed_damage_db(loss_fp=LOSS_FP, obs_dir=OBS_DIR, lsn_dir=LSN_DIR):
    """Join the loss records to the observations and the LSN grid, event by event.

    Args:
        loss_fp: The geocoded loss GeoPackage.
        obs_dir: Directory holding the buffered observation parquets.
        lsn_dir: Directory holding the per-event LSN grid parquets.

    Returns:
        One row per property-event, carrying :data:`OUTPUT_COLUMNS`.
    """
    properties = get_losses(loss_fp)

    joined = []
    for name, event in EVENTS.items():
        print(f"\n{event['label']}")
        subset = properties.loc[properties["simple_event_name"] == name].copy()
        print(f"  {len(subset):,} properties with a loss record")
        if subset.empty:
            continue

        observations = get_observed_damage(obs_dir / event["obs"])
        subset = assign_observed_damage(subset, observations)
        matched = int(subset["observed_land_damage_category"].notna().sum())
        share = matched / len(subset)
        print(f"  {matched:,} matched an observation polygon ({share:.0%})")

        subset = assign_lsn(subset, lsn_dir / event["lsn"])
        within = int(subset["lsn_p50"].notna().sum())
        print(f"  {within:,} fell inside the LSN grid ({within / len(subset):.0%})")

        joined.append(subset)

    database = pd.concat(joined, ignore_index=True)
    database = gpd.GeoDataFrame(database, geometry="geometry", crs=properties.crs)
    return database[[column for column in OUTPUT_COLUMNS if column in database.columns]]


def describe(database):
    """Print what came out, so the joins can be sanity checked before plotting."""
    print(RULE)
    print(f"{len(database):,} property-event rows")

    print("\nObserved land damage category:")
    counts = database["observed_land_damage_category"].value_counts(dropna=False)
    for category in DAMAGE_RANKS:
        print(f"  {category:<18} {counts.get(category, 0):>9,}")
    unmatched = int(database["observed_land_damage_category"].isna().sum())
    print(f"  {'No observation':<18} {unmatched:>9,}")

    print("\nBy event:")
    print(f"  {'Event':<28} {'Rows':>9} {'Median LSN':>11} {'Land $ sum':>16}")
    for name, event in EVENTS.items():
        subset = database.loc[database["simple_event_name"] == name]
        if subset.empty:
            continue
        median_lsn = subset["lsn_p50"].median()
        median_lsn = 0.0 if np.isnan(median_lsn) else median_lsn
        print(
            f"  {event['label']:<28} {len(subset):>9,}"
            f" {median_lsn:>11.1f}"
            f" {subset['land_assessment'].sum():>16,.0f}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--losses",
        type=Path,
        default=LOSS_FP,
        help="The geocoded loss GeoPackage from gen_ces_loss_data.py.",
    )
    parser.add_argument(
        "--obs-dir",
        type=Path,
        default=OBS_DIR,
        help="Directory holding the buffered land damage observation parquets.",
    )
    parser.add_argument(
        "--lsn-dir",
        type=Path,
        default=LSN_DIR,
        help="Directory holding the per-event LSN grid parquets.",
    )
    args = parser.parse_args()

    for path in (args.losses, args.obs_dir, args.lsn_dir):
        if not path.exists():
            print(f"Cannot reach {path}")
            print("\nEverything this step reads lives on T:. Check the drive is")
            print("mapped, and that gen_ces_loss_data.py has been run.")
            return 1

    print(f"Observations : {constants.NLM_OBS_VERSION}")
    print(f"LSN grids    : {constants.NLM_VERSION}")
    print(RULE)

    database = build_observed_damage_db(
        loss_fp=args.losses, obs_dir=args.obs_dir, lsn_dir=args.lsn_dir
    )
    describe(database)

    versioned_store.save_vul(database, fname=OUT_NAME, sub_dirs=OUT_SUB_DIRS)

    print(RULE)
    print(f"Wrote {OUT_NAME} to the vul versioned data store ({OUT_SUB_DIRS[0]})")
    return 0


if __name__ == "__main__":
    # Only raise on failure. Falling off the end already exits 0, so the shell
    # contract is unchanged, but running this under an IPython or PyCharm console
    # no longer ends in a "SystemExit: 0" traceback that reads like a crash.
    status = main()
    if status:
        raise SystemExit(status)
