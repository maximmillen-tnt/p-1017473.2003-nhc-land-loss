import numpy as np
import pytest

from landloss.exposure.rw.beta_population import (
    BETA_MAX_HEIGHT_M,
    BETA_MIN_HEIGHT_M,
    MEDIUM_MAX_HEIGHT_M,
    SIZE_CLASSES,
    SMALL_MAX_HEIGHT_M,
    classify_wall_size,
)
from landloss.loss.policy import PolicySettings
from landloss.loss.pricing import (
    BETA_SIZE_CLASS_HEIGHT_M,
    BETA_WALL_RATE_EXCL_GST_NZD_PER_M2,
    BETA_WALL_TYPES,
    MAX_SITE_MULTIPLIER,
    WALL_RATE_EXCL_GST_NZD_PER_M2,
    SiteRatings,
    beta_wall_face_area_m2,
    beta_wall_height_m,
    beta_wall_repair_cost_incl_gst_nzd,
    wall_face_area_m2,
    wall_rate_excl_gst_nzd_per_m2,
    wall_repair_cost_incl_gst_nzd,
)

ACT = PolicySettings()

# The costing tool's own combination table, transcribed row for row. The three
# letters are construction access, earthworks required, and constructability
# and reinstatement, in the order the duty report's table lists them. This is
# the oracle: the module computes the multiplier rather than storing the table,
# so these 27 rows are what says the formula reproduces the tool.
TOOL_COMBINATION_TABLE = {
    "EEE": 0.00,
    "EEM": 0.05,
    "EED": 0.10,
    "EME": 0.05,
    "EMM": 0.10,
    "EMD": 0.15,
    "EDE": 0.10,
    "EDM": 0.15,
    "EDD": 0.20,
    "MEE": 0.05,
    "MEM": 0.10,
    "MED": 0.15,
    "MME": 0.10,
    "MMM": 0.15,
    "MMD": 0.20,
    "MDE": 0.15,
    "MDM": 0.20,
    "MDD": 0.25,
    "DEE": 0.10,
    "DEM": 0.15,
    "DED": 0.20,
    "DME": 0.15,
    "DMM": 0.20,
    "DMD": 0.25,
    "DDE": 0.20,
    "DDM": 0.25,
    "DDD": 0.30,
}


def ratings_from(combo):
    access, earthworks, constructability = tuple(combo)
    return SiteRatings(
        construction_access=access,
        earthworks_required=earthworks,
        constructability_reinstatement=constructability,
    )


# ---------------------------------------------------------------------------
# The site multiplier, against the costing tool's table.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("combo", "expected"), TOOL_COMBINATION_TABLE.items())
def test_multiplier_matches_the_costing_tool_table(combo, expected):
    assert ratings_from(combo).multiplier == pytest.approx(expected)


def test_the_table_is_a_complete_enumeration():
    # 3 ratings across 3 factors. If the tool ever grows a fourth rating or a
    # fourth factor, this is what notices.
    assert len(TOOL_COMBINATION_TABLE) == 27


def test_multiplier_never_exceeds_the_line_item_ceiling():
    worst = max(ratings_from(combo).multiplier for combo in TOOL_COMBINATION_TABLE)
    assert worst == pytest.approx(MAX_SITE_MULTIPLIER)
    assert worst == pytest.approx(0.30)


def test_an_all_easy_site_adds_nothing():
    assert ratings_from("EEE").multiplier == pytest.approx(0.0)


def test_the_order_of_the_three_ratings_does_not_matter():
    # The markup is a sum, so a site rated easy/moderate/difficult costs the
    # same however the three are assigned. Worth pinning: it is the reason the
    # module can compute the figure instead of looking the combination up.
    assert ratings_from("EMD").multiplier == pytest.approx(
        ratings_from("DME").multiplier
    )


def test_ratings_are_case_insensitive():
    assert ratings_from("emd").multiplier == pytest.approx(
        ratings_from("EMD").multiplier
    )


