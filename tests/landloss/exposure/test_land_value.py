"""Tests for the land value model.

The assets these functions read by default are written by hand and live under
``src/landloss/io/assets``. Nothing here touches them: every fixture is built in
memory or written to ``tmp_path``, so the tests describe the model rather than
the particular numbers that happen to be in the asset this week.
"""

import datetime

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from landloss.exposure.land_value import (
    estimate_land_value,
    index_base_rates,
    load_base_rates,
    load_factors,
    solve_normalising_constant,
    summarise_by_suburb,
)
from landloss.exposure.landform import FLAT, HILL

# The published QV anchors for the four study area territorial authorities, with
# an index onto the common valuation date. Real figures, so that a number that
# looks wrong in a failure message is recognisable.
ANCHORS = [
    ("044", "Porirua City", "2025-09-01", 21481, 830_000, 420_000, 1.000, 600),
    ("045", "Upper Hutt City", "2025-06-01", 18474, 776_000, 438_000, 1.010, 700),
    ("046", "Lower Hutt City", "2025-08-01", 43576, 775_000, 415_000, 1.005, 550),
    ("047", "Wellington City", "2024-09-01", 82591, 1_086_000, 621_000, 1.020, 450),
]


@pytest.fixture
def base_rates():
    """The published anchors, as load_base_rates would return them."""
    return pd.DataFrame(
        ANCHORS,
        columns=[
            "ta_code",
            "ta_name",
            "valuation_date",
            "rating_units",
            "avg_capital_value_nzd",
            "avg_land_value_nzd",
            "index_to_2025_09",
            "median_lot_size_m2",
        ],
    ).assign(source_url="https://example.invalid/revaluation")


@pytest.fixture
def factors():
    """Model parameters with a clip band wide enough that it never binds."""
    return {
        "landform_factor_hill": 0.85,
        "landform_factor_flat": 1.15,
        "landform_factor_elevated_flat": 1.05,
        "rate_clip_min_multiple": 0.25,
        "rate_clip_max_multiple": 4.0,
    }


def make_addresses(rows: list[tuple[str, str, str]]):
    """Build an address frame from (territorial authority, suburb, landform) rows."""
    return gpd.GeoDataFrame(
        {
            "address_id": list(range(len(rows))),
            "territorial_authority": [row[0] for row in rows],
            "suburb_locality": [row[1] for row in rows],
            "landform_class": [row[2] for row in rows],
        },
        geometry=[Point(index, index) for index in range(len(rows))],
        crs="EPSG:2193",
    )


@pytest.fixture
def addresses():
    """A mixed population: four TAs, differing sizes and differing landform mixes."""
    return make_addresses(
        [
            ("Wellington City", "Kelburn", HILL),
            ("Wellington City", "Kelburn", HILL),
            ("Wellington City", "Kilbirnie", FLAT),
            ("Lower Hutt City", "Petone", FLAT),
            ("Lower Hutt City", "Petone", FLAT),
            ("Lower Hutt City", "Wainuiomata", HILL),
            ("Lower Hutt City", "Wainuiomata", HILL),
            ("Porirua City", "Titahi Bay", FLAT),
            ("Upper Hutt City", "Totara Park", HILL),
        ]
    )


def indexed_average(base_rates: pd.DataFrame, ta_name: str) -> float:
    """Return one TA's published average, indexed onto the common valuation date."""
    indexed = index_base_rates(base_rates).set_index("ta_name")
    return float(indexed.loc[ta_name, "indexed_land_value_nzd"])


# --- reading the assets -------------------------------------------------------


def test_the_base_rates_round_trip_through_a_csv(tmp_path, base_rates) -> None:
    """The anchors are held as a CSV a valuer can open and check against QV."""
    path = tmp_path / "land-value-base-rates.csv"
    base_rates.to_csv(path, index=False)

    loaded = load_base_rates(path)

    assert list(loaded["ta_name"]) == list(base_rates["ta_name"])
    assert list(loaded["avg_land_value_nzd"]) == list(base_rates["avg_land_value_nzd"])


def test_a_ta_code_keeps_its_leading_zero(tmp_path, base_rates) -> None:
    """Porirua is "044"; read as a number it becomes 44 and stops matching."""
    path = tmp_path / "land-value-base-rates.csv"
    base_rates.to_csv(path, index=False)

    loaded = load_base_rates(path)

    assert "044" in set(loaded["ta_code"])


def test_the_valuation_date_is_parsed_to_a_date(tmp_path, base_rates) -> None:
    """The four councils revalue on different dates, so the date has to be usable."""
    path = tmp_path / "land-value-base-rates.csv"
    base_rates.to_csv(path, index=False)

    loaded = load_base_rates(path)

    assert isinstance(loaded["valuation_date"].iloc[0], datetime.date)


def test_a_missing_territorial_authority_is_named(tmp_path, base_rates) -> None:
    """Silently modelling three of the four TAs would understate the whole study."""
    path = tmp_path / "land-value-base-rates.csv"
    base_rates[base_rates["ta_code"] != "045"].to_csv(path, index=False)

    with pytest.raises(ValueError, match="045"):
        load_base_rates(path)


