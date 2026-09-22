import numpy as np
import pytest

from landloss.loss.policy import PolicySettings
from landloss.loss.settlement import (
    DamagedClaim,
    land_cover_cap_nzd,
    settle,
    structure_contribution_nzd,
)

# One dwelling, current Act. The explainer works all three of its examples on
# these settings, so they are the baseline the worked-example tests run against.
ACT = PolicySettings()

# $50,000 + GST, the applicable retaining wall limit for a single dwelling. The
# explainer states this figure, which is what pins the GST rate at 15%.
ONE_DWELLING_WALL_LIMIT = 57_500.0

# The claim the explainer's Examples 2 and 3 share: 60 m2 of damaged land
# assessed at $45,000, on a single-dwelling property. Only the wall differs.
DAMAGED_LAND_NZD = 45_000.0


# ---------------------------------------------------------------------------
# The three worked examples in .agents/context/nhi-act-land-cover-explainer.md.
# These are the only fully specified settlements the study has, so they are the
# primary check on the arithmetic rather than one check among several.
# ---------------------------------------------------------------------------


def test_worked_example_1_wall_only_settles_on_the_sub_cap():
    # Substantial cracking to a wall, no damage to the insured land areas. The
    # wall's $70,000 undepreciated value exceeds the limit, so the limit is what
    # it contributes, and the repair cost is far above that.
    result = settle(
        DamagedClaim(
            repair_cost_incl_gst_nzd=120_000.0,
            market_value_incl_gst_nzd=0.0,
            retaining_wall_udv_incl_gst_nzd=70_000.0,
            n_dwellings=1,
        ),
        policy=ACT,
    )
    assert result.land_cover_cap_nzd == pytest.approx(ONE_DWELLING_WALL_LIMIT)
    assert result.settlement_nzd == pytest.approx(ONE_DWELLING_WALL_LIMIT - 500.0)
    assert result.capped


def test_worked_example_2_land_and_wall_settle_on_the_cap():
    # The same $70,000 wall, now with $45,000 of damaged land. The cap is the
    # sum of the two contributions, and the $210,000 repair cost is above it.
    result = settle(
        DamagedClaim(
            repair_cost_incl_gst_nzd=210_000.0,
            market_value_incl_gst_nzd=DAMAGED_LAND_NZD,
            retaining_wall_udv_incl_gst_nzd=70_000.0,
            n_dwellings=1,
        ),
        policy=ACT,
    )
    assert result.land_cover_cap_nzd == pytest.approx(102_500.0)
    assert result.settlement_nzd == pytest.approx(102_000.0)
    assert result.capped


def test_worked_example_3_a_modest_wall_settles_on_the_repair_cost():
    # Same land, but a timber pole wall worth $30,000 new. The sub-cap is
    # irrelevant because the undepreciated value is below it, and the repair
    # cost now falls under the cap, so the repair cost is what is paid.
    result = settle(
        DamagedClaim(
            repair_cost_incl_gst_nzd=58_000.0,
            market_value_incl_gst_nzd=DAMAGED_LAND_NZD,
            retaining_wall_udv_incl_gst_nzd=30_000.0,
            n_dwellings=1,
        ),
        policy=ACT,
    )
    assert result.land_cover_cap_nzd == pytest.approx(75_000.0)
    assert result.settlement_nzd == pytest.approx(57_500.0)
    assert not result.capped


# ---------------------------------------------------------------------------
# The misreadings the module exists to prevent.
# ---------------------------------------------------------------------------


def test_a_sub_cap_limits_the_contribution_not_the_settlement():
    # Example 2 settles at $102,000, well above the $57,500 wall sub-cap. Read
    # as a ceiling on the payout, the sub-cap would have held this to $57,500.
    result = settle(
        DamagedClaim(
            repair_cost_incl_gst_nzd=210_000.0,
            market_value_incl_gst_nzd=DAMAGED_LAND_NZD,
            retaining_wall_udv_incl_gst_nzd=70_000.0,
            n_dwellings=1,
        ),
        policy=ACT,
    )
    assert result.settlement_nzd > ONE_DWELLING_WALL_LIMIT


def test_a_modest_wall_never_reaches_its_sub_cap():
    contribution = structure_contribution_nzd(30_000.0, ONE_DWELLING_WALL_LIMIT)
    assert contribution == pytest.approx(30_000.0)


def test_the_sub_caps_are_grossed_up_for_gst():
    assert ACT.retaining_wall_limit_nzd(1) == pytest.approx(57_500.0)
    assert ACT.bridge_culvert_limit_nzd(1) == pytest.approx(28_750.0)


def test_the_sub_caps_multiply_by_dwellings():
    # The explainer's own illustration: five dwellings give $250,000 + GST.
    assert ACT.retaining_wall_limit_nzd(5) == pytest.approx(250_000.0 * 1.15)


# ---------------------------------------------------------------------------
# The excess.
# ---------------------------------------------------------------------------


