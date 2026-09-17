"""Land value per address, anchored on the published rating valuations.

There is no public per-property land value for the study area that can simply be
redistributed, so the value has to be modelled. The model here is deliberately
the simplest one that is defensible: each territorial authority's published QV
average residential land value is spread across its addresses in proportion to a
landform multiplier, and a per-TA normalising constant pulls the modelled mean
back onto the published average.

The normalising constant is the point of the design. It means the engineering
judgement expressed in the landform factors moves value *between* properties and
never changes the total. A reviewer who disagrees with the factors is arguing
about the distribution within a territorial authority, not about whether
Wellington's land is worth what QV says it is worth -- and the aggregate the
client cares about is unaffected by that argument.

The anchors are the published district revaluations:

===============  ====  ==========  ============  ============  ============
Territorial      TA    Valued at   Rating units  Average CV    Average LV
authority        code
===============  ====  ==========  ============  ============  ============
Wellington City  047   2024-09-01  82,591        $1,086,000    $621,000
Lower Hutt City  046   2025-08-01  43,576        $775,000      $415,000
Porirua City     044   2025-09-01  21,481        $830,000      $420,000
Upper Hutt City  045   2025-06-01  18,474        $776,000      $438,000
===============  ====  ==========  ============  ============  ============

Those four dates are not the same, so each average is indexed onto the common
valuation date :data:`COMMON_VALUATION_DATE` before it is used. The index factors
live in the base rates asset alongside the averages, so the published figure and
the adjustment applied to it are both visible in the output rather than one being
silently folded into the other.

Phase 1 only distinguishes hill from flat. The elevated flat factor is carried in
the factors asset and read by this module, but nothing assigns that class yet --
see :mod:`landloss.exposure.landform`.

Two approximations are worth stating plainly, because they bound what any
per-property figure from this module can be used for. The published averages are
*residential* averages applied to every address, and the LINZ address layer has
no residential flag to narrow them with. And lot size is a per-TA median rather
than a measured parcel area, so the rate per square metre is an order-of-
magnitude figure for comparing cohorts, not a valuation of any one property.
"""

from collections.abc import Collection, Sequence
from pathlib import Path

import geopandas as gpd
import pandas as pd

from landloss.domain import constants
from landloss.exposure.landform import ELEVATED_FLAT, FLAT, HILL

# The assets live under landloss.io rather than beside this module, because they
# are inputs that get read rather than code, and landloss.io is where the other
# packaged data files sit.
ASSETS_DIR = Path(__file__).resolve().parents[1] / "io" / "assets"

BASE_RATES_PATH = ASSETS_DIR / "land-value-base-rates.csv"
FACTORS_PATH = ASSETS_DIR / "land-value-factors.csv"

# The date every published average is indexed onto. The four councils revalue on
# their own cycles, so without a common date the TA totals are not comparable.
COMMON_VALUATION_DATE = "2025-09-01"

# The columns an address frame has to carry before it can be valued.
REQUIRED_ADDRESS_COLUMNS = ("territorial_authority", "landform_class")

# The parameter names read out of the factors asset.
LANDFORM_FACTOR_PARAMETERS = {
    HILL: "landform_factor_hill",
    FLAT: "landform_factor_flat",
    ELEVATED_FLAT: "landform_factor_elevated_flat",
}
RATE_CLIP_MIN_PARAMETER = "rate_clip_min_multiple"
RATE_CLIP_MAX_PARAMETER = "rate_clip_max_multiple"