def test_the_factors_load_as_a_plain_mapping_of_floats(tmp_path) -> None:
    """The basis column documents each number for a reader; the model wants floats."""
    path = tmp_path / "land-value-factors.csv"
    pd.DataFrame(
        {
            "parameter": ["landform_factor_hill", "rate_clip_max_multiple"],
            "value": ["0.85", "4"],
            "basis": ["Judgement, hill sections", "Judgement"],
        }
    ).to_csv(path, index=False)

    loaded = load_factors(path)

    assert loaded == {"landform_factor_hill": 0.85, "rate_clip_max_multiple": 4.0}


# --- indexing -----------------------------------------------------------------


def test_indexing_adds_a_column_without_touching_the_published_figure(
    base_rates,
) -> None:
    """A reviewer has to see both what QV published and what the model used."""
    indexed = index_base_rates(base_rates)

    assert list(indexed["avg_land_value_nzd"]) == list(base_rates["avg_land_value_nzd"])
    assert "indexed_land_value_nzd" in indexed.columns


def test_indexing_applies_the_index_factor(base_rates) -> None:
    """Wellington was valued a year early, so its average is carried forward."""
    indexed = index_base_rates(base_rates).set_index("ta_name")

    assert indexed.loc["Wellington City", "indexed_land_value_nzd"] == pytest.approx(
        621_000 * 1.020
    )


def test_indexing_does_not_modify_the_caller_s_frame(base_rates) -> None:
    """Indexing returns a copy, so the anchors can be re-used unchanged."""
    index_base_rates(base_rates)

    assert "indexed_land_value_nzd" not in base_rates.columns


# --- the normalising constant -------------------------------------------------


def test_the_constant_puts_the_mean_on_target() -> None:
    """This is the arithmetic the whole model rests on."""
    constant = solve_normalising_constant([0.85, 1.15], target_mean=500_000)

    assert constant == pytest.approx(500_000 / 1.0)


def test_the_constant_does_not_depend_on_how_many_addresses_there_are() -> None:
    """A TA with more addresses is not worth more per address than a small one."""
    small = solve_normalising_constant([0.85, 1.15], target_mean=500_000)
    large = solve_normalising_constant([0.85] * 500 + [1.15] * 500, 500_000)

    assert large == pytest.approx(small)


def test_the_constant_does_depend_on_the_mix_of_factors() -> None:
    """A TA that is mostly hill has to scale up to reach the same published mean."""
    balanced = solve_normalising_constant([0.85, 1.15], target_mean=500_000)
    hilly = solve_normalising_constant([0.85, 0.85, 0.85, 1.15], 500_000)

    assert hilly > balanced


def test_an_empty_set_of_factors_is_rejected() -> None:
    """There is nothing to spread the published average across, so this is a bug."""
    with pytest.raises(ValueError, match="empty"):
        solve_normalising_constant([], target_mean=500_000)


def test_a_non_positive_mean_factor_is_rejected() -> None:
    """A zero or negative mean means the factors asset is wrong, not the data."""
    with pytest.raises(ValueError, match="positive"):
        solve_normalising_constant([1.0, -1.0], target_mean=500_000)


# --- valuing addresses --------------------------------------------------------


def test_the_mean_value_in_each_ta_is_the_published_average(
    addresses, base_rates, factors
) -> None:
    """The one property the model guarantees: judgement moves value, never totals."""
    valued = estimate_land_value(addresses, base_rates=base_rates, factors=factors)

    means = valued.groupby("territorial_authority")["land_value_nzd"].mean()

    for ta_name, modelled_mean in means.items():
        assert modelled_mean == pytest.approx(indexed_average(base_rates, ta_name))


def test_clipping_does_not_break_the_ta_mean(addresses, base_rates) -> None:
    """The clip is a sanity bound on one address, not a licence to lose value."""
    # A hill factor far enough below the clip floor that every hill address is
    # pushed back up to it, which is what makes the re-solve do some work.
    binding = {
        "landform_factor_hill": 0.20,
        "landform_factor_flat": 1.00,
        "landform_factor_elevated_flat": 1.05,
        "rate_clip_min_multiple": 0.50,
        "rate_clip_max_multiple": 2.00,
    }

    valued = estimate_land_value(addresses, base_rates=base_rates, factors=binding)

    hutt = valued[valued["territorial_authority"] == "Lower Hutt City"]
    assert hutt["land_value_nzd"].mean() == pytest.approx(
        indexed_average(base_rates, "Lower Hutt City")
    )


def test_the_clip_floor_is_respected(addresses, base_rates) -> None:
    """The clip is there so that no single address is modelled at an absurd value."""
    binding = {
        "landform_factor_hill": 0.20,
        "landform_factor_flat": 1.00,
        "landform_factor_elevated_flat": 1.05,
        "rate_clip_min_multiple": 0.50,
        "rate_clip_max_multiple": 2.00,
    }

    valued = estimate_land_value(addresses, base_rates=base_rates, factors=binding)

    hutt = valued[valued["territorial_authority"] == "Lower Hutt City"]
    floor = 0.50 * indexed_average(base_rates, "Lower Hutt City")
    assert hutt["land_value_nzd"].min() >= floor - 1e-6


