import numpy as np
import pandas as pd
import pytest

from landloss.exposure.land import extent
from landloss.loss.claims import (
    CLAIM_ID_COLUMN,
    DWELLING_COUNT_COLUMN,
    dwelling_counts,
)
from landloss.loss.policy import PolicySettings
from landloss.loss.settlement import DamagedClaim, settle

ACT = PolicySettings()


def property_table(counts):
    return pd.DataFrame(
        {
            CLAIM_ID_COLUMN: list(counts),
            DWELLING_COUNT_COLUMN: list(counts.values()),
        }
    )


# ---------------------------------------------------------------------------
# The contract with exposure. The four top-level modules exchange data files
# rather than symbols, so the column names are written out in both places --
# which is exactly why something has to hold them to each other.
# ---------------------------------------------------------------------------


def test_the_column_names_match_what_exposure_writes():
    assert CLAIM_ID_COLUMN == extent.CLAIM_ID_COLUMN
    assert DWELLING_COUNT_COLUMN == extent.DWELLING_COUNT_COLUMN


# ---------------------------------------------------------------------------
# Reading the count.
# ---------------------------------------------------------------------------


def test_counts_come_back_in_the_order_asked_for():
    # Not the order of the property table: the result has to line up with the
    # other arrays the caller is settling.
    table = property_table({"c1": 1, "c2": 4, "c3": 2})
    assert dwelling_counts(["c3", "c1", "c2"], table) == pytest.approx([2.0, 1.0, 4.0])


def test_a_claim_can_be_asked_for_more_than_once():
    table = property_table({"c1": 3})
    assert dwelling_counts(["c1", "c1"], table) == pytest.approx([3.0, 3.0])


def test_properties_not_asked_for_are_ignored():
    table = property_table({"c1": 1, "c2": 9})
    assert dwelling_counts(["c1"], table) == pytest.approx([1.0])


def test_counts_come_back_as_floats_for_the_sub_cap_arithmetic():
    counts = dwelling_counts(["c1"], property_table({"c1": 2}))
    assert counts.dtype == float


def test_an_empty_request_gives_an_empty_result():
    assert len(dwelling_counts([], property_table({"c1": 1}))) == 0


# ---------------------------------------------------------------------------
# What it refuses. Each of these would otherwise reach `settle` as a silently
# wrong multiplier on both sub-caps and the excess.
# ---------------------------------------------------------------------------


def test_a_claim_with_no_count_is_refused_rather_than_defaulted():
    table = property_table({"c1": 1})
    with pytest.raises(ValueError, match="no dwelling count for 'c9'"):
        dwelling_counts(["c1", "c9"], table)


def test_the_refusal_names_the_claims_and_stops_at_five():
    table = property_table({"c1": 1})
    missing = [f"m{i}" for i in range(8)]
    with pytest.raises(ValueError, match="and 3 more"):
        dwelling_counts(missing, table)


def test_a_duplicated_claim_is_refused_as_ambiguous():
    table = pd.DataFrame({CLAIM_ID_COLUMN: ["c1", "c1"], DWELLING_COUNT_COLUMN: [1, 4]})
    with pytest.raises(ValueError, match="more than once"):
        dwelling_counts(["c1"], table)


def test_a_count_below_one_is_refused():
    with pytest.raises(ValueError, match="below one"):
        dwelling_counts(["c1"], property_table({"c1": 0}))


def test_a_missing_column_is_refused():
    table = property_table({"c1": 1}).rename(columns={DWELLING_COUNT_COLUMN: "n"})
    with pytest.raises(ValueError, match="no 'dwelling_count' column"):
        dwelling_counts(["c1"], table)


# ---------------------------------------------------------------------------
# End to end: the count reaches the settlement it is supposed to scale.
# ---------------------------------------------------------------------------


def test_the_count_feeds_straight_into_a_settlement():
    table = property_table({"c1": 1, "c2": 4})
    result = settle(
        DamagedClaim(
            repair_cost_incl_gst_nzd=np.array([500_000.0, 500_000.0]),
            damaged_area_m2=np.array([0.0, 0.0]),
            land_rate_incl_gst_nzd_per_m2=750.0,
            retaining_wall_udv_incl_gst_nzd=np.array([300_000.0, 300_000.0]),
            n_dwellings=dwelling_counts(["c1", "c2"], table),
        ),
        policy=ACT,
    )
    # Four dwellings carry four times the wall sub-cap, and an excess of
    # $2,000 rather than $500.
    assert result.land_cover_cap_nzd == pytest.approx([57_500.0, 230_000.0])
    assert result.excess_nzd == pytest.approx([500.0, 2_000.0])
    assert list(result.retaining_wall_sub_cap_bound) == [True, True]


def test_the_excess_stops_growing_where_the_sub_caps_do_not():
    # Ten dwellings reach the excess ceiling; the sub-caps keep scaling.
    table = property_table({"c1": 20})
    counts = dwelling_counts(["c1"], table)
    assert ACT.excess_nzd(counts) == pytest.approx(5_000.0)
    assert ACT.retaining_wall_limit_nzd(counts) == pytest.approx(20 * 57_500.0)