def load_base_rates(path: Path = BASE_RATES_PATH) -> pd.DataFrame:
    """Read the published per-TA rating valuation anchors.

    Args:
        path: The CSV to read. Defaults to the packaged asset.

    Returns:
        A DataFrame with one row per territorial authority, with
        ``valuation_date`` parsed to a ``datetime.date`` and ``ta_code`` kept as
        a string so that its leading zero survives.

    Raises:
        ValueError: If any of the four study area territorial authorities is
            absent, naming the codes that are missing.
    """
    # ta_code is read as text on purpose: the Stats NZ codes are zero padded, and
    # reading "044" as an integer would turn it into 44 and stop it matching
    # STUDY_AREA_TA_CODES.
    base_rates = pd.read_csv(path, dtype={"ta_code": str})

    # An explicit format rather than inference, so that a malformed date in the
    # asset fails here instead of being quietly parsed as something else.
    base_rates["valuation_date"] = pd.to_datetime(
        base_rates["valuation_date"], format="%Y-%m-%d"
    ).dt.date

    missing = sorted(set(constants.STUDY_AREA_TA_CODES) - set(base_rates["ta_code"]))
    if missing:
        named = ", ".join(
            f"{code} ({constants.STUDY_AREA_TA_CODES[code]})" for code in missing
        )
        msg = (
            f"The base rates at {path} are missing the study area territorial "
            f"authority/authorities {named}."
        )
        raise ValueError(msg)

    return base_rates


def load_factors(path: Path = FACTORS_PATH) -> dict[str, float]:
    """Read the land value model parameters.

    The asset is a tall parameter/value/basis table rather than a wide one, so
    that the justification for each number sits on the same row as the number and
    cannot drift away from it.

    Args:
        path: The CSV to read. Defaults to the packaged asset.

    Returns:
        The parameters, keyed by the ``parameter`` column. The ``basis`` column
        is documentation for a human reader and is not returned.
    """
    factors = pd.read_csv(path)
    pairs = zip(factors["parameter"], factors["value"], strict=True)
    return {str(parameter): float(value) for parameter, value in pairs}


def index_base_rates(base_rates: pd.DataFrame) -> pd.DataFrame:
    """Bring every published average onto the common valuation date.

    The source column is left in place rather than overwritten, so that an output
    table shows both the figure the council published and the figure the model
    used, and the step between them stays auditable.

    Args:
        base_rates: The anchors as returned by :func:`load_base_rates`.

    Returns:
        A copy with an ``indexed_land_value_nzd`` column added, holding
        ``avg_land_value_nzd`` multiplied by ``index_to_2025_09``.
    """
    indexed = base_rates.copy()
    indexed["indexed_land_value_nzd"] = (
        indexed["avg_land_value_nzd"] * indexed["index_to_2025_09"]
    )
    return indexed


def solve_normalising_constant(
    factors: Sequence[float] | pd.Series, target_mean: float
) -> float:
    """Return the constant that puts the mean of ``constant * factors`` on target.

    This is the whole normalisation, in one line of arithmetic: because the mean
    is linear, scaling every factor by ``target_mean / mean(factors)`` makes the
    mean of the result exactly ``target_mean``. The constant therefore depends
    only on the *mix* of factors and not on how many addresses carry them --
    doubling the population leaves it unchanged.

    Args:
        factors: The landform multipliers, one per address.
        target_mean: The mean the scaled factors have to average out to, which
            here is a TA's indexed published average land value.

    Returns:
        The normalising constant.

    Raises:
        ValueError: If ``factors`` is empty, or if its mean is not positive.
            Neither has a normalisation, and both mean the factors asset or the
            landform classification is wrong rather than the data being unusual.
    """
    values = [float(factor) for factor in factors]

    if not values:
        msg = (
            "Cannot solve a normalising constant for an empty set of factors: "
            "there is nothing to spread the published average across."
        )
        raise ValueError(msg)

    mean_factor = sum(values) / len(values)
    if mean_factor <= 0:
        msg = (
            f"The mean landform factor is {mean_factor}, but it has to be "
            "positive to normalise against. Check the landform factors asset."
        )
        raise ValueError(msg)

    return target_mean / mean_factor