def test_an_unknown_rating_is_refused():
    with pytest.raises(ValueError, match="earthworks_required must be one of"):
        _ = ratings_from("EXD").multiplier


def test_ratings_apply_across_a_population():
    ratings = SiteRatings(
        construction_access=np.array(["E", "M", "D"]),
        earthworks_required=np.array(["E", "M", "D"]),
        constructability_reinstatement=np.array(["E", "M", "D"]),
    )
    assert ratings.multiplier == pytest.approx([0.00, 0.15, 0.30])


# ---------------------------------------------------------------------------
# The rates.
# ---------------------------------------------------------------------------


def test_every_wall_type_the_tool_carries_is_priced():
    assert len(WALL_RATE_EXCL_GST_NZD_PER_M2) == 29


def test_rate_lookup_returns_the_tools_figure():
    assert wall_rate_excl_gst_nzd_per_m2("Concrete Block") == pytest.approx(1_010.58)
    assert wall_rate_excl_gst_nzd_per_m2("Shotcrete") == pytest.approx(226.67)


def test_rate_lookup_works_across_a_population():
    rates = wall_rate_excl_gst_nzd_per_m2(np.array(["Shotcrete", "UC: 310mm x 158mm"]))
    assert rates == pytest.approx([226.67, 4_736.23])


def test_an_unknown_wall_type_is_refused():
    # The rates are a closed list, so an unrecognised type means the mapping
    # from the wall population picked a name the tool does not price.
    with pytest.raises(ValueError, match="unknown wall type"):
        wall_rate_excl_gst_nzd_per_m2("Mud Brick")


# ---------------------------------------------------------------------------
# Face area.
# ---------------------------------------------------------------------------


def test_face_area_is_retained_height_by_length():
    assert wall_face_area_m2(1.8, 10.0) == pytest.approx(18.0)


def test_face_area_refuses_a_negative_height():
    with pytest.raises(ValueError, match="height_m must be finite"):
        wall_face_area_m2(-1.0, 10.0)


# ---------------------------------------------------------------------------
# Repair cost.
# ---------------------------------------------------------------------------


def test_repair_cost_is_rate_by_area_by_multiplier_grossed_up():
    # A 1.8 m by 10 m timber pole wall on a site rated easy access, moderate
    # earthworks, moderate constructability: $744.69 x 18 m2 x 1.10 x 1.15.
    cost = wall_repair_cost_incl_gst_nzd(
        "Timber Pole: 250mm SED",
        wall_face_area_m2(1.8, 10.0),
        ratings=ratings_from("EMM"),
        policy=ACT,
    )
    assert cost == pytest.approx(744.69 * 18.0 * 1.10 * 1.15)


def test_an_easy_site_pays_the_bare_rate_plus_gst():
    cost = wall_repair_cost_incl_gst_nzd(
        "Concrete Block",
        10.0,
        ratings=ratings_from("EEE"),
        policy=ACT,
    )
    assert cost == pytest.approx(1_010.58 * 10.0 * 1.15)


def test_the_hardest_site_pays_thirty_percent_more_than_the_easiest():
    easy = wall_repair_cost_incl_gst_nzd(
        "Concrete Block", 10.0, ratings=ratings_from("EEE"), policy=ACT
    )
    hard = wall_repair_cost_incl_gst_nzd(
        "Concrete Block", 10.0, ratings=ratings_from("DDD"), policy=ACT
    )
    assert hard == pytest.approx(easy * 1.30)


def test_repair_cost_is_gst_inclusive_on_the_scenarios_rate():
    # The rates arrive excluding GST and settlement compares on a GST-inclusive
    # basis, so the gross-up has to happen here rather than at the call site.
    zero_gst = PolicySettings(gst_rate=0.0)
    assert wall_repair_cost_incl_gst_nzd(
        "Concrete Block", 10.0, ratings=ratings_from("EEE"), policy=zero_gst
    ) == pytest.approx(1_010.58 * 10.0)