def test_a_flat_address_is_worth_more_than_a_hill_address_in_the_same_ta(
    base_rates, factors
) -> None:
    """The landform factors are the whole reason two addresses differ in Phase 1."""
    addresses = make_addresses(
        [("Porirua City", "Titahi Bay", FLAT), ("Porirua City", "Titahi Bay", HILL)]
    )

    valued = estimate_land_value(addresses, base_rates=base_rates, factors=factors)

    assert valued["land_value_nzd"].iloc[0] > valued["land_value_nzd"].iloc[1]


def test_the_rate_is_the_value_over_the_assumed_lot_size(
    addresses, base_rates, factors
) -> None:
    """Lot size is a per-TA median, so the rate is reported next to the size it used."""
    valued = estimate_land_value(addresses, base_rates=base_rates, factors=factors)

    expected = valued["land_value_nzd"] / valued["assumed_lot_size_m2"]
    assert valued["land_rate_nzd_per_m2"].tolist() == pytest.approx(expected.tolist())


def test_the_assumed_lot_size_comes_from_the_matching_ta(
    addresses, base_rates, factors
) -> None:
    """A Wellington address must not be sized with Porirua's median section."""
    valued = estimate_land_value(addresses, base_rates=base_rates, factors=factors)

    wellington = valued[valued["territorial_authority"] == "Wellington City"]
    assert set(wellington["assumed_lot_size_m2"]) == {450.0}


def test_a_missing_column_is_named(base_rates, factors) -> None:
    """Failing here beats producing a column of NaN that nobody notices."""
    addresses = make_addresses([("Porirua City", "Titahi Bay", FLAT)]).drop(
        columns=["landform_class"]
    )

    with pytest.raises(ValueError, match="landform_class"):
        estimate_land_value(addresses, base_rates=base_rates, factors=factors)


def test_an_unknown_territorial_authority_is_rejected(base_rates, factors) -> None:
    """Dropping the address would quietly shrink the exposure the study reports."""
    addresses = make_addresses([("Kapiti Coast District", "Paraparaumu", FLAT)])

    with pytest.raises(ValueError, match="Kapiti Coast District"):
        estimate_land_value(addresses, base_rates=base_rates, factors=factors)


def test_an_unknown_landform_class_is_rejected(base_rates, factors) -> None:
    """There is no factor to value it with, and no factor means no defensible value."""
    addresses = make_addresses([("Porirua City", "Titahi Bay", "swamp")])

    with pytest.raises(ValueError, match="swamp"):
        estimate_land_value(addresses, base_rates=base_rates, factors=factors)


def test_an_empty_address_frame_is_handled(base_rates, factors) -> None:
    """A pilot extent can contain no addresses at all, and that is not an error."""
    valued = estimate_land_value(
        make_addresses([]), base_rates=base_rates, factors=factors
    )

    assert len(valued) == 0
    assert "land_value_nzd" in valued.columns


def test_the_input_is_not_modified(addresses, base_rates, factors) -> None:
    """Valuing returns a copy, leaving the caller's frame untouched."""
    estimate_land_value(addresses, base_rates=base_rates, factors=factors)

    assert "land_value_nzd" not in addresses.columns


# --- the cohort table ---------------------------------------------------------


def test_the_summary_has_one_row_per_ta_suburb_and_landform(
    addresses, base_rates, factors
) -> None:
    """These three columns are the cohort the Phase 1 Excel tool is keyed on."""
    valued = estimate_land_value(addresses, base_rates=base_rates, factors=factors)

    summary = summarise_by_suburb(valued)

    cohorts = summary[["territorial_authority", "suburb_locality", "landform_class"]]
    assert len(summary) == len(cohorts.drop_duplicates())


def test_the_summary_counts_every_address(addresses, base_rates, factors) -> None:
    """A cohort table that loses addresses understates the loss built on it."""
    valued = estimate_land_value(addresses, base_rates=base_rates, factors=factors)

    summary = summarise_by_suburb(valued)

    assert summary["address_count"].sum() == len(addresses)


def test_the_summary_reports_the_median_value_and_rate(
    addresses, base_rates, factors
) -> None:
    """Medians, so that a handful of clipped extremes cannot move a cohort."""
    valued = estimate_land_value(addresses, base_rates=base_rates, factors=factors)

    summary = summarise_by_suburb(valued).set_index(
        ["territorial_authority", "suburb_locality", "landform_class"]
    )

    kelburn = valued[valued["suburb_locality"] == "Kelburn"]
    assert summary.loc[
        ("Wellington City", "Kelburn", HILL), "median_land_value_nzd"
    ] == pytest.approx(kelburn["land_value_nzd"].median())


def test_the_summary_is_a_plain_table_without_geometry(
    addresses, base_rates, factors
) -> None:
    """Pooled rows have no location, and carrying geometry would imply they do."""
    valued = estimate_land_value(addresses, base_rates=base_rates, factors=factors)

    summary = summarise_by_suburb(valued)

    assert not isinstance(summary, gpd.GeoDataFrame)
    assert "geometry" not in summary.columns