def _value_one_ta(
    factor: pd.Series, indexed_average: float, lower: float, upper: float
) -> pd.Series:
    """Value the addresses of a single territorial authority.

    Args:
        factor: The landform multiplier for each address in the TA.
        indexed_average: The TA's published average land value, indexed onto the
            common valuation date.
        lower: The smallest land value an address may take.
        upper: The largest land value an address may take.

    Returns:
        The land value of each address, indexed as ``factor`` is. The mean is the
        indexed published average, except in the one case noted below.
    """
    constant = solve_normalising_constant(factor, indexed_average)
    raw = constant * factor
    value = raw.clip(lower=lower, upper=upper)

    # Clipping takes value off the extremes, which drags the TA mean off the
    # published average -- and holding that mean is the entire justification for
    # the model. So the constant is solved a second time, this time across only
    # the addresses the clip did not bind, carrying whatever the clipped
    # addresses gave up or gained. The clipped addresses stay pinned at their
    # bounds, which is what makes the total come out exactly right.
    binding = (raw < lower) | (raw > upper)
    free = ~binding
    free_factor_total = float(factor[free].sum())

    if free_factor_total > 0:
        residual = indexed_average * len(factor) - float(value[binding].sum())
        constant = residual / free_factor_total

        # Re-applied once, not iterated to convergence. Two cases leave the mean
        # slightly off: the re-solve pushing a previously free address onto a
        # bound, and -- handled by the guard above -- every address binding, so
        # there is nobody free to carry the residual. Both need a clip band
        # narrower than the spread of the factors themselves, which means the
        # clip multiples and the factors disagree and one of them is wrong. With
        # the values the study actually runs, nothing binds at all.
        value.loc[free] = (constant * factor[free]).clip(lower=lower, upper=upper)

    return value


def _check_known(values: pd.Series, known: Collection, what: str) -> None:
    """Raise if a column holds a value the model has no parameter for.

    Args:
        values: The column to check.
        known: The keys, index or other container of the values that are known.
        what: What the values are, used in the error message.

    Raises:
        ValueError: If any value is absent from ``known``.
    """
    unknown = sorted(set(values) - set(known))
    if unknown:
        listed = ", ".join(repr(value) for value in unknown)
        expected = ", ".join(repr(value) for value in sorted(known))
        msg = (
            f"The addresses carry {what} value(s) the land value model has no "
            f"parameter for: {listed}. Known: {expected}."
        )
        raise ValueError(msg)