def test_a_portfolio_prices_in_one_call():
    cost = wall_repair_cost_incl_gst_nzd(
        np.array(["Shotcrete", "Concrete Block"]),
        wall_face_area_m2(np.array([1.0, 2.0]), np.array([5.0, 5.0])),
        ratings=SiteRatings(
            construction_access=np.array(["E", "D"]),
            earthworks_required=np.array(["E", "D"]),
            constructability_reinstatement=np.array(["E", "D"]),
        ),
        policy=ACT,
    )
    assert cost == pytest.approx([226.67 * 5.0 * 1.15, 1_010.58 * 10.0 * 1.30 * 1.15])


def test_an_undamaged_wall_costs_nothing():
    assert wall_repair_cost_incl_gst_nzd(
        "Concrete Block", 0.0, ratings=ratings_from("DDD"), policy=ACT
    ) == pytest.approx(0.0)


def test_a_negative_area_is_refused():
    with pytest.raises(ValueError, match="face_area_m2 must be finite"):
        wall_repair_cost_incl_gst_nzd(
            "Concrete Block", -1.0, ratings=ratings_from("EEE"), policy=ACT
        )


# ---------------------------------------------------------------------------
# The beta rate, standing in until a wall type mapping is settled.
# ---------------------------------------------------------------------------


def test_the_beta_rate_averages_the_four_non_driven_timber_pole_walls():
    assert BETA_WALL_TYPES == (
        "Timber Pole: 175mm SED",
        "Timber Pole: 250mm SED",
        "Timber Pole: 300mm SED",
        "Timber Pole: 350mm SED",
    )
    assert (
        pytest.approx((643.19 + 744.69 + 798.80 + 879.87) / 4)
        == BETA_WALL_RATE_EXCL_GST_NZD_PER_M2
    )
    assert pytest.approx(766.6375) == BETA_WALL_RATE_EXCL_GST_NZD_PER_M2


def test_the_beta_rate_excludes_the_driven_timber_poles():
    # The driven rates are a separate and cheaper family; including them would
    # pull the average down without anything saying it should.
    assert not any("Driven" in wall_type for wall_type in BETA_WALL_TYPES)


def test_beta_cost_is_the_flat_rate_by_area_by_multiplier_grossed_up():
    cost = beta_wall_repair_cost_incl_gst_nzd(
        wall_face_area_m2(1.8, 10.0), ratings=ratings_from("EMM"), policy=ACT
    )
    assert cost == pytest.approx(766.6375 * 18.0 * 1.10 * 1.15)


def test_beta_cost_sits_between_the_cheapest_and_dearest_timber_pole():
    area, ratings = 10.0, ratings_from("EEE")
    beta = beta_wall_repair_cost_incl_gst_nzd(area, ratings=ratings, policy=ACT)
    smallest = wall_repair_cost_incl_gst_nzd(
        "Timber Pole: 175mm SED", area, ratings=ratings, policy=ACT
    )
    largest = wall_repair_cost_incl_gst_nzd(
        "Timber Pole: 350mm SED", area, ratings=ratings, policy=ACT
    )
    assert smallest < beta < largest


def test_beta_cost_varies_with_size_through_area_not_rate():
    # A large wall costs more than a small one because it has more face, not
    # because it is priced differently. Worth pinning: it is the only way size
    # reaches the cost while one flat rate stands in for the type.
    ratings = ratings_from("EEE")
    small = beta_wall_repair_cost_incl_gst_nzd(
        wall_face_area_m2(0.8, 10.0), ratings=ratings, policy=ACT
    )
    large = beta_wall_repair_cost_incl_gst_nzd(
        wall_face_area_m2(3.2, 10.0), ratings=ratings, policy=ACT
    )
    assert large == pytest.approx(small * 4.0)


