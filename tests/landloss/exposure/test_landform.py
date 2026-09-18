"""Tests for the hill versus flat landform classification."""

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from landloss.domain import constants
from landloss.exposure import landform as landform_module
from landloss.exposure.landform import (
    ELEVATED_FLAT,
    FLAT,
    HILL,
    LANDFORM_CLASSES,
    LANDFORM_COLUMN,
    TOPOGRAPHIC_POSITION_COLUMN,
    assign_elevated_flat,
    classify_landform,
    get_flatland,
)


def make_addresses(points: list[tuple[float, float]]):
    """Build an address frame with one point per coordinate pair."""
    return gpd.GeoDataFrame(
        {"address_id": list(range(len(points)))},
        geometry=[Point(x, y) for x, y in points],
        crs=constants.DEFAULT_CRS,
    )


def make_flatland(boxes: list[tuple[float, float, float, float]]):
    """Build a flatland frame from (minx, miny, maxx, maxy) rectangles."""
    return gpd.GeoDataFrame(
        {"nlm_id": list(range(len(boxes)))},
        geometry=[
            Polygon([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)])
            for minx, miny, maxx, maxy in boxes
        ],
        crs=constants.DEFAULT_CRS,
    )


# --- classification -----------------------------------------------------------


def test_an_address_inside_flat_land_is_flat() -> None:
    """The flat classes are what the liquefaction and inundation losses hang off."""
    result = classify_landform(
        make_addresses([(5, 5)]), make_flatland([(0, 0, 10, 10)])
    )

    assert result[LANDFORM_COLUMN].iloc[0] == FLAT


def test_an_address_outside_flat_land_is_a_hill() -> None:
    """Anything the NLM does not call flat is sloping, and loses land differently."""
    result = classify_landform(
        make_addresses([(50, 50)]), make_flatland([(0, 0, 10, 10)])
    )

    assert result[LANDFORM_COLUMN].iloc[0] == HILL


def test_an_address_on_the_boundary_is_not_flat() -> None:
    """The join is ``within``, so the edge of the flat land is where the hill starts."""
    result = classify_landform(
        make_addresses([(10, 5)]), make_flatland([(0, 0, 10, 10)])
    )

    assert result[LANDFORM_COLUMN].iloc[0] == HILL


def test_with_no_flat_land_every_address_is_a_hill() -> None:
    """An extent the NLM maps no flat land over still classifies every address."""
    addresses = make_addresses([(1, 1), (2, 2), (3, 3)])

    result = classify_landform(addresses, make_flatland([]))

    assert list(result[LANDFORM_COLUMN]) == [HILL, HILL, HILL]


def test_every_class_is_one_of_the_declared_values() -> None:
    """The landform column never holds a value outside LANDFORM_CLASSES."""
    addresses = make_addresses([(5, 5), (50, 50)])

    result = classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert set(result[LANDFORM_COLUMN]) <= set(LANDFORM_CLASSES)


def test_elevated_flat_is_never_assigned_in_phase_one() -> None:
    """Separating raised flat land needs the DEM, which is Phase 2 work."""
    addresses = make_addresses([(5, 5), (50, 50)])

    result = classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert ELEVATED_FLAT not in set(result[LANDFORM_COLUMN])


# --- frame shape --------------------------------------------------------------


def test_overlapping_flatland_polygons_do_not_duplicate_an_address() -> None:
    """The NLM polygons overlap; a duplicated address would be counted twice."""
    addresses = make_addresses([(2, 2)])
    flatland = make_flatland([(0, 0, 10, 10), (0, 0, 5, 5), (1, 1, 4, 4)])

    result = classify_landform(addresses, flatland)

    assert len(result) == 1


def test_exactly_one_column_is_added() -> None:
    """Downstream code selects by name, so a stray join column would surprise it."""
    addresses = make_addresses([(5, 5)])

    result = classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert list(result.columns) == [*addresses.columns, LANDFORM_COLUMN]


def test_the_index_is_reset() -> None:
    """A contiguous index is what lets later steps address rows by label safely."""
    addresses = make_addresses([(5, 5), (50, 50)])
    addresses.index = [7, 9]

    result = classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert list(result.index) == [0, 1]


def test_the_input_is_not_modified() -> None:
    """Classifying returns a copy, leaving the caller's frame untouched."""
    addresses = make_addresses([(5, 5)])

    classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert LANDFORM_COLUMN not in addresses


def test_an_empty_address_frame_is_handled() -> None:
    """Clipping to a boundary can leave nothing behind, and that is not an error."""
    addresses = make_addresses([]).astype({"address_id": "int64"})

    result = classify_landform(addresses, make_flatland([(0, 0, 10, 10)]))

    assert len(result) == 0
    assert LANDFORM_COLUMN in result.columns


# --- promoting to elevated flat -----------------------------------------------


def make_classified(rows: list[tuple[str, float]]):
    """Build a classified frame from (landform class, topographic position) rows."""
    return gpd.GeoDataFrame(
        {
            "address_id": list(range(len(rows))),
            LANDFORM_COLUMN: [row[0] for row in rows],
            TOPOGRAPHIC_POSITION_COLUMN: [row[1] for row in rows],
        },
        geometry=[Point(index, index) for index in range(len(rows))],
        crs=constants.DEFAULT_CRS,
    )


def test_flat_land_standing_above_its_surroundings_becomes_elevated_flat() -> None:
    """A terrace is flat for shaking but sits above the ground that floods."""
    addresses = make_classified([(FLAT, 6.0)])

    result = assign_elevated_flat(addresses, min_topographic_position_m=3.0)

    assert result[LANDFORM_COLUMN].iloc[0] == ELEVATED_FLAT