def test_the_excess_is_per_dwelling():
    assert ACT.excess_nzd(1) == pytest.approx(500.0)
    assert ACT.excess_nzd(4) == pytest.approx(2_000.0)


def test_the_excess_stops_growing_at_ten_dwellings():
    assert ACT.excess_nzd(10) == pytest.approx(5_000.0)
    assert ACT.excess_nzd(40) == pytest.approx(5_000.0)


def test_a_claim_below_the_excess_settles_at_nothing_rather_than_owing():
    result = settle(
        DamagedClaim(
            repair_cost_incl_gst_nzd=300.0,
            market_value_incl_gst_nzd=10_000.0,
            n_dwellings=1,
        ),
        policy=ACT,
    )
    assert result.settlement_nzd == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# The total cap, which is the setting under test rather than current law.
# ---------------------------------------------------------------------------


def test_the_current_act_has_no_total_cap():
    assert ACT.total_cap_nzd is None


def test_a_total_cap_binds_before_the_excess():
    claim = DamagedClaim(
        repair_cost_incl_gst_nzd=210_000.0,
        market_value_incl_gst_nzd=DAMAGED_LAND_NZD,
        retaining_wall_udv_incl_gst_nzd=70_000.0,
        n_dwellings=1,
    )
    result = settle(claim, policy=PolicySettings(total_cap_nzd=80_000.0))
    # Example 2's $102,500 cap, cut to the total cap, then the excess.
    assert result.land_cover_cap_nzd == pytest.approx(80_000.0)
    assert result.settlement_nzd == pytest.approx(79_500.0)


def test_a_generous_total_cap_changes_nothing():
    claim = DamagedClaim(
        repair_cost_incl_gst_nzd=210_000.0,
        market_value_incl_gst_nzd=DAMAGED_LAND_NZD,
        retaining_wall_udv_incl_gst_nzd=70_000.0,
        n_dwellings=1,
    )
    under_act = settle(claim, policy=ACT)
    under_cap = settle(claim, policy=PolicySettings(total_cap_nzd=10_000_000.0))
    assert under_cap.settlement_nzd == pytest.approx(under_act.settlement_nzd)


# ---------------------------------------------------------------------------
# Whole portfolios, and inputs that should be refused.
# ---------------------------------------------------------------------------


def test_a_portfolio_settles_in_one_call():
    # The three worked examples, settled together.
    result = settle(
        DamagedClaim(
            repair_cost_incl_gst_nzd=np.array([120_000.0, 210_000.0, 58_000.0]),
            market_value_incl_gst_nzd=np.array([0.0, 45_000.0, 45_000.0]),
            retaining_wall_udv_incl_gst_nzd=np.array([70_000.0, 70_000.0, 30_000.0]),
            n_dwellings=np.array([1.0, 1.0, 1.0]),
        ),
        policy=ACT,
    )
    assert result.settlement_nzd == pytest.approx([57_000.0, 102_000.0, 57_500.0])
    assert result.capped.tolist() == [True, True, False]


def test_bridges_and_culverts_add_their_own_contribution():
    result = settle(
        DamagedClaim(
            repair_cost_incl_gst_nzd=500_000.0,
            market_value_incl_gst_nzd=0.0,
            bridge_culvert_udv_incl_gst_nzd=90_000.0,
            n_dwellings=1,
        ),
        policy=ACT,
    )
    assert result.bridge_culvert_contribution_nzd == pytest.approx(28_750.0)
    assert result.land_cover_cap_nzd == pytest.approx(28_750.0)


def test_undamaged_structures_contribute_nothing():
    result = settle(
        DamagedClaim(
            repair_cost_incl_gst_nzd=20_000.0,
            market_value_incl_gst_nzd=DAMAGED_LAND_NZD,
            n_dwellings=1,
        ),
        policy=ACT,
    )
    assert result.retaining_wall_contribution_nzd == pytest.approx(0.0)
    assert result.land_cover_cap_nzd == pytest.approx(DAMAGED_LAND_NZD)


def test_a_missing_dwelling_count_is_refused_rather_than_read_as_no_cover():
    with pytest.raises(ValueError, match="n_dwellings"):
        settle(
            DamagedClaim(
                repair_cost_incl_gst_nzd=10_000.0,
                market_value_incl_gst_nzd=10_000.0,
                n_dwellings=0,
            ),
            policy=ACT,
        )


def test_negative_amounts_are_refused():
    with pytest.raises(ValueError, match="repair_cost_incl_gst_nzd"):
        settle(
            DamagedClaim(
                repair_cost_incl_gst_nzd=-1.0,
                market_value_incl_gst_nzd=10_000.0,
                n_dwellings=1,
            ),
            policy=ACT,
        )


def test_a_cap_can_be_computed_without_settling():
    cap = land_cover_cap_nzd(
        market_value_incl_gst_nzd=DAMAGED_LAND_NZD,
        retaining_wall_udv_incl_gst_nzd=70_000.0,
        n_dwellings=1,
        policy=ACT,
    )
    assert cap == pytest.approx(102_500.0)