def estimate_land_value(
    addresses: gpd.GeoDataFrame,
    base_rates: pd.DataFrame | None = None,
    factors: dict[str, float] | None = None,
) -> gpd.GeoDataFrame:
    """Put a modelled land value on every address.

    For each territorial authority in turn:

    1. the published average land value is indexed onto
       :data:`COMMON_VALUATION_DATE`;
    2. each address is given the landform multiplier for its class;
    3. a normalising constant is solved so that the scaled multipliers average to
       the indexed published figure;
    4. the resulting values are clipped to the configured multiples of that
       figure, so that no single address is modelled at an absurd value;
    5. the constant is solved once more across the addresses the clip did not
       bind, so that the TA mean still lands on the published average.

    Step 5 is what makes the model arguable-with in a useful way. The landform
    factors are judgement, and judgement moves value from one property to another
    -- but never changes what the territorial authority is worth in total, which
    stays exactly what the council published.

    Args:
        addresses: Address points carrying :data:`REQUIRED_ADDRESS_COLUMNS`, as
            produced by :func:`landloss.exposure.landform.classify_landform`.
        base_rates: The published anchors. Defaults to the packaged asset.
        factors: The model parameters. Defaults to the packaged asset.

    Returns:
        A new GeoDataFrame, re-indexed from zero, with ``land_value_nzd``,
        ``land_rate_nzd_per_m2`` and ``assumed_lot_size_m2`` added. The caller's
        frame is left untouched.

    Raises:
        ValueError: If a required column is absent, if an address carries a
            territorial authority the base rates say nothing about, or if it
            carries a landform class the factors say nothing about. None of the
            three is silently dropped, because an address that vanishes between
            the exposure model and the loss model is an expensive thing to
            notice late.
    """
    missing = [
        column for column in REQUIRED_ADDRESS_COLUMNS if column not in addresses.columns
    ]
    if missing:
        msg = (
            f"The address frame is missing the column(s) {', '.join(missing)}. "
            f"Expected all of: {', '.join(REQUIRED_ADDRESS_COLUMNS)}."
        )
        raise ValueError(msg)

    if base_rates is None:
        base_rates = load_base_rates()
    if factors is None:
        factors = load_factors()

    rates = index_base_rates(base_rates).set_index("ta_name")
    factor_by_class = {
        landform: factors[parameter]
        for landform, parameter in LANDFORM_FACTOR_PARAMETERS.items()
    }

    # A copy, so that nothing written below can reach back into the caller's
    # frame. Re-indexed for the same reason classify_landform re-indexes: the
    # per-TA assignment below addresses rows by label, which needs unique labels.
    valued = addresses.copy().reset_index(drop=True)

    _check_known(valued["territorial_authority"], rates.index, "territorial authority")
    _check_known(valued["landform_class"], factor_by_class, "landform class")

    factor = valued["landform_class"].map(factor_by_class).astype(float)
    land_value = pd.Series(float("nan"), index=valued.index, dtype=float)

    clip_min = factors[RATE_CLIP_MIN_PARAMETER]
    clip_max = factors[RATE_CLIP_MAX_PARAMETER]

    # Grouped rather than vectorised because each TA has its own anchor, its own
    # normalising constant and its own clip bounds; there is no shared scale.
    grouped = valued.groupby("territorial_authority", sort=False)
    for ta_name, rows in grouped.groups.items():
        indexed_average = float(rates.loc[ta_name, "indexed_land_value_nzd"])
        land_value.loc[rows] = _value_one_ta(
            factor.loc[rows],
            indexed_average,
            lower=clip_min * indexed_average,
            upper=clip_max * indexed_average,
        )

    lot_size = valued["territorial_authority"].map(rates["median_lot_size_m2"])
    lot_size = lot_size.astype(float)

    valued["land_value_nzd"] = land_value
    valued["land_rate_nzd_per_m2"] = land_value / lot_size
    valued["assumed_lot_size_m2"] = lot_size

    return valued


def summarise_by_suburb(valued: gpd.GeoDataFrame) -> pd.DataFrame:
    """Reduce valued addresses to the cohort table the Phase 1 tool consumes.

    One row per territorial authority, suburb and landform class. Medians rather
    than means, because within a cohort the interest is in the typical property
    and a handful of clipped extremes should not move the number.

    Args:
        valued: Addresses as returned by :func:`estimate_land_value`, also
            carrying ``suburb_locality``.

    Returns:
        A tidy DataFrame with ``territorial_authority``, ``suburb_locality``,
        ``landform_class``, ``address_count``, ``median_land_value_nzd`` and
        ``median_land_rate_nzd_per_m2``. The geometry is dropped: this is a table
        to read, not a layer to map.
    """
    cohorts = ["territorial_authority", "suburb_locality", "landform_class"]

    # Dropped to a plain DataFrame first, because the geometry has no meaning
    # once rows are pooled into a cohort and carrying it would imply otherwise.
    attributes = pd.DataFrame(
        valued.drop(columns=valued.geometry.name, errors="ignore")
    )

    # dropna=False so that an address with no suburb recorded is reported as its
    # own cohort rather than disappearing out of the totals.
    return (
        attributes.groupby(cohorts, dropna=False, sort=True)
        .agg(
            address_count=("land_value_nzd", "size"),
            median_land_value_nzd=("land_value_nzd", "median"),
            median_land_rate_nzd_per_m2=("land_rate_nzd_per_m2", "median"),
        )
        .reset_index()
    )