def test_flat_land_sitting_low_in_the_valley_stays_flat() -> None:
    """Most of the Hutt Valley floor is ordinary flat land and has to stay that way."""
    addresses = make_classified([(FLAT, 0.4)])

    result = assign_elevated_flat(addresses, min_topographic_position_m=3.0)

    assert result[LANDFORM_COLUMN].iloc[0] == FLAT


def test_a_hill_address_is_never_promoted_however_high_it_stands() -> None:
    """A spur stands well above its valley, and being high up does not make it flat."""
    addresses = make_classified([(HILL, 40.0), (HILL, 3.1)])

    result = assign_elevated_flat(addresses, min_topographic_position_m=3.0)

    assert list(result[LANDFORM_COLUMN]) == [HILL, HILL]


def test_an_address_exactly_on_the_threshold_is_not_promoted() -> None:
    """The comparison is strict, so the threshold means the same thing every run."""
    addresses = make_classified([(FLAT, 3.0)])

    result = assign_elevated_flat(addresses, min_topographic_position_m=3.0)

    assert result[LANDFORM_COLUMN].iloc[0] == FLAT


def test_an_address_the_dem_has_no_value_for_keeps_its_class() -> None:
    """Outside the DEM the honest answer is the flatland join's, not a guess."""
    addresses = make_classified([(FLAT, float("nan"))])

    result = assign_elevated_flat(addresses, min_topographic_position_m=3.0)

    assert result[LANDFORM_COLUMN].iloc[0] == FLAT


def test_a_lower_threshold_promotes_more_addresses() -> None:
    """The threshold is tuned against the observed share, so it has to bite."""
    addresses = make_classified([(FLAT, 1.0), (FLAT, 4.0), (FLAT, 9.0)])

    high = assign_elevated_flat(addresses, min_topographic_position_m=5.0)
    low = assign_elevated_flat(addresses, min_topographic_position_m=2.0)

    assert (high[LANDFORM_COLUMN] == ELEVATED_FLAT).sum() == 1
    assert (low[LANDFORM_COLUMN] == ELEVATED_FLAT).sum() == 2


def test_a_missing_topographic_position_column_is_named() -> None:
    """Without it every address stays flat, and a missing class is noticed late."""
    addresses = make_classified([(FLAT, 6.0)]).drop(
        columns=[TOPOGRAPHIC_POSITION_COLUMN]
    )

    with pytest.raises(ValueError, match=TOPOGRAPHIC_POSITION_COLUMN):
        assign_elevated_flat(addresses, min_topographic_position_m=3.0)


def test_a_missing_landform_column_is_named() -> None:
    """Promotion runs after the flatland join, and says so when it has not."""
    addresses = make_classified([(FLAT, 6.0)]).drop(columns=[LANDFORM_COLUMN])

    with pytest.raises(ValueError, match=LANDFORM_COLUMN):
        assign_elevated_flat(addresses, min_topographic_position_m=3.0)


def test_promotion_leaves_every_other_column_alone() -> None:
    """The step answers one question, and an address must stay the same address."""
    addresses = make_classified([(FLAT, 6.0), (HILL, 20.0)])

    result = assign_elevated_flat(addresses, min_topographic_position_m=3.0)

    assert list(result.columns) == list(addresses.columns)
    assert list(result["address_id"]) == list(addresses["address_id"])


def test_every_class_after_promotion_is_one_of_the_declared_values() -> None:
    """Downstream the class is a key into the land value factors, so it is closed."""
    addresses = make_classified([(FLAT, 6.0), (FLAT, 0.1), (HILL, 30.0)])

    result = assign_elevated_flat(addresses, min_topographic_position_m=3.0)

    assert set(result[LANDFORM_COLUMN]) <= set(LANDFORM_CLASSES)


def test_promotion_does_not_modify_the_caller_s_frame() -> None:
    """Promotion returns a copy, so the unpromoted classification stays available."""
    addresses = make_classified([(FLAT, 6.0)])

    assign_elevated_flat(addresses, min_topographic_position_m=3.0)

    assert addresses[LANDFORM_COLUMN].iloc[0] == FLAT


# --- loading ------------------------------------------------------------------


@pytest.fixture
def fake_layer(monkeypatch: pytest.MonkeyPatch):
    """Serve a fixed two-polygon layer in place of the Koordinates read."""
    calls = {}
    source = make_flatland([(0, 0, 10, 10), (100, 100, 110, 110)])

    def fake_read(**kwargs):
        calls.update(kwargs)
        return source.copy()

    monkeypatch.setattr(landform_module, "get_koordinates_layer_extent", fake_read)
    return calls


def test_the_flatland_is_read_from_the_nlm_layer_on_the_tt_domain(fake_layer) -> None:
    """The NLM layer is mirrored on T+T's instance, not on LINZ's."""
    get_flatland()

    assert fake_layer["layer"] == constants.NLM_FLATLAND_LAYER_ID
    assert fake_layer["domain"] == constants.TTGROUP_DOMAIN


def test_without_a_clip_everything_read_is_kept(fake_layer) -> None:
    """Omitting clip_to leaves the bounding box read untouched."""
    result = get_flatland()

    assert len(result) == 2


def test_clip_to_removes_what_falls_outside_the_boundary(fake_layer) -> None:
    """A bounding box is a rectangle; clip_to cuts back to the real study area."""
    boundary = gpd.GeoDataFrame(
        geometry=[Polygon([(-5, -5), (50, -5), (50, 50), (-5, 50)])],
        crs=constants.DEFAULT_CRS,
    )

    result = get_flatland(clip_to=boundary)

    assert list(result["nlm_id"]) == [0]