def test_each_size_class_is_priced_at_a_set_height():
    assert beta_wall_height_m("small") == pytest.approx(0.75)
    assert beta_wall_height_m("medium") == pytest.approx(1.75)
    assert beta_wall_height_m("large") == pytest.approx(2.75)


def test_every_size_class_the_population_emits_has_a_height():
    # If the population ever grows a fourth class, this is what notices before
    # a wall reaches pricing with no height to charge against.
    assert set(BETA_SIZE_CLASS_HEIGHT_M) == set(SIZE_CLASSES)


def test_each_height_classifies_back_to_its_own_size_class():
    # The height a class is priced at has to be a height of that class, or the
    # mapping and the bands in beta_population have drifted apart. This is what
    # ruled out pricing small at 1 m, which the bands read back as medium.
    for size_class, height in BETA_SIZE_CLASS_HEIGHT_M.items():
        assert classify_wall_size(height) == size_class


def test_each_height_lies_inside_what_its_class_can_actually_contain():
    # The population draws heights over BETA_MIN_HEIGHT_M to BETA_MAX_HEIGHT_M,
    # so a class holds that range clipped to its own band. Each set height sits
    # strictly inside its own, near the middle; small is 0.75 against a realised
    # midpoint of 0.70, rounded to a clean quarter.
    bounds = {
        "small": (BETA_MIN_HEIGHT_M, SMALL_MAX_HEIGHT_M),
        "medium": (SMALL_MAX_HEIGHT_M, MEDIUM_MAX_HEIGHT_M),
        "large": (MEDIUM_MAX_HEIGHT_M, BETA_MAX_HEIGHT_M),
    }
    for size_class, (low, high) in bounds.items():
        assert low < BETA_SIZE_CLASS_HEIGHT_M[size_class] < high


def test_the_set_heights_are_ordered_and_evenly_spaced():
    small, medium, large = (
        BETA_SIZE_CLASS_HEIGHT_M[size_class] for size_class in SIZE_CLASSES
    )
    assert small < medium < large
    assert medium - small == pytest.approx(large - medium)


def test_size_classes_are_case_insensitive():
    assert beta_wall_height_m("Medium") == pytest.approx(1.75)


def test_an_unknown_size_class_is_refused():
    with pytest.raises(ValueError, match="rw_size must be one of"):
        beta_wall_height_m("enormous")


def test_face_area_from_a_size_class_is_its_height_by_length():
    assert beta_wall_face_area_m2("medium", 12.0) == pytest.approx(21.0)


def test_face_area_from_a_size_class_works_across_a_population():
    areas = beta_wall_face_area_m2(
        np.array(["small", "medium", "large"]), np.array([10.0, 10.0, 10.0])
    )
    assert areas == pytest.approx([7.5, 17.5, 27.5])


def test_a_wall_prices_straight_from_what_vul_sends():
    # rw_size and rw_length are the only wall attributes the contract carries,
    # so this is the whole path from vul's row to a repair cost.
    cost = beta_wall_repair_cost_incl_gst_nzd(
        beta_wall_face_area_m2("medium", 12.0),
        ratings=ratings_from("EMM"),
        policy=ACT,
    )
    assert cost == pytest.approx(766.6375 * 21.0 * 1.10 * 1.15)


def test_beta_cost_prices_a_population_in_one_call():
    cost = beta_wall_repair_cost_incl_gst_nzd(
        wall_face_area_m2(np.array([1.0, 2.0]), np.array([5.0, 5.0])),
        ratings=SiteRatings(
            construction_access=np.array(["E", "D"]),
            earthworks_required=np.array(["E", "D"]),
            constructability_reinstatement=np.array(["E", "D"]),
        ),
        policy=ACT,
    )
    assert cost == pytest.approx(
        [
            766.6375 * 5.0 * 1.15,
            766.6375 * 10.0 * 1.30 * 1.15,
        ]
    )
